# ============================================================================
# OPENCLAW EC2 INFRASTRUCTURE - Sovereign Agent Instances
# ============================================================================
# Architecture: 1 EC2 instance per agent (t3.small, 2 vCPU, 2GB RAM)
# Phase 1: 6 system agents ($91/mo)
# Phase 2: +18 community agents ($364/mo)
#
# Each agent:
#   - Runs Docker container with OpenClaw gateway
#   - Has own EBS volume for persistent data
#   - Communicates via IRC (MeshRelay), HTTP (EM API), blockchain (x402)
#   - NO shared filesystem between agents

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "karmacadabra-terraform-state"
    key            = "openclaw/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "karmacadabra-terraform-locks"
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "karmacadabra"
      ManagedBy   = "terraform"
      Environment = "production"
      Component   = "openclaw"
    }
  }
}

# ----------------------------------------------------------------------------
# Data Sources
# ----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

# Use default VPC for simplicity (no NAT Gateway costs)
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ----------------------------------------------------------------------------
# Security Group
# ----------------------------------------------------------------------------

resource "aws_security_group" "openclaw" {
  name_prefix = "kk-openclaw-"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidrs
    description = "SSH access"
  }

  ingress {
    from_port   = 18790
    to_port     = 18790
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "OpenClaw gateway"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound"
  }

  tags = {
    Name = "kk-openclaw-agents"
  }
}

# ----------------------------------------------------------------------------
# IAM Role for EC2 (Secrets Manager + ECR + CloudWatch)
# ----------------------------------------------------------------------------

resource "aws_iam_role" "openclaw_agent" {
  name = "kk-openclaw-agent"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "openclaw_agent" {
  name = "kk-openclaw-agent-policy"
  role = aws_iam_role.openclaw_agent.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:kk/*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:CreateLogGroup"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::karmacadabra-agent-data",
          "arn:aws:s3:::karmacadabra-agent-data/*"
        ]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "openclaw_agent" {
  name = "kk-openclaw-agent"
  role = aws_iam_role.openclaw_agent.name
}

# ----------------------------------------------------------------------------
# SSH Key Pair
# ----------------------------------------------------------------------------

resource "aws_key_pair" "openclaw" {
  key_name   = "kk-openclaw"
  public_key = var.ssh_public_key
}

# ----------------------------------------------------------------------------
# EC2 Instances - One Per Agent
# ----------------------------------------------------------------------------

resource "aws_instance" "agent" {
  for_each = var.agents

  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.openclaw.key_name
  vpc_security_group_ids = [aws_security_group.openclaw.id]
  iam_instance_profile   = aws_iam_instance_profile.openclaw_agent.name
  subnet_id              = data.aws_subnets.default.ids[0]

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    agent_name   = each.key
    wallet_index = each.value.index
    ecr_repo     = var.ecr_repository
    region       = var.region
    account_id   = data.aws_caller_identity.current.account_id
  })

  tags = {
    Name  = "kk-${each.key}"
    Agent = each.key
  }
}
