# AWS Security Groups Creation Script
# Profile: sarowar-ostad
# Region: ap-south-1
# VPC: vpc-06f7dead5c49ece64
# Key Pair: sarowar-ostad-mumbai (for EC2 instance launches)

$PROFILE = "sarowar-ostad"
$REGION = "ap-south-1"
$VPC_ID = "vpc-0a9b75a4b2b020a0e"
$KEY_PAIR = "sarowar-ostad"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Creating Security Groups for BMI App Auto-Scaling" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create Frontend ALB Security Group
Write-Host "[1/5] Creating Frontend ALB Security Group..." -ForegroundColor Yellow

# Check if it already exists
$FRONTEND_ALB_SG = aws ec2 describe-security-groups `
    --filters "Name=group-name,Values=frontend-alb-sg" "Name=vpc-id,Values=$VPC_ID" `
    --profile $PROFILE `
    --region $REGION `
    --query 'SecurityGroups[0].GroupId' `
    --output text 2>$null

if ($FRONTEND_ALB_SG -and $FRONTEND_ALB_SG -ne "None") {
    Write-Host "[EXISTS] frontend-alb-sg already exists ($FRONTEND_ALB_SG)" -ForegroundColor Yellow
    Write-Host "  Skipping creation, will use existing security group..." -ForegroundColor Yellow
} else {
    # Create new security group
    $FRONTEND_ALB_SG = aws ec2 create-security-group `
        --group-name "frontend-alb-sg" `
        --description "Security group for Frontend ALB" `
        --vpc-id $VPC_ID `
        --profile $PROFILE `
        --region $REGION `
        --query 'GroupId' `
        --output text

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Created: frontend-alb-sg ($FRONTEND_ALB_SG)" -ForegroundColor Green
    } else {
        Write-Host "[FAILED] Failed to create frontend-alb-sg" -ForegroundColor Red
        exit 1
    }
}

# Add rules only if they don't exist
$EXISTING_RULES = aws ec2 describe-security-groups `
    --group-ids $FRONTEND_ALB_SG `
    --profile $PROFILE `
    --region $REGION `
    --query 'SecurityGroups[0].IpPermissions[?FromPort==`80`]' `
    --output text 2>$null

if (-not $EXISTING_RULES) {
    
    # Add inbound rules for Frontend ALB - HTTP
    aws ec2 authorize-security-group-ingress `
        --group-id $FRONTEND_ALB_SG `
        --protocol tcp `
        --port 80 `
        --cidr 0.0.0.0/0 `
        --profile $PROFILE `
        --region $REGION 2>$null | Out-Null
    
    Write-Host "  [OK] Added HTTP (80) from 0.0.0.0/0" -ForegroundColor Green
    
    # Add HTTPS rule
    aws ec2 authorize-security-group-ingress `
        --group-id $FRONTEND_ALB_SG `
        --protocol tcp `
        --port 443 `
        --cidr 0.0.0.0/0 `
        --profile $PROFILE `
        --region $REGION 2>$null | Out-Null
    
    Write-Host "  [OK] Added HTTPS (443) from 0.0.0.0/0" -ForegroundColor Green
} else {
    Write-Host "  [EXISTS] Rules already configured" -ForegroundColor Yellow
}
Write-Host ""

# Step 2: Create Frontend EC2 Security Group
Write-Host "[2/5] Creating Frontend EC2 Security Group..." -ForegroundColor Yellow

# Check if it already exists
$FRONTEND_EC2_SG = aws ec2 describe-security-groups `
    --filters "Name=group-name,Values=frontend-ec2-sg" "Name=vpc-id,Values=$VPC_ID" `
    --profile $PROFILE `
    --region $REGION `
    --query 'SecurityGroups[0].GroupId' `
    --output text 2>$null

if ($FRONTEND_EC2_SG -and $FRONTEND_EC2_SG -ne "None") {
    Write-Host "[EXISTS] frontend-ec2-sg already exists ($FRONTEND_EC2_SG)" -ForegroundColor Yellow
    Write-Host "  Skipping creation, will use existing security group..." -ForegroundColor Yellow
} else {
    # Create new security group
    $FRONTEND_EC2_SG = aws ec2 create-security-group `
        --group-name "frontend-ec2-sg" `
        --description "Security group for Frontend EC2 instances" `
        --vpc-id $VPC_ID `
        --profile $PROFILE `
        --region $REGION `
        --query 'GroupId' `
        --output text

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Created: frontend-ec2-sg ($FRONTEND_EC2_SG)" -ForegroundColor Green
    } else {
        Write-Host "[FAILED] Failed to create frontend-ec2-sg" -ForegroundColor Red
        exit 1
    }
}

# Add rules only if they don't exist
$EXISTING_RULES = aws ec2 describe-security-groups `
    --group-ids $FRONTEND_EC2_SG `
    --profile $PROFILE `
    --region $REGION `
    --query 'SecurityGroups[0].IpPermissions[?FromPort==`80`]' `
    --output text 2>$null

if (-not $EXISTING_RULES) {
    
    # Add inbound rules for Frontend EC2 - HTTP from ALB
    aws ec2 authorize-security-group-ingress `
        --group-id $FRONTEND_EC2_SG `
        --protocol tcp `
        --port 80 `
        --source-group $FRONTEND_ALB_SG `
        --profile $PROFILE `
        --region $REGION 2>$null | Out-Null
    
    Write-Host "  [OK] Added HTTP (80) from frontend-alb-sg" -ForegroundColor Green
    
    # Add HTTPS from VPC CIDR
    aws ec2 authorize-security-group-ingress `
        --group-id $FRONTEND_EC2_SG `
        --protocol tcp `
        --port 443 `
        --cidr 10.0.0.0/16 `
        --profile $PROFILE `
        --region $REGION 2>$null | Out-Null
    
    Write-Host "  [OK] Added HTTPS (443) from 10.0.0.0/16" -ForegroundColor Green
} else {
    Write-Host "  [EXISTS] Rules already configured" -ForegroundColor Yellow
}
Write-Host ""

# Step 3: Create Backend ALB Security Group
Write-Host "[3/5] Creating Backend ALB Security Group..." -ForegroundColor Yellow

# Check if it already exists
$BACKEND_ALB_SG = aws ec2 describe-security-groups `
    --filters "Name=group-name,Values=backend-alb-sg" "Name=vpc-id,Values=$VPC_ID" `
    --profile $PROFILE `
    --region $REGION `
    --query 'SecurityGroups[0].GroupId' `
    --output text 2>$null

if ($BACKEND_ALB_SG -and $BACKEND_ALB_SG -ne "None") {
    Write-Host "[EXISTS] backend-alb-sg already exists ($BACKEND_ALB_SG)" -ForegroundColor Yellow
    Write-Host "  Skipping creation, will use existing security group..." -ForegroundColor Yellow
} else {
    # Create new security group
    $BACKEND_ALB_SG = aws ec2 create-security-group `
        --group-name "backend-alb-sg" `
        --description "Security group for Backend Internal ALB" `
        --vpc-id $VPC_ID `
        --profile $PROFILE `
        --region $REGION `
        --query 'GroupId' `
        --output text

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Created: backend-alb-sg ($BACKEND_ALB_SG)" -ForegroundColor Green
    } else {
        Write-Host "[FAILED] Failed to create backend-alb-sg" -ForegroundColor Red
        exit 1
    }
}

# Add rules only if they don't exist
$EXISTING_RULES = aws ec2 describe-security-groups `
    --group-ids $BACKEND_ALB_SG `
    --profile $PROFILE `
    --region $REGION `
    --query 'SecurityGroups[0].IpPermissions[?FromPort==`80`]' `
    --output text 2>$null

if (-not $EXISTING_RULES) {
    
    # Add inbound rules for Backend ALB from Frontend EC2
    aws ec2 authorize-security-group-ingress `
        --group-id $BACKEND_ALB_SG `
        --protocol tcp `
        --port 80 `
        --source-group $FRONTEND_EC2_SG `
        --profile $PROFILE `
        --region $REGION 2>$null | Out-Null
    
    Write-Host "  [OK] Added HTTP (80) from frontend-ec2-sg" -ForegroundColor Green
} else {
    Write-Host "  [EXISTS] Rules already configured" -ForegroundColor Yellow
}
Write-Host ""

# Step 4: Create Backend EC2 Security Group
Write-Host "[4/5] Creating Backend EC2 Security Group..." -ForegroundColor Yellow

# Check if it already exists
$BACKEND_EC2_SG = aws ec2 describe-security-groups `
    --filters "Name=group-name,Values=backend-ec2-sg" "Name=vpc-id,Values=$VPC_ID" `
    --profile $PROFILE `
    --region $REGION `
    --query 'SecurityGroups[0].GroupId' `
    --output text 2>$null

if ($BACKEND_EC2_SG -and $BACKEND_EC2_SG -ne "None") {
    Write-Host "[EXISTS] backend-ec2-sg already exists ($BACKEND_EC2_SG)" -ForegroundColor Yellow
    Write-Host "  Skipping creation, will use existing security group..." -ForegroundColor Yellow
} else {
    # Create new security group
    $BACKEND_EC2_SG = aws ec2 create-security-group `
        --group-name "backend-ec2-sg" `
        --description "Security group for Backend EC2 instances" `
        --vpc-id $VPC_ID `
        --profile $PROFILE `
        --region $REGION `
        --query 'GroupId' `
        --output text

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Created: backend-ec2-sg ($BACKEND_EC2_SG)" -ForegroundColor Green
    } else {
        Write-Host "[FAILED] Failed to create backend-ec2-sg" -ForegroundColor Red
        exit 1
    }
}

# Add rules only if they don't exist
$EXISTING_RULES = aws ec2 describe-security-groups `
    --group-ids $BACKEND_EC2_SG `
    --profile $PROFILE `
    --region $REGION `
    --query 'SecurityGroups[0].IpPermissions[?FromPort==`3000`]' `
    --output text 2>$null

if (-not $EXISTING_RULES) {
    
    # Add inbound rules for Backend EC2 from Backend ALB
    aws ec2 authorize-security-group-ingress `
        --group-id $BACKEND_EC2_SG `
        --protocol tcp `
        --port 3000 `
        --source-group $BACKEND_ALB_SG `
        --profile $PROFILE `
        --region $REGION 2>$null | Out-Null
    
    Write-Host "  [OK] Added TCP (3000) from backend-alb-sg" -ForegroundColor Green
} else {
    Write-Host "  [EXISTS] Rules already configured" -ForegroundColor Yellow
}
Write-Host ""

# Step 5: Update Aurora Security Group (if exists)
Write-Host "[5/5] Checking for Aurora Security Group..." -ForegroundColor Yellow
$AURORA_SG = aws ec2 describe-security-groups `
    --filters "Name=group-name,Values=aurora-sg" "Name=vpc-id,Values=$VPC_ID" `
    --profile $PROFILE `
    --region $REGION `
    --query 'SecurityGroups[0].GroupId' `
    --output text 2>$null

if ($AURORA_SG -and $AURORA_SG -ne "None") {
    Write-Host "[OK] Found: aurora-sg ($AURORA_SG)" -ForegroundColor Green
    
    # Get existing rules
    $EXISTING_RULES = aws ec2 describe-security-groups `
        --group-ids $AURORA_SG `
        --profile $PROFILE `
        --region $REGION `
        --query 'SecurityGroups[0].IpPermissions' `
        --output json | ConvertFrom-Json
    
    # Remove existing inbound rules if any
    if ($EXISTING_RULES.Count -gt 0) {
        Write-Host "  Removing existing inbound rules..." -ForegroundColor Yellow
        foreach ($rule in $EXISTING_RULES) {
            aws ec2 revoke-security-group-ingress `
                --group-id $AURORA_SG `
                --ip-permissions (ConvertTo-Json -Depth 10 @($rule) -Compress) `
                --profile $PROFILE `
                --region $REGION 2>$null | Out-Null
        }
        Write-Host "  [OK] Removed old rules" -ForegroundColor Green
    }
    
    # Add new rule for Backend EC2
    aws ec2 authorize-security-group-ingress `
        --group-id $AURORA_SG `
        --protocol tcp `
        --port 5432 `
        --source-group $BACKEND_EC2_SG `
        --profile $PROFILE `
        --region $REGION 2>$null | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Added PostgreSQL (5432) from backend-ec2-sg" -ForegroundColor Green
    } else {
        Write-Host "  [EXISTS] Rules may already be configured" -ForegroundColor Yellow
    }
} else {
    Write-Host "[WARN] aurora-sg not found - you will need to create it manually" -ForegroundColor Yellow
    Write-Host "  When creating Aurora cluster, create aurora-sg with this rule:" -ForegroundColor Yellow
    Write-Host "  PostgreSQL (5432) from backend-ec2-sg ($BACKEND_EC2_SG)" -ForegroundColor Cyan
}
Write-Host ""

# Summary
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "[SUCCESS] Security Groups Creation Complete!" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Created Security Groups:" -ForegroundColor White
Write-Host "  1. frontend-alb-sg    : $FRONTEND_ALB_SG" -ForegroundColor White
Write-Host "  2. frontend-ec2-sg    : $FRONTEND_EC2_SG" -ForegroundColor White
Write-Host "  3. backend-alb-sg     : $BACKEND_ALB_SG" -ForegroundColor White
Write-Host "  4. backend-ec2-sg     : $BACKEND_EC2_SG" -ForegroundColor White
if ($AURORA_SG -and $AURORA_SG -ne "None") {
    Write-Host "  5. aurora-sg (updated): $AURORA_SG" -ForegroundColor White
} else {
    Write-Host "  5. aurora-sg          : NOT FOUND (create during Aurora setup)" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  - Continue with Phase 6: Create Golden AMIs" -ForegroundColor White
Write-Host "  - Use these security group IDs in your resource creation" -ForegroundColor White
Write-Host ""
