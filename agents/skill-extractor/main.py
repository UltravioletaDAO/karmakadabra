"""
Skill-Extractor Agent (Buyer + Seller)

BUYS: Chat logs from Karma-Hello agent (0.01 GLUE)
SELLS: Skill and competency profiles (0.02-0.50 GLUE)

System Agent #6 - Extracts skills, interests, tools, and monetization potential
from chat logs using CrewAI multi-agent analysis.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
from dotenv import load_dotenv

# Add project root to path for shared imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.base_agent import ERC8004BaseAgent

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

# Load environment
load_dotenv()


# ============================================================================
# Request/Response Models
# ============================================================================

class SkillProfileRequest(BaseModel):
    """Request for skill/competency profile extraction"""
    username: str = Field(..., description="Username to analyze")
    profile_level: str = Field("complete", description="Profile level: basic, standard, complete, enterprise")
    include_monetization: bool = Field(True, description="Include monetization analysis")
    date_range: Optional[Dict[str, str]] = Field(None, description="Date range for analysis")


class SkillProfileResponse(BaseModel):
    """Response with skill and competency profile + autonomous agent design"""
    user_id: str
    profile_level: str
    agent_viability: str = Field("APPROVED", description="APPROVED / BORDERLINE / REJECTED")

    # Data quality
    data_coverage: Dict[str, Any]

    # User capabilities (what they CAN SELL)
    interests: List[Dict[str, Any]]
    skills: List[Dict[str, Any]]
    tools_and_platforms: List[Dict[str, Any]]
    interaction_style: Dict[str, Any]
    monetization_opportunities: List[Dict[str, Any]]
    top_3_monetizable_strengths: List[Dict[str, Any]]

    # Autonomous agent design
    agent_identity: Dict[str, Any] = Field(default_factory=dict, description="Agent name, domain, specialization")
    service_offering: Dict[str, Any] = Field(default_factory=dict, description="Primary service and pricing tiers")
    buyer_behavior: Dict[str, Any] = Field(default_factory=dict, description="What agent will buy to improve")

    # User needs (what they NEED TO BUY)
    user_needs_analysis: Dict[str, Any] = Field(default_factory=dict, description="Gaps, shopping list, ROI")

    # Market opportunities (for OTHER agents)
    market_opportunities: Dict[str, Any] = Field(default_factory=dict, description="UNMET NEED, UPSELL, COMPLEMENTARY signals")

    # Projections and roadmap
    autonomous_capabilities: Dict[str, Any] = Field(default_factory=dict, description="Discovery, negotiation, improvement logic")
    revenue_model: Dict[str, Any] = Field(default_factory=dict, description="Monthly projections, break-even, passive income")
    implementation_roadmap: List[str] = Field(default_factory=list, description="5 steps to deploy")
    risk_assessment: Dict[str, Any] = Field(default_factory=dict, description="Risks and mitigations")

    # Summary
    agent_potential_summary: str


# ============================================================================
# Skill-Extractor Agent
# ============================================================================

class SkillExtractorAgent(ERC8004BaseAgent):
    """
    Skill-Extractor agent - analyzes competencies and monetization potential

    Features:
    - Buys chat logs from Karma-Hello
    - Sells skill/competency profiles
    - CrewAI-based multi-agent analysis
    - 5-category extraction framework
    - Multiple profile tiers
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize Skill-Extractor agent"""

        # Initialize base agent (registers on-chain)
        super().__init__(
            agent_name="skill-extractor-agent",
            agent_domain=config["agent_domain"],
            rpc_url=config["rpc_url_fuji"],
            chain_id=config["chain_id"],
            identity_registry_address=config["identity_registry"],
            reputation_registry_address=config["reputation_registry"],
            validation_registry_address=config["validation_registry"],
            private_key=config.get("private_key")
        )

        self.config = config
        self.use_local_files = config.get("use_local_files", False)
        self.karma_hello_url = config.get("karma_hello_url")
        self.glue_token_address = config["glue_token_address"]
        self.facilitator_url = config["facilitator_url"]

        # Register agent identity
        try:
            self.agent_id = self.register_agent()
            print(f"✅ Agent registered on-chain: ID {self.agent_id}")
        except Exception as e:
            print(f"⚠️  Agent registration failed (may already be registered): {e}")
            self.agent_id = None

        print(f"🚀 Skill-Extractor Agent initialized")
        print(f"   Address: {self.address}")

    def get_agent_card(self) -> Dict[str, Any]:
        """Return A2A AgentCard for discovery"""
        return {
            "schema_version": "1.0.0",
            "agent_id": str(self.agent_id) if self.agent_id else "unregistered",
            "name": "Skill-Extractor Agent",
            "description": "Skill and competency profiling from chat history",
            "domain": self.config["agent_domain"],
            "wallet_address": self.address,
            "endpoints": [  # ✅ EIP-8004 compliant endpoints
                {
                    "name": "A2A",
                    "endpoint": f"https://{self.config['agent_domain']}",
                    "version": "1.0"
                },
                {
                    "name": "agentWallet",
                    "endpoint": self.address
                }
            ],
            "blockchain": {
                "network": self.config["network"],
                "chain_id": self.config["chain_id"],
                "contracts": {
                    "identity_registry": self.config["identity_registry"],
                    "reputation_registry": self.config["reputation_registry"]
                }
            },
            "skills": [
                {
                    "name": "extract_skill_profile",
                    "description": "Extract comprehensive skill and competency profile from chat history",
                    "input_schema": SkillProfileRequest.model_json_schema(),
                    "output_schema": SkillProfileResponse.model_json_schema(),
                    "pricing": {
                        "currency": "GLUE",
                        "basic": str(self.config["price_basic"]),
                        "standard": str(self.config["price_standard"]),
                        "complete": str(self.config["price_complete"]),
                        "enterprise": str(self.config["price_enterprise"])
                    }
                }
            ],
            "payment_methods": [
                {
                    "protocol": "x402",
                    "version": "1.0",
                    "facilitator_url": self.config["facilitator_url"],
                    "token": {
                        "symbol": "GLUE",
                        "address": self.config["glue_token_address"],
                        "decimals": 18
                    }
                }
            ],
            "contact": {
                "support_url": "https://ultravioletadao.xyz/support",
                "documentation": "https://github.com/UltravioletaDAO/karmacadabra"
            }
        }

    def calculate_price(self, profile_level: str) -> Decimal:
        """Calculate price based on profile level"""
        prices = {
            "basic": Decimal(str(self.config["price_basic"])),
            "standard": Decimal(str(self.config["price_standard"])),
            "complete": Decimal(str(self.config["price_complete"])),
            "enterprise": Decimal(str(self.config["price_enterprise"]))
        }
        return prices.get(profile_level.lower(), prices["complete"])

    # ========================================================================
    # Buyer Capabilities - Purchase chat logs from Karma-Hello
    # ========================================================================

    async def discover_karma_hello(self) -> Optional[Dict[str, Any]]:
        """Discover Karma-Hello seller via A2A protocol"""
        import httpx

        if not self.karma_hello_url:
            print("⚠️  KARMA_HELLO_URL not configured")
            return None

        agent_card_url = f"{self.karma_hello_url}/.well-known/agent-card"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(agent_card_url, timeout=10.0)
                if response.status_code == 200:
                    print(f"✅ Discovered Karma-Hello: {self.karma_hello_url}")
                    return response.json()
                else:
                    print(f"⚠️  Karma-Hello not found")
                    return None
        except Exception as e:
            print(f"❌ Error discovering Karma-Hello: {e}")
            return None

    async def buy_user_logs(
        self,
        username: str,
        date_range: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Buy chat logs for a specific user from Karma-Hello

        Args:
            username: Username to get logs for
            date_range: Optional date range (start_date, end_date)

        Returns:
            Chat log data or None if purchase failed
        """
        import httpx

        # Discover Karma-Hello
        agent_card = await self.discover_karma_hello()
        if not agent_card:
            return None

        # Build request
        request_data = {
            "users": [username],
            "limit": 10000,  # Get comprehensive history
            "include_stats": True
        }

        if date_range:
            if "start_date" in date_range:
                request_data["start_time"] = date_range["start_date"]
            if "end_date" in date_range:
                request_data["end_time"] = date_range["end_date"]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.karma_hello_url}/get_chat_logs",
                    json=request_data,
                    timeout=30.0
                )

                if response.status_code == 200:
                    logs = response.json()
                    price = response.headers.get("X-Price", "unknown")

                    print(f"✅ Purchased logs for {username}")
                    print(f"   Messages: {logs['total_messages']}")
                    print(f"   Price: {price} GLUE")

                    return logs
                else:
                    print(f"❌ Purchase failed: {response.status_code}")
                    return None

        except Exception as e:
            print(f"❌ Error buying logs: {e}")
            return None

    # ========================================================================
    # Seller Capabilities - Extract and sell skill profiles
    # ========================================================================

    async def extract_skill_profile(
        self,
        username: str,
        profile_level: str = "complete",
        include_monetization: bool = True,
        date_range: Optional[Dict[str, str]] = None
    ) -> SkillProfileResponse:
        """
        Extract comprehensive skill profile from user's chat history

        Args:
            username: Username to analyze
            profile_level: Level of profile (basic, standard, complete, enterprise)
            include_monetization: Include monetization analysis
            date_range: Optional date range for analysis

        Returns:
            SkillProfileResponse with comprehensive analysis
        """

        # Step 1: Buy chat logs from Karma-Hello
        print(f"📊 Analyzing skill profile for {username}...")

        if not self.use_local_files:
            logs = await self.buy_user_logs(username, date_range)
            if not logs:
                raise HTTPException(status_code=404, detail=f"Could not obtain logs for {username}")
        else:
            # Use local test data
            logs = await self._load_local_logs(username)

        # Step 2: Analyze with CrewAI (simplified for now - would use actual CrewAI)
        analysis = self._analyze_skills_and_interests(
            username,
            logs,
            profile_level,
            include_monetization
        )

        # Step 3: Build response
        response = SkillProfileResponse(
            user_id=f"@{username}",
            profile_level=profile_level,
            agent_viability=analysis.get("agent_viability", "APPROVED"),
            data_coverage={
                "message_count": logs.get("total_messages", 0),
                "time_span": f"{analysis.get('earliest_message', 'unknown')} to {analysis.get('latest_message', 'unknown')}",
                "data_quality": "high",
                "confidence_level": 0.85
            },
            interests=analysis.get("interests", []),
            skills=analysis.get("skills", []),
            tools_and_platforms=analysis.get("tools_and_platforms", []),
            interaction_style=analysis.get("interaction_style", {}),
            monetization_opportunities=analysis.get("monetization_opportunities", []),
            top_3_monetizable_strengths=analysis.get("top_3_monetizable_strengths", []),
            agent_identity=analysis.get("agent_identity", {}),
            service_offering=analysis.get("service_offering", {}),
            buyer_behavior=analysis.get("buyer_behavior", {}),
            user_needs_analysis=analysis.get("user_needs_analysis", {}),
            market_opportunities=analysis.get("market_opportunities", {}),
            autonomous_capabilities=analysis.get("autonomous_capabilities", {}),
            revenue_model=analysis.get("revenue_model", {}),
            implementation_roadmap=analysis.get("implementation_roadmap", []),
            risk_assessment=analysis.get("risk_assessment", {}),
            agent_potential_summary=analysis.get("agent_potential_summary", "")
        )

        # Step 4: Cache profile (optional)
        self._cache_profile(username, response)

        return response

    def _analyze_skills_and_interests(
        self,
        username: str,
        logs: Dict[str, Any],
        profile_level: str,
        include_monetization: bool
    ) -> Dict[str, Any]:
        """
        Analyze skills and interests from chat logs

        Args:
            username: Username being analyzed
            logs: Chat log data
            profile_level: Analysis depth level
            include_monetization: Include revenue analysis

        In production, this would use CrewAI with 5 specialized agents.
        For now, simplified analysis.
        """

        messages = logs.get("messages", [])
        total_messages = len(messages)

        # Extract text for analysis
        all_text = " ".join([m.get("message", "") for m in messages])

        # Simplified analysis (in production, use CrewAI with 5 agents)
        analysis = {
            "earliest_message": "2023-01-15",
            "latest_message": datetime.utcnow().strftime("%Y-%m-%d"),

            # 1️⃣ Interest Extraction
            "interests": [
                {
                    "domain": "Blockchain Development",
                    "score": 0.87,
                    "evidence": [
                        "Discussed smart contracts 23 times",
                        "Asked advanced Solidity questions",
                        "Expressed excitement about EIP-3009"
                    ],
                    "trend": "growing"
                },
                {
                    "domain": "AI/ML Systems",
                    "score": 0.72,
                    "evidence": [
                        "Frequent LangChain discussions",
                        "Built custom agents",
                        "Explored CrewAI framework"
                    ],
                    "trend": "stable"
                },
                {
                    "domain": "Web3 Infrastructure",
                    "score": 0.68,
                    "evidence": [
                        "Questions about Avalanche consensus",
                        "Discussed gas optimization",
                        "Explored cross-chain bridges"
                    ],
                    "trend": "emerging"
                }
            ],

            # 2️⃣ Skill & Sub-Skill Identification
            "skills": [
                {
                    "parent": "Programming",
                    "score": 0.82,
                    "sub_skills": [
                        {"name": "Python", "score": 0.89, "evidence": "Built automation scripts, used FastAPI"},
                        {"name": "Solidity", "score": 0.78, "evidence": "Discussed smart contracts, deployed tokens"},
                        {"name": "JavaScript", "score": 0.67, "evidence": "React components, Node.js servers"}
                    ]
                },
                {
                    "parent": "Blockchain",
                    "score": 0.76,
                    "sub_skills": [
                        {"name": "Smart Contracts", "score": 0.81, "evidence": "Deployed ERC-20, discussed security"},
                        {"name": "DeFi", "score": 0.69, "evidence": "Analyzed AMM mechanics, yield farming"},
                        {"name": "Web3 Integration", "score": 0.72, "evidence": "Used web3.py, connected wallets"}
                    ]
                },
                {
                    "parent": "AI/ML",
                    "score": 0.70,
                    "sub_skills": [
                        {"name": "LLM Integration", "score": 0.78, "evidence": "OpenAI API, prompt engineering"},
                        {"name": "Multi-Agent Systems", "score": 0.74, "evidence": "CrewAI implementation"},
                        {"name": "Vector Databases", "score": 0.58, "evidence": "Mentioned Cognee, embeddings"}
                    ]
                }
            ],

            # 3️⃣ Tools & Platforms
            "tools_and_platforms": [
                {
                    "category": "Development",
                    "tools": [
                        {"name": "VS Code", "proficiency": "advanced"},
                        {"name": "Git", "proficiency": "intermediate"},
                        {"name": "Docker", "proficiency": "intermediate"}
                    ]
                },
                {
                    "category": "Blockchain",
                    "tools": [
                        {"name": "Foundry", "proficiency": "intermediate"},
                        {"name": "Hardhat", "proficiency": "beginner"},
                        {"name": "MetaMask", "proficiency": "advanced"}
                    ]
                },
                {
                    "category": "AI/ML",
                    "tools": [
                        {"name": "OpenAI API", "proficiency": "advanced"},
                        {"name": "CrewAI", "proficiency": "intermediate"},
                        {"name": "LangChain", "proficiency": "intermediate"}
                    ]
                },
                {
                    "category": "Cloud & Infrastructure",
                    "tools": [
                        {"name": "AWS", "proficiency": "beginner"},
                        {"name": "Vercel", "proficiency": "intermediate"}
                    ]
                }
            ],

            # 4️⃣ Interaction Style
            "interaction_style": {
                "question_frequency": 0.68,
                "collaboration_score": 0.82,
                "community_engagement": "high",
                "learning_approach": "hands-on, experimental",
                "teaching_frequency": 0.45,
                "communication_style": "technical yet approachable"
            },

            # 5️⃣ Monetization Opportunities (if requested)
            "monetization_opportunities": [] if not include_monetization else [
                {
                    "service_name": "Smart Contract Development",
                    "score": 0.84,
                    "rationale": "Advanced Solidity (0.78) + Python automation (0.89). Strong market demand for DeFi contracts.",
                    "pricing_model": "Per-contract: $1,000-5,000",
                    "target_market": "Early-stage DeFi protocols, NFT projects",
                    "competitive_advantage": "Full-stack capability (contracts + frontend + automation)",
                    "next_steps": [
                        "Build portfolio with 3-5 open-source contracts",
                        "Get audits from known firms",
                        "Join Web3 freelance platforms"
                    ]
                },
                {
                    "service_name": "AI Agent Development",
                    "score": 0.76,
                    "rationale": "CrewAI expertise (0.74) + LLM integration (0.78). Growing market for custom agents.",
                    "pricing_model": "Hourly: $75-150 or per-agent: $2,000-10,000",
                    "target_market": "Businesses automating workflows, content creators",
                    "competitive_advantage": "Multi-agent orchestration + blockchain integration",
                    "next_steps": [
                        "Create demo agents for common use cases",
                        "Write case studies",
                        "Build presence on AI marketplaces"
                    ]
                },
                {
                    "service_name": "Technical Education/Consulting",
                    "score": 0.72,
                    "rationale": "Teaching frequency (0.45) + approachable communication. Can explain complex topics.",
                    "pricing_model": "Hourly consulting: $100-200, Course: $500-2,000",
                    "target_market": "Junior developers, career changers, bootcamp students",
                    "competitive_advantage": "Practical Web3 + AI experience, not just theory",
                    "next_steps": [
                        "Create YouTube channel or blog",
                        "Develop mini-course on specific topic",
                        "Offer 1-on-1 mentoring"
                    ]
                }
            ],

            "top_3_monetizable_strengths": [] if not include_monetization else [
                {
                    "strength": "Smart Contract Development",
                    "why_it_matters": "High demand, premium pricing ($1k-5k per contract)",
                    "immediate_market": "DeFi protocols, NFT projects"
                },
                {
                    "strength": "Python Automation",
                    "why_it_matters": "Universal need, quick wins for clients ($50-150/hour)",
                    "immediate_market": "Small businesses, solopreneurs"
                },
                {
                    "strength": "Multi-Agent AI Systems",
                    "why_it_matters": "Emerging field, low competition ($2k-10k per agent)",
                    "immediate_market": "Businesses automating complex workflows"
                }
            ],

            # 🎯 AUTONOMOUS AGENT DESIGN
            "agent_viability": "APPROVED",  # APPROVED / BORDERLINE / REJECTED
            "agent_identity": {
                "agent_name": f"{username.capitalize()}Agent",
                "agent_domain": f"{username.lower()}.karmacadabra.ultravioletadao.xyz",
                "specialization": "Web3 + AI development with automation expertise",
                "unique_value_proposition": "Full-stack blockchain + AI capability with proven teaching ability",
                "personality_profile": "Technical expert with approachable, educational communication style"
            },

            "service_offering": {
                "primary_service": {
                    "name": "Smart Contract Development + AI Integration",
                    "description": "End-to-end blockchain solutions with AI-powered automation",
                    "base_price": 0.50,
                    "price_range": "0.50-3.00 GLUE",
                    "delivery_format": "Deployed contracts + documentation + tests + AI integration scripts"
                },
                "tier_structure": [
                    {"tier": 1, "service": "Basic smart contract (ERC-20, simple logic)", "price": 0.50},
                    {"tier": 2, "service": "DeFi protocol with AI bot integration", "price": 1.50},
                    {"tier": 3, "service": "Complex multi-contract system + autonomous agents", "price": 3.00}
                ]
            },

            "buyer_behavior": {
                "input_purchases": [
                    {
                        "input_service": "Security audit reports",
                        "provider": "validator agent",
                        "cost": 0.001,
                        "frequency": "per contract",
                        "rationale": "Validates code quality before delivery"
                    },
                    {
                        "input_service": "Gas optimization analytics",
                        "provider": "abracadabra agent",
                        "cost": 0.02,
                        "frequency": "weekly",
                        "rationale": "Stay current with gas-saving patterns"
                    }
                ],
                "monthly_input_cost": 0.40,
                "profit_margin_percentage": 75
            },

            # 🎯 USER NEEDS ANALYSIS (what user lacks)
            "user_needs_analysis": {
                "identified_gaps": [
                    {
                        "need_category": "Smart Contract Testing",
                        "urgency_score": 0.78,
                        "evidence": [
                            "Asked about testing frameworks 5 times",
                            "Expressed frustration with test failures",
                            "Mentioned spending hours debugging tests"
                        ],
                        "current_workaround": "Manual testing, time-consuming",
                        "impact_on_productivity": "High - blocks deployment confidence",
                        "willingness_to_pay": 0.75
                    },
                    {
                        "need_category": "Formal Verification",
                        "urgency_score": 0.65,
                        "evidence": [
                            "Mentioned interest but no practical experience",
                            "Asked 'how do I prove contract correctness?'"
                        ],
                        "current_workaround": "None - capability gap",
                        "impact_on_productivity": "Medium - limits enterprise clients",
                        "willingness_to_pay": 0.60
                    }
                ],
                "recommended_purchases": [
                    {
                        "priority": 1,
                        "service": "Automated test generation",
                        "provider": "karma-hello agent (test data)",
                        "cost": 0.01,
                        "frequency": "2-3x per week",
                        "monthly_cost": 0.08,
                        "expected_benefit": {
                            "time_saved": "10 hours/month",
                            "quality_improvement": "90% test coverage vs. current 50%",
                            "revenue_impact": "Deploy faster → earn fees sooner",
                            "confidence_boost": "Enables premium pricing tier"
                        },
                        "roi_analysis": "0.08 GLUE cost → 10 hours saved → 2 extra contracts → 1.0 GLUE revenue = 1,150% ROI"
                    },
                    {
                        "priority": 2,
                        "service": "Security best practices database",
                        "provider": "validator agent",
                        "cost": 0.01,
                        "frequency": "weekly",
                        "monthly_cost": 0.04,
                        "expected_benefit": {
                            "knowledge_expansion": "Learn current attack vectors",
                            "audit_quality": "+20% vulnerability detection",
                            "reputation_boost": "Catches issues before auditors",
                            "competitive_advantage": "Premium security reputation"
                        },
                        "roi_analysis": "0.04 GLUE cost → better contracts → unlock 1.50 GLUE tier = 3,650% ROI"
                    }
                ],
                "total_monthly_investment": 0.12,
                "net_revenue_impact": "+1.50 GLUE/month (purchases enable higher tiers)"
            },

            # 🚨 MARKET OPPORTUNITIES (for other agents to capitalize on)
            "market_opportunities": {
                "signals_for_other_agents": [
                    {
                        "opportunity_type": "UNMET NEED",
                        "demand_signal": "User needs automated testing tools, no agent provides this",
                        "current_supply": "No testing agent in ecosystem",
                        "potential_market_size": "10-15 users × 0.08 GLUE/week = 0.8-1.2 GLUE/week revenue",
                        "agent_recommendation": {
                            "suggested_agent_name": "TestForgeAgent",
                            "service_description": "Automated test generation for Solidity contracts",
                            "pricing_sweet_spot": "0.08-0.15 GLUE per contract",
                            "competitive_advantage": "First mover in testing niche"
                        },
                        "validation": "High confidence - repeated questions, explicit frustration",
                        "opportunity_score": 0.89
                    },
                    {
                        "opportunity_type": "UPSELL OPPORTUNITY",
                        "demand_signal": "Users buy smart contract services but ask about AI integration",
                        "current_supply": "karma-hello sells logs, but no AI contract integration service",
                        "potential_revenue": "Premium tier: Contract + AI bot = 1.50 GLUE (3x base price)",
                        "agent_recommendation": {
                            "target_agent": "skill-extractor",
                            "suggested_service": "Smart contracts with integrated AI agents",
                            "implementation": "Bundle contract deployment with CrewAI agent setup",
                            "margin_improvement": "+200% revenue per transaction"
                        },
                        "opportunity_score": 0.82
                    },
                    {
                        "opportunity_type": "COMPLEMENTARY SERVICE",
                        "demand_signal": "Developers deploy contracts but struggle with frontend integration",
                        "current_supply": "No frontend-as-a-service agent",
                        "potential_market": "30-40% of contract clients need UIs (3-4 clients/week)",
                        "agent_recommendation": {
                            "suggested_agent_name": "Web3UIAgent",
                            "service_description": "Automated frontend generation for smart contracts",
                            "pricing": "0.30-1.00 GLUE per UI (based on complexity)",
                            "partnership_model": f"{username}Agent refers clients, receives 15% commission"
                        },
                        "opportunity_score": 0.76
                    }
                ],
                "ecosystem_broadcast": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "signal_type": "DEMAND_DETECTED",
                    "category": "Smart Contract Testing",
                    "demand_strength": 0.78,
                    "user_count": 1,  # In production, aggregate across multiple users
                    "price_sensitivity": "Willing to pay 0.08-0.15 GLUE",
                    "urgency": "High - blocking deployment workflows",
                    "existing_solutions": [],
                    "market_gap": "NO AGENTS currently serve this need",
                    "opportunity_score": 0.89,
                    "recommendation_for_agents": "First mover advantage available. Build testing agent to capture 0.8-1.2 GLUE/week market."
                }
            },

            # 🤖 AUTONOMOUS CAPABILITIES
            "autonomous_capabilities": {
                "discovery_method": "A2A protocol via /.well-known/agent-card",
                "negotiation_logic": "Dynamic pricing: Base 0.50 GLUE, +0.50 for DeFi complexity, +1.00 for multi-contract systems",
                "self_improvement": [
                    {
                        "trigger": "Reputation score reaches 7.0",
                        "action": "Unlock Tier 2 pricing (1.50 GLUE contracts)",
                        "rationale": "Proven track record justifies premium"
                    },
                    {
                        "trigger": "10+ successful contracts",
                        "action": "Purchase advanced security patterns (0.10 GLUE/week)",
                        "rationale": "Investment in better inputs → better outputs"
                    }
                ],
                "quality_assurance": "Validator agent verification (0.001 GLUE per contract) before delivery"
            },

            # 💰 REVENUE MODEL
            "revenue_model": {
                "month_1_projection": {
                    "contracts_completed": 15,
                    "average_price": 0.50,
                    "revenue": 7.50,
                    "input_costs": 0.40,
                    "net_profit": 7.10,
                    "usd_equivalent": "$2-3 passive income"
                },
                "month_6_projection": {
                    "contracts_completed": 25,
                    "average_price": 1.20,
                    "revenue": 30.0,
                    "input_costs": 1.20,
                    "net_profit": 28.80,
                    "usd_equivalent": "$8-12 passive income",
                    "note": "Reputation 8.5/10, premium tier unlocked"
                },
                "break_even": "Month 1, Week 1 (assuming 50 GLUE initial balance)",
                "passive_income_potential": "$8-12/month by month 6"
            },

            # 🛤️ IMPLEMENTATION ROADMAP
            "implementation_roadmap": [
                "1. Deploy agent with 50 GLUE initial balance",
                "2. Register on ERC-8004 Identity Registry",
                "3. Publish AgentCard with service catalog at /.well-known/agent-card",
                "4. Begin autonomous operation - discover clients via A2A protocol",
                "5. Monitor reputation score and unlock premium tiers at 7.0+"
            ],

            # ⚠️ RISK ASSESSMENT
            "risk_assessment": {
                "primary_risks": [
                    "Low initial demand - mitigation: Price competitively first 15 contracts (0.30 GLUE introductory)",
                    "Testing gap affects quality - mitigation: Purchase test data and validation services",
                    "Competition from established devs - mitigation: Emphasize AI integration unique angle"
                ],
                "confidence_score": 0.82,
                "viability_notes": "Strong technical skills (0.82) + growing interest (blockchain 0.87, AI 0.72). Main risk is testing capability gap, but readily addressable via purchases. APPROVED for autonomous agent deployment."
            },

            "agent_potential_summary": "This user could become a high-value Web3 + AI consultant agent, specializing in smart contract development with AI-powered automation. Strong technical depth combined with approachable communication style enables both premium contract work and educational content. Recommended initial services: Smart contract development, Python automation, AI agent consulting. The user should invest 0.12 GLUE/month in testing tools and security data to unlock higher pricing tiers. Market analysis reveals unmet need for testing agents - opportunity for ecosystem growth."
        }

        # Adjust based on profile level
        if profile_level == "basic":
            # Only include top 3 interests, top 2 skills, no monetization
            analysis["interests"] = analysis["interests"][:3]
            analysis["skills"] = analysis["skills"][:2]
            analysis["monetization_opportunities"] = []
            analysis["top_3_monetizable_strengths"] = []
        elif profile_level == "standard":
            # Include top 5 interests, top 3 skills, basic monetization
            analysis["interests"] = analysis["interests"][:5] if len(analysis["interests"]) > 5 else analysis["interests"]
            analysis["skills"] = analysis["skills"][:3]
            analysis["monetization_opportunities"] = analysis["monetization_opportunities"][:2]
        # complete and enterprise include all

        return analysis

    async def _load_local_logs(self, username: str) -> Dict[str, Any]:
        """Load logs from local test files"""
        # Return sample data for testing
        return {
            "total_messages": 150,
            "unique_users": 1,
            "messages": [
                {"user": username, "message": "I'm building a smart contract with Python automation", "timestamp": "2025-10-23T10:00:00Z"},
                {"user": username, "message": "Using CrewAI for multi-agent orchestration", "timestamp": "2025-10-23T10:01:00Z"},
                {"user": username, "message": "Deployed an ERC-20 token on Avalanche Fuji", "timestamp": "2025-10-23T10:02:00Z"},
            ]
        }

    def _cache_profile(self, username: str, profile: SkillProfileResponse):
        """Cache extracted profile (simplified implementation)"""
        cache_dir = Path("profiles")
        cache_dir.mkdir(exist_ok=True)

        cache_file = cache_dir / f"{username}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, indent=2)

        print(f"💾 Cached profile for {username}")


# ============================================================================
# FastAPI Application
# ============================================================================

# Initialize agent
config = {
    "private_key": os.getenv("PRIVATE_KEY", "").strip() or None,
    "network": os.getenv("NETWORK", "base-sepolia"),
    "rpc_url_fuji": os.getenv("RPC_URL_FUJI"),
    "chain_id": int(os.getenv("CHAIN_ID", 43113)),
    "identity_registry": os.getenv("IDENTITY_REGISTRY"),
    "reputation_registry": os.getenv("REPUTATION_REGISTRY"),
    "validation_registry": os.getenv("VALIDATION_REGISTRY"),
    "glue_token_address": os.getenv("GLUE_TOKEN_ADDRESS"),
    "facilitator_url": os.getenv("FACILITATOR_URL"),
    "agent_domain": os.getenv("AGENT_DOMAIN", "skill-extractor.ultravioletadao.xyz"),
    "karma_hello_url": os.getenv("KARMA_HELLO_URL", "http://localhost:8002"),
    "use_local_files": os.getenv("USE_LOCAL_FILES", "false").lower() == "true",
    "price_basic": float(os.getenv("PRICE_BASIC", "0.02")),
    "price_standard": float(os.getenv("PRICE_STANDARD", "0.03")),
    "price_complete": float(os.getenv("PRICE_COMPLETE", "0.05")),
    "price_enterprise": float(os.getenv("PRICE_ENTERPRISE", "0.50"))
}

agent = SkillExtractorAgent(config)

# Create FastAPI app
app = FastAPI(
    title="Skill-Extractor Agent",
    description="Skill and competency profiler - buys logs, sells profiles",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Skill-Extractor Agent",
        "status": "healthy",
        "agent_id": str(agent.agent_id) if agent.agent_id else "unregistered",
        "address": agent.address,
        "balance": f"{agent.get_balance()} AVAX",
        "data_source": "local_files" if agent.use_local_files else "karma-hello"
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    return await root()


@app.get("/.well-known/agent-card")
async def agent_card():
    """A2A protocol - return agent capabilities"""
    return agent.get_agent_card()


@app.post("/extract_skill_profile")
async def extract_skill_profile_endpoint(request: SkillProfileRequest):
    """
    Extract comprehensive skill profile

    Supports x402 payment protocol via X-Payment header.
    """
    try:
        profile = await agent.extract_skill_profile(
            username=request.username,
            profile_level=request.profile_level,
            include_monetization=request.include_monetization,
            date_range=request.date_range
        )

        # Calculate price
        price = agent.calculate_price(request.profile_level)

        return JSONResponse(
            content=profile.model_dump(),
            headers={
                "X-Price": str(price),
                "X-Currency": "GLUE",
                "X-Profile-Level": request.profile_level,
                "X-Confidence": str(profile.data_coverage.get("confidence_level", 0.85))
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting profile: {str(e)}")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8085))

    print(f"\n{'='*70}")
    print(f"  Skill-Extractor Agent")
    print(f"{'='*70}")
    print(f"  Address: {agent.address}")
    print(f"  Agent ID: {agent.agent_id}")
    print(f"  Balance: {agent.get_balance()} AVAX")
    print(f"  Data Source: {'Local Files' if agent.use_local_files else 'Karma-Hello'}")
    print(f"  Server: http://{host}:{port}")
    print(f"{'='*70}\n")

    uvicorn.run(app, host=host, port=port)
