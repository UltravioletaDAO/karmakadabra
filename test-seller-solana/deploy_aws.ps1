# PowerShell script for deploying test-seller-solana to AWS ECS
$ErrorActionPreference = "Stop"

$PROJECT = "karmacadabra"
$ENV = "prod"
$SERVICE = "test-seller-solana"
$REGION = "us-east-1"
$AWS_ACCOUNT_ID = "518898403364"
$CLUSTER = "$PROJECT-$ENV"
$ECS_SERVICE = "$PROJECT-$ENV-$SERVICE"
$LOG_GROUP = "/ecs/$PROJECT-$ENV-$SERVICE"
$TASK_DEF_FILE = "../terraform/ecs-fargate/task-definitions/test-seller-solana.json"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Deploying $SERVICE to AWS ECS" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Project: $PROJECT"
Write-Host "Environment: $ENV"
Write-Host "Region: $REGION"
Write-Host "Cluster: $CLUSTER"
Write-Host "Service: $ECS_SERVICE"
Write-Host "=========================================" -ForegroundColor Cyan

# Step 1: Create CloudWatch Log Group
Write-Host "`n[1/7] Creating CloudWatch log group..." -ForegroundColor Yellow
try {
    aws logs create-log-group --log-group-name $LOG_GROUP --region $REGION 2>$null
    Write-Host "Log group created successfully" -ForegroundColor Green
} catch {
    Write-Host "Log group already exists (continuing)" -ForegroundColor Gray
}

# Step 2: Build Docker image
Write-Host "`n[2/7] Building Docker image..." -ForegroundColor Yellow
docker build --platform linux/amd64 -t ${SERVICE}:latest .
if ($LASTEXITCODE -ne 0) {
    throw "Docker build failed"
}

# Step 3: Login to ECR
Write-Host "`n[3/7] Logging in to ECR..." -ForegroundColor Yellow
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
if ($LASTEXITCODE -ne 0) {
    throw "ECR login failed"
}

# Step 4: Create ECR repository if it doesn't exist
Write-Host "`n[4/7] Checking ECR repository..." -ForegroundColor Yellow
$ecrCheck = aws ecr describe-repositories --repository-names "$PROJECT/$SERVICE" --region $REGION 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating ECR repository..." -ForegroundColor Gray
    aws ecr create-repository --repository-name "$PROJECT/$SERVICE" --region $REGION
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create ECR repository"
    }
}

# Step 5: Push Docker image
Write-Host "`n[5/7] Pushing Docker image to ECR..." -ForegroundColor Yellow
$ECR_REPO = "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$PROJECT/$SERVICE"
docker tag ${SERVICE}:latest ${ECR_REPO}:latest
docker push ${ECR_REPO}:latest
if ($LASTEXITCODE -ne 0) {
    throw "Docker push failed"
}

# Step 6: Register task definition
Write-Host "`n[6/7] Registering ECS task definition..." -ForegroundColor Yellow
aws ecs register-task-definition --cli-input-json file://$TASK_DEF_FILE --region $REGION
if ($LASTEXITCODE -ne 0) {
    throw "Task definition registration failed"
}

# Step 7: Create or update ECS service
Write-Host "`n[7/7] Creating/updating ECS service..." -ForegroundColor Yellow

# Check if service exists
$serviceCheck = aws ecs describe-services --cluster $CLUSTER --services $ECS_SERVICE --region $REGION 2>&1 | ConvertFrom-Json
$serviceExists = $serviceCheck.services.Count -gt 0 -and $serviceCheck.services[0].status -eq "ACTIVE"

if ($serviceExists) {
    Write-Host "Service exists, forcing new deployment..." -ForegroundColor Gray
    aws ecs update-service `
        --cluster $CLUSTER `
        --service $ECS_SERVICE `
        --force-new-deployment `
        --region $REGION
} else {
    Write-Host "Creating new service..." -ForegroundColor Gray

    # Get VPC subnets and security group (reuse from existing services)
    $describeResult = aws ecs describe-services `
        --cluster $CLUSTER `
        --services karmacadabra-prod-facilitator `
        --region $REGION | ConvertFrom-Json

    $networkConfig = $describeResult.services[0].networkConfiguration.awsvpcConfiguration
    $subnets = $networkConfig.subnets -join ','
    $securityGroups = $networkConfig.securityGroups -join ','

    aws ecs create-service `
        --cluster $CLUSTER `
        --service-name $ECS_SERVICE `
        --task-definition "$PROJECT-$ENV-$SERVICE" `
        --desired-count 1 `
        --launch-type FARGATE `
        --network-configuration "awsvpcConfiguration={subnets=[$subnets],securityGroups=[$securityGroups],assignPublicIp=ENABLED}" `
        --region $REGION
}

if ($LASTEXITCODE -ne 0) {
    throw "Service creation/update failed"
}

Write-Host "`n=========================================" -ForegroundColor Cyan
Write-Host "Deployment initiated successfully!" -ForegroundColor Green
Write-Host "=========================================`n" -ForegroundColor Cyan

Write-Host "Monitor deployment:" -ForegroundColor Yellow
Write-Host "  aws ecs describe-services --cluster $CLUSTER --services $ECS_SERVICE --region $REGION`n"

Write-Host "Check logs:" -ForegroundColor Yellow
Write-Host "  aws logs tail $LOG_GROUP --follow --region $REGION`n"

Write-Host "Service will be available at:" -ForegroundColor Yellow
Write-Host "  https://test-seller-solana.karmacadabra.ultravioletadao.xyz`n"

Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Configure ALB target group for port 8080"
Write-Host "  2. Add Route53 DNS record pointing to ALB"
Write-Host "  3. Fund seller address with SOL: Ez4frLQzDbV1AT9BNJkQFEjyTFRTsEwJ5YFaSGG8nRGB"
Write-Host "  4. Generate buyer keypair: python generate_keypair.py"
Write-Host "  5. Fund buyer with SOL + USDC for testing"
Write-Host "  6. Run load test: python load_test_solana.py --keypair buyer_keypair.json --seller Ez4frLQzDbV1AT9BNJkQFEjyTFRTsEwJ5YFaSGG8nRGB`n"
