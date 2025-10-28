# ECS Fargate Quick Reference

One-page cheat sheet for common operations.

## Deployment Commands

```bash
# Initial Setup
cp terraform.tfvars.example terraform.tfvars
make init
make plan
make apply

# Build and Push Images
make push-images

# Deploy Updates
make update-services
```

## Access Agents

```bash
# Get ALB DNS
terraform output alb_dns_name

# Health Checks
curl http://<ALB_DNS>/validator/health
curl http://<ALB_DNS>/karma-hello/health
curl http://<ALB_DNS>/abracadabra/health
curl http://<ALB_DNS>/skill-extractor/health
curl http://<ALB_DNS>/voice-extractor/health
```

## View Logs

```bash
# Tail logs
make logs-validator
make logs-karma-hello
make logs-abracadabra
make logs-skill-extractor
make logs-voice-extractor

# Or manually
aws logs tail /ecs/karmacadabra-prod/validator --follow
```

## Scaling

```bash
# Scale all services
make scale-up    # Scale to 2 tasks
make scale-down  # Scale to 1 task
make scale-zero  # Scale to 0 tasks (stop all)

# Scale specific service
aws ecs update-service \
  --cluster karmacadabra-prod \
  --service karmacadabra-prod-validator \
  --desired-count 2
```

## Debugging

```bash
# Get task ID
TASK_ID=$(aws ecs list-tasks \
  --cluster karmacadabra-prod \
  --service-name karmacadabra-prod-validator \
  --query 'taskArns[0]' \
  --output text | cut -d'/' -f3)

# SSH into container (ECS Exec)
aws ecs execute-command \
  --cluster karmacadabra-prod \
  --task $TASK_ID \
  --container validator \
  --interactive \
  --command '/bin/bash'

# View task details
aws ecs describe-tasks \
  --cluster karmacadabra-prod \
  --tasks $TASK_ID
```

## Update Docker Images

```bash
# Login to ECR
make ecr-login

# Build specific agent
cd /home/user/karmacadabra
docker build -f Dockerfile.agent -t karmacadabra/validator .

# Tag and push
ECR_URL=$(terraform output -json ecr_repository_urls | jq -r '.validator')
docker tag karmacadabra/validator:latest $ECR_URL:latest
docker push $ECR_URL:latest

# Force new deployment
aws ecs update-service \
  --cluster karmacadabra-prod \
  --service karmacadabra-prod-validator \
  --force-new-deployment
```

## Monitoring

```bash
# CloudWatch Dashboard
make dashboard
# or
terraform output cloudwatch_dashboard_url

# Check service health
make health-check

# View metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=karmacadabra-prod-validator Name=ClusterName,Value=karmacadabra-prod \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

## Cost Management

```bash
# View cost estimate
make cost

# Check current spend
aws ce get-cost-and-usage \
  --time-period Start=$(date -d "$(date +%Y-%m-01)" +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=SERVICE
```

## Troubleshooting

### Tasks Not Starting
```bash
# Check logs
aws logs tail /ecs/karmacadabra-prod/validator --follow

# Check task stopped reason
aws ecs describe-tasks \
  --cluster karmacadabra-prod \
  --tasks $TASK_ID \
  --query 'tasks[0].stoppedReason'
```

### Health Checks Failing
```bash
# Check target health
aws elbv2 describe-target-health \
  --target-group-arn $(terraform output -json target_group_arns | jq -r '.validator')

# Check security groups
aws ec2 describe-security-groups \
  --group-ids $(terraform output -raw ecs_tasks_security_group_id)
```

### High Costs
```bash
# Check Fargate Spot usage
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-validator \
  --query 'services[0].capacityProviderStrategy'

# Check NAT data transfer
aws cloudwatch get-metric-statistics \
  --namespace AWS/NATGateway \
  --metric-name BytesOutToSource \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

## Terraform Commands

```bash
# Show outputs
terraform output

# Show specific output
terraform output alb_dns_name

# Refresh state
terraform refresh

# Format code
terraform fmt -recursive

# Validate
terraform validate

# Show state
terraform show

# List resources
terraform state list
```

## Common Resource ARNs

```bash
# ECS Cluster
terraform output ecs_cluster_arn

# Service ARNs
terraform output -json ecs_service_arns

# Task Definition ARNs
terraform output -json ecs_task_definition_arns

# ECR Repository URLs
terraform output -json ecr_repository_urls

# Log Group Names
terraform output -json cloudwatch_log_group_names
```

## Emergency Procedures

### Stop All Agents (Cost Savings)
```bash
make scale-zero
# Or manually scale each service to 0
```

### Restore Service
```bash
make scale-up
# Or set desired count to 1
```

### Rollback Deployment
```bash
# Get previous task definition revision
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-validator \
  --query 'services[0].deployments[1].taskDefinition'

# Update service to previous revision
aws ecs update-service \
  --cluster karmacadabra-prod \
  --service karmacadabra-prod-validator \
  --task-definition karmacadabra-prod-validator:REVISION_NUMBER
```

### Destroy Everything (WARNING)
```bash
make destroy
# Confirm with 'yes'
```

## Important URLs

- AWS ECS Console: https://console.aws.amazon.com/ecs/
- CloudWatch Dashboard: `terraform output cloudwatch_dashboard_url`
- Cost Explorer: https://console.aws.amazon.com/cost-management/home

## Configuration Snippets

### Scheduled Scaling (Business Hours Only)
```bash
# Scale down at 6 PM
aws application-autoscaling put-scheduled-action \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/karmacadabra-prod/karmacadabra-prod-validator \
  --scheduled-action-name scale-down-evening \
  --schedule "cron(0 18 * * MON-FRI *)" \
  --scalable-target-action MinCapacity=0,MaxCapacity=0

# Scale up at 9 AM
aws application-autoscaling put-scheduled-action \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/karmacadabra-prod/karmacadabra-prod-validator \
  --scheduled-action-name scale-up-morning \
  --schedule "cron(0 9 * * MON-FRI *)" \
  --scalable-target-action MinCapacity=1,MaxCapacity=3
```

### Update Secrets
```bash
# Update secrets in AWS Secrets Manager
aws secretsmanager update-secret \
  --secret-id karmacadabra \
  --secret-string file://secrets.json

# Force new deployment to pick up new secrets
make update-services
```

## Performance Tuning

### Increase Task Resources
```hcl
# terraform.tfvars
task_cpu    = 512   # 0.5 vCPU (from 256)
task_memory = 1024  # 1 GB (from 512)
```

### Increase Auto-Scaling Limits
```hcl
# terraform.tfvars
autoscaling_max_capacity = 5  # From 3
autoscaling_cpu_target   = 70 # From 75 (scale sooner)
```

## Backup Procedures

### Export Terraform State
```bash
terraform state pull > terraform.tfstate.backup
```

### Export Configuration
```bash
tar -czf karmacadabra-terraform-backup.tar.gz \
  *.tf \
  terraform.tfvars \
  terraform.tfstate.backup
```

### Export Docker Images
```bash
docker save karmacadabra/validator > validator.tar
```

## Key Files

```
terraform/ecs-fargate/
├── main.tf                 # ECS cluster, services
├── vpc.tf                  # Networking
├── alb.tf                  # Load balancer
├── iam.tf                  # Permissions
├── security_groups.tf      # Firewall rules
├── cloudwatch.tf           # Observability
├── ecr.tf                  # Docker registry
├── variables.tf            # Input variables
├── outputs.tf              # Outputs
├── terraform.tfvars        # Your config (gitignored)
├── Makefile                # Common commands
├── README.md               # Full documentation
├── COST_ANALYSIS.md        # Cost breakdown
└── DEPLOYMENT_CHECKLIST.md # Deployment steps
```

## Cost Targets

| Target | Monthly Cost |
|--------|--------------|
| **Recommended** | $79-96 |
| **Business Hours Only** | $40-60 |
| **Extreme Budget** | $30-50 |
| **Development** | $20-30 |

## Support Resources

- [Full README](./README.md)
- [Cost Analysis](./COST_ANALYSIS.md)
- [Deployment Checklist](./DEPLOYMENT_CHECKLIST.md)
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [Terraform AWS Provider Docs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
