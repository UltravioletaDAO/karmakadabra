#!/bin/bash
set -e

# Configuration
PROJECT="karmacadabra"
ENV="prod"
SERVICE="test-seller-solana"
REGION="us-east-1"
AWS_ACCOUNT_ID="518898403364"
CLUSTER="${PROJECT}-${ENV}"
ECS_SERVICE="${PROJECT}-${ENV}-${SERVICE}"
ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${PROJECT}/${SERVICE}"

echo "========================================="
echo "Deploying ${SERVICE} to ECS"
echo "========================================="
echo "Project: ${PROJECT}"
echo "Environment: ${ENV}"
echo "Region: ${REGION}"
echo "Cluster: ${CLUSTER}"
echo "Service: ${ECS_SERVICE}"
echo "ECR Repo: ${ECR_REPO}"
echo "========================================="

# Step 1: Build Docker image for linux/amd64 (ECS Fargate)
echo "[1/5] Building Docker image..."
docker build --platform linux/amd64 -t ${SERVICE}:latest .

# Step 2: Login to ECR
echo "[2/5] Logging in to ECR..."
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

# Step 3: Create ECR repository if it doesn't exist
echo "[3/5] Checking ECR repository..."
aws ecr describe-repositories --repository-names ${PROJECT}/${SERVICE} --region ${REGION} 2>/dev/null || \
  aws ecr create-repository --repository-name ${PROJECT}/${SERVICE} --region ${REGION}

# Step 4: Tag and push Docker image
echo "[4/5] Pushing Docker image to ECR..."
docker tag ${SERVICE}:latest ${ECR_REPO}:latest
docker push ${ECR_REPO}:latest

# Step 5: Force new deployment of ECS service
echo "[5/5] Forcing new ECS deployment..."
aws ecs update-service \
  --cluster ${CLUSTER} \
  --service ${ECS_SERVICE} \
  --force-new-deployment \
  --region ${REGION}

echo "========================================="
echo "Deployment initiated!"
echo "Monitor status:"
echo "  aws ecs describe-services --cluster ${CLUSTER} --services ${ECS_SERVICE} --region ${REGION}"
echo "Check logs:"
echo "  aws logs tail /ecs/${PROJECT}-${ENV}-${SERVICE} --follow --region ${REGION}"
echo "========================================="
