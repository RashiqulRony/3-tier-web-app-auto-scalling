#!/usr/bin/env python3
"""
BMI Health Tracker — AWS Infrastructure Provisioner
====================================================
Automates Phases 1 through 6 (inclusive):

  Phase 1  ✅  VPC, IGW, Subnets, NAT, Route Tables, VPC Endpoints
  Phase 2  ✅  Aurora Serverless v2 Cluster
  Phase 3  ✅  IAM Inline Policy
  Phase 4  ✅  SSM Parameters (5)
  Phase 5  ✅  Security Groups (all 5, properly chained)
  Phase 6  ✅  Golden AMIs (backend + frontend baked via SSM in parallel)

After this script completes continue in README_V2.md:
  Phase 7  → ALBs + Target Groups (manual console)
  Phase 8  → Backend EC2 Instances
  Phase 9  → Frontend Auto Scaling Group

Usage:
  python provision.py
  python provision.py --db-password "MyPass123!"
  python provision.py --profile my-profile --region us-east-1
  python provision.py --teardown
"""

import argparse
import json
import logging
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from botocore.exceptions import ClientError

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

class _ColourFmt(logging.Formatter):
    _C = {'DEBUG': '\033[36m', 'INFO': '\033[32m',
          'WARNING': '\033[33m', 'ERROR': '\033[31m', 'CRITICAL': '\033[35m'}
    _R = '\033[0m'
    def format(self, record):
        c = self._C.get(record.levelname, '')
        record.levelname = f"{c}{record.levelname:<8}{self._R}"
        return super().format(record)

def _setup_log():
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(_ColourFmt(fmt='%(asctime)s  %(levelname)s  %(message)s', datefmt='%H:%M:%S'))
    lg = logging.getLogger('provision')
    lg.setLevel(logging.DEBUG)
    lg.addHandler(h)
    return lg

log = _setup_log()

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

DEFAULTS = {'profile': 'sarowar-ostad', 'region': 'ap-south-1', 'db_pass': '0stad2025'}

CFG = {
    'vpc_name':   'devops-vpc',
    'vpc_cidr':   '10.0.0.0/16',
    'igw_name':   'devops-igw',
    'nat_name':   'devops-regional-nat',
    'subnets': [
        {'key': 'pub1',  'name': 'devops-subnet-public1-ap-south-1a',  'cidr': '10.0.0.0/20',   'az': 'a', 'public': True},
        {'key': 'pub2',  'name': 'devops-subnet-public2-ap-south-1b',  'cidr': '10.0.16.0/20',  'az': 'b', 'public': True},
        {'key': 'priv1', 'name': 'devops-subnet-private1-ap-south-1a', 'cidr': '10.0.128.0/20', 'az': 'a', 'public': False},
        {'key': 'priv2', 'name': 'devops-subnet-private2-ap-south-1b', 'cidr': '10.0.144.0/20', 'az': 'b', 'public': False},
    ],
    'iam_role':          'EC2RoleForBMIApp',
    'iam_policy_name':   'BMIAppParameterStoreAccess',
    'aurora_cluster_id': 'bmi-aurora-cluster',
    'aurora_inst_id':    'bmi-aurora-instance-1',
    'aurora_db':         'bmidb',
    'aurora_user':       'postgres',
    'aurora_engine_ver': '15.17',
    'db_subnet_group':   'bmi-db-subnet-group',
    'ssm_prefix':        '/bmi-app',
    'repo_base_url':     ('https://raw.githubusercontent.com/sarowar-alam/'
                          '3-tier-web-app-auto-scalling/main/AutoScaling-FrontEnd-CPU'),
    'golden_amis': {
        'backend': {
            'ami_name': 'bmi-backend-golden-ami',
            'ami_desc': 'Golden AMI: Node.js 20, PM2, PostgreSQL 15 client (Amazon Linux 2023)',
            'script':   'backend-userdata.sh',
            'ami_key':  'backend_ami_id',
            'inst_key': 'backend_temp_inst_id',
            'cmd_key':  'backend_ssm_cmd_id',
        },
        'frontend': {
            'ami_name': 'bmi-frontend-golden-ami',
            'ami_desc': 'Golden AMI: nginx, Node.js 20, git (Amazon Linux 2023)',
            'script':   'frontend-userdata.sh',
            'ami_key':  'frontend_ami_id',
            'inst_key': 'frontend_temp_inst_id',
            'cmd_key':  'frontend_ssm_cmd_id',
        },
    },
}

IAM_POLICY_DOC = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"],
            "Resource": "arn:aws:ssm:*:*:parameter/bmi-app/*",
        },
        {
            "Effect": "Allow",
            "Action": "kms:Decrypt",
            "Resource": "*",
            "Condition": {"StringEquals": {"kms:ViaService": "ssm.*.amazonaws.com"}},
        },
    ],
}

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'provision-state.json')
_state_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# State + shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def _save_state(state):
    with _state_lock:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)

def _set(state, key, value):
    with _state_lock:
        state[key] = value
    _save_state(state)

def _tag(name):
    return [{'Key': 'Name', 'Value': name}, {'Key': 'Project', 'Value': 'bmi-autoscaling'}]

def _try(label, fn):
    try:
        fn()
    except ClientError as e:
        log.warning(f"[SKIP]   {label}: {e.response['Error']['Code']}")
    except Exception as e:
        log.warning(f"[SKIP]   {label}: {e}")

def _get_or_create_sg(ec2, vpc_id, name, description, state_key, state):
    if state_key in state:
        log.info(f"[SKIP]   SG {name} ({state[state_key]})")
        return state[state_key]
    r = ec2.describe_security_groups(Filters=[
        {'Name': 'group-name', 'Values': [name]},
        {'Name': 'vpc-id',     'Values': [vpc_id]},
    ])
    if r['SecurityGroups']:
        sg_id = r['SecurityGroups'][0]['GroupId']
        log.info(f"[EXIST]  SG {name}: {sg_id}")
        _set(state, state_key, sg_id)
        return sg_id
    log.info(f"[CREATE] SG {name}")
    r = ec2.create_security_group(
        GroupName=name, Description=description, VpcId=vpc_id,
        TagSpecifications=[{'ResourceType': 'security-group', 'Tags': _tag(name)}])
    sg_id = r['GroupId']
    _set(state, state_key, sg_id)
    log.info(f"[OK]     SG {name}: {sg_id}")
    return sg_id

def _add_ingress(ec2, sg_id, sg_name, rules):
    existing = ec2.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]['IpPermissions']
    for rule in rules:
        port  = rule.get('FromPort', -1)
        proto = rule.get('IpProtocol', '-1')
        if any(e.get('FromPort') == port and e.get('IpProtocol') == proto for e in existing):
            log.debug(f"  [{sg_name}] port {port} rule exists — skip")
            continue
        try:
            ec2.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=[rule])
            log.info(f"  [{sg_name}] added inbound port {port}")
        except ClientError as e:
            if 'InvalidPermission.Duplicate' not in str(e):
                raise

# ─────────────────────────────────────────────────────────────────────────────
# Wave 1 — Independent resources (parallel)
# ─────────────────────────────────────────────────────────────────────────────

def w1_vpc(ec2, state):
    name = CFG['vpc_name']
    if 'vpc_id' in state:
        log.info(f"[SKIP]   VPC {name} ({state['vpc_id']})")
        return state['vpc_id']
    r = ec2.describe_vpcs(Filters=[
        {'Name': 'tag:Name', 'Values': [name]}, {'Name': 'state', 'Values': ['available']}])
    if r['Vpcs']:
        vpc_id = r['Vpcs'][0]['VpcId']
        log.info(f"[EXIST]  VPC {name}: {vpc_id}")
        _set(state, 'vpc_id', vpc_id)
        return vpc_id
    log.info(f"[CREATE] VPC {name} ({CFG['vpc_cidr']})")
    r = ec2.create_vpc(
        CidrBlock=CFG['vpc_cidr'],
        TagSpecifications=[{'ResourceType': 'vpc', 'Tags': _tag(name)}])
    vpc_id = r['Vpc']['VpcId']
    ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={'Value': True})
    ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsSupport={'Value': True})
    _set(state, 'vpc_id', vpc_id)
    log.info(f"[OK]     VPC: {vpc_id}")
    return vpc_id

def w1_iam_policy(iam, state):
    role, policy = CFG['iam_role'], CFG['iam_policy_name']
    if state.get('iam_policy_done'):
        log.info(f"[SKIP]   IAM policy {policy}")
        return
    try:
        iam.put_role_policy(RoleName=role, PolicyName=policy,
                            PolicyDocument=json.dumps(IAM_POLICY_DOC))
        _set(state, 'iam_policy_done', True)
        log.info(f"[OK]     IAM inline policy {policy} → {role}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            log.warning(f"[WARN]   IAM role {role} not found — skipping inline policy")
        else:
            raise

def w1_ssm_params(ssm, db_pass, state):
    prefix = CFG['ssm_prefix']
    for suffix, value, ptype in [
        ('db-name',         'bmidb',             'String'),
        ('db-user',         'postgres',           'String'),
        ('db-password',     db_pass,              'SecureString'),
        ('backend-alb-url', 'http://placeholder', 'String'),
    ]:
        name = f"{prefix}/{suffix}"
        skey = f"ssm_{suffix.replace('-', '_')}"
        if state.get(skey):
            log.info(f"[SKIP]   SSM {name}")
            continue
        ssm.put_parameter(Name=name, Value=value, Type=ptype, Overwrite=True)
        _set(state, skey, True)
        log.info(f"[OK]     SSM {name} ({ptype})")

# ─────────────────────────────────────────────────────────────────────────────
# Wave 2 — VPC children (parallel)
# ─────────────────────────────────────────────────────────────────────────────

def w2_igw(ec2, vpc_id, state):
    name = CFG['igw_name']
    if 'igw_id' in state:
        log.info(f"[SKIP]   IGW {name} ({state['igw_id']})")
        return state['igw_id']
    r = ec2.describe_internet_gateways(Filters=[{'Name': 'tag:Name', 'Values': [name]}])
    if r['InternetGateways']:
        igw_id = r['InternetGateways'][0]['InternetGatewayId']
        if not any(a['VpcId'] == vpc_id
                   for a in r['InternetGateways'][0].get('Attachments', [])):
            ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
            log.info(f"  Attached existing IGW to VPC")
        log.info(f"[EXIST]  IGW: {igw_id}")
        _set(state, 'igw_id', igw_id)
        return igw_id
    log.info(f"[CREATE] IGW {name}")
    r = ec2.create_internet_gateway(
        TagSpecifications=[{'ResourceType': 'internet-gateway', 'Tags': _tag(name)}])
    igw_id = r['InternetGateway']['InternetGatewayId']
    ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
    _set(state, 'igw_id', igw_id)
    log.info(f"[OK]     IGW: {igw_id}")
    return igw_id

def w2_subnets(ec2, vpc_id, region, state):
    sn = dict(state.get('subnet_ids', {}))
    existing = {s['CidrBlock']: s['SubnetId'] for s in
                ec2.describe_subnets(Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc_id]}])['Subnets']}
    for s in CFG['subnets']:
        if s['key'] in sn:
            log.info(f"[SKIP]   Subnet {s['name']} ({sn[s['key']]})")
            continue
        az = f"{region}{s['az']}"
        if s['cidr'] in existing:
            sid = existing[s['cidr']]
            log.info(f"[EXIST]  Subnet {s['name']}: {sid}")
        else:
            log.info(f"[CREATE] Subnet {s['name']} ({s['cidr']}, {az})")
            r = ec2.create_subnet(
                VpcId=vpc_id, CidrBlock=s['cidr'], AvailabilityZone=az,
                TagSpecifications=[{'ResourceType': 'subnet', 'Tags': _tag(s['name'])}])
            sid = r['Subnet']['SubnetId']
            log.info(f"[OK]     Subnet: {sid}")
        if s['public']:
            ec2.modify_subnet_attribute(SubnetId=sid, MapPublicIpOnLaunch={'Value': True})
        sn[s['key']] = sid
    _set(state, 'subnet_ids', sn)
    return sn

def w2_sg_ssm_ep(ec2, vpc_id, state):
    sg = _get_or_create_sg(ec2, vpc_id, 'ssm-endpoint-sg',
                           'SSM VPC endpoint security group', 'sg_ssm_ep', state)
    _add_ingress(ec2, sg, 'ssm-endpoint-sg', [{
        'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443,
        'IpRanges': [{'CidrIp': CFG['vpc_cidr'], 'Description': 'HTTPS from VPC'}]}])
    return sg

def w2_sg_frontend_alb(ec2, vpc_id, state):
    sg = _get_or_create_sg(ec2, vpc_id, 'frontend-alb-sg',
                           'Frontend ALB security group', 'sg_frontend_alb', state)
    _add_ingress(ec2, sg, 'frontend-alb-sg', [
        {'IpProtocol': 'tcp', 'FromPort': 80,  'ToPort': 80,
         'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTP from internet'}]},
        {'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443,
         'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTPS from internet'}]},
    ])
    return sg

def w2_sg_aurora(ec2, vpc_id, state):
    # Broad rule initially; tightened in Wave 6 after backend-ec2-sg exists
    return _get_or_create_sg(ec2, vpc_id, 'aurora-sg',
                             'Aurora PostgreSQL security group', 'sg_aurora', state)

# ─────────────────────────────────────────────────────────────────────────────
# Wave 3 — NAT + DB Subnet Group + frontend-ec2-sg
# ─────────────────────────────────────────────────────────────────────────────

def w3_nat(ec2, subnet_ids, state):
    name = CFG['nat_name']
    if 'nat_id' in state:
        log.info(f"[SKIP]   NAT Gateway ({state['nat_id']})")
        return state['nat_id']
    r = ec2.describe_nat_gateways(Filter=[
        {'Name': 'tag:Name', 'Values': [name]},
        {'Name': 'state',    'Values': ['available', 'pending']}])
    if r['NatGateways']:
        nat_id = r['NatGateways'][0]['NatGatewayId']
        log.info(f"[EXIST]  NAT Gateway: {nat_id}")
        _set(state, 'nat_id', nat_id)
        return nat_id
    if 'eip_alloc_id' not in state:
        log.info("[CREATE] EIP for NAT Gateway")
        r2 = ec2.allocate_address(
            Domain='vpc',
            TagSpecifications=[{'ResourceType': 'elastic-ip', 'Tags': _tag('bmi-nat-eip')}])
        _set(state, 'eip_alloc_id', r2['AllocationId'])
        log.info(f"[OK]     EIP: {state['eip_alloc_id']}")
    else:
        log.info(f"[SKIP]   EIP ({state['eip_alloc_id']})")
    log.info(f"[CREATE] NAT Gateway {name}")
    r3 = ec2.create_nat_gateway(
        SubnetId=subnet_ids['pub1'],
        AllocationId=state['eip_alloc_id'],
        TagSpecifications=[{'ResourceType': 'natgateway', 'Tags': _tag(name)}])
    nat_id = r3['NatGateway']['NatGatewayId']
    _set(state, 'nat_id', nat_id)
    log.info(f"[OK]     NAT Gateway {nat_id} — waiting for available (≈60s)…")
    ec2.get_waiter('nat_gateway_available').wait(
        NatGatewayIds=[nat_id], WaiterConfig={'Delay': 15, 'MaxAttempts': 20})
    log.info(f"[OK]     NAT Gateway available: {nat_id}")
    return nat_id

def w3_db_subnet_group(rds, subnet_ids, state):
    name = CFG['db_subnet_group']
    if state.get('db_sng_done'):
        log.info(f"[SKIP]   DB Subnet Group {name}")
        return
    expected = {subnet_ids['priv1'], subnet_ids['priv2']}
    try:
        r        = rds.describe_db_subnet_groups(DBSubnetGroupName=name)
        existing = {s['SubnetIdentifier']
                    for s in r['DBSubnetGroups'][0]['Subnets']}
        if expected.issubset(existing):
            log.info(f"[EXIST]  DB Subnet Group: {name} (subnets match)")
        else:
            log.warning(f"[MISMATCH] DB Subnet Group {name} belongs to a different VPC "
                        f"— deleting and recreating with current subnets")
            rds.delete_db_subnet_group(DBSubnetGroupName=name)
            log.info(f"[CREATE] DB Subnet Group {name}")
            rds.create_db_subnet_group(
                DBSubnetGroupName=name,
                DBSubnetGroupDescription='Subnet group for BMI Aurora cluster',
                SubnetIds=[subnet_ids['priv1'], subnet_ids['priv2']],
                Tags=[{'Key': 'Name', 'Value': name}])
            log.info(f"[OK]     DB Subnet Group: {name} (recreated)")
    except ClientError as e:
        if e.response['Error']['Code'] == 'DBSubnetGroupNotFoundFault':
            log.info(f"[CREATE] DB Subnet Group {name}")
            rds.create_db_subnet_group(
                DBSubnetGroupName=name,
                DBSubnetGroupDescription='Subnet group for BMI Aurora cluster',
                SubnetIds=[subnet_ids['priv1'], subnet_ids['priv2']],
                Tags=[{'Key': 'Name', 'Value': name}])
            log.info(f"[OK]     DB Subnet Group: {name}")
        else:
            raise
    _set(state, 'db_sng_done', True)

def w3_sg_frontend_ec2(ec2, vpc_id, sg_fe_alb, state):
    sg = _get_or_create_sg(ec2, vpc_id, 'frontend-ec2-sg',
                           'Frontend EC2 security group', 'sg_frontend_ec2', state)
    _add_ingress(ec2, sg, 'frontend-ec2-sg', [
        {'IpProtocol': 'tcp', 'FromPort': 80,  'ToPort': 80,
         'UserIdGroupPairs': [{'GroupId': sg_fe_alb,
                               'Description': 'HTTP from Frontend ALB'}]},
        {'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443,
         'IpRanges': [{'CidrIp': CFG['vpc_cidr'], 'Description': 'HTTPS within VPC'}]},
    ])
    return sg

# ─────────────────────────────────────────────────────────────────────────────
# Wave 4 — Route Tables + VPC Endpoints + backend-alb-sg
# ─────────────────────────────────────────────────────────────────────────────

def w4_route_tables(ec2, vpc_id, igw_id, nat_id, subnet_ids, state):
    results = {}
    for rt_key, name, target_k, target_v, sn_keys in [
        ('public_rt_id',  'bmi-public-rt',  'GatewayId',    igw_id, ['pub1',  'pub2']),
        ('private_rt_id', 'bmi-private-rt', 'NatGatewayId', nat_id, ['priv1', 'priv2']),
    ]:
        if rt_key in state:
            log.info(f"[SKIP]   Route Table {name} ({state[rt_key]})")
            results[rt_key] = state[rt_key]
            continue
        log.info(f"[CREATE] Route Table {name}")
        r = ec2.create_route_table(
            VpcId=vpc_id,
            TagSpecifications=[{'ResourceType': 'route-table', 'Tags': _tag(name)}])
        rt_id = r['RouteTable']['RouteTableId']
        ec2.create_route(RouteTableId=rt_id, DestinationCidrBlock='0.0.0.0/0',
                         **{target_k: target_v})
        for k in sn_keys:
            ec2.associate_route_table(RouteTableId=rt_id, SubnetId=subnet_ids[k])
        _set(state, rt_key, rt_id)
        results[rt_key] = rt_id
        log.info(f"[OK]     Route Table {name}: {rt_id}")
    return results['public_rt_id'], results['private_rt_id']

def w4_vpc_endpoints(ec2, vpc_id, subnet_ids, sg_ssm_ep, region, state):
    priv = [subnet_ids['priv1'], subnet_ids['priv2']]
    for short, svc, key in [
        ('ssm',         f'com.amazonaws.{region}.ssm',        'vpce_ssm'),
        ('ec2messages', f'com.amazonaws.{region}.ec2messages', 'vpce_ec2msg'),
        ('ssmmessages', f'com.amazonaws.{region}.ssmmessages', 'vpce_ssmmsg'),
    ]:
        if key in state:
            log.info(f"[SKIP]   VPC Endpoint {svc} ({state[key]})")
            continue
        r = ec2.describe_vpc_endpoints(Filters=[
            {'Name': 'service-name',       'Values': [svc]},
            {'Name': 'vpc-id',             'Values': [vpc_id]},
            {'Name': 'vpc-endpoint-state', 'Values': ['pending', 'available']}])
        if r['VpcEndpoints']:
            _set(state, key, r['VpcEndpoints'][0]['VpcEndpointId'])
            log.info(f"[EXIST]  VPC Endpoint {svc}: {state[key]}")
            continue
        log.info(f"[CREATE] VPC Endpoint {svc}")
        r2 = ec2.create_vpc_endpoint(
            VpcId=vpc_id, ServiceName=svc, VpcEndpointType='Interface',
            SubnetIds=priv, SecurityGroupIds=[sg_ssm_ep], PrivateDnsEnabled=True,
            TagSpecifications=[{'ResourceType': 'vpc-endpoint',
                                'Tags': _tag(f'bmi-{short}-endpoint')}])
        _set(state, key, r2['VpcEndpoint']['VpcEndpointId'])
        log.info(f"[OK]     VPC Endpoint {svc}: {state[key]}")

def w4_sg_backend_alb(ec2, vpc_id, sg_fe_ec2, state):
    sg = _get_or_create_sg(ec2, vpc_id, 'backend-alb-sg',
                           'Backend Internal ALB security group', 'sg_backend_alb', state)
    _add_ingress(ec2, sg, 'backend-alb-sg', [{
        'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80,
        'UserIdGroupPairs': [{'GroupId': sg_fe_ec2,
                              'Description': 'HTTP from Frontend EC2'}]}])
    return sg

# ─────────────────────────────────────────────────────────────────────────────
# Wave 5 — S3 Endpoint + backend-ec2-sg
# ─────────────────────────────────────────────────────────────────────────────

def w5_s3_endpoint(ec2, vpc_id, pub_rt, priv_rt, region, state):
    svc, key = f'com.amazonaws.{region}.s3', 'vpce_s3'
    if key in state:
        log.info(f"[SKIP]   S3 Gateway Endpoint ({state[key]})")
        return
    r = ec2.describe_vpc_endpoints(Filters=[
        {'Name': 'service-name',       'Values': [svc]},
        {'Name': 'vpc-id',             'Values': [vpc_id]},
        {'Name': 'vpc-endpoint-type',  'Values': ['Gateway']},
        {'Name': 'vpc-endpoint-state', 'Values': ['pending', 'available']}])
    if r['VpcEndpoints']:
        _set(state, key, r['VpcEndpoints'][0]['VpcEndpointId'])
        log.info(f"[EXIST]  S3 Gateway Endpoint: {state[key]}")
        return
    log.info("[CREATE] S3 Gateway Endpoint")
    r2 = ec2.create_vpc_endpoint(
        VpcId=vpc_id, ServiceName=svc, VpcEndpointType='Gateway',
        RouteTableIds=[pub_rt, priv_rt],
        TagSpecifications=[{'ResourceType': 'vpc-endpoint',
                            'Tags': _tag('devops-vpce-s3')}])
    _set(state, key, r2['VpcEndpoint']['VpcEndpointId'])
    log.info(f"[OK]     S3 Gateway Endpoint: {state[key]}")

def w5_sg_backend_ec2(ec2, vpc_id, sg_be_alb, state):
    sg = _get_or_create_sg(ec2, vpc_id, 'backend-ec2-sg',
                           'Backend EC2 security group', 'sg_backend_ec2', state)
    _add_ingress(ec2, sg, 'backend-ec2-sg', [{
        'IpProtocol': 'tcp', 'FromPort': 3000, 'ToPort': 3000,
        'UserIdGroupPairs': [{'GroupId': sg_be_alb,
                              'Description': 'Node.js from Backend ALB'}]}])
    return sg

# ─────────────────────────────────────────────────────────────────────────────
# Wave 6 — Aurora Serverless v2
# ─────────────────────────────────────────────────────────────────────────────

def w6_tighten_aurora_sg(ec2, sg_aurora, sg_be_ec2, state):
    if state.get('aurora_sg_tightened'):
        log.info("[SKIP]   aurora-sg already tightened")
        return
    log.info("[UPDATE] aurora-sg → 5432 from backend-ec2-sg only")
    existing = ec2.describe_security_groups(
        GroupIds=[sg_aurora])['SecurityGroups'][0]['IpPermissions']
    if existing:
        ec2.revoke_security_group_ingress(GroupId=sg_aurora, IpPermissions=existing)
    ec2.authorize_security_group_ingress(GroupId=sg_aurora, IpPermissions=[{
        'IpProtocol': 'tcp', 'FromPort': 5432, 'ToPort': 5432,
        'UserIdGroupPairs': [{'GroupId': sg_be_ec2,
                              'Description': 'PostgreSQL from Backend EC2'}]}])
    _set(state, 'aurora_sg_tightened', True)
    log.info("[OK]     aurora-sg tightened")

def w6_aurora(rds, sg_aurora, db_pass, state):
    cluster_id = CFG['aurora_cluster_id']
    if state.get('aurora_done'):
        log.info(f"[SKIP]   Aurora cluster ({state.get('aurora_endpoint')})")
        return state['aurora_endpoint']
    try:
        r = rds.describe_db_clusters(DBClusterIdentifier=cluster_id)
        endpoint = r['DBClusters'][0]['Endpoint']
        log.info(f"[EXIST]  Aurora cluster: {endpoint}")
        _set(state, 'aurora_endpoint', endpoint)
        _set(state, 'aurora_done', True)
        return endpoint
    except ClientError as e:
        if e.response['Error']['Code'] != 'DBClusterNotFoundFault':
            raise
    log.info(f"[CREATE] Aurora Serverless v2 cluster {cluster_id}")
    rds.create_db_cluster(
        DBClusterIdentifier=cluster_id,
        Engine='aurora-postgresql',
        EngineVersion=CFG['aurora_engine_ver'],
        MasterUsername=CFG['aurora_user'],
        MasterUserPassword=db_pass,
        DatabaseName=CFG['aurora_db'],
        DBSubnetGroupName=CFG['db_subnet_group'],
        VpcSecurityGroupIds=[sg_aurora],
        ServerlessV2ScalingConfiguration={'MinCapacity': 0.5, 'MaxCapacity': 2.0},
        BackupRetentionPeriod=1,
        StorageEncrypted=True,
        Tags=[{'Key': 'Name', 'Value': cluster_id}])
    log.info(f"[CREATE] Aurora instance {CFG['aurora_inst_id']}")
    rds.create_db_instance(
        DBInstanceIdentifier=CFG['aurora_inst_id'],
        DBClusterIdentifier=cluster_id,
        DBInstanceClass='db.serverless',
        Engine='aurora-postgresql',
        Tags=[{'Key': 'Name', 'Value': CFG['aurora_inst_id']}])
    log.info("  Waiting for Aurora cluster (≈10-12 min)…")
    start = time.time()
    while True:
        r = rds.describe_db_clusters(DBClusterIdentifier=cluster_id)
        status = r['DBClusters'][0]['Status']
        elapsed = int(time.time() - start)
        log.info(f"  Aurora status: {status} ({elapsed}s elapsed)")
        if status == 'available':
            break
        if elapsed > 900:
            raise TimeoutError("Aurora did not become available in 15 min")
        time.sleep(30)
    endpoint = r['DBClusters'][0]['Endpoint']
    _set(state, 'aurora_endpoint', endpoint)
    _set(state, 'aurora_done', True)
    log.info(f"[OK]     Aurora: {endpoint}")
    return endpoint

# ─────────────────────────────────────────────────────────────────────────────
# Wave 7 — SSM db-host + Golden AMIs
# ─────────────────────────────────────────────────────────────────────────────

def w7_ssm_db_host(ssm, endpoint, state):
    name = f"{CFG['ssm_prefix']}/db-host"
    if state.get('ssm_db_host_done'):
        log.info(f"[SKIP]   SSM {name}")
        return
    ssm.put_parameter(Name=name, Value=endpoint, Type='String', Overwrite=True)
    _set(state, 'ssm_db_host_done', True)
    log.info(f"[OK]     SSM {name} = {endpoint}")

def _get_al2023_ami(ec2):
    """Return the latest Amazon Linux 2023 x86_64 AMI ID."""
    r = ec2.describe_images(
        Owners=['amazon'],
        Filters=[
            {'Name': 'name',         'Values': ['al2023-ami-2023.*-x86_64']},
            {'Name': 'state',        'Values': ['available']},
            {'Name': 'architecture', 'Values': ['x86_64']},
        ])
    if not r['Images']:
        raise RuntimeError("Could not find Amazon Linux 2023 AMI")
    latest = sorted(r['Images'], key=lambda x: x['CreationDate'], reverse=True)[0]
    log.info(f"[OK]     AL2023 base AMI: {latest['ImageId']} ({latest['Name']})")
    return latest['ImageId']

def _ensure_instance_profile(iam, role_name):
    """Ensure an EC2 instance profile exists for the IAM role."""
    try:
        r = iam.get_instance_profile(InstanceProfileName=role_name)
        arn = r['InstanceProfile']['Arn']
        log.info(f"[EXIST]  Instance profile {role_name}: {arn}")
        return arn
    except ClientError as e:
        if e.response['Error']['Code'] != 'NoSuchEntity':
            raise
    log.info(f"[CREATE] Instance profile {role_name}")
    iam.create_instance_profile(InstanceProfileName=role_name)
    iam.add_role_to_instance_profile(InstanceProfileName=role_name, RoleName=role_name)
    time.sleep(15)  # IAM propagation delay
    r = iam.get_instance_profile(InstanceProfileName=role_name)
    arn = r['InstanceProfile']['Arn']
    log.info(f"[OK]     Instance profile ARN: {arn}")
    return arn

def _bake_golden_ami(ec2, ssm_client, label, al2023_ami, subnet_id, sg_id,
                     profile_arn, setup_script_url, ami_name, ami_desc,
                     ami_key, inst_key, cmd_key, state):
    """
    Full AMI baking pipeline (thread-safe):
      launch temp instance → wait for SSM agent → run setup script
      → wait for completion → create AMI → wait for available → terminate instance
    """
    # Already baked?
    if ami_key in state:
        log.info(f"[SKIP]   [{label}] AMI already baked: {state[ami_key]}")
        return state[ami_key]

    # AMI exists by name (e.g. previous run without state file)?
    r = ec2.describe_images(
        Owners=['self'],
        Filters=[{'Name': 'name',  'Values': [ami_name]},
                 {'Name': 'state', 'Values': ['available']}])
    if r['Images']:
        ami_id = r['Images'][0]['ImageId']
        log.info(f"[EXIST]  [{label}] AMI {ami_name}: {ami_id}")
        _set(state, ami_key, ami_id)
        return ami_id

    # ── Launch temp instance ─────────────────────────────────────────────────
    instance_id = state.get(inst_key)
    if instance_id:
        log.info(f"[RESUME] [{label}] Temp instance: {instance_id}")
    else:
        log.info(f"[CREATE] [{label}] Launching temp instance for AMI baking")
        r = ec2.run_instances(
            ImageId=al2023_ami,
            InstanceType='t3.micro',
            MinCount=1, MaxCount=1,
            IamInstanceProfile={'Arn': profile_arn},
            NetworkInterfaces=[{
                'DeviceIndex': 0,
                'SubnetId': subnet_id,
                'Groups': [sg_id],
                'AssociatePublicIpAddress': True,
            }],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': _tag(f'{label}-golden-ami-temp'),
            }])
        instance_id = r['Instances'][0]['InstanceId']
        _set(state, inst_key, instance_id)
        log.info(f"[OK]     [{label}] Temp instance: {instance_id}")

    # ── Wait for running ─────────────────────────────────────────────────────
    log.info(f"  [{label}] Waiting for instance to be running…")
    ec2.get_waiter('instance_running').wait(
        InstanceIds=[instance_id], WaiterConfig={'Delay': 10, 'MaxAttempts': 30})
    log.info(f"  [{label}] Instance running ✓")

    # ── Wait for SSM agent registration (≈1-2 min after boot) ───────────────
    log.info(f"  [{label}] Waiting for SSM agent registration…")
    deadline = time.time() + 360
    while time.time() < deadline:
        r = ssm_client.describe_instance_information(
            Filters=[{'Key': 'InstanceIds', 'Values': [instance_id]}])
        if r['InstanceInformationList']:
            log.info(f"  [{label}] SSM agent registered ✓")
            break
        time.sleep(10)
    else:
        raise TimeoutError(
            f"[{label}] SSM agent did not register in 6 min for {instance_id}")

    # ── Run setup script via SSM SendCommand ─────────────────────────────────
    cmd_id = state.get(cmd_key)
    if cmd_id:
        log.info(f"  [{label}] Resuming SSM command {cmd_id}")
    else:
        log.info(f"  [{label}] Sending setup command via SSM…")
        r = ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunShellScript',
            Parameters={
                'commands': [
                    f'curl -fsSL {setup_script_url} -o /tmp/setup.sh',
                    'chmod +x /tmp/setup.sh',
                    'sudo bash /tmp/setup.sh',
                ],
                'executionTimeout': ['1800'],
            },
            TimeoutSeconds=1800,
            Comment=f'Bake {ami_name}',
        )
        cmd_id = r['Command']['CommandId']
        _set(state, cmd_key, cmd_id)
        log.info(f"  [{label}] SSM command sent: {cmd_id}")

    # ── Poll until command finishes ──────────────────────────────────────────
    log.info(f"  [{label}] Waiting for setup to complete (≈5-10 min)…")
    terminal = {'Success', 'Failed', 'Cancelled', 'TimedOut', 'Undeliverable', 'Terminated'}
    deadline = time.time() + 1200
    while time.time() < deadline:
        r = ssm_client.get_command_invocation(CommandId=cmd_id, InstanceId=instance_id)
        status = r['StatusDetails']
        log.info(f"  [{label}] Setup status: {status}")
        if status == 'Success':
            log.info(f"  [{label}] Setup completed successfully ✓")
            break
        if status in terminal:
            err = r.get('StandardErrorContent', '')[:500]
            raise RuntimeError(f"[{label}] Setup script {status}: {err}")
        time.sleep(20)
    else:
        raise TimeoutError(f"[{label}] Setup timed out after 20 min")

    # ── Create AMI ───────────────────────────────────────────────────────────
    log.info(f"  [{label}] Creating AMI {ami_name}…")
    r = ec2.create_image(
        InstanceId=instance_id,
        Name=ami_name,
        Description=ami_desc,
        NoReboot=False,
        TagSpecifications=[{'ResourceType': 'image', 'Tags': _tag(ami_name)}])
    ami_id = r['ImageId']
    log.info(f"  [{label}] AMI {ami_id} pending — waiting for available (≈3-5 min)…")
    ec2.get_waiter('image_available').wait(
        ImageIds=[ami_id], WaiterConfig={'Delay': 15, 'MaxAttempts': 30})
    _set(state, ami_key, ami_id)
    log.info(f"[OK]     [{label}] AMI ready: {ami_id}")

    # ── Terminate temp instance ──────────────────────────────────────────────
    ec2.terminate_instances(InstanceIds=[instance_id])
    log.info(f"[OK]     [{label}] Temp instance {instance_id} terminating")

    return ami_id

def w7_golden_amis(ec2, ssm_client, iam, subnet_ids, vpc_id, state):
    al2023_ami  = _get_al2023_ami(ec2)
    profile_arn = _ensure_instance_profile(iam, CFG['iam_role'])

    # Minimal outbound-only SG for temp instances (SSM + dnf/npm need outbound HTTPS/80)
    sg_temp = _get_or_create_sg(ec2, vpc_id, 'golden-ami-temp-sg',
                                'Temp SG for golden AMI baking (outbound only)',
                                'sg_golden_ami_temp', state)

    base    = CFG['repo_base_url']
    ami_ids = {}

    # Bake backend and frontend AMIs in parallel
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='ami') as ex:
        futures = {
            ex.submit(
                _bake_golden_ami,
                ec2, ssm_client, role, al2023_ami,
                subnet_ids['pub1'], sg_temp, profile_arn,
                f"{base}/{cfg['script']}",
                cfg['ami_name'], cfg['ami_desc'],
                cfg['ami_key'], cfg['inst_key'], cfg['cmd_key'],
                state,
            ): role
            for role, cfg in CFG['golden_amis'].items()
        }
        for fut in as_completed(futures):
            ami_ids[futures[fut]] = fut.result()

    return ami_ids

# ─────────────────────────────────────────────────────────────────────────────
# Teardown — reverse dependency order
# ─────────────────────────────────────────────────────────────────────────────

def teardown(session, state, region):
    ec2 = session.client('ec2')
    rds = session.client('rds')
    ssm = session.client('ssm')
    iam = session.client('iam')

    log.info("=" * 60)
    log.info("TEARDOWN — deleting all provisioned resources")
    log.info("=" * 60)

    # Terminate any still-running temp instances
    for key, label in [('backend_temp_inst_id',  'backend temp instance'),
                       ('frontend_temp_inst_id', 'frontend temp instance')]:
        if key in state:
            _try(f"Terminate {label}",
                 lambda i=state[key]: ec2.terminate_instances(InstanceIds=[i]))
            log.info(f"[OK]   {label} terminated: {state[key]}")

    # Deregister Golden AMIs + delete backing EBS snapshots
    for ami_key, label in [('backend_ami_id',  'Backend AMI'),
                           ('frontend_ami_id', 'Frontend AMI')]:
        if ami_key not in state:
            continue
        ami_id = state[ami_key]
        try:
            r = ec2.describe_images(ImageIds=[ami_id])
            snapshots = [
                bdm['Ebs']['SnapshotId']
                for img in r['Images']
                for bdm in img.get('BlockDeviceMappings', [])
                if 'Ebs' in bdm
            ]
            ec2.deregister_image(ImageId=ami_id)
            log.info(f"[OK]   {label} deregistered: {ami_id}")
            for snap in snapshots:
                time.sleep(2)
                _try(f"Snapshot {snap}",
                     lambda s=snap: ec2.delete_snapshot(SnapshotId=s))
                log.info(f"[OK]   Snapshot deleted: {snap}")
        except ClientError as e:
            log.warning(f"[SKIP] {label}: {e.response['Error']['Code']}")

    # SSM parameters
    for suffix in ['db-name', 'db-user', 'db-password', 'backend-alb-url', 'db-host']:
        name = f"{CFG['ssm_prefix']}/{suffix}"
        _try(f"SSM {name}", lambda n=name: ssm.delete_parameter(Name=n))
        log.info(f"[OK]   SSM {name} deleted")

    # IAM inline policy
    _try('IAM policy', lambda: iam.delete_role_policy(
        RoleName=CFG['iam_role'], PolicyName=CFG['iam_policy_name']))
    log.info("[OK]   IAM inline policy deleted")

    # Aurora instance → cluster → subnet group
    _try('Aurora instance', lambda: rds.delete_db_instance(
        DBInstanceIdentifier=CFG['aurora_inst_id'], SkipFinalSnapshot=True))
    log.info("[OK]   Aurora instance deletion initiated — waiting…")
    for _ in range(30):
        try:
            rds.describe_db_instances(DBInstanceIdentifier=CFG['aurora_inst_id'])
            time.sleep(10)
        except ClientError:
            break

    _try('Aurora cluster', lambda: rds.delete_db_cluster(
        DBClusterIdentifier=CFG['aurora_cluster_id'], SkipFinalSnapshot=True))
    log.info("[OK]   Aurora cluster deletion initiated — waiting…")
    for _ in range(30):
        try:
            rds.describe_db_clusters(DBClusterIdentifier=CFG['aurora_cluster_id'])
            time.sleep(10)
        except ClientError:
            break

    _try('DB Subnet Group', lambda: rds.delete_db_subnet_group(
        DBSubnetGroupName=CFG['db_subnet_group']))
    log.info("[OK]   DB Subnet Group deleted")

    # VPC Endpoints
    ep_ids = [state[k] for k in
              ['vpce_ssm', 'vpce_ec2msg', 'vpce_ssmmsg', 'vpce_s3'] if k in state]
    if ep_ids:
        ec2.delete_vpc_endpoints(VpcEndpointIds=ep_ids)
        log.info(f"[OK]   VPC Endpoints deleted: {ep_ids}")
        time.sleep(15)

    # NAT Gateway
    if 'nat_id' in state:
        _try('NAT Gateway',
             lambda: ec2.delete_nat_gateway(NatGatewayId=state['nat_id']))
        log.info(f"[OK]   NAT Gateway deletion initiated — waiting…")
        for _ in range(20):
            r = ec2.describe_nat_gateways(NatGatewayIds=[state['nat_id']])
            if r['NatGateways'][0]['State'] == 'deleted':
                break
            time.sleep(15)

    if 'eip_alloc_id' in state:
        _try('EIP', lambda: ec2.release_address(AllocationId=state['eip_alloc_id']))
        log.info("[OK]   EIP released")

    vpc_id = state.get('vpc_id')
    if vpc_id:
        # Route Tables
        for rt_key in ['public_rt_id', 'private_rt_id']:
            if rt_key in state:
                try:
                    rt = ec2.describe_route_tables(
                        RouteTableIds=[state[rt_key]])['RouteTables'][0]
                    for assoc in rt.get('Associations', []):
                        if not assoc.get('Main'):
                            ec2.disassociate_route_table(
                                AssociationId=assoc['RouteTableAssociationId'])
                    ec2.delete_route_table(RouteTableId=state[rt_key])
                    log.info(f"[OK]   Route Table deleted: {state[rt_key]}")
                except ClientError as e:
                    log.warning(f"[SKIP] Route Table {state[rt_key]}: "
                                f"{e.response['Error']['Code']}")

        # Subnets
        for sid in state.get('subnet_ids', {}).values():
            _try(f"Subnet {sid}", lambda s=sid: ec2.delete_subnet(SubnetId=s))
            log.info(f"[OK]   Subnet deleted: {sid}")

        # IGW
        if 'igw_id' in state:
            _try('IGW detach', lambda: ec2.detach_internet_gateway(
                InternetGatewayId=state['igw_id'], VpcId=vpc_id))
            _try('IGW delete', lambda: ec2.delete_internet_gateway(
                InternetGatewayId=state['igw_id']))
            log.info(f"[OK]   IGW deleted: {state['igw_id']}")

        # Security Groups — reverse dependency order
        for key in ['sg_golden_ami_temp', 'sg_aurora', 'sg_backend_ec2',
                    'sg_backend_alb', 'sg_frontend_ec2', 'sg_frontend_alb', 'sg_ssm_ep']:
            if key in state:
                _try(f"SG {key}",
                     lambda g=state[key]: ec2.delete_security_group(GroupId=g))
                log.info(f"[OK]   SG deleted: {state[key]} ({key})")

        # VPC
        _try('VPC', lambda: ec2.delete_vpc(VpcId=vpc_id))
        log.info(f"[OK]   VPC deleted: {vpc_id}")

    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
        log.info(f"[OK]   State file removed")

    log.info("=" * 60)
    log.info("TEARDOWN COMPLETE")
    log.info("=" * 60)

# ─────────────────────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def provision(args):
    sess   = boto3.Session(profile_name=args.profile, region_name=args.region)
    ec2    = sess.client('ec2')
    rds    = sess.client('rds')
    ssm    = sess.client('ssm')
    iam    = sess.client('iam')
    region = args.region
    state  = _load_state()

    log.info("=" * 60)
    log.info("BMI Infrastructure Provisioner  (Phases 1–6 + Golden AMIs)")
    log.info(f"Profile : {args.profile}   Region : {region}")
    log.info("=" * 60)

    # ── Wave 1 ──────────────────────────────────────────────────────────────
    log.info("\n▶  Wave 1 — Independent resources (parallel)")
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix='w1') as ex:
        futs = {
            ex.submit(w1_vpc,        ec2, state):                   'vpc',
            ex.submit(w1_iam_policy, iam, state):                   'iam',
            ex.submit(w1_ssm_params, ssm, args.db_password, state): 'ssm',
        }
        for fut in as_completed(futs):
            fut.result()
    vpc_id = state['vpc_id']
    _save_state(state)

    # ── Wave 2 ──────────────────────────────────────────────────────────────
    log.info("\n▶  Wave 2 — VPC children (parallel)")
    with ThreadPoolExecutor(max_workers=5, thread_name_prefix='w2') as ex:
        futs = {
            ex.submit(w2_igw,             ec2, vpc_id, state):         'igw',
            ex.submit(w2_subnets,         ec2, vpc_id, region, state): 'subnets',
            ex.submit(w2_sg_ssm_ep,       ec2, vpc_id, state):         'sg_ssm',
            ex.submit(w2_sg_frontend_alb, ec2, vpc_id, state):         'sg_fe_alb',
            ex.submit(w2_sg_aurora,       ec2, vpc_id, state):         'sg_aurora',
        }
        for fut in as_completed(futs):
            fut.result()
    _save_state(state)
    sn        = state['subnet_ids']
    sg_ssm_ep = state['sg_ssm_ep']
    sg_fe_alb = state['sg_frontend_alb']
    sg_aurora = state['sg_aurora']
    igw_id    = state['igw_id']

    # ── Wave 3 ──────────────────────────────────────────────────────────────
    log.info("\n▶  Wave 3 — NAT Gateway, DB Subnet Group, frontend-ec2-sg")
    nat_id = w3_nat(ec2, sn, state)
    _save_state(state)
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='w3') as ex:
        futs = {
            ex.submit(w3_db_subnet_group, rds, sn, state):                'db_sng',
            ex.submit(w3_sg_frontend_ec2, ec2, vpc_id, sg_fe_alb, state): 'sg_fe_ec2',
        }
        for fut in as_completed(futs):
            fut.result()
    _save_state(state)
    sg_fe_ec2 = state['sg_frontend_ec2']

    # ── Wave 4 ──────────────────────────────────────────────────────────────
    log.info("\n▶  Wave 4 — Route Tables, VPC Endpoints, backend-alb-sg")
    pub_rt, priv_rt = w4_route_tables(ec2, vpc_id, igw_id, nat_id, sn, state)
    _save_state(state)
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='w4') as ex:
        futs = {
            ex.submit(w4_vpc_endpoints,  ec2, vpc_id, sn, sg_ssm_ep, region, state): 'vpce',
            ex.submit(w4_sg_backend_alb, ec2, vpc_id, sg_fe_ec2, state):              'sg_be_alb',
        }
        for fut in as_completed(futs):
            fut.result()
    _save_state(state)
    sg_be_alb = state['sg_backend_alb']

    # ── Wave 5 ──────────────────────────────────────────────────────────────
    log.info("\n▶  Wave 5 — S3 Endpoint, backend-ec2-sg")
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='w5') as ex:
        futs = {
            ex.submit(w5_s3_endpoint,    ec2, vpc_id, pub_rt, priv_rt, region, state): 's3ep',
            ex.submit(w5_sg_backend_ec2, ec2, vpc_id, sg_be_alb, state):               'sg_be_ec2',
        }
        for fut in as_completed(futs):
            fut.result()
    _save_state(state)
    sg_be_ec2 = state['sg_backend_ec2']

    # ── Wave 6 ──────────────────────────────────────────────────────────────
    log.info("\n▶  Wave 6 — Tighten aurora-sg + Aurora Serverless v2")
    w6_tighten_aurora_sg(ec2, sg_aurora, sg_be_ec2, state)
    aurora_endpoint = w6_aurora(rds, sg_aurora, args.db_password, state)
    _save_state(state)

    # ── Wave 7 ──────────────────────────────────────────────────────────────
    log.info("\n▶  Wave 7 — SSM db-host + Golden AMIs (backend + frontend in parallel)")
    w7_ssm_db_host(ssm, aurora_endpoint, state)
    ami_ids = w7_golden_amis(ec2, ssm, iam, sn, vpc_id, state)
    _save_state(state)

    # ── Summary ─────────────────────────────────────────────────────────────
    log.info("\n" + "=" * 60)
    log.info("PHASES 1-6 COMPLETE")
    log.info("=" * 60)
    log.info(f"  VPC ID              : {vpc_id}")
    log.info(f"  Aurora Endpoint     : {aurora_endpoint}")
    log.info(f"  Backend Golden AMI  : {ami_ids.get('backend')}")
    log.info(f"  Frontend Golden AMI : {ami_ids.get('frontend')}")
    log.info(f"  State file          : {STATE_FILE}")
    log.info("")
    log.info("Continue in README_V2.md:")
    log.info("  Phase 7 → Create ALBs + Target Groups  (manual console)")
    log.info("  Phase 8 → Launch 2 backend EC2 instances")
    log.info("  Phase 9 → Create Frontend ASG + Launch Template")
    log.info("=" * 60)

# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='BMI App — AWS Infrastructure Provisioner (Phases 1-6)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python provision.py
  python provision.py --db-password "MySecurePass1!"
  python provision.py --profile my-profile --region us-east-1
  python provision.py --teardown
        """,
    )
    parser.add_argument('--profile',     default=DEFAULTS['profile'],
                        help=f'AWS CLI profile (default: {DEFAULTS["profile"]})')
    parser.add_argument('--region',      default=DEFAULTS['region'],
                        help=f'AWS region (default: {DEFAULTS["region"]})')
    parser.add_argument('--db-password', default=DEFAULTS['db_pass'], dest='db_password',
                        help='Aurora master password (min 8 chars, no @/\"/\')')
    parser.add_argument('--teardown',    action='store_true',
                        help='Delete all resources created by this script')
    args = parser.parse_args()

    if len(args.db_password) < 8:
        log.error("--db-password must be at least 8 characters")
        sys.exit(1)

    try:
        sess     = boto3.Session(profile_name=args.profile, region_name=args.region)
        identity = sess.client('sts').get_caller_identity()
        log.info(f"Authenticated as: {identity['Arn']}")

        if args.teardown:
            state = _load_state()
            if not state:
                log.warning("No provision-state.json found — nothing to tear down")
                sys.exit(0)
            teardown(sess, state, args.region)
        else:
            provision(args)

    except ClientError as e:
        log.error(f"AWS: {e.response['Error']['Code']} — {e.response['Error']['Message']}")
        sys.exit(1)
    except KeyboardInterrupt:
        log.warning("\nInterrupted. State saved — re-run to resume from where it stopped.")
        sys.exit(130)
    except Exception as e:
        log.error(f"Fatal: {e}")
        raise

if __name__ == '__main__':
    main()
