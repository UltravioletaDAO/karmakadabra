# 🏗️ Architecture Diagrams

> Visual representations of the Karmacadabra trustless agent economy

**Deployed on**: Avalanche Fuji Testnet  
**Last Updated**: October 2025

📸 **PNG Exports**: All diagrams are available as high-resolution PNG images in [`docs/images/architecture/`](./docs/images/architecture/)

---

## 📊 High-Level Architecture

### Three-Layer System

```mermaid
graph TB
    subgraph "Layer 1: Blockchain (Avalanche Fuji)"
        GLUE[GLUE Token<br/>EIP-3009<br/>Gasless Transfers]
        ERC[ERC-8004 Extended<br/>Bidirectional Reputation]
        
        subgraph "ERC-8004 Registries"
            ID[Identity Registry<br/>Agent Registration]
            REP[Reputation Registry<br/>Ratings Storage]
            VAL[Validation Registry<br/>Quality Scores]
        end
    end
    
    subgraph "Layer 2: Payment Facilitator"
        FAC[x402 Facilitator<br/>Rust Axum<br/>Stateless Verifier]
    end
    
    subgraph "Layer 3: AI Agents (Python)"
        VAL_AGENT[Validator Agent<br/>Port 8001<br/>CrewAI Validation]
        KARMA[Karma-Hello Agent<br/>Port 8002<br/>Chat Logs Seller]
        ABRA[Abracadabra Agent<br/>Port 8003<br/>Transcripts Seller]
        CLIENT[Client Agent<br/>Orchestrator<br/>Comprehensive Reports]
        VOICE[Voice-Extractor<br/>Port 8005<br/>Personality Profiles]
        SKILL[Skill-Extractor<br/>Port 8085<br/>Skill Profiles]
    end
    
    FAC -->|POST /verify| GLUE
    FAC -->|POST /settle| GLUE
    VAL_AGENT -->|validationResponse| VAL
    VAL_AGENT -->|Pays Gas| GLUE
    
    KARMA -.->|Buy 0.01 GLUE| ABRA
    ABRA -.->|Buy 0.01 GLUE| KARMA
    CLIENT -.->|Buy 0.211 GLUE| KARMA
    CLIENT -.->|Buy 0.211 GLUE| ABRA
    CLIENT -.->|Buy 0.211 GLUE| SKILL
    CLIENT -.->|Buy 0.211 GLUE| VOICE
    CLIENT -.->|Buy 0.001 GLUE| VAL_AGENT
    
    VAL_AGENT -.->|Validate| KARMA
    VAL_AGENT -.->|Validate| ABRA
    
    style GLUE fill:#e1f5ff
    style ERC fill:#ffe1f5
    style FAC fill:#fff5e1
    style VAL_AGENT fill:#e1ffe1
    style KARMA fill:#f5e1ff
    style ABRA fill:#f5e1ff
    style CLIENT fill:#ffe1e1
```

---

## 🔄 Data Flow: Complete Purchase Transaction

### Buyer Discovers and Purchases from Seller

```mermaid
sequenceDiagram
    participant Buyer as Buyer Agent<br/>(e.g., Karma-Hello)
    participant Seller as Seller Agent<br/>(e.g., Abracadabra)
    participant Facilitator as x402 Facilitator<br/>(Rust)
    participant Validator as Validator Agent<br/>(CrewAI)
    participant Blockchain as Avalanche Fuji<br/>(ERC-8004 + GLUE)
    
    Note over Buyer,Seller: Phase 1: Discovery
    Buyer->>Seller: GET /.well-known/agent-card
    Seller-->>Buyer: AgentCard<br/>{skills, price, paymentMethods}
    
    Note over Buyer: Phase 2: Payment Signing (Off-chain)
    Buyer->>Buyer: Sign EIP-712 message<br/>{from, to, value, nonce}
    
    Note over Buyer,Seller: Phase 3: Purchase Request
    Buyer->>Seller: POST /api/resource<br/>X-Payment: {signature}
    
    Seller->>Facilitator: POST /verify<br/>{signature, balance}
    Facilitator->>Blockchain: Verify signature<br/>Check balance
    Blockchain-->>Facilitator: {valid: true}
    Facilitator-->>Seller: {valid: true}
    
    Note over Seller,Validator: Phase 4: Validation (Optional)
    Seller->>Validator: POST /validate<br/>{data_hash}
    Validator->>Validator: CrewAI Analysis<br/>(Quality + Fraud + Price)
    Validator->>Blockchain: validationResponse()<br/>{score: 95/100}
    Blockchain-->>Validator: Transaction receipt
    Validator-->>Seller: {score: 95}
    
    Note over Seller,Blockchain: Phase 5: Settlement
    Seller->>Facilitator: POST /settle<br/>{signature}
    Facilitator->>Blockchain: transferWithAuthorization()<br/>{from, to, value}
    Blockchain-->>Facilitator: Transaction receipt
    Facilitator-->>Seller: {txHash: "0x..."}
    
    Note over Seller,Buyer: Phase 6: Data Delivery
    Seller->>Seller: Query Database<br/>Process with CrewAI
    Seller-->>Buyer: 200 OK<br/>{data: {...}}
    
    Note over Buyer: Phase 7: Integration
    Buyer->>Buyer: Store data<br/>Update knowledge base
```

**Total Duration**: ~3-4 seconds (gasless for agents)

---

## 🎯 Agent Relationships

### Buyer+Seller Pattern Ecosystem

```mermaid
graph LR
    subgraph "Data Sources"
        TWITCH[Twitch Streams<br/>Chat + Audio]
    end
    
    subgraph "Base Layer"
        KARMA[Karma-Hello<br/>Sells: Chat Logs<br/>Buys: Transcripts<br/>0.01 GLUE]
        ABRA[Abracadabra<br/>Sells: Transcripts<br/>Buys: Chat Logs<br/>0.02 GLUE]
    end
    
    subgraph "Analysis Layer"
        SKILL[Skill-Extractor<br/>Sells: Skill Profiles<br/>Buys: Chat Logs<br/>0.10 GLUE]
        VOICE[Voice-Extractor<br/>Sells: Personality<br/>Buys: Chat Logs<br/>0.10 GLUE]
    end
    
    subgraph "Orchestration Layer"
        CLIENT[Client Agent<br/>Sells: Full Reports<br/>Buys: All Data<br/>1.00 GLUE]
    end
    
    subgraph "Validation Layer"
        VAL[Validator<br/>Validates All<br/>0.001 GLUE]
    end
    
    TWITCH --> KARMA
    TWITCH --> ABRA
    
    KARMA <--> ABRA
    KARMA --> SKILL
    KARMA --> VOICE
    KARMA --> CLIENT
    ABRA --> CLIENT
    
    SKILL --> CLIENT
    VOICE --> CLIENT
    
    CLIENT --> VAL
    SKILL -.-> VAL
    VOICE -.-> VAL
    KARMA -.-> VAL
    ABRA -.-> VAL
    
    style KARMA fill:#e1f5ff
    style ABRA fill:#e1f5ff
    style SKILL fill:#ffe1f5
    style VOICE fill:#ffe1f5
    style CLIENT fill:#fff5e1
    style VAL fill:#e1ffe1
```

---

## 💰 Economic Flow

### Payment and Token Circulation

```mermaid
graph TB
    subgraph "Token Holders"
        CLIENT_WALLET[Client Agent<br/>220,000 GLUE]
        AGENT_WALLETS[Service Agents<br/>55,000 GLUE each]
    end
    
    subgraph "Purchase Flows"
        CLIENT_BUYS[Client Agent<br/>Buys Data<br/>Cost: 0.211 GLUE]
        AGENT_BUYS[Agents Buy<br/>from Each Other<br/>Cost: varies]
    end
    
    subgraph "Revenue Flows"
        CLIENT_SELLS[Client Agent<br/>Sells Reports<br/>Price: 1.00 GLUE]
        AGENT_SELLS[Agents Sell<br/>Products<br/>Price: varies]
    end
    
    subgraph "Blockchain"
        GLUE_CONTRACT[GLUE Token<br/>24M Supply]
        REPUTATION[Reputation Registry<br/>Rating Storage]
    end
    
    CLIENT_WALLET --> CLIENT_BUYS
    AGENT_WALLETS --> AGENT_BUYS
    
    CLIENT_BUYS --> AGENT_SELLS
    AGENT_BUYS --> AGENT_SELLS
    
    CLIENT_SELLS --> GLUE_CONTRACT
    AGENT_SELLS --> GLUE_CONTRACT
    
    CLIENT_BUYS -.->|Rate Buyer| REPUTATION
    AGENT_BUYS -.->|Rate Buyer| REPUTATION
    CLIENT_SELLS -.->|Rate Seller| REPUTATION
    AGENT_SELLS -.->|Rate Seller| REPUTATION
    
    style CLIENT_WALLET fill:#ffe1e1
    style AGENT_WALLETS fill:#e1f5ff
    style GLUE_CONTRACT fill:#fff5e1
    style REPUTATION fill:#e1ffe1
```

---

## 🔐 Security Architecture

### Key Management and Access Control

```mermaid
graph TB
    subgraph "Environment"
        LOCAL[Local .env Files<br/>PRIVATE_KEY= empty]
    end
    
    subgraph "AWS Secrets Manager"
        AWS_SECRETS[AWS Secret: karmacadabra<br/>JSON with all agent keys]
    end
    
    subgraph "Agents"
        VAL_KEY[Validator Agent<br/>Loads from AWS]
        KARMA_KEY[Karma-Hello Agent<br/>Loads from AWS]
        ABRA_KEY[Abracadabra Agent<br/>Loads from AWS]
        CLIENT_KEY[Client Agent<br/>Loads from AWS]
        VOICE_KEY[Voice-Extractor<br/>Loads from AWS]
        SKILL_KEY[Skill-Extractor<br/>Loads from AWS]
    end
    
    subgraph "Blockchain"
        REGISTRY[Identity Registry<br/>Agent Domains]
        WALLETS[Agent Wallets<br/>On-chain Addresses]
    end
    
    AWS_SECRETS --> VAL_KEY
    AWS_SECRETS --> KARMA_KEY
    AWS_SECRETS --> ABRA_KEY
    AWS_SECRETS --> CLIENT_KEY
    AWS_SECRETS --> VOICE_KEY
    AWS_SECRETS --> SKILL_KEY
    
    VAL_KEY --> REGISTRY
    KARMA_KEY --> REGISTRY
    ABRA_KEY --> REGISTRY
    CLIENT_KEY --> REGISTRY
    VOICE_KEY --> REGISTRY
    SKILL_KEY --> REGISTRY
    
    REGISTRY --> WALLETS
    
    style AWS_SECRETS fill:#ffe1e1
    style REGISTRY fill:#e1ffe1
    style WALLETS fill:#e1f5ff
```

---

## 🌐 Network Architecture

### Agent Communication and Endpoints

```mermaid
graph TB
    subgraph "Public Internet"
        DOMAINS[Agent Domains<br/>*.karmacadabra.ultravioletadao.xyz]
    end
    
    subgraph "Agent Services"
        VAL_SVC[Validator Service<br/>Port 8001<br/>FastAPI]
        KARMA_SVC[Karma-Hello Service<br/>Port 8002<br/>FastAPI]
        ABRA_SVC[Abracadabra Service<br/>Port 8003<br/>FastAPI]
        VOICE_SVC[Voice-Extractor<br/>Port 8005<br/>FastAPI]
        SKILL_SVC[Skill-Extractor<br/>Port 8085<br/>FastAPI]
    end
    
    subgraph "Payment Facilitator"
        FACILITATOR[facilitator.ultravioletadao.xyz<br/>Port 8080<br/>Rust Axum]
    end
    
    subgraph "Avalanche Fuji"
        BLOCKCHAIN[Smart Contracts<br/>RPC: avalanche-fuji-c-chain-rpc.publicnode.com]
    end
    
    DOMAINS --> VAL_SVC
    DOMAINS --> KARMA_SVC
    DOMAINS --> ABRA_SVC
    DOMAINS --> VOICE_SVC
    DOMAINS --> SKILL_SVC
    
    VAL_SVC --> FACILITATOR
    KARMA_SVC --> FACILITATOR
    ABRA_SVC --> FACILITATOR
    VOICE_SVC --> FACILITATOR
    SKILL_SVC --> FACILITATOR
    
    FACILITATOR --> BLOCKCHAIN
    VAL_SVC --> BLOCKCHAIN
    
    style DOMAINS fill:#ffe1e1
    style FACILITATOR fill:#fff5e1
    style BLOCKCHAIN fill:#e1f5ff
```

---

## 📦 Component Stack

### Technology Stack Visualization

```mermaid
graph LR
    subgraph "Blockchain"
        AVAX[Avalanche Fuji<br/>EVM Compatible]
        SOLIDITY[Solidity 0.8.20+<br/>Smart Contracts]
        FOUNDRY[Foundry<br/>Build Tool]
    end
    
    subgraph "Facilitator"
        RUST[Rust<br/>Language]
        AXUM[Axum<br/>HTTP Framework]
        ETHERS[ethers-rs<br/>Web3 Client]
    end
    
    subgraph "Agents"
        PYTHON[Python 3.11+<br/>Runtime]
        FASTAPI[FastAPI<br/>API Framework]
        CREWAI[CrewAI<br/>Multi-Agent]
        GPT4[GPT-4o<br/>LLM]
        WEB3PY[web3.py<br/>Blockchain Client]
    end
    
    subgraph "Data"
        MONGO[MongoDB<br/>Chat Logs]
        SQLITE[SQLite<br/>Transcripts]
        COGNEE[Cognee<br/>Knowledge Graph]
    end
    
    AVAX --> SOLIDITY
    SOLIDITY --> FOUNDRY
    
    RUST --> AXUM
    AXUM --> ETHERS
    
    PYTHON --> FASTAPI
    PYTHON --> CREWAI
    CREWAI --> GPT4
    PYTHON --> WEB3PY
    
    FASTAPI --> MONGO
    FASTAPI --> SQLITE
    FASTAPI --> COGNEE
    
    ETHERS --> AVAX
    WEB3PY --> AVAX
    
    style AVAX fill:#e84142
    style RUST fill:#ff9800
    style PYTHON fill:#3776ab
    style GPT4 fill:#10a37f
```

---

## 🔍 Agent Discovery Flow

### A2A Protocol Discovery

```mermaid
sequenceDiagram
    participant Buyer as Buyer Agent
    participant DNS as DNS Server
    participant Seller as Seller Agent
    participant Registry as Identity Registry
    
    Note over Buyer: Buyer wants to purchase data
    
    Buyer->>DNS: Resolve<br/>karma-hello.karmacadabra.ultravioletadao.xyz
    DNS-->>Buyer: IP Address
    
    Buyer->>Seller: GET /.well-known/agent-card
    Seller->>Registry: Query agent_id<br/>by domain
    Registry-->>Seller: agent_id: 2
    Seller-->>Buyer: AgentCard<br/>{agentId, skills, price}
    
    Note over Buyer: Parse AgentCard
    
    Buyer->>Buyer: Extract:<br/>- Skill name<br/>- Price (0.01 GLUE)<br/>- Payment method (x402-eip3009)
    
    Note over Buyer: Buyer signs payment
    
    Buyer->>Buyer: Sign EIP-712<br/>transferWithAuthorization
    
    Buyer->>Seller: POST /api/<skill><br/>X-Payment: {signature}
    
    Seller-->>Buyer: 200 OK<br/>{data}
```

---

## 📊 System Status

### Deployment Status Diagram

```mermaid
graph TB
    subgraph "✅ Deployed Contracts"
        GLUE_DEPLOYED[GLUE Token<br/>0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743<br/>VERIFIED]
        ID_DEPLOYED[Identity Registry<br/>0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618<br/>VERIFIED]
        REP_DEPLOYED[Reputation Registry<br/>0x932d32194C7A47c0fe246C1d61caF244A4804C6a<br/>VERIFIED]
        VAL_DEPLOYED[Validation Registry<br/>0x9aF4590035C109859B4163fd8f2224b820d11bc2<br/>VERIFIED]
        TXLOG_DEPLOYED[Transaction Logger<br/>0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654<br/>VERIFIED]
    end
    
    subgraph "✅ Funded Agents"
        VAL_FUNDED[Validator Agent<br/>55,000 GLUE<br/>0x1219eF9484BF7E40E6479141B32634623d37d507]
        KARMA_FUNDED[Karma-Hello<br/>55,000 GLUE<br/>0x2C3e071df446B25B821F59425152838ae4931E75]
        ABRA_FUNDED[Abracadabra<br/>55,000 GLUE<br/>0x940DDDf6fB28E611b132FbBedbc4854CC7C22648]
        CLIENT_FUNDED[Client Agent<br/>220,000 GLUE<br/>0xCf30021812F27132d36dc791E0eC17f34B4eE8BA]
        VOICE_FUNDED[Voice-Extractor<br/>110,000 GLUE<br/>0xDd63D5840090B98D9EB86f2c31974f9d6c270b17]
        SKILL_FUNDED[Skill-Extractor<br/>55,000 GLUE<br/>0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9]
    end
    
    subgraph "✅ Complete Agents"
        VAL_COMPLETE[Validator Agent<br/>CrewAI Validation<br/>On-chain Scores]
        KARMA_COMPLETE[Karma-Hello<br/>Buyer + Seller<br/>MongoDB Integration]
        ABRA_COMPLETE[Abracadabra<br/>Buyer + Seller<br/>SQLite Integration]
        CLIENT_COMPLETE[Client Agent<br/>Orchestrator<br/>Multi-agent Flow]
        VOICE_COMPLETE[Voice-Extractor<br/>Personality Analysis<br/>8 Categories]
        SKILL_COMPLETE[Skill-Extractor<br/>Skill Profiling<br/>5 Categories]
    end
    
    GLUE_DEPLOYED --> VAL_FUNDED
    GLUE_DEPLOYED --> KARMA_FUNDED
    GLUE_DEPLOYED --> ABRA_FUNDED
    GLUE_DEPLOYED --> CLIENT_FUNDED
    GLUE_DEPLOYED --> VOICE_FUNDED
    GLUE_DEPLOYED --> SKILL_FUNDED
    
    VAL_FUNDED --> VAL_COMPLETE
    KARMA_FUNDED --> KARMA_COMPLETE
    ABRA_FUNDED --> ABRA_COMPLETE
    CLIENT_FUNDED --> CLIENT_COMPLETE
    VOICE_FUNDED --> VOICE_COMPLETE
    SKILL_FUNDED --> SKILL_COMPLETE
    
    ID_DEPLOYED --> VAL_COMPLETE
    ID_DEPLOYED --> KARMA_COMPLETE
    ID_DEPLOYED --> ABRA_COMPLETE
    ID_DEPLOYED --> CLIENT_COMPLETE
    ID_DEPLOYED --> VOICE_COMPLETE
    ID_DEPLOYED --> SKILL_COMPLETE
    
    style GLUE_DEPLOYED fill:#e1ffe1
    style ID_DEPLOYED fill:#e1ffe1
    style REP_DEPLOYED fill:#e1ffe1
    style VAL_DEPLOYED fill:#e1ffe1
    style TXLOG_DEPLOYED fill:#e1ffe1
    style VAL_COMPLETE fill:#fff5e1
    style KARMA_COMPLETE fill:#fff5e1
    style ABRA_COMPLETE fill:#fff5e1
    style CLIENT_COMPLETE fill:#fff5e1
    style VOICE_COMPLETE fill:#fff5e1
    style SKILL_COMPLETE fill:#fff5e1
```

---

## 📝 Notes

- All agents follow the **Buyer+Seller pattern** - they both buy inputs and sell outputs
- Payments are **gasless** for agents using EIP-3009 meta-transactions
- Validator pays gas fees (~0.01 AVAX) for on-chain validation scores
- All agent wallets funded with GLUE tokens from ERC-20 deployer wallet
- Domain convention: `<agent-name>.karmacadabra.ultravioletadao.xyz`
- AWS Secrets Manager stores all private keys (no keys in .env files)

---

**See Also**:
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Detailed technical documentation
- [README.md](../README.md) - Project overview and quick start
- [MASTER_PLAN.md](../MASTER_PLAN.md) - Complete vision and roadmap

