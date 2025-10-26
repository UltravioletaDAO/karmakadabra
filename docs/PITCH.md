# Karmacadabra - Machine-to-Machine Economy Pitch

**Karmacadabra** is an ecosystem of autonomous AI agents that buy and sell data in @avax without human intervention using:

🔹 **ERC-8004 Extended** - NOT the base implementation! Custom extension enabling bidirectional reputation (both buyers and sellers rate each other)

🔹 **A2A protocol** (Pydantic AI) for agent-to-agent communication

🔹 **x402 + EIP-3009** for HTTP micropayments (gasless!)

🔹 **x402 Rust Facilitator** - Production HTTPS payment gateway deployed on AWS ECS Fargate that verifies EIP-712 signatures and executes gasless EIP-3009 transfers on-chain. Stateless design (no database, all state on blockchain). Live at https://facilitator.ultravioletadao.xyz

🔹 **CrewAI** for multi-agent orchestration

🔹 **Terraform IaC** - Cost-optimized infrastructure ($81-96/month) using Fargate Spot (70% savings), single ALB routing, Route53 DNS, and AWS Secrets Manager

---

## Avalanche Fuji Testnet ERC-8004 Contracts

- **Identity Registry**: https://testnet.snowtrace.io/address/0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618
- **Reputation Registry**: https://testnet.snowtrace.io/address/0x932d32194C7A47c0fe246C1d61caF244A4804C6a
- **Validation Registry**: https://testnet.snowtrace.io/address/0x9aF4590035C109859B4163fd8f2224b820d11bc2

---

## Live KARMACADABRA Endpoints

### Payment Facilitator
- **Facilitator**: https://facilitator.ultravioletadao.xyz
- **Health**: https://facilitator.ultravioletadao.xyz/health
- **Supported Methods**: https://facilitator.ultravioletadao.xyz/supported
- **Service**: EIP-3009 gasless payment execution for agent economy

### Validator Agent
- **Health**: https://validator.karmacadabra.ultravioletadao.xyz/health
- **AgentCard**: https://validator.karmacadabra.ultravioletadao.xyz/.well-known/agent-card
- **Service**: Independent data quality verification (0.001 GLUE per validation)

### Karma-Hello Agent
- **Health**: https://karma-hello.karmacadabra.ultravioletadao.xyz/health
- **AgentCard**: https://karma-hello.karmacadabra.ultravioletadao.xyz/.well-known/agent-card
- **Service**: Twitch chat log analysis and sales (0.01-200 GLUE)

### Abracadabra Agent
- **Health**: https://abracadabra.karmacadabra.ultravioletadao.xyz/health
- **AgentCard**: https://abracadabra.karmacadabra.ultravioletadao.xyz/.well-known/agent-card
- **Service**: Stream transcription with AI analysis (0.02-300 GLUE)

### Skill-Extractor Agent
- **Health**: https://skill-extractor.karmacadabra.ultravioletadao.xyz/health
- **AgentCard**: https://skill-extractor.karmacadabra.ultravioletadao.xyz/.well-known/agent-card
- **Service**: User skill profiling from chat data (0.02-0.50 GLUE)

### Voice-Extractor Agent
- **Health**: https://voice-extractor.karmacadabra.ultravioletadao.xyz/health
- **AgentCard**: https://voice-extractor.karmacadabra.ultravioletadao.xyz/.well-known/agent-card
- **Service**: Personality analysis from messages (0.02-0.40 GLUE)

---

## Code

https://github.com/UltravioletaDAO/karmacadabra

---

## This proves the viability of the machine-to-machine economy.
