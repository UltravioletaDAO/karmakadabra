"""
Client Agent - Orchestrator with Buyer+Seller capabilities

BUYS: Logs (0.01), Transcriptions (0.02), Skills (0.10), Personality (0.10)
SELLS: Comprehensive user insights and reports (1.00-2.00 GLUE)

This agent demonstrates the complete buyer+seller pattern using inherited
base agent capabilities.
"""

import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from shared.base_agent import ERC8004BaseAgent

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

CONFIG = {
    "agent_name": os.getenv("AGENT_NAME", "client-agent"),
    "agent_domain": os.getenv("AGENT_DOMAIN", "client.karmacadabra.ultravioletadao.xyz"),
    "private_key": os.getenv("PRIVATE_KEY") or None,
    "rpc_url": os.getenv("RPC_URL_FUJI"),
    "chain_id": int(os.getenv("CHAIN_ID", "43113")),
    "identity_registry": os.getenv("IDENTITY_REGISTRY"),
    "reputation_registry": os.getenv("REPUTATION_REGISTRY"),
    "validation_registry": os.getenv("VALIDATION_REGISTRY"),
    "glue_token": os.getenv("GLUE_TOKEN_ADDRESS"),
    "host": os.getenv("HOST", "0.0.0.0"),
    "port": int(os.getenv("PORT", "8006")),

    # Service URLs
    "karma_hello_url": os.getenv("KARMA_HELLO_URL", "http://localhost:8002"),
    "abracadabra_url": os.getenv("ABRACADABRA_URL", "http://localhost:8003"),
    "skill_extractor_url": os.getenv("SKILL_EXTRACTOR_URL", "http://localhost:8004"),
    "voice_extractor_url": os.getenv("VOICE_EXTRACTOR_URL", "http://localhost:8005"),
    "validator_url": os.getenv("VALIDATOR_URL", "http://localhost:8001"),
}


# ============================================================================
# Request/Response Models
# ============================================================================

class ComprehensiveReportRequest(BaseModel):
    """Request for comprehensive user report"""
    username: str = Field(..., description="Username to analyze")
    include_logs: bool = Field(default=True, description="Include chat logs")
    include_transcription: bool = Field(default=False, description="Include stream transcription")
    include_skills: bool = Field(default=True, description="Include skill analysis")
    include_personality: bool = Field(default=True, description="Include personality profile")
    validate: bool = Field(default=True, description="Request validation")


class ComprehensiveReportResponse(BaseModel):
    """Comprehensive user report combining multiple data sources"""
    username: str
    report_id: str
    timestamp: str

    # Data from various agents
    chat_logs: Optional[Dict] = None
    transcription: Optional[Dict] = None
    skills: Optional[Dict] = None
    personality: Optional[Dict] = None
    validation: Optional[Dict] = None

    # Synthesis
    summary: str
    key_insights: List[str]
    monetization_opportunities: List[Dict]

    # Metadata
    total_cost_glue: str
    data_sources: List[str]
    processing_time_seconds: float


# ============================================================================
# Client Agent - Orchestrator with Buyer+Seller Pattern
# ============================================================================

class ClientAgent(ERC8004BaseAgent):
    """
    Client Agent - Orchestrator that demonstrates buyer+seller pattern

    BUYER CAPABILITIES (inherited from base agent):
    - discover_agent(url)
    - buy_from_agent(url, endpoint, data, price)
    - save_purchased_data(key, data)

    SELLER CAPABILITIES (custom + inherited):
    - Sells comprehensive user reports
    - Uses create_agent_card() and create_fastapi_app()
    """

    def __init__(self, config: Dict[str, Any]):
        # Initialize base agent with ERC-8004 capabilities
        super().__init__(
            agent_name=config["agent_name"],
            agent_domain=config["agent_domain"],
            private_key=config["private_key"],
            rpc_url=config["rpc_url"],
            chain_id=config["chain_id"],
            identity_registry_address=config["identity_registry"],
            reputation_registry_address=config["reputation_registry"],
            validation_registry_address=config["validation_registry"]
        )

        self.config = config
        logger.info(f"Client agent initialized: {self.address}")

    # ========================================================================
    # BUYER CAPABILITIES - Using inherited base agent methods
    # ========================================================================

    async def buy_chat_logs(self, username: str) -> Optional[Dict]:
        """
        Buy chat logs from Karma-Hello using inherited buy_from_agent()

        Uses base_agent.buy_from_agent() - no custom implementation needed!
        """
        logger.info(f"Buying chat logs for {username}")

        data = await self.buy_from_agent(
            agent_url=self.config["karma_hello_url"],
            endpoint="/get_chat_logs",
            request_data={"users": [username], "limit": 1000},
            expected_price_glue="0.01"
        )

        if data:
            # Use inherited cache method
            self.save_purchased_data(f"karma-hello_logs_{username}", data)

        return data

    async def buy_transcription(self, stream_id: str) -> Optional[Dict]:
        """Buy stream transcription from Abracadabra"""
        logger.info(f"Buying transcription for stream {stream_id}")

        return await self.buy_from_agent(
            agent_url=self.config["abracadabra_url"],
            endpoint="/get_transcription",
            request_data={"stream_id": stream_id},
            expected_price_glue="0.02"
        )

    async def buy_skill_profile(self, username: str) -> Optional[Dict]:
        """Buy skill profile from Skill-Extractor"""
        logger.info(f"Buying skill profile for {username}")

        return await self.buy_from_agent(
            agent_url=self.config["skill_extractor_url"],
            endpoint="/get_skill_profile",
            request_data={
                "username": username,
                "profile_level": "standard",
                "include_monetization": True
            },
            expected_price_glue="0.10"
        )

    async def buy_personality_profile(self, username: str) -> Optional[Dict]:
        """Buy personality profile from Voice-Extractor"""
        logger.info(f"Buying personality profile for {username}")

        return await self.buy_from_agent(
            agent_url=self.config["voice_extractor_url"],
            endpoint="/get_voice_profile",
            request_data={
                "username": username,
                "profile_type": "standard"
            },
            expected_price_glue="0.10"
        )

    async def request_validation(
        self,
        data: Dict,
        data_type: str,
        seller_address: str,
        price: str
    ) -> Optional[Dict]:
        """Request validation from Validator"""
        logger.info(f"Requesting validation for {data_type}")

        return await self.buy_from_agent(
            agent_url=self.config["validator_url"],
            endpoint="/validate",
            request_data={
                "data_type": data_type,
                "data_content": data,
                "seller_address": seller_address,
                "buyer_address": self.address,
                "price_glue": price
            },
            expected_price_glue="0.001",
            timeout=120.0
        )

    # ========================================================================
    # SELLER CAPABILITIES - What this agent SELLS
    # ========================================================================

    async def generate_comprehensive_report(
        self,
        request: ComprehensiveReportRequest
    ) -> ComprehensiveReportResponse:
        """
        Generate comprehensive user report by orchestrating multiple purchases

        This is what the client agent SELLS - synthesized insights from
        multiple data sources.
        """
        start_time = datetime.utcnow()
        report_id = f"report_{int(start_time.timestamp())}_{request.username}"

        logger.info(f"Generating comprehensive report {report_id}")

        # Track data sources and costs
        data_sources = []
        total_cost = 0.0

        # Collect data from multiple sources
        report_data = {}

        # 1. Chat logs (if requested)
        if request.include_logs:
            logs = await self.buy_chat_logs(request.username)
            if logs:
                report_data["chat_logs"] = logs
                data_sources.append("karma-hello")
                total_cost += 0.01

        # 2. Skills (if requested)
        if request.include_skills:
            skills = await self.buy_skill_profile(request.username)
            if skills:
                report_data["skills"] = skills
                data_sources.append("skill-extractor")
                total_cost += 0.10

        # 3. Personality (if requested)
        if request.include_personality:
            personality = await self.buy_personality_profile(request.username)
            if personality:
                report_data["personality"] = personality
                data_sources.append("voice-extractor")
                total_cost += 0.10

        # 4. Validation (if requested)
        validation = None
        if request.validate and report_data:
            validation = await self.request_validation(
                data=report_data,
                data_type="comprehensive_report",
                seller_address=self.address,
                price="1.00"
            )
            if validation:
                report_data["validation"] = validation
                data_sources.append("validator")
                total_cost += 0.001

        # Synthesize insights
        summary, key_insights, opportunities = self._synthesize_insights(
            report_data, request.username
        )

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        return ComprehensiveReportResponse(
            username=request.username,
            report_id=report_id,
            timestamp=start_time.isoformat(),
            chat_logs=report_data.get("chat_logs"),
            transcription=report_data.get("transcription"),
            skills=report_data.get("skills"),
            personality=report_data.get("personality"),
            validation=validation,
            summary=summary,
            key_insights=key_insights,
            monetization_opportunities=opportunities,
            total_cost_glue=f"{total_cost:.3f}",
            data_sources=data_sources,
            processing_time_seconds=processing_time
        )

    def _synthesize_insights(
        self,
        data: Dict,
        username: str
    ) -> tuple[str, List[str], List[Dict]]:
        """Synthesize insights from collected data"""

        # Generate summary
        sources = list(data.keys())
        summary = (
            f"Comprehensive analysis of user '{username}' based on "
            f"{len(sources)} data sources: {', '.join(sources)}. "
        )

        # Extract key insights
        insights = [
            f"Data sources analyzed: {len(sources)}",
        ]

        if "skills" in data:
            skills_count = len(data["skills"].get("skills", []))
            insights.append(f"Identified {skills_count} professional skills")

        if "personality" in data:
            insights.append("Personality profile completed")

        if "chat_logs" in data:
            msg_count = data["chat_logs"].get("total_messages", 0)
            insights.append(f"Analyzed {msg_count} chat messages")

        # Generate monetization opportunities
        opportunities = []

        if "skills" in data:
            skill_opps = data["skills"].get("monetization_opportunities", [])
            opportunities.extend(skill_opps[:3])  # Top 3

        return summary, insights, opportunities


# ============================================================================
# FastAPI Application (using inherited create_fastapi_app)
# ============================================================================

# Global agent instance
client_agent: Optional[ClientAgent] = None


def create_app():
    """Create FastAPI app using inherited base agent method"""
    global client_agent

    # Initialize client agent
    client_agent = ClientAgent(CONFIG)

    # Use inherited create_fastapi_app() method!
    app = client_agent.create_fastapi_app(
        title="Client Agent - Orchestrator",
        description="Comprehensive user insights via multi-agent orchestration"
    )

    # Note: / and /health endpoints are automatically created by base agent

    # Add AgentCard endpoint
    @app.get("/.well-known/agent-card")
    async def agent_card():
        """Return A2A AgentCard using inherited method"""
        try:
            agent_id = client_agent.get_agent_id(client_agent.agent_domain)
        except:
            agent_id = 6  # Fallback ID

        # Use inherited create_agent_card() method!
        card = client_agent.create_agent_card(
            agent_id=agent_id,
            name="Client Agent - Orchestrator",
            description="Comprehensive user insights combining multiple AI agent services",
            skills=[
                {
                    "skillId": "comprehensive_report",
                    "name": "comprehensive_report",
                    "description": "Multi-source user analysis with skills, personality, and chat insights",
                    "price": {"amount": "1.00", "currency": "GLUE"},
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string"},
                            "include_logs": {"type": "boolean"},
                            "include_skills": {"type": "boolean"},
                            "include_personality": {"type": "boolean"}
                        },
                        "required": ["username"]
                    }
                }
            ]
        )
        return card

    # Add seller endpoint - this is what the agent SELLS
    @app.post("/get_comprehensive_report", response_model=ComprehensiveReportResponse)
    async def get_comprehensive_report(request: ComprehensiveReportRequest):
        """
        Generate comprehensive user report (SELLER endpoint)

        Price: 1.00 GLUE

        This endpoint orchestrates purchases from multiple agents and
        synthesizes a comprehensive user report.
        """
        if not client_agent:
            raise HTTPException(503, "Client agent not initialized")

        try:
            report = await client_agent.generate_comprehensive_report(request)

            # Return with price header
            return JSONResponse(
                content=report.model_dump(),
                headers={"X-Price": "1.00 GLUE"}
            )
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            raise HTTPException(500, f"Report generation failed: {str(e)}")

    return app


# Create the app
app = create_app()


# ============================================================================
# Demo / Testing
# ============================================================================

async def demo():
    """Demo showing buyer+seller pattern in action"""
    print("\n" + "="*70)
    print("  CLIENT AGENT - Buyer+Seller Pattern Demo")
    print("="*70 + "\n")

    agent = ClientAgent(CONFIG)
    print(f"Agent Address: {agent.address}")
    print(f"Agent Domain: {agent.agent_domain}\n")

    # Demo BUYER capabilities using inherited methods
    print("BUYER CAPABILITIES (inherited from base agent):")
    print("-" * 70)

    # Discover another agent
    print("\n1. Discovering Karma-Hello agent...")
    card = await agent.discover_agent(CONFIG["karma_hello_url"])
    if card:
        print(f"   Found: {card.get('name', 'Unknown')}")
        print(f"   Skills: {len(card.get('skills', []))}")

    # Buy data using inherited method
    print("\n2. Buying chat logs...")
    logs = await agent.buy_chat_logs("test_user")
    if logs:
        print(f"   Purchased: {logs.get('total_messages', 0)} messages")

    # Demo SELLER capabilities
    print("\n\nSELLER CAPABILITIES (custom synthesis + inherited methods):")
    print("-" * 70)

    print("\n3. Agent can SELL comprehensive reports at 1.00 GLUE")
    print("   Start the FastAPI server to test:")
    print(f"   uvicorn main:app --host {CONFIG['host']} --port {CONFIG['port']}")

    print("\n" + "="*70)
    print("Demo complete! This agent demonstrates the complete buyer+seller pattern.")
    print("="*70 + "\n")


if __name__ == "__main__":
    # Run demo if executed directly
    asyncio.run(demo())
