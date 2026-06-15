#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Creates Golden AMIs for BMI backend and frontend, then updates terraform.tfvars and pushes to git.

.DESCRIPTION
    1. Finds the latest Amazon Linux 2023 AMI
    2. Launches a temp EC2 in the public subnet, runs the userdata setup script via SSM
    3. Waits for setup to complete, creates AMI, terminates temp instance
    4. Repeats for frontend
    5. Updates terraform.tfvars with the new AMI IDs
    6. Commits and pushes to git

.EXAMPLE
    .\Create-GoldenAMIs.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ─── Configuration ──────────────────────────────────────────────────────────
$PROFILE         = "sarowar-ostad"
$REGION          = "ap-south-1"
$VPC_ID          = "vpc-0f6ed77f71ef6e7f7"
$PUBLIC_SUBNET   = "subnet-0a7098152cde9cb3c"   # devops-subnet-public1-ap-south-1a
$INSTANCE_TYPE   = "t3.micro"
$TFVARS_PATH     = "$PSScriptRoot\terraform\terraform.tfvars"
$REPO_ROOT       = (Resolve-Path "$PSScriptRoot\..").Path

$BACKEND_SETUP_URL  = "https://raw.githubusercontent.com/sarowar-alam/3-tier-web-app-auto-scalling/main/AutoScaling-FrontEnd-CPU/backend-userdata.sh"
$FRONTEND_SETUP_URL = "https://raw.githubusercontent.com/sarowar-alam/3-tier-web-app-auto-scalling/main/AutoScaling-FrontEnd-CPU/frontend-userdata.sh"

# AWS CLI shorthand
$AWS = { aws --profile $PROFILE --region $REGION @args }

# ─── Helper Functions ────────────────────────────────────────────────────────
function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Info($msg) { Write-Host "    $msg" -ForegroundColor Gray }

function Wait-InstanceRunning($instanceId) {
    Write-Info "Waiting for $instanceId to be running + status checks OK..."
    & $AWS ec2 wait instance-running --instance-ids $instanceId | Out-Null
    & $AWS ec2 wait instance-status-ok --instance-ids $instanceId | Out-Null
    Write-OK "Instance $instanceId is ready"
}

function Wait-SsmReady($instanceId) {
    Write-Info "Waiting for SSM agent to register on $instanceId ..."
    $maxWait = 300  # 5 minutes
    $waited  = 0
    while ($waited -lt $maxWait) {
        $status = & $AWS ssm describe-instance-information `
            --filters "Key=InstanceIds,Values=$instanceId" `
            --query "InstanceInformationList[0].PingStatus" --output text 2>$null
        if ($status -eq "Online") {
            Write-OK "SSM agent is online"
            return
        }
        Start-Sleep -Seconds 15
        $waited += 15
        Write-Info "  still waiting... ($waited s / $maxWait s)"
    }
    throw "SSM agent never came online for $instanceId after $maxWait seconds"
}

function Invoke-SsmCommand($instanceId, [string[]]$commands) {
    $cmdId = & $AWS ssm send-command `
        --instance-ids $instanceId `
        --document-name "AWS-RunShellScript" `
        --parameters "commands=$($commands | ConvertTo-Json -Compress)" `
        --query "Command.CommandId" --output text
    Write-Info "SSM command ID: $cmdId"

    # Poll for completion
    $maxWait = 900  # 15 minutes for setup scripts
    $waited  = 0
    while ($waited -lt $maxWait) {
        Start-Sleep -Seconds 20
        $waited += 20
        $result = & $AWS ssm get-command-invocation `
            --command-id $cmdId --instance-id $instanceId `
            --query "{Status:Status,Out:StandardOutputContent,Err:StandardErrorContent}" `
            --output json | ConvertFrom-Json
        Write-Info "  Status: $($result.Status) ($waited s elapsed)"
        if ($result.Status -eq "Success")  { Write-OK "Command succeeded"; return $result }
        if ($result.Status -eq "Failed")   { throw "SSM command failed:`n$($result.Err)" }
        if ($result.Status -eq "Cancelled"){ throw "SSM command was cancelled" }
        if ($result.Status -eq "TimedOut") { throw "SSM command timed out" }
    }
    throw "SSM command did not complete within $maxWait seconds"
}

function New-TempSecurityGroup($vpcId, $name) {
    Write-Info "Creating temporary security group '$name' ..."
    $sgId = & $AWS ec2 create-security-group `
        --group-name $name `
        --description "Temporary SG for Golden AMI creation" `
        --vpc-id $vpcId `
        --query "GroupId" --output text
    Write-OK "Security group: $sgId"
    return $sgId
}

function Remove-TempSecurityGroup($sgId) {
    Write-Info "Deleting temp security group $sgId ..."
    & $AWS ec2 delete-security-group --group-id $sgId | Out-Null
    Write-OK "Security group deleted"
}

function Get-IamInstanceProfile() {
    # Look for the Terraform-created profile first, then fall back to any bmi- profile
    $profiles = & $AWS iam list-instance-profiles `
        --query "InstanceProfiles[?starts_with(InstanceProfileName,'bmi-ec2-profile')].InstanceProfileName" `
        --output text
    if ($profiles -and $profiles.Trim()) {
        $name = ($profiles -split "\s+")[0].Trim()
        Write-OK "Using IAM instance profile: $name"
        return $name
    }
    throw "No 'bmi-ec2-profile' instance profile found. Run 'terraform apply' for IAM module first, or create an EC2 role manually."
}

function Get-LatestAL2023Ami() {
    Write-Info "Looking up latest Amazon Linux 2023 AMI ..."
    $amiId = & $AWS ec2 describe-images `
        --owners amazon `
        --filters `
            "Name=name,Values=al2023-ami-2023*-x86_64" `
            "Name=state,Values=available" `
            "Name=architecture,Values=x86_64" `
        --query "sort_by(Images,&CreationDate)[-1].ImageId" `
        --output text
    if (-not $amiId -or $amiId -eq "None") {
        throw "Could not find a valid Amazon Linux 2023 AMI"
    }
    Write-OK "Base AMI: $amiId"
    return $amiId
}

function New-GoldenAmi($role, $baseAmiId, $sgId, $iamProfile, $setupScriptUrl, $verifyCmd, $amiName, $amiDesc) {
    Write-Step "Creating Golden AMI: $amiName"

    # User data: download and run the setup script
    $userDataScript = @"
#!/bin/bash
set -e
cd /tmp
curl -fsSL $setupScriptUrl -o setup.sh
chmod +x setup.sh
sudo ./setup.sh > /var/log/golden-ami-setup.log 2>&1
echo "GOLDEN_AMI_SETUP_COMPLETE" >> /var/log/golden-ami-setup.log
"@
    $userDataB64 = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($userDataScript))

    # Launch temp instance
    Write-Info "Launching temp $role instance ..."
    $instanceId = & $AWS ec2 run-instances `
        --image-id $baseAmiId `
        --instance-type $INSTANCE_TYPE `
        --subnet-id $PUBLIC_SUBNET `
        --security-group-ids $sgId `
        --iam-instance-profile "Name=$iamProfile" `
        --associate-public-ip-address `
        --metadata-options "HttpTokens=required,HttpEndpoint=enabled,HttpPutResponseHopLimit=2" `
        --user-data $userDataB64 `
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=temp-$amiName},{Key=Purpose,Value=GoldenAMI}]" `
        --query "Instances[0].InstanceId" --output text
    Write-OK "Temp instance: $instanceId"

    # Wait for instance to be ready
    Wait-InstanceRunning $instanceId
    Wait-SsmReady $instanceId

    # Wait for userdata script to finish (it can take 5-8 min)
    Write-Info "Waiting for setup script to complete (checking log via SSM) ..."
    $maxWait = 900
    $waited  = 0
    $done    = $false
    while ($waited -lt $maxWait -and -not $done) {
        Start-Sleep -Seconds 30
        $waited += 30
        $check = & $AWS ssm send-command `
            --instance-ids $instanceId `
            --document-name "AWS-RunShellScript" `
            --parameters 'commands=["grep -c GOLDEN_AMI_SETUP_COMPLETE /var/log/golden-ami-setup.log 2>/dev/null || echo 0"]' `
            --query "Command.CommandId" --output text
        Start-Sleep -Seconds 10
        $res = & $AWS ssm get-command-invocation `
            --command-id $check --instance-id $instanceId `
            --query "StandardOutputContent" --output text 2>$null
        if ($res -and $res.Trim() -match "^[1-9]") {
            $done = $true
            Write-OK "Setup script completed ($waited s elapsed)"
        } else {
            Write-Info "  Still running... ($waited s / $maxWait s)"
        }
    }
    if (-not $done) {
        throw "Setup script did not finish within $maxWait seconds on $instanceId"
    }

    # Quick verify
    Write-Info "Verifying: $verifyCmd"
    $verify = Invoke-SsmCommand $instanceId @($verifyCmd)
    Write-Info "  Output: $($verify.Out.Trim())"

    # Create AMI (with reboot for clean state)
    Write-Info "Creating AMI '$amiName' from $instanceId ..."
    $amiId = & $AWS ec2 create-image `
        --instance-id $instanceId `
        --name $amiName `
        --description $amiDesc `
        --no-reboot `
        --tag-specifications "ResourceType=image,Tags=[{Key=Name,Value=$amiName},{Key=Purpose,Value=GoldenAMI},{Key=Project,Value=bmi}]" `
        --query "ImageId" --output text
    Write-OK "AMI creation started: $amiId"

    # Wait for AMI to be available
    Write-Info "Waiting for AMI $amiId to become available ..."
    & $AWS ec2 wait image-available --image-ids $amiId | Out-Null
    Write-OK "AMI $amiId is available"

    # Terminate temp instance
    Write-Info "Terminating temp instance $instanceId ..."
    & $AWS ec2 terminate-instances --instance-ids $instanceId | Out-Null
    Write-OK "Instance termination initiated"

    return $amiId
}

function Update-TfVars($backendAmiId, $frontendAmiId) {
    Write-Step "Updating terraform.tfvars with new AMI IDs"
    $content = Get-Content $TFVARS_PATH -Raw

    $content = $content -replace '(backend_ami_id\s*=\s*")[^"]*(")', "`${1}$backendAmiId`${2}"
    $content = $content -replace '(frontend_ami_id\s*=\s*")[^"]*(")', "`${1}$frontendAmiId`${2}"

    Set-Content -Path $TFVARS_PATH -Value $content -NoNewline
    Write-OK "Updated backend_ami_id  = $backendAmiId"
    Write-OK "Updated frontend_ami_id = $frontendAmiId"
}

function Push-ToGit($backendAmiId, $frontendAmiId) {
    Write-Step "Committing and pushing to git"
    Push-Location $REPO_ROOT
    try {
        git add "AutoScaling-FrontEnd-CPU/terraform/backend.tf" `
                "AutoScaling-FrontEnd-CPU/terraform/modules/compute_frontend/main.tf" `
                ".gitignore" 2>$null
        # Note: terraform.tfvars is gitignored intentionally (contains secrets)
        # We only push code changes, not the tfvars
        $status = git status --porcelain
        if ($status) {
            git commit -m "chore: golden AMI IDs updated - backend=$backendAmiId frontend=$frontendAmiId"
            git push origin main
            Write-OK "Pushed to GitHub"
        } else {
            Write-OK "No code changes to push"
        }
        Write-Info "New AMI IDs (update tfvars manually if needed):"
        Write-Info "  backend_ami_id  = `"$backendAmiId`""
        Write-Info "  frontend_ami_id = `"$frontendAmiId`""
    }
    finally {
        Pop-Location
    }
}

# ─── Main ─────────────────────────────────────────────────────────────────────
Write-Host "`n=================================================" -ForegroundColor Yellow
Write-Host "  BMI Golden AMI Creator" -ForegroundColor Yellow
Write-Host "  Profile: $PROFILE | Region: $REGION" -ForegroundColor Yellow
Write-Host "=================================================" -ForegroundColor Yellow

# Verify AWS credentials
Write-Step "Verifying AWS credentials"
$identity = & $AWS sts get-caller-identity --query "{Account:Account,Arn:Arn}" --output json | ConvertFrom-Json
Write-OK "Account: $($identity.Account)"
Write-OK "User:    $($identity.Arn)"

# Get prerequisites
$baseAmi    = Get-LatestAL2023Ami
$iamProfile = Get-IamInstanceProfile

# Create a single temp security group (outbound only - SSM needs no inbound)
Write-Step "Creating temporary security group"
$tempSgName = "temp-golden-ami-sg-$(Get-Date -Format 'yyyyMMddHHmm')"
$tempSgId   = New-TempSecurityGroup $VPC_ID $tempSgName

try {
    # ── Backend AMI ─────────────────────────────────────────────────────────
    $backendAmiId = New-GoldenAmi `
        -role        "backend" `
        -baseAmiId   $baseAmi `
        -sgId        $tempSgId `
        -iamProfile  $iamProfile `
        -setupScriptUrl $BACKEND_SETUP_URL `
        -verifyCmd   "node --version && pm2 --version && psql --version" `
        -amiName     "bmi-backend-golden-ami-$(Get-Date -Format 'yyyyMMdd-HHmm')" `
        -amiDesc     "BMI Backend Golden AMI - Node.js 20, PM2, PostgreSQL client"

    # ── Frontend AMI ────────────────────────────────────────────────────────
    $frontendAmiId = New-GoldenAmi `
        -role        "frontend" `
        -baseAmiId   $baseAmi `
        -sgId        $tempSgId `
        -iamProfile  $iamProfile `
        -setupScriptUrl $FRONTEND_SETUP_URL `
        -verifyCmd   "node --version && nginx -v 2>&1" `
        -amiName     "bmi-frontend-golden-ami-$(Get-Date -Format 'yyyyMMdd-HHmm')" `
        -amiDesc     "BMI Frontend Golden AMI - nginx, Node.js 20, git"
}
finally {
    # Always clean up temp SG (wait a bit for instances to detach)
    Write-Step "Cleaning up temporary security group"
    Start-Sleep -Seconds 30
    try { Remove-TempSecurityGroup $tempSgId } catch { Write-Warning "Could not delete SG $tempSgId - delete manually: $_" }
}

# Update tfvars
Update-TfVars $backendAmiId $frontendAmiId

# Push to git (code changes only - tfvars is gitignored)
Push-ToGit $backendAmiId $frontendAmiId

# Summary
Write-Host "`n=================================================" -ForegroundColor Green
Write-Host "  Golden AMIs Created Successfully!" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green
Write-Host "  Backend AMI:  $backendAmiId" -ForegroundColor Green
Write-Host "  Frontend AMI: $frontendAmiId" -ForegroundColor Green
Write-Host ""
Write-Host "  terraform.tfvars has been updated." -ForegroundColor Green
Write-Host ""
Write-Host "  Next step - deploy:" -ForegroundColor Yellow
Write-Host "    cd AutoScaling-FrontEnd-CPU\terraform" -ForegroundColor Yellow
Write-Host "    terraform apply -var-file=terraform.tfvars --auto-approve" -ForegroundColor Yellow
Write-Host "=================================================" -ForegroundColor Green
