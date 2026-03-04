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
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
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

# Deep Learning Base AMI (AL2023 + NVIDIA drivers pre-installed)
data "aws_ami" "deep_learning" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Deep Learning Base OSS Nvidia Driver GPU AMI (Amazon Linux 2023)*"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
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

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    self        = true
    description = "vLLM inference API (internal, agents only)"
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
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::karmacadabra-agent-data",
          "arn:aws:s3:::karmacadabra-agent-data/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["ec2:DescribeInstances"]
        Resource = "*"
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
    volume_size = 50
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    agent_name     = each.key
    wallet_index   = each.value.index
    wallet_address = each.value.wallet_address
    ecr_repo       = var.ecr_repository
    region         = var.region
    account_id     = data.aws_caller_identity.current.account_id
    llm_provider   = var.llm_provider
    vllm_api_key   = random_password.vllm_api_key.result
  })

  tags = {
    Name  = "kk-${each.key}"
    Agent = each.key
  }
}

# ----------------------------------------------------------------------------
# vLLM API Key (shared between inference server and agents)
# ----------------------------------------------------------------------------

resource "random_password" "vllm_api_key" {
  length  = 32
  special = false
}

# ----------------------------------------------------------------------------
# IAM Role for Spot Fleet (required to manage EC2 instances)
# ----------------------------------------------------------------------------

resource "aws_iam_role" "spot_fleet" {
  count = var.enable_inference ? 1 : 0
  name  = "kk-openclaw-spot-fleet"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "spotfleet.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "spot_fleet" {
  count      = var.enable_inference ? 1 : 0
  role       = aws_iam_role.spot_fleet[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole"
}

# ----------------------------------------------------------------------------
# GPU Inference Server - vLLM + Qwen3-8B (Spot Fleet, Multi-Type)
# ----------------------------------------------------------------------------

resource "aws_launch_template" "inference" {
  count         = var.enable_inference ? 1 : 0
  name_prefix   = "kk-inference-"
  image_id      = data.aws_ami.deep_learning.id
  key_name      = aws_key_pair.openclaw.key_name

  vpc_security_group_ids = [aws_security_group.openclaw.id]

  iam_instance_profile {
    name = aws_iam_instance_profile.openclaw_agent.name
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = 100
      volume_type = "gp3"
    }
  }

  user_data = base64encode(templatefile("${path.module}/inference_user_data.sh.tpl", {
    vllm_model   = var.vllm_model
    vllm_api_key = random_password.vllm_api_key.result
  }))

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name      = "kk-inference-gpu"
      Component = "inference"
      Project   = "karmacadabra"
    }
  }
}

resource "aws_spot_fleet_request" "inference" {
  count                               = var.enable_inference ? 1 : 0
  iam_fleet_role                      = aws_iam_role.spot_fleet[0].arn
  target_capacity                     = 1
  allocation_strategy                 = "capacityOptimized"
  terminate_instances_with_expiration = true
  replace_unhealthy_instances         = true
  fleet_type                          = "maintain"

  dynamic "launch_template_config" {
    for_each = var.inference_instance_types
    content {
      launch_template_specification {
        id      = aws_launch_template.inference[0].id
        version = aws_launch_template.inference[0].latest_version
      }
      overrides {
        instance_type = launch_template_config.value
      }
    }
  }

  tags = {
    Name = "kk-inference-fleet"
  }
}
