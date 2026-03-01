# ============================================================================
# VARIABLES - OpenClaw EC2 Infrastructure
# ============================================================================

# ----------------------------------------------------------------------------
# General Configuration
# ----------------------------------------------------------------------------

variable "region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type for agents (t3.small = 2 vCPU, 2GB RAM)"
  type        = string
  default     = "t3.small"
}

variable "ssh_public_key" {
  description = "SSH public key for EC2 access"
  type        = string
}

variable "ssh_allowed_cidrs" {
  description = "CIDR blocks allowed SSH access (restrict in production)"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "ecr_repository" {
  description = "ECR repository URL for OpenClaw agent images"
  type        = string
}

# ----------------------------------------------------------------------------
# Agent Configuration - Phase 1: 6 System Agents
# ----------------------------------------------------------------------------

variable "agents" {
  description = "Map of agent names to their configuration"
  type = map(object({
    index          = number
    wallet_address = string
  }))
  default = {
    kk-coordinator = {
      index          = 0
      wallet_address = "0xE66C0A519F4B4Bef94FC45447FDba5bF381cDD48"
    }
    kk-karma-hello = {
      index          = 1
      wallet_address = "0xa3279F744438F83Bc75ce9f8A8282c448F97cc8A"
    }
    kk-skill-extractor = {
      index          = 2
      wallet_address = "0xE3fB9e1592b1F445d984E9FA4Db2abb3d04eacdC"
    }
    kk-voice-extractor = {
      index          = 3
      wallet_address = "0x8E503212c3c0806ADEcD2Cc24F74379A3dEDcBBC"
    }
    kk-validator = {
      index          = 4
      wallet_address = "0x7a729393D3854a6B85F84a86F62e19f74f4234F7"
    }
    kk-soul-extractor = {
      index          = 5
      wallet_address = "0x04EaEDdBA3b03B9a5aBbD2ECb024458c7b1dCEFA"
    }
    kk-juanjumagalp = {
      index          = 6
      wallet_address = "0x3aebb73a33377F0d6FC2195F83559635aDeE8408"
    }
    kk-0xjokker = {
      index          = 11
      wallet_address = "0x5975442E9608f71cEA6e9b1f3841b5A045e0500d"
    }
  }
}
