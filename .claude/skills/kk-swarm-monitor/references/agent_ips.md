# Agent IPs — OpenClaw EC2 Swarm

| Agent | IP | Type | HD Index |
|-------|-----|------|----------|
| kk-coordinator | 44.211.242.65 | system | 0 |
| kk-karma-hello | 13.218.119.234 | system | 1 |
| kk-skill-extractor | 100.53.60.94 | system | 2 |
| kk-voice-extractor | 100.52.188.43 | system | 3 |
| kk-validator | 44.203.23.11 | system | 4 |
| kk-soul-extractor | 3.234.249.61 | system | 5 |
| kk-juanjumagalp | 3.235.151.197 | user | 6 |

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
