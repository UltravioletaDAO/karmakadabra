# Agent IPs — OpenClaw EC2 Swarm

**IPs are DYNAMIC** — after terraform destroy/apply, IPs change.
Use `terraform output agent_public_ips` or AWS tag lookup for current IPs.

| Agent | IP (as of 2026-03-03) | Type | HD Index |
|-------|-----|------|----------|
| kk-coordinator | 35.175.131.60 | system | 0 |
| kk-karma-hello | 18.215.188.251 | system | 1 |
| kk-skill-extractor | 32.192.232.149 | system | 2 |
| kk-voice-extractor | 34.201.0.116 | system | 3 |
| kk-validator | 34.205.90.226 | system | 4 |
| kk-soul-extractor | 54.175.121.254 | system | 5 |
| kk-juanjumagalp | 44.204.220.220 | user | 6 |
| kk-0xjokker | 13.220.23.234 | user | 11 |
| kk-0xyuls | 3.238.16.22 | user | 7 |

## Dynamic IP Resolution

```bash
# Get current IPs from AWS tags (preferred method)
aws ec2 describe-instances \
  --region us-east-1 \
  --filters "Name=tag:Project,Values=karmacadabra" "Name=tag:Component,Values=openclaw" "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[].{Name: Tags[?Key==`Agent`].Value | [0], IP: PublicIpAddress}' \
  --output table

# Or from terraform
cd terraform/openclaw && terraform output agent_public_ips
```

## SSH Access

```bash
KEY="$HOME/.ssh/kk-openclaw.pem"
ssh -o StrictHostKeyChecking=no -i "$KEY" ec2-user@<IP>
```

## AWS

- Region: us-east-1
- Instance type: t3.small (2 vCPU, 2GB RAM)
- AMI: Amazon Linux 2023
- SSH key pair: kk-openclaw
- S3 bucket: karmacadabra-agent-data
- ECR: 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent

## Data Volumes

Each agent has a persistent EBS volume mounted at `/data/<agent-name>/` inside the container as `/app/data`.
