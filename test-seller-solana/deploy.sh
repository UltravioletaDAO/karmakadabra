#!/bin/bash

# Test Seller (Solana) - Deployment Script
# Builds Docker image, pushes to ECR, and triggers ECS deployment

set -e

PROJECT="karmacadabra"
ENV="prod"
SERVICE="test-seller-solana"
REGION="us-east-1"
AWS_ACCOUNT_ID="518898403364"

ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${PROJECT}-${ENV}-${SERVICE}"
CLUSTER="${PROJECT}-${ENV}"
ECS_SERVICE="${PROJECT}-${ENV}-${SERVICE}"

echo "========================================="
echo "Test Seller (Solana) Deployment"
echo "========================================="
echo "Project: $PROJECT"
echo "Environment: $ENV"
echo "Service: $SERVICE"
echo "Region: $REGION"
echo "ECR Repo: $ECR_REPO"
echo "========================================="

# Step 1: Build Docker image
echo ""
echo "[1/5] Building Docker image for linux/amd64..."
docker build --platform linux/amd64 -t ${SERVICE}:latest .

# Step 2: ECR Login
echo ""
echo "[2/5] Logging into ECR..."
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

# Step 3: Create ECR repository if it doesn't exist
echo ""
echo "[3/5] Ensuring ECR repository exists..."
aws ecr describe-repositories --repository-names ${PROJECT}-${ENV}-${SERVICE} --region ${REGION} 2>/dev/null || \
  aws ecr create-repository --repository-name ${PROJECT}-${ENV}-${SERVICE} --region ${REGION}

# Step 4: Tag and push
echo ""
echo "[4/5] Tagging and pushing to ECR..."
docker tag ${SERVICE}:latest ${ECR_REPO}:latest
docker push ${ECR_REPO}:latest

# Step 5: Force new deployment
echo ""
echo "[5/5] Triggering ECS deployment..."
aws ecs update-service \
  --cluster ${CLUSTER} \
  --service ${ECS_SERVICE} \
  --force-new-deployment \
  --region ${REGION}

echo ""
echo "========================================="
echo "Deployment initiated successfully!"
echo "========================================="
echo ""
echo "Monitor deployment:"
echo "  aws ecs describe-services --cluster ${CLUSTER} --services ${ECS_SERVICE} --region ${REGION}"
echo ""
echo "View logs:"
echo "  aws logs tail /ecs/${ECS_SERVICE} --follow --region ${REGION}"
echo ""
echo "Test endpoint:"
echo "  curl https://test-seller-solana.karmacadabra.ultravioletadao.xyz/health"
echo ""
