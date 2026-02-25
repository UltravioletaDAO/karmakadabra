# ============================================================================
# OUTPUTS - OpenClaw EC2 Infrastructure
# ============================================================================

output "agent_public_ips" {
  description = "Public IP addresses of agent instances"
  value = {
    for k, v in aws_instance.agent : k => v.public_ip
  }
}

output "agent_instance_ids" {
  description = "EC2 instance IDs"
  value = {
    for k, v in aws_instance.agent : k => v.id
  }
}

output "agent_private_ips" {
  description = "Private IP addresses of agent instances"
  value = {
    for k, v in aws_instance.agent : k => v.private_ip
  }
}

output "security_group_id" {
  description = "Security group ID for OpenClaw agents"
  value       = aws_security_group.openclaw.id
}

output "ssh_command_examples" {
  description = "SSH commands to access each agent"
  value = {
    for k, v in aws_instance.agent : k => "ssh -i kk-openclaw.pem ec2-user@${v.public_ip}"
  }
}

output "estimated_monthly_cost" {
  description = "Estimated monthly cost"
  value = {
    per_agent = "$15.18 (t3.small on-demand)"
    phase_1   = "$91.08 (6 system agents)"
    phase_2   = "$364.32 (24 total agents)"
    notes     = "Reduce with Reserved Instances or Spot"
  }
}
