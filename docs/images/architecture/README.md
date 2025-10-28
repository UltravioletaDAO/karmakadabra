# Architecture Diagrams (PNG)

This directory contains PNG exports of all architecture diagrams for Karmacadabra.

## Available Diagrams

### 1. High-Level Architecture
**File**: `high-level-architecture-three-layer-system.png`  
**Description**: Three-layer system showing blockchain (Layer 1), payment facilitator (Layer 2), and AI agents (Layer 3)

### 2. Data Flow - Complete Purchase Transaction
**File**: `data-flow-complete-purchase-transaction-buyer-discovers-and-purchases-from-seller.png`  
**Description**: Sequence diagram showing the complete flow from discovery to data delivery

### 3. Agent Relationships
**File**: `agent-relationships-buyerseller-pattern-ecosystem.png`  
**Description**: Buyer+Seller pattern ecosystem showing how agents interact

### 4. Economic Flow
**File**: `economic-flow-payment-and-token-circulation.png`  
**Description**: Token circulation and payment flows between agents

### 5. Security Architecture
**File**: `security-architecture-key-management-and-access-control.png`  
**Description**: AWS Secrets Manager integration and key management

### 6. Network Architecture
**File**: `network-architecture-agent-communication-and-endpoints.png`  
**Description**: Agent domains, ports, and communication endpoints

### 7. Component Stack
**File**: `component-stack-technology-stack-visualization.png`  
**Description**: Technology stack from blockchain to AI agents

### 8. Agent Discovery Flow
**File**: `agent-discovery-flow-a2a-protocol-discovery.png`  
**Description**: A2A protocol discovery sequence

### 9. System Status
**File**: `system-status-deployment-status-diagram.png`  
**Description**: Deployment status of contracts and agents

---

## Terraform/AWS Infrastructure Diagrams

### 10. ECS Fargate Complete Infrastructure
**File**: `terraform-ecs-fargate-complete-infrastructure.png`  
**Description**: Complete AWS infrastructure showing VPC, subnets, ALB, ECS cluster, Fargate tasks, ECR, Route53, CloudWatch, and Secrets Manager

### 11. Deployment Flow - Build to ECS
**File**: `terraform-deployment-flow-build-to-ecs.png`  
**Description**: Sequence diagram showing the complete deployment flow from local Docker build to running Fargate containers

### 12. ALB Routing - Path and Hostname
**File**: `terraform-alb-routing-path-and-hostname.png`  
**Description**: Application Load Balancer routing logic with path-based and hostname-based rules, target groups, and Fargate tasks

### 13. Fargate Spot Cost Optimization
**File**: `terraform-fargate-spot-cost-optimization.png`  
**Description**: Cost breakdown, Fargate Spot capacity providers, auto-scaling policies, and optimization strategies

### 14. Secrets Management in ECS
**File**: `terraform-secrets-management-ecs.png`  
**Description**: Sequence diagram showing how ECS tasks fetch secrets from AWS Secrets Manager at runtime using IAM execution roles

## Image Specifications

- **Format**: PNG
- **Width**: 2400px
- **Height**: 1600px (max)
- **Background**: White
- **Source**: Mermaid diagrams from `architecture-diagrams.md`

## Regenerating Images

To regenerate all PNG images from the Mermaid source files:

```bash
# From project root
python scripts/generate-diagrams.py

# Then convert to PNG (Windows)
scripts\convert-diagrams.bat

# Or manually convert each file
cd docs/images/architecture
npx -y @mermaid-js/mermaid-cli -i <file.mmd> -o <file.png> -w 2400 -H 1600 -b white
```

## Usage in Presentations

These high-resolution PNG files can be used in:
- Presentations (PowerPoint, Google Slides)
- Documentation (PDF exports)
- Blog posts and articles
- GitHub README (if preferred over Mermaid)
- Social media posts

## License

Same as the main project (MIT License)

