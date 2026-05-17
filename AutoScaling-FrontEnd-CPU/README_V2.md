# AWS Auto-Scaling Demo - Frontend CPU-Based Scaling

**Comprehensive Educational Guide for BMI Health Tracker**

This guide sets up a 3-tier architecture with **Frontend Auto-Scaling based on CPU utilization** (60% target). Perfect for learning AWS auto-scaling concepts hands-on!

---

## 🚀 Choose Your Deployment Path

This project supports **THREE** deployment approaches. Choose based on your learning goals:

### 📚 Path 1: Manual AWS Console (This README)
- **Time:** 60-75 minutes
- **Best for:** First-time learners, understanding each AWS component
- **What you'll learn:** 
  - EC2 Launch Templates and Auto Scaling Groups
  - Application Load Balancers and Target Groups
  - Aurora Serverless v2 configuration
  - VPC networking and security groups
  - SSM Session Manager setup
- **Documentation:** Continue reading below ⬇️
- **Skill level:** ✅ Beginner - **Start here if new to AWS!**

### ⚡ Path 2: Terraform Infrastructure as Code
- **Time:** 15-20 minutes (4x faster!)
- **Best for:** Repeatable deployments, team collaboration, production use
- **What you'll learn:**
  - Infrastructure as Code principles
  - Terraform module design
  - State management
  - Automated resource provisioning
- **Documentation:** **[📖 terraform/README.md](terraform/README.md)**
- **Skill level:** Intermediate (requires Terraform knowledge)

### 🪟 Path 3: Hybrid (PowerShell + Console)
- **Time:** 45-60 minutes
- **Best for:** Windows users wanting partial automation
- **What you'll learn:** Same as Path 1, but with scripted security groups
- **Uses:** `create-security-groups.ps1` for security groups, then manual steps
- **Skill level:** Beginner-Intermediate

---

**💡 Recommendation:**
- **First deployment?** → Use Path 1 (Manual) to understand each component
- **Second deployment?** → Try Path 2 (Terraform) to learn IaC
- **Production use?** → Always use Path 2 (Terraform) for maintainability

---

## Architecture Overview

```
Internet
   ↓
[Public ALB] ← Frontend Load Balancer
   ↓
[Frontend ASG] ← 2-4 EC2 instances (Auto-scales on CPU 60%)
   ↓ (proxies /api requests)
[Internal ALB] ← Backend Load Balancer
   ↓
[Backend EC2] ← 2 fixed instances
   ↓
[Aurora Serverless v2] ← PostgreSQL (0.5-2 ACU, auto-scales)
```

**Key Features:**
- ✅ Frontend auto-scales based on CPU utilization (60% target)
- ✅ Backend fixed at 2 instances (no auto-scaling)
- ✅ Aurora Serverless v2 auto-scales compute (0.5→2 ACU)
- ✅ SSM Session Manager for secure access (no SSH keys)
- ✅ All private subnets (frontend + backend in private)
- ✅ Multi-AZ setup for high availability

**Estimated Costs:**
- ~$2-3 for 1-hour demo
- ~$10-15 if left running for 24 hours

---

## Prerequisites

- AWS Account with admin access
- AWS CLI installed locally (for monitoring)
- Basic understanding of AWS Console
- GitHub repo: `https://github.com/sarowar-alam/3-tier-web-app-auto-scalling.git`

---

## 📂 Project Structure & Files

Understanding what each file does helps you navigate this project:

### Golden AMI Creation Scripts (Instructor Use Only)
These scripts prepare the base AMIs with all required software:

| File | Purpose | When to Use |
|------|---------|-------------|
| `frontend-userdata.sh` | Installs nginx, Node.js 20, git on Amazon Linux 2023 | Run ONCE to create Frontend Golden AMI |
| `backend-userdata.sh` | Installs Node.js 20, PM2, PostgreSQL client | Run ONCE to create Backend Golden AMI |

**⚠️ Note:** Your instructor has already created these AMIs (`ami-0dab0b890a96c6f37` and `ami-032e8cf6d0d558851`). You do NOT need to run these scripts for this lab.

### Deployment Scripts (Runs on Every Instance Launch)
These scripts execute automatically when instances boot:

| File | Purpose | Used By | Execution Time |
|------|---------|---------|----------------|
| `deploy-frontend.sh` | Clones repo, builds React app, configures nginx | Frontend ASG instances | ~2-3 minutes |
| `deploy-backend.sh` | Clones repo, npm install, runs DB migrations, starts PM2 | Backend EC2 instances | ~3-5 minutes |

**How they're used:**
- **Manual deployment:** Copy script contents into EC2 User Data field (Phase 8 & 9)
- **Terraform deployment:** Automatically downloaded and executed via launch templates

### Automation & Testing

| File/Directory | Purpose | Deployment Path |
|----------------|---------|-----------------|
| `create-security-groups.ps1` | Creates all 5 security groups automatically | Path 3 (Hybrid) - Windows/PowerShell users |
| `load-test/quick-test.sh` | Apache Bench load generator to trigger auto-scaling | All paths - for testing |
| `load-test/monitor.sh` | Real-time ASG monitoring dashboard in terminal | All paths - for monitoring |

### Infrastructure as Code

| Directory | Contains | Deployment Path |
|-----------|----------|-----------------|
| `terraform/` | Complete IaC implementation with 7 modules | Path 2 (Terraform only) |
| └─ `modules/network/` | VPC endpoints, security groups | |
| └─ `modules/iam/` | IAM roles and policies | |
| └─ `modules/database/` | Aurora Serverless v2 cluster | |
| └─ `modules/load_balancing/` | Frontend & Backend ALBs, target groups | |
| └─ `modules/compute_backend/` | Backend EC2 instances (fixed 2) | |
| └─ `modules/compute_frontend/` | Frontend Auto Scaling Group | |
| └─ `modules/parameter_store/` | SSM parameters for app configuration | |

### Reference & Documentation

| File | Purpose |
|------|---------|
| `iam-policies.json` | Complete IAM policy structure (for reference) |
| `TEARDOWN-CHECKLIST.md` | ⚠️ **Critical!** Step-by-step cleanup to avoid AWS charges |
| `terraform/terraform.tfvars.example` | Template for Terraform variables |
| `terraform/README.md` | Complete Terraform deployment guide |

---

## 🔄 Understanding the Two-Phase Deployment

This project uses a **Golden AMI** approach for faster, more reliable instance launches:

### Phase 1: Golden AMI Creation (One-Time, Done by Instructor)

```
Amazon Linux 2023 Base AMI
          ↓
    [Run userdata script]
    frontend-userdata.sh or backend-userdata.sh
          ↓
    [Install Software]
    ✓ Node.js 20.x
    ✓ nginx (frontend) or PM2 (backend)
    ✓ git
    ✓ PostgreSQL client
    ✓ CloudWatch agent
          ↓
    [Create AMI Snapshot]
          ↓
    Golden AMI (Ready to Use)
```

**Scripts used:** `frontend-userdata.sh`, `backend-userdata.sh`  
**Duration:** ~10-15 minutes per AMI  
**Result:** Pre-baked AMIs with all software installed  

**Your Golden AMIs (provided):**
- **Frontend:** `ami-0dab0b890a96c6f37`
- **Backend:** `ami-032e8cf6d0d558851`

### Phase 2: Application Deployment (Every Instance Launch)

```
Golden AMI (software pre-installed)
          ↓
    [Launch EC2 Instance]
          ↓
    [Execute Deploy Script]
    ✓ Clone GitHub repository
    ✓ npm install (production dependencies)
    ✓ Build React app (frontend only)
    ✓ Run database migrations (backend only)
    ✓ Start nginx (frontend) or PM2 (backend)
          ↓
    Instance Ready & Healthy!
```

**Scripts used:** `deploy-frontend.sh`, `deploy-backend.sh`  
**Runs:** Every time Auto Scaling launches a new instance  
**Duration:** ~2-3 minutes (much faster than installing from scratch!)

### Why Use Golden AMIs?

| Without Golden AMI | With Golden AMI (This Project) |
|-------------------|-------------------------------|
| Install Node.js on every boot | ✅ Pre-installed |
| Install nginx/PM2 on every boot | ✅ Pre-installed |
| Download packages on every boot | ✅ Base packages pre-installed |
| **Boot time:** 8-12 minutes | **Boot time:** 2-3 minutes |
| **Failure risk:** High (package availability) | **Failure risk:** Low (consistent environment) |
| ❌ Bad for auto-scaling | ✅ Perfect for auto-scaling |

**Benefits for auto-scaling:**
- ⚡ **Faster scale-out** - New instances ready in 2-3 min vs 10+ min
- 🔒 **Consistent environment** - All instances identical (no drift)
- 📉 **Fewer failures** - No dependency on package repos during deployment
- 💰 **Lower costs** - Less CPU time during boot, faster scale-in possible

---

## Phase 1: Network Setup (5 minutes)

### Step 1.1: Use Existing VPC ✅

**You already have the VPC infrastructure!** We'll use:
- **VPC**: `devops-vpc` (10.0.0.0/16)
- **Region**: `ap-south-1` (Mumbai)
- **Public Subnets**:
  - `devops-subnet-public1-ap-south-1a` (10.0.0.0/20)
  - `devops-subnet-public2-ap-south-1b` (10.0.16.0/20)
- **Private Subnets**:
  - `devops-subnet-private1-ap-south-1a` (10.0.128.0/20)
  - `devops-subnet-private2-ap-south-1b` (10.0.144.0/20)
- **NAT Gateway**: `devops-regional-nat` ✅ (already exists)
- **Internet Gateway**: `devops-igw` ✅ (already exists)
- **S3 Gateway Endpoint**: `devops-vpce-s3` ✅ (already exists)

**No VPC creation needed!** Skip to creating SSM endpoints.

### Step 1.2: Create VPC Endpoints for SSM

1. Go to **VPC** → **Endpoints** → **Create endpoint**

**Create 3 endpoints:**

**Endpoint 1: SSM**
- **Name**: `bmi-ssm-endpoint`
- **Service**: `com.amazonaws.ap-south-1.ssm`
- **VPC**: Select `devops-vpc`
- **Subnets**: Select both private subnets:
  - `devops-subnet-private1-ap-south-1a`
  - `devops-subnet-private2-ap-south-1b`
- **Security group**: Create new → `ssm-endpoint-sg`
  - Inbound: HTTPS (443) from `10.0.0.0/16`
- Click **Create endpoint**

**Endpoint 2: EC2 Messages**
- **Name**: `bmi-ec2messages-endpoint`
- **Service**: `com.amazonaws.ap-south-1.ec2messages`
- **VPC**: Select `devops-vpc`
- **Subnets**: Select both private subnets (same as above)
- **Security group**: Select `ssm-endpoint-sg`
- Click **Create endpoint**

**Endpoint 3: SSM Messages**
- **Name**: `bmi-ssmmessages-endpoint`
- **Service**: `com.amazonaws.ap-south-1.ssmmessages`
- **VPC**: Select `devops-vpc`
- **Subnets**: Select both private subnets (same as above)
- **Security group**: Select `ssm-endpoint-sg`
- Click **Create endpoint**

---

## Phase 2: Database Setup (15 minutes)

### Step 2.1: Create DB Subnet Group

1. Go to **RDS** → **Subnet groups** → **Create DB subnet group**
2. Configure:
   - **Name**: `bmi-db-subnet-group`
   - **Description**: `Subnet group for BMI Aurora cluster`
   - **VPC**: Select `devops-vpc`
   - **Availability Zones**: Select **ap-south-1a** and **ap-south-1b**
   - **Subnets**: Select **both private subnets**:
     - `devops-subnet-private1-ap-south-1a` (10.0.128.0/20)
     - `devops-subnet-private2-ap-south-1b` (10.0.144.0/20)
3. Click **Create**

### Step 2.2: Create Aurora Security Group

1. Go to **EC2** → **Security Groups** → **Create security group**
2. Configure:
   - **Name**: `aurora-sg`
   - **Description**: `Security group for Aurora PostgreSQL`
   - **VPC**: Select `devops-vpc`
3. **Inbound rules**:
   - Type: `PostgreSQL` (5432)
   - Source: `10.0.0.0/16` (entire VPC)
   - Description: `Allow from VPC`
4. Click **Create security group**

### Step 2.3: Create Aurora Serverless v2 Cluster

1. Go to **RDS** → **Databases** → **Create database**
2. Configure:

**Engine options:**
- **Engine type**: `Aurora (PostgreSQL Compatible)`
- **Engine version**: `Aurora PostgreSQL (Compatible with PostgreSQL 15.x)` (latest)
- **Template**: `Dev/Test` (not Production - saves cost)

**DB cluster identifier:**
- **Name**: `bmi-aurora-cluster`

**Credentials:**
- **Master username**: `postgres`
- **Master password**: `YourSecurePassword123!` (remember this!)
- **Confirm password**: Same as above

**Instance configuration:**
- **DB instance class**: `Serverless v2`
- **Minimum ACUs**: `0.5`
- **Maximum ACUs**: `2`

**Connectivity:**
- **VPC**: Select `devops-vpc`
- **DB subnet group**: Select `bmi-db-subnet-group`
- **Public access**: `No`
- **VPC security group**: Choose existing → Select `aurora-sg`
- **Availability Zone**: `No preference`

**Database options:**
- **Initial database name**: `bmidb`
- Leave other options as default

**Backup:**
- **Automated backups**: Uncheck (for demo only)

**Monitoring:**
- **Enhanced monitoring**: Uncheck (for demo only)

3. Click **Create database**
4. Wait ~10-12 minutes for Aurora cluster to be available

**Note the endpoint:**
- Go to **RDS** → **Databases** → Click `bmi-aurora-cluster`
- Copy **Writer endpoint** (e.g., `bmi-aurora-cluster.cluster-xxxxx.ap-south-1.rds.amazonaws.com`)

---

## Phase 3: IAM Role Setup (5 minutes)

### Step 3.1: Create IAM Role

1. Go to **IAM** → **Roles** → **Create role**
2. **Trusted entity**: Select `AWS service` → `EC2`
3. Click **Next**

**Attach policies:**
- Search and select: `AmazonSSMManagedInstanceCore`
- Search and select: `CloudWatchAgentServerPolicy`
- Click **Next**

4. **Role name**: `EC2RoleForBMIApp`
5. **Description**: `Role for BMI App EC2 instances with SSM and Parameter Store access`
6. Click **Create role**

### Step 3.2: Add Inline Policy for Parameter Store

1. Go to **IAM** → **Roles** → Find `EC2RoleForBMIApp`
2. Click on the role → **Permissions** tab
3. Click **Add permissions** → **Create inline policy**
4. Switch to **JSON** tab
5. Paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:GetParametersByPath"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/bmi-app/*"
    },
    {
      "Effect": "Allow",
      "Action": "kms:Decrypt",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": "ssm.*.amazonaws.com"
        }
      }
    }
  ]
}
```

6. Click **Review policy**
7. **Name**: `BMIAppParameterStoreAccess`
8. Click **Create policy**

💡 **Tip:** See `iam-policies.json` for the complete IAM role structure reference.

---

## Phase 4: Parameter Store Configuration (3 minutes)

### Step 4.1: Create Parameters

Go to **Systems Manager** → **Parameter Store** → **Create parameter**

Create these 5 parameters:

**Parameter 1: Database Host**
- **Name**: `/bmi-app/db-host`
- **Description**: `Aurora cluster endpoint`
- **Type**: `String`
- **Value**: `<Your-Aurora-Writer-Endpoint>` (e.g., `bmi-aurora-cluster.cluster-xxxxx.ap-south-1.rds.amazonaws.com`)
- Click **Create parameter**

**Parameter 2: Database Name**
- **Name**: `/bmi-app/db-name`
- **Type**: `String`
- **Value**: `bmidb`
- Click **Create parameter**

**Parameter 3: Database User**
- **Name**: `/bmi-app/db-user`
- **Type**: `String`
- **Value**: `postgres`
- Click **Create parameter**

**Parameter 4: Database Password**
- **Name**: `/bmi-app/db-password`
- **Type**: `SecureString`
- **Value**: `YourSecurePassword123!` (same as Aurora password)
- Click **Create parameter**

**Parameter 5: Backend ALB URL (Placeholder)**
- **Name**: `/bmi-app/backend-alb-url`
- **Type**: `String`
- **Value**: `http://placeholder` (will update later)
- Click **Create parameter**

---

## 💡 Windows Users: Automated Security Group Creation

**Save 15-20 minutes!** Instead of manually creating security groups (Steps 5.1-5.5 below), you can use the PowerShell automation script.

### Option A: PowerShell Script (Recommended for Windows)

#### Prerequisites
- Windows PowerShell 5.1 or later (Windows 10/11 built-in)
- AWS CLI installed and configured
- AWS profile: `sarowar-ostad` (or edit script to use your profile name)

#### Steps

1. **Open PowerShell as Administrator**
   - Press `Win + X`
   - Select "Windows PowerShell (Admin)" or "Terminal (Admin)"

2. **Navigate to project directory:**
   ```powershell
   cd "C:\Path\To\3-tier-web-app-auto-scalling\AutoScaling-FrontEnd-CPU"
   ```

3. **(Optional) Review script configuration:**
   ```powershell
   notepad create-security-groups.ps1
   
   # Verify these match your environment:
   $PROFILE = "sarowar-ostad"     # Your AWS CLI profile
   $REGION  = "ap-south-1"        # Your AWS region
   $VPC_ID  = "vpc-06f7dead5c49ece64"  # Your VPC ID
   ```

4. **Run the script:**
   ```powershell
   .\create-security-groups.ps1
   ```

5. **Expected output:**
   ```
   ==================================================
   Creating Security Groups for BMI App Auto-Scaling
   ==================================================

   [1/5] Creating Frontend ALB Security Group...
   [OK] Created: frontend-alb-sg (sg-0a1b2c3d4e5f6g7h8)
     [OK] Added HTTP (80) from 0.0.0.0/0
     [OK] Added HTTPS (443) from 0.0.0.0/0

   [2/5] Creating Frontend EC2 Security Group...
   [OK] Created: frontend-ec2-sg (sg-1b2c3d4e5f6g7h8i9)
     [OK] Added HTTP (80) from frontend-alb-sg
     [OK] Added HTTPS (443) from 10.0.0.0/16

   [3/5] Creating Backend ALB Security Group...
   [OK] Created: backend-alb-sg (sg-2c3d4e5f6g7h8i9j0)
     [OK] Added HTTP (80) from frontend-ec2-sg

   [4/5] Creating Backend EC2 Security Group...
   [OK] Created: backend-ec2-sg (sg-3d4e5f6g7h8i9j0k1)
     [OK] Added TCP 3000 from backend-alb-sg

   [5/5] Updating Aurora Security Group...
   [OK] Updated: aurora-sg
     [OK] Added PostgreSQL (5432) from backend-ec2-sg

   ==================================================
   Security Groups Created Successfully!
   ==================================================
   
   Next Steps:
   1. Verify security groups in AWS Console
   2. Continue with Phase 6: Create Golden AMIs
   ```

6. **Verify in AWS Console:**
   - Go to **VPC → Security Groups** (or **EC2 → Security Groups**)
   - Filter by VPC: `vpc-06f7dead5c49ece64`
   - You should see 5 security groups:
     - ✅ `frontend-alb-sg`
     - ✅ `frontend-ec2-sg`
     - ✅ `backend-alb-sg`
     - ✅ `backend-ec2-sg`
     - ✅ `aurora-sg` (updated)

7. **Skip to Phase 6** - Security groups are done!

#### What the Script Creates

| Security Group | Direction | Port | Source | Purpose |
|---------------|-----------|------|--------|---------|
| `frontend-alb-sg` | Inbound | 80 (HTTP) | 0.0.0.0/0 | Allow internet traffic |
| | Inbound | 443 (HTTPS) | 0.0.0.0/0 | Allow HTTPS traffic |
| `frontend-ec2-sg` | Inbound | 80 (HTTP) | frontend-alb-sg | Allow only from ALB |
| | Inbound | 443 (HTTPS) | 10.0.0.0/16 | HTTPS within VPC |
| `backend-alb-sg` | Inbound | 80 (HTTP) | frontend-ec2-sg | Allow only from frontend |
| `backend-ec2-sg` | Inbound | 3000 (TCP) | backend-alb-sg | Allow only from backend ALB |
| `aurora-sg` | Inbound | 5432 (PostgreSQL) | backend-ec2-sg | Allow only from backend |

**All outbound:** Allow all (default)

#### Troubleshooting

**Error: "Security group already exists"**
- The script detects existing security groups and skips creation
- It's safe to run multiple times (idempotent)
- It will show `[EXISTS]` instead of creating duplicates

**Error: "AWS CLI profile not found: sarowar-ostad"**
- Update the `$PROFILE` variable in the script to match your AWS CLI profile name
- Check your profiles: `aws configure list-profiles`
- Or configure the profile: `aws configure --profile sarowar-ostad`

**Error: "AccessDenied" or "UnauthorizedOperation"**
- Your AWS user needs these permissions:
  - `ec2:CreateSecurityGroup`
  - `ec2:AuthorizeSecurityGroupIngress`
  - `ec2:DescribeSecurityGroups`
- Contact your AWS administrator

**Script runs but security groups not appearing:**
- Check you're looking in the correct region (`ap-south-1`)
- Verify VPC ID in script matches your actual VPC
- Check AWS Console → VPC → Security Groups → Filter by VPC

---

### Option B: Manual Creation (All Platforms)

If you prefer manual creation or don't have PowerShell, follow Steps 5.1-5.5 below.

---

## Phase 5: Security Groups Setup (5 minutes)

### Step 5.1: Create Frontend ALB Security Group

1. Go to **EC2** → **Security Groups** → **Create security group**
2. Configure:
   - **Name**: `frontend-alb-sg`
   - **Description**: `Security group for Frontend ALB`
   - **VPC**: Select `devops-vpc`
3. **Inbound rules**:
   - Type: `HTTP` (80), Source: `0.0.0.0/0`, Description: `Allow HTTP from internet`
   - Type: `HTTPS` (443), Source: `0.0.0.0/0`, Description: `Allow HTTPS from internet`
4. **Outbound rules**: Leave default (all traffic)
5. Click **Create security group**

### Step 5.2: Create Frontend EC2 Security Group

1. **Create security group**:
   - **Name**: `frontend-ec2-sg`
   - **Description**: `Security group for Frontend EC2 instances`
   - **VPC**: Select `devops-vpc`
2. **Inbound rules**:
   - Type: `HTTP` (80), Source: Select `frontend-alb-sg`, Description: `Allow from Frontend ALB`
   - Type: `HTTPS` (443), Source: `10.0.0.0/16`, Description: `Allow HTTPS within VPC`
3. Click **Create security group**

### Step 5.3: Create Backend ALB Security Group

1. **Create security group**:
   - **Name**: `backend-alb-sg`
   - **Description**: `Security group for Backend Internal ALB`
   - **VPC**: Select `devops-vpc`
2. **Inbound rules**:
   - Type: `HTTP` (80), Source: Select `frontend-ec2-sg`, Description: `Allow from Frontend EC2`
3. Click **Create security group**

### Step 5.4: Create Backend EC2 Security Group

1. **Create security group**:
   - **Name**: `backend-ec2-sg`
   - **Description**: `Security group for Backend EC2 instances`
   - **VPC**: Select `devops-vpc`
2. **Inbound rules**:
   - Type: `Custom TCP` (3000), Source: Select `backend-alb-sg`, Description: `Allow from Backend ALB`
3. Click **Create security group**

### Step 5.5: Update Aurora Security Group

1. Go to **Security Groups** → Find `aurora-sg`
2. **Edit inbound rules**:
   - Delete existing rule
   - Add: Type `PostgreSQL` (5432), Source: Select `backend-ec2-sg`, Description: `Allow from Backend EC2`
3. Click **Save rules**

---

## Phase 6: Create Golden AMIs (20 minutes)

### Step 6.1: Launch Temporary Backend Instance

1. Go to **EC2** → **Launch instance**
2. Configure:
   - **Name**: `backend-golden-ami-temp`
   - **AMI**: `Amazon Linux 2023 AMI` (latest)
   - **Instance type**: `t3.micro`
   - **Key pair**: Select existing or create new
   - **Network**:
     - VPC: `devops-vpc`
     - Subnet: Select `devops-subnet-public1-ap-south-1a` (for initial setup)
     - Auto-assign public IP: `Enable`
   - **Security group**: Create new → Allow SSH (22) from your IP
   - **IAM instance profile**: Select `EC2RoleForBMIApp`
3. Click **Launch instance**
4. Wait for instance to be running

### Step 6.2: Connect and Setup Backend AMI

1. Connect via **Session Manager** (or SSH)
2. Run setup script:

```bash
# Download and run the backend setup script
wget https://raw.githubusercontent.com/sarowar-alam/3-tier-web-app-auto-scalling/main/AutoScaling-FrontEnd-CPU/backend-userdata.sh
chmod +x backend-userdata.sh
sudo ./backend-userdata.sh
```

3. Wait ~5 minutes for installation
4. Verify installations:
```bash
node --version  # Should show v20.x
pm2 --version   # Should show PM2
psql --version  # Should show PostgreSQL 15
```

### Step 6.3: Create Backend AMI

1. Go to **EC2** → **Instances**
2. Select `backend-golden-ami-temp`
3. **Actions** → **Image and templates** → **Create image**
4. Configure:
   - **Image name**: `bmi-backend-golden-ami`
   - **Description**: `Golden AMI for BMI Backend with Node.js 20 and PM2`
   - **No reboot**: Leave unchecked
5. Click **Create image**
6. Wait ~3-5 minutes
7. Go to **AMIs** and note the AMI ID (e.g., `ami-xxxxxxxxx`)

### Step 6.4: Launch Temporary Frontend Instance

1. **Launch instance**:
   - **Name**: `frontend-golden-ami-temp`
   - **AMI**: `Amazon Linux 2023 AMI`
   - **Instance type**: `t3.micro`
   - **Network**: Same as backend (public subnet)
   - **Security group**: Allow SSH from your IP
   - **IAM instance profile**: `EC2RoleForBMIApp`
2. Click **Launch instance**

### Step 6.5: Connect and Setup Frontend AMI

1. Connect via **Session Manager**
2. Run setup script:

```bash
wget https://raw.githubusercontent.com/sarowar-alam/3-tier-web-app-auto-scalling/main/AutoScaling-FrontEnd-CPU/frontend-userdata.sh
chmod +x frontend-userdata.sh
sudo ./frontend-userdata.sh
```

3. Wait ~5 minutes
4. Verify:
```bash
node --version   # v20.x
nginx -v         # nginx version
```

### Step 6.6: Create Frontend AMI

1. Select `frontend-golden-ami-temp`
2. **Actions** → **Create image**
3. Configure:
   - **Image name**: `bmi-frontend-golden-ami`
   - **Description**: `Golden AMI for BMI Frontend with nginx and Node.js 20`
4. Click **Create image**
5. Wait ~3-5 minutes
6. Note the AMI ID

### Step 6.7: Terminate Temporary Instances

1. Select both temporary instances
2. **Instance state** → **Terminate instance**

---

## Phase 7: Application Load Balancers (10 minutes)

### Step 7.1: Create Backend Target Group

1. Go to **EC2** → **Target Groups** → **Create target group**
2. Configure:
   - **Target type**: `Instances`
   - **Name**: `bmi-backend-tg`
   - **Protocol**: `HTTP`, Port: `3000`
   - **VPC**: Select `devops-vpc`
   - **Health check**:
     - Protocol: `HTTP`
     - Path: `/health`
     - Interval: `10 seconds`
     - Timeout: `5 seconds`
     - Healthy threshold: `2`
     - Unhealthy threshold: `3`
3. Click **Next**
4. **Don't register any targets yet**
5. Click **Create target group**

### Step 7.2: Create Backend ALB (Internal)

1. Go to **EC2** → **Load Balancers** → **Create Load Balancer**
2. Choose **Application Load Balancer**
3. Configure:
   - **Name**: `bmi-backend-alb`
   - **Scheme**: `Internal` ⚠️ (not internet-facing)
   - **IP address type**: `IPv4`
   - **VPC**: Select `devops-vpc`
   - **Mappings**: Select **both AZs** and **both private subnets**:
     - ap-south-1a: `devops-subnet-private1-ap-south-1a`
     - ap-south-1b: `devops-subnet-private2-ap-south-1b`
   - **Security groups**: Select `backend-alb-sg`
   - **Listeners**: HTTP (80)
   - **Default action**: Forward to `bmi-backend-tg`
4. Click **Create load balancer**
5. Wait ~2 minutes
6. **Copy the DNS name** (e.g., `internal-bmi-backend-alb-xxxxx.ap-south-1.elb.amazonaws.com`)

### Step 7.3: Update Parameter Store with Backend ALB URL

1. Go to **Systems Manager** → **Parameter Store**
2. Click `/bmi-app/backend-alb-url`
3. Click **Edit**
4. Update **Value**: `http://<backend-alb-dns-name>` (e.g., `http://internal-bmi-backend-alb-xxxxx.ap-south-1.elb.amazonaws.com`)
5. Click **Save changes**

### Step 7.4: Create Frontend Target Group

1. **Create target group**:
   - **Target type**: `Instances`
   - **Name**: `bmi-frontend-tg`
   - **Protocol**: `HTTP`, Port: `80`
   - **VPC**: Select `devops-vpc`
   - **Health check**:
     - Path: `/health`
     - Interval: `10 seconds`
     - Timeout: `5 seconds`
     - Healthy threshold: `2`
     - Unhealthy threshold: `3`
2. Click **Create target group**

### Step 7.5: Create Frontend ALB (Public)

1. **Create Load Balancer** → **Application Load Balancer**
2. Configure:
   - **Name**: `bmi-frontend-alb`
   - **Scheme**: `Internet-facing`
   - **VPC**: Select `devops-vpc`
   - **Mappings**: Select **both AZs** and **both public subnets**:
     - ap-south-1a: `devops-subnet-public1-ap-south-1a`
     - ap-south-1b: `devops-subnet-public2-ap-south-1b`
   - **Security groups**: Select `frontend-alb-sg`
   - **Listeners**: HTTP (80) → Forward to `bmi-frontend-tg`
3. Click **Create load balancer**
4. Wait ~2 minutes
5. **Copy the DNS name** (this is your application URL!)

---

## Phase 8: Backend EC2 Instances (Manual - Fixed 2 Instances) (10 minutes)

### Step 8.1: Launch Backend Instance 1

1. Go to **EC2** → **Launch instance**
2. Configure:
   - **Name**: `bmi-backend-1`
   - **AMI**: Select `bmi-backend-golden-ami` (from Phase 6.3)
   - **Instance type**: `t3.micro`
   - **Key pair**: Not needed (using SSM)
   - **Network**:
     - VPC: `devops-vpc`
     - Subnet: Select `devops-subnet-private1-ap-south-1a`
     - Auto-assign public IP: `Disable`
   - **Security group**: Select `backend-ec2-sg`
   - **IAM instance profile**: Select `EC2RoleForBMIApp`
   - **Advanced details** → **User data**:

```bash
#!/bin/bash
wget https://raw.githubusercontent.com/sarowar-alam/3-tier-web-app-auto-scalling/main/AutoScaling-FrontEnd-CPU/deploy-backend.sh
chmod +x deploy-backend.sh
./deploy-backend.sh
```

3. Click **Launch instance**

### Step 8.2: Launch Backend Instance 2

1. Repeat above steps with:
   - **Name**: `bmi-backend-2`
   - **Subnet**: Select **second private subnet** (different AZ) `devops-subnet-private2-ap-south-1b`
   - Same user data script

### Step 8.3: Register Backend Instances with Target Group

1. Wait ~5-7 minutes for instances to run deployment scripts
2. Go to **Target Groups** → Select `bmi-backend-tg`
3. **Targets** tab → **Register targets**
4. Select both `bmi-backend-1` and `bmi-backend-2`
5. Click **Include as pending below** → **Register pending targets**
6. Wait 2-3 minutes for health checks to pass (status: `healthy`)

---

## Phase 9: Frontend Auto Scaling Group (10 minutes)

### Step 9.1: Create Launch Template

1. Go to **EC2** → **Launch Templates** → **Create launch template**
2. Configure:

**Template name**: `bmi-frontend-lt`
**Description**: `Launch template for frontend auto-scaling`

**AMI**: Select `bmi-frontend-golden-ami`
**Instance type**: `t3.micro`

**Key pair**: Not needed

**Network settings**:
- **Subnet**: Don't include in template
- **Security groups**: Select `frontend-ec2-sg`

**Advanced details**:
- **IAM instance profile**: Select `EC2RoleForBMIApp`
- **Metadata version**: `V2 only (token required)`
- **User data**:

```bash
#!/bin/bash
wget https://raw.githubusercontent.com/sarowar-alam/3-tier-web-app-auto-scalling/main/AutoScaling-FrontEnd-CPU/deploy-frontend.sh
chmod +x deploy-frontend.sh
./deploy-frontend.sh
```

3. Click **Create launch template**

### Step 9.2: Create Auto Scaling Group

1. Go to **EC2** → **Auto Scaling Groups** → **Create Auto Scaling group**
2. **Step 1: Choose launch template**
   - **Name**: `bmi-frontend-asg`
   - **Launch template**: Select `bmi-frontend-lt`
   - Click **Next**

3. **Step 2: Network**
   - **VPC**: Select `devops-vpc`
   - **Availability Zones and subnets**: Select **both private subnets**:
     - `devops-subnet-private1-ap-south-1a`
     - `devops-subnet-private2-ap-south-1b`
   - Click **Next**

4. **Step 3: Load balancing**
   - **Load balancing**: `Attach to an existing load balancer`
   - **Choose target groups**: Select `bmi-frontend-tg`
   - **Health checks**:
     - ELB health check: `Enable`
     - Health check grace period: `300 seconds` (5 minutes)
   - Click **Next**

5. **Step 4: Group size and scaling**
   - **Desired capacity**: `2`
   - **Min**: `1`
   - **Max**: `4`
   - **Scaling policies**: `Target tracking scaling policy`
     - **Policy name**: `cpu-target-tracking`
     - **Metric type**: `Average CPU utilization`
     - **Target value**: `60`
     - **Instances need**: `60` seconds warmup
   - Click **Next**

6. **Step 5: Notifications** - Skip
7. **Step 6: Tags**
   - Add tag: Key=`Name`, Value=`bmi-frontend-asg-instance`
8. Click **Next** → **Create Auto Scaling Group**

### Step 9.3: Verify Frontend Deployment

1. Wait ~5-7 minutes for instances to launch and deploy
2. Go to **Target Groups** → `bmi-frontend-tg` → **Targets** tab
3. Verify 2 instances are `healthy`
4. Go to **Load Balancers** → Copy Frontend ALB DNS name
5. Open in browser: `http://<frontend-alb-dns>.elb.amazonaws.com`
6. You should see the BMI Health Tracker app! 🎉

---

## Phase 10: Load Testing and Monitoring (15-20 minutes)

This phase demonstrates auto-scaling in action. You'll generate load to trigger scale-out, watch instances launch, then observe scale-in when load stops.

### Understanding Auto-Scaling Timeline

Before testing, understand what you'll observe:

```
Load Test Start
     │
     ├─ T+00:30  Frontend CPU starts rising
     ├─ T+01:30  Average CPU hits 60% (target threshold)
     ├─ T+02:00  CloudWatch metric aggregated & alarm triggered
     ├─ T+02:30  ASG receives scale-out signal
     ├─ T+03:00  New EC2 instance(s) launching
     ├─ T+04:00  Deploy script running (git clone, npm install, build)
     ├─ T+05:30  Health checks passing, instance marked "healthy"
     ├─ T+06:00  Instance added to ALB, starts receiving traffic
     ├─ T+07:00  CPU normalizes across 3-4 instances (~40% each)
     │
 Load Test Stop
     │
     ├─ T+00:30  CPU drops below 60%
     ├─ T+05:00  Scale-in cooldown period expires (default 300s)
     ├─ T+06:00  ASG detects overcapacity
     ├─ T+06:30  ASG terminates excess instance(s)
     ├─ T+08:00  Back to 2 instances (desired capacity)
```

**Key insight:** Auto-scaling is designed for **sustained** load changes, not instant spikes. The 5-7 minute delay is intentional to avoid thrashing.

---

### Step 10.1: Setup Load Testing Tools (Your Local Machine)

#### Install Apache Bench

**macOS:**
```bash
# Pre-installed, verify:
ab -V
# Should show: Apache Bench Version 2.3
```

**Linux (Amazon Linux / RHEL / CentOS):**
```bash
sudo yum install -y httpd-tools
ab -V
```

**Linux (Ubuntu / Debian):**
```bash
sudo apt-get update
sudo apt-get install -y apache2-utils
ab -V
```

**Windows:**
```powershell
# Option 1: WSL (Recommended)
wsl --install
# After WSL installed, inside WSL:
sudo apt-get install apache2-utils

# Option 2: Native Windows
# Download Apache for Windows: http://www.apachelounge.com/download/
# Extract and add bin/ to PATH
```

#### Download Test Scripts

```bash
# If you haven't cloned the repo locally:
git clone https://github.com/sarowar-alam/3-tier-web-app-auto-scalling.git
cd 3-tier-web-app-auto-scalling/AutoScaling-FrontEnd-CPU/load-test

# Make scripts executable (Linux/macOS)
chmod +x quick-test.sh monitor.sh

# Verify scripts are ready
ls -lah
```

---

### Step 10.2: Get Your Frontend ALB DNS Name

1. **AWS Console → EC2 → Load Balancers**
2. Find: `bmi-frontend-alb` (or similar name)
3. Copy **DNS name** (e.g., `bmi-frontend-alb-123456789.ap-south-1.elb.amazonaws.com`)
4. Test it works:
   ```bash
   curl http://YOUR-ALB-DNS/health
   # Should return: healthy
   ```

---

### Step 10.3: Start Real-Time Monitoring (Terminal 1)

**Open a terminal and run:**

```bash
cd load-test
./monitor.sh bmi-frontend-asg ap-south-1
```

**What you'll see:**

```
=========================================
Auto Scaling Group Status
=========================================
Time: 2026-05-17 14:30:45

Capacity:
  Min: 1 | Desired: 2 | Max: 4 | Current: 2

Instances:
Instance ID          State           Health          AZ              CPU %
--------------------------------------------------------------------------------
i-0123456789abcdef0  InService       Healthy         ap-south-1a     25.3
i-0fedcba987654321f  InService       Healthy         ap-south-1b     22.7

Recent Scaling Activities (last 5):
  2026-05-17 14:15:23 | Launching a new EC2 instance... | Successful
  2026-05-17 14:10:45 | Terminating EC2 instance... | Successful

Refreshing in 10 seconds... (Ctrl+C to stop)
```

**📌 Keep this terminal open!** It will show scaling events in real-time.

---

### Step 10.4: Run Load Test (Terminal 2)

**Open a SECOND terminal:**

```bash
cd load-test

# Set your ALB DNS (from Step 10.2)
export ALB_DNS="bmi-frontend-alb-123456789.ap-south-1.elb.amazonaws.com"

# Run the test
./quick-test.sh http://${ALB_DNS}
```

**Script Output:**

```
=========================================
BMI App Auto-Scaling Load Test
=========================================
Target: http://bmi-frontend-alb-xxxxx.elb.amazonaws.com
Concurrent Users: 100
Total Requests: 50,000
Duration: 300 seconds (5 minutes)

Testing connectivity...
✓ Connection successful

=========================================
Starting Load Test
=========================================

Phase 1: Warmup (30 seconds)
  Sending light traffic to warm up instances...
  [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓] 100%

Phase 2: Gradual Increase (60 seconds)
  Ramping up to 25 concurrent users...
  [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓] 100%

Phase 3: Heavy Load - GET Requests
  Target: http://YOUR-ALB/
  100 concurrent users hitting homepage...
  Running in background (PID: 12345)

Phase 4: Heavy Load - API POST Requests
  Target: http://YOUR-ALB/api/measurements
  50 concurrent users submitting BMI data...
  Running in background (PID: 12346)

Phase 5: Heavy Load - API GET Requests
  Target: http://YOUR-ALB/api/measurements
  50 concurrent users fetching data...
  Running in background (PID: 12347)

=========================================
Load Test Running...
=========================================

Monitor these in AWS Console:
  ✓ EC2 > Auto Scaling Groups > bmi-frontend-asg > Activity
  ✓ CloudWatch > Metrics > EC2 > CPUUtilization
  ✓ Target Groups > bmi-frontend-tg > Targets

Or watch Terminal 1 (monitor.sh) for live updates!

The test will run for ~5 minutes.
Press Ctrl+C to stop early.
```

---

### Step 10.5: Observe Scaling in AWS Console

While the load test runs, open these tabs in AWS Console:

#### Tab 1: Auto Scaling Group Activity 🎯 **Most Important**

1. **EC2 → Auto Scaling Groups**
2. Click `bmi-frontend-asg`
3. **Activity** tab
4. Click **Refresh** every 30 seconds

**What to watch for:**

| Time | Activity Message | Status |
|------|-----------------|--------|
| T+0 | No recent activity | - |
| T+2-3min | `Launching a new EC2 instance: i-abc123` | In progress |
| T+5-6min | `Successfully launched instance i-abc123` | Successful |
| T+6-7min | (If heavy load) `Launching a new EC2 instance: i-def456` | In progress |

**Screenshot opportunity:** This is where scaling happens!

#### Tab 2: CloudWatch Metrics

1. **CloudWatch → Metrics → All metrics**
2. **EC2 → Per-Instance Metrics**
3. Search: `CPUUtilization`
4. ✅ **Select all** instances with "bmi-frontend" in name
5. **Graphed metrics** tab → Period: **1 minute**
6. Watch the graph update

**What you'll see:**
```
CPU %
100 |
 80 |              ╱╲  (Initial spike on 2 instances)
 60 |    ────────╯  ╰─────╮
 40 |                      ╰───────── (Normalized across 4 instances)
 20 |                                
  0 |_________________________________________________
     0min    2min    4min    6min    8min    10min
     
     Scale-out →              ← Normalized
```

#### Tab 3: Target Group Health

1. **EC2 → Target Groups**
2. Click `bmi-frontend-tg`
3. **Targets** tab
4. Auto-refresh every 10 seconds

**Instance state progression:**

| Time | Healthy Count | States |
|------|--------------|--------|
| T+0 | 2 | 2 healthy |
| T+3min | 2 → 3 | 2 healthy, 1 initial |
| T+5min | 3 | 3 healthy ✅ |
| T+6min | 3 → 4 | 3 healthy, 1 initial |
| T+8min | 4 | 4 healthy ✅ |

**Color codes:**
- 🟢 **Green = Healthy** - Instance passing health checks
- 🟡 **Yellow = Initial** - Instance booting, not ready
- 🔴 **Red = Unhealthy** - Instance failing health checks (bad!)

#### Tab 4: CloudWatch Alarms

1. **CloudWatch → Alarms → All alarms**
2. Filter: `TargetTracking`
3. Look for alarm with `bmi-frontend` in name

**Alarm state changes:**

| State | Means | When |
|-------|-------|------|
| 🟢 OK | CPU below target (60%) | Before load test |
| 🔴 ALARM | CPU above target | 1-2 min after test starts |
| 🟢 OK | CPU back below target | After scale-out completes |

---

### Step 10.6: Expected Scaling Behavior

**Timeline of events you should observe:**

#### Minute 0-2: Load Starts
- ✅ Monitor.sh shows CPU rising on 2 instances
- ✅ CPU graph shows spike to 80-100%
- ✅ ASG desired capacity: still 2

#### Minute 2-3: Threshold Crossed
- ✅ Average CPU sustains >60% for ~1 minute
- ✅ CloudWatch alarm state: OK → ALARM
- ✅ ASG Activity shows: "Launching new instance..."

#### Minute 3-5: Instance Launching
- ✅ ASG desired capacity: 2 → 3 (or 4 if very high load)
- ✅ Monitor.sh shows new instance in "Pending" state
- ✅ Target group shows instance in "initial" health state
- ✅ Deploy script running on new instance (git clone, build, etc.)

#### Minute 5-7: Instance Becomes Healthy
- ✅ New instance passes health checks
- ✅ Target group shows instance as "healthy"
- ✅ New instance starts receiving traffic
- ✅ CPU on original instances drops (load distributed)

#### Minute 7-10: Steady State
- ✅ Load distributed across 3-4 instances
- ✅ Each instance CPU: ~30-50% (below 60% target)
- ✅ All instances healthy
- ✅ Application responsive

---

### Step 10.7: Observe Scale-IN (After Test Stops)

After ~5 minutes, **STOP the load test:**
- Press `Ctrl+C` in the load test terminal (Terminal 2)
- Or wait for it to complete automatically

**What happens next:**

| Time After Stop | Event |
|----------------|-------|
| T+0 | Load test stops, CPU drops immediately |
| T+1 min | CloudWatch alarm: ALARM → OK |
| T+5 min | Cooldown period expires (default 300 seconds) |
| T+6 min | ASG evaluates: "We have too many instances" |
| T+6.5 min | ASG Activity: "Terminating EC2 instance: i-xxx" |
| T+7 min | Instance removed from target group |
| T+8 min | Instance terminated |
| T+8-10 min | Back to 2 instances (desired capacity) |

**📌 Important:** Scale-in is SLOWER than scale-out (by design). This prevents rapid up/down cycling.

---

### Step 10.8: Verify Aurora Auto-Scaling

While you're testing, Aurora also scales:

1. **RDS → Databases → bmi-aurora-cluster**
2. **Monitoring** tab
3. Find metric: **Serverless Database Capacity**
4. Time range: **Last 1 hour**

**What you'll see:**

```
ACU
2.0 |              ╱─╲
1.5 |            ╱   ╰╮
1.0 |          ╱      ╰╮
0.5 |────────╯         ╰─────────
0.0 |_________________________________
     Before    During    After
     load      load      load
```

**Notes:**
- Aurora scaling is MUCH slower than EC2 (10-15 minutes)
- Scales based on CPU, connections, and workload patterns
- Min ACU: 0.5 (configured in terraform.tfvars)
- Max ACU: 2 (cost-limited for demo)

---

### Step 10.9: Success Checklist

Did your auto-scaling demo work? Check these:

#### During Scale-OUT ✅
- [ ] Monitor.sh showed CPU rising on initial instances
- [ ] ASG Activity showed "Launching new instance" message
- [ ] Desired capacity increased (2 → 3 or 4)
- [ ] New instances appeared in target group
- [ ] New instances became "healthy" within 5-7 minutes
- [ ] CPU normalized across all instances
- [ ] Application remained responsive (no errors)

#### During Scale-IN ✅
- [ ] After stopping test, CPU dropped
- [ ] After 5-10 minutes, ASG started terminating instances
- [ ] Desired capacity decreased back to 2
- [ ] Only 2 instances remain running
- [ ] Application still works with fewer instances

**If all checked:** 🎉 **SUCCESS!** Your auto-scaling is working perfectly!

---

### Step 10.10: Troubleshooting Common Issues

#### Issue: Load test can't connect to ALB
```
Error: curl: (7) Failed to connect to xxx.elb.amazonaws.com port 80
```

**Diagnosis:**
- Security group blocking traffic
- Wrong DNS name
- ALB not created or deleted

**Fix:**
```bash
# 1. Verify ALB exists
aws elbv2 describe-load-balancers --region ap-south-1 | grep bmi-frontend

# 2. Check security group allows HTTP
aws ec2 describe-security-groups --filters "Name=group-name,Values=frontend-alb-sg" --region ap-south-1

# 3. Test with curl
curl -v http://YOUR-ALB-DNS/health
```

---

#### Issue: CPU increases but ASG doesn't scale

**Symptoms:**
- CPU shows 80-100%
- No new instances launching
- Alarm shows ALARM state but no action

**Possible causes & fixes:**

**Cause 1: Already at max capacity**
```bash
# Check ASG limits
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names bmi-frontend-asg \
  --region ap-south-1 \
  --query 'AutoScalingGroups[0].[MinSize,DesiredCapacity,MaxSize]'

# Should show: [1, 2, 4]
# If DesiredCapacity == MaxSize, can't scale further
```

**Fix:** Wait for existing instances to handle load, or increase max size

**Cause 2: Scaling policy missing or misconfigured**
```bash
# Check scaling policies exist
aws autoscaling describe-policies \
  --auto-scaling-group-name bmi-frontend-asg \
  --region ap-south-1

# Should show TargetTrackingScaling policy
```

**Fix:** Recreate ASG with scaling policy (Phase 9, Step 9.2)

**Cause 3: Not enough sustained load**
- CloudWatch aggregates metrics over 1-minute periods
- Need sustained >60% CPU for ~1-2 minutes
- Quick spikes don't trigger scaling

**Fix:** Run load test for longer (5+ minutes)

---

#### Issue: New instances launch but stay "unhealthy"

**Symptoms:**
- ASG launches instance
- Instance shows in EC2 console
- Target group shows "initial" or "unhealthy" for >10 minutes

**Diagnosis via SSM:**
```bash
# 1. Get unhealthy instance ID from target group
INSTANCE_ID="i-xxxxxxxxx"

# 2. Connect via SSM
aws ssm start-session --target $INSTANCE_ID --region ap-south-1

# 3. Check deploy script logs
sudo tail -f /var/log/frontend-deploy.log

# Common errors:
# - "fatal: could not read from remote repository" → GitHub rate limit
# - "npm ERR!" → npm install failed
# - "nginx: [emerg]" → nginx config error
```

**Common fixes:**

**GitHub rate limiting:**
```bash
# The deploy script fetches from public GitHub
# If rate limited, wait 1 hour or use authenticated access
```

**npm install timeout:**
```bash
# Check if npm install completed
cd /var/www/app/frontend
ls -la node_modules/  # Should have many packages
```

**Health check path wrong:**
```bash
# Verify nginx serving /health endpoint
curl localhost/health
# Should return: healthy

# If not, check nginx config
sudo nginx -t
sudo systemctl status nginx
```

---

#### Issue: Instances don't scale back down

**Symptoms:**
- Load test stopped 15+ minutes ago
- Still have 4 instances running
- CPU low (<20%) but no termination

**Possible causes:**

**Cause 1: Min size too high**
```bash
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names bmi-frontend-asg \
  --region ap-south-1 \
  --query 'AutoScalingGroups[0].MinSize'
  
# If MinSize = 4, ASG won't go below 4
```

**Fix:**
```bash
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name bmi-frontend-asg \
  --min-size 1 \
  --region ap-south-1
```

**Cause 2: Still in cooldown period**
- Default cooldown: 300 seconds (5 minutes)
- Scale-in is conservative to avoid oscillation

**Fix:** Wait longer (up to 10-15 minutes total)

**Cause 3: Load still present**
- Background processes keeping CPU elevated
- Active user sessions

**Fix:** Verify no traffic:
```bash
# Check ALB request count
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name RequestCount \
  --dimensions Name=LoadBalancer,Value=app/bmi-frontend-alb/xxx \
  --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum \
  --region ap-south-1
```

---

### Step 10.11: Cost Warning ⚠️

**Running overnight cost:** ~$15-20

**What's expensive:**
- NAT Gateway: $0.045/hour = $1.08/day (always running)
- Aurora Serverless v2: 0.5 ACU minimum = ~$1.80/day
- EC2 instances: 4× t3.micro = $0.0416/hour = $1.00/day
- ALBs: 2× ALB = $0.67/day

**After testing, either:**

**Option A: Tear down completely** (if done for the day)
- Follow [TEARDOWN-CHECKLIST.md](TEARDOWN-CHECKLIST.md)
- Total cleanup time: ~20 minutes
- Cost: $0 (everything deleted)

**Option B: Scale to minimum** (if continuing tomorrow)
```bash
# Set ASG to 0 instances
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name bmi-frontend-asg \
  --min-size 0 \
  --desired-capacity 0 \
  --region ap-south-1

# Stop backend instances
aws ec2 stop-instances \
  --instance-ids i-backend1 i-backend2 \
  --region ap-south-1

# Aurora will scale to 0.5 ACU automatically
# Saves ~$1-2/day
```

---

## ✅ Phase 10 Complete!

You've successfully:
- ✅ Generated load to trigger auto-scaling
- ✅ Observed new instances launching
- ✅ Watched traffic distribute across instances
- ✅ Verified scale-in after load stopped
- ✅ Monitored Aurora auto-scaling

---

## Phase 11: Verification and Testing (5 minutes)

### Verify Auto-Scaling Works:

**Expected Behavior:**
- Start: 2 instances (desired capacity)
- During load: Scales to 3-4 instances
- After cooldown (5-7 min): Scales back to 2 instances

**Check these:**
- [ ] Frontend ALB accessible via browser
- [ ] App loads and displays UI correctly
- [ ] Can submit measurements via form
- [ ] Backend API responding (check Network tab)
- [ ] ASG activity shows scaling events
- [ ] CloudWatch shows CPU spikes
- [ ] Instances scale up during load
- [ ] Instances scale down after load stops

### Test Aurora Auto-Scaling:

1. Go to **RDS** → **Databases** → `bmi-aurora-cluster`
2. Click **Monitoring** tab
3. Check **Serverless Database Capacity** metric
4. During load test, capacity should increase from 0.5 ACU → 1-2 ACU
5. After load stops, scales back down

---

## Troubleshooting

### Frontend not loading?
- Check Target Group health status
- Connect to instance via SSM: `aws ssm start-session --target <instance-id> --region ap-south-1`
- Check logs: `sudo tail -f /var/log/frontend-deploy.log`
- Verify nginx: `sudo systemctl status nginx`

### Backend API not responding?
- Check backend target group health
- Connect via SSM to backend instance
- Check logs: `sudo tail -f /var/log/backend-deploy.log`
- Check PM2: `sudo pm2 status`
- Check database: `sudo pm2 logs`

### Auto-scaling not triggering?
- Verify scaling policy: ASG → Automatic scaling tab
- Check CloudWatch alarms: CloudWatch → Alarms
- Ensure load test is actually hitting the ALB
- Wait longer - scaling has cooldown periods (60-120 seconds)

### Can't connect via SSM?
- Verify IAM role has `AmazonSSMManagedInstanceCore`
- Check VPC endpoints are created and available
- Ensure security groups allow outbound HTTPS (443)
- Wait 5 minutes after instance launch

---

## Cost Optimization

**During demo:**
- Use t3.micro instances ($0.0104/hour)
- Aurora Serverless v2 minimal ACUs (0.5-2)
- Single NAT Gateway ($0.045/hour)

**After demo:**
- **DELETE EVERYTHING** using [TEARDOWN-CHECKLIST.md](TEARDOWN-CHECKLIST.md)
- Most expensive: NAT Gateway and Aurora (even when idle)
- **Don't forget!** Left running 24 hours = ~$10-15

---

## Next Steps

1. **Test the application** - Add measurements, view trends
2. **Run load tests** - Trigger auto-scaling multiple times
3. **Monitor metrics** - Watch CloudWatch dashboards
4. **Experiment** - Change scaling thresholds, test different loads
5. **Learn Terraform** - Try the IaC approach in [terraform/README.md](terraform/README.md)
6. **CLEANUP** - Follow [TEARDOWN-CHECKLIST.md](TEARDOWN-CHECKLIST.md) to avoid charges

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                  ┌────────▼─────────┐
                  │  Public ALB      │ (Internet-facing)
                  │  Port 80         │
                  └────────┬─────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐        ┌────▼────┐       ┌────▼────┐
   │Frontend │        │Frontend │       │Frontend │
   │EC2      │        │EC2      │       │EC2      │
   │(nginx)  │        │(nginx)  │       │(nginx)  │
   └────┬────┘        └────┬────┘       └────┬────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │ /api proxy
                  ┌────────▼─────────┐
                  │ Internal ALB     │ (private)
                  │ Port 80          │
                  └────────┬─────────┘
                           │
                  ┌────────┼─────────┐
                  │        │         │
             ┌────▼────┐  ┌▼────────┐
             │Backend  │  │Backend  │
             │EC2      │  │EC2      │
             │Node/PM2 │  │Node/PM2 │
             └────┬────┘  └┬────────┘
                  │        │
                  └────┬───┘
                       │
              ┌────────▼────────┐
              │ Aurora          │
              │ Serverless v2   │
              │ PostgreSQL      │
              │ (0.5-2 ACU)     │
              └─────────────────┘
```

---

## Summary

**What You've Built:**
- ✅ 3-tier auto-scaling architecture
- ✅ Frontend ASG with CPU-based scaling (60% target)
- ✅ Backend on fixed EC2 instances (2)
- ✅ Aurora Serverless v2 with auto-scaling compute
- ✅ Multi-AZ high availability
- ✅ Private subnets with SSM access
- ✅ Load testing and monitoring tools

**Total Setup Time:** ~60-75 minutes (Manual) or ~15-20 minutes (Terraform)
**Demo Time:** 15-20 minutes
**Teardown Time:** 20-30 minutes

---

## 🎓 Learning Outcomes

After completing this lab, you've learned:

### AWS Services
- ✅ **EC2**: Launch templates, instances, AMIs
- ✅ **Auto Scaling**: ASG, scaling policies, target tracking
- ✅ **ELB**: Application Load Balancers (public + internal), target groups
- ✅ **RDS**: Aurora Serverless v2, multi-AZ, serverless scaling
- ✅ **VPC**: Subnets, security groups, VPC endpoints, NAT gateway
- ✅ **IAM**: Roles, policies, instance profiles
- ✅ **Systems Manager**: Session Manager, Parameter Store
- ✅ **CloudWatch**: Metrics, alarms, monitoring

### DevOps Concepts
- ✅ **Golden AMIs**: Fast, consistent deployments
- ✅ **Auto-scaling**: CPU-based target tracking
- ✅ **Health checks**: ALB health monitoring
- ✅ **Multi-AZ**: High availability architecture
- ✅ **Private networking**: Secure instance placement
- ✅ **Infrastructure patterns**: 3-tier architecture
- ✅ **Load testing**: Triggering and observing auto-scaling

### Next Learning Paths
- **Infrastructure as Code**: Try the Terraform implementation
- **CI/CD**: Automate deployments with GitHub Actions
- **Monitoring**: Set up CloudWatch dashboards and alarms
- **Security**: Add HTTPS, WAF, secrets rotation
- **Cost optimization**: Reserved instances, scheduled scaling

---

## Support

For issues with this setup:
1. Check [Troubleshooting](#troubleshooting) section
2. Review AWS CloudWatch logs
3. Verify all security group rules
4. Ensure Parameter Store values are correct

**Remember to clean up!** See [TEARDOWN-CHECKLIST.md](TEARDOWN-CHECKLIST.md)

---

**Demo complete! 🎉**

---

## 🧑‍💻 Author

*Md. Sarowar Alam*  
Lead DevOps Engineer, Hogarth Worldwide  
📧 Email: sarowar@hotmail.com  
🔗 LinkedIn: [linkedin.com/in/sarowar](https://www.linkedin.com/in/sarowar/)

---

## 📖 Additional Resources

- [AWS Auto Scaling Documentation](https://docs.aws.amazon.com/autoscaling/)
- [Aurora Serverless v2 Guide](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)

---

**Version:** 2.0 (Comprehensive Educational Edition)  
**Last Updated:** May 17, 2026
