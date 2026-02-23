"""
Voice-Extractor Agent (Buyer + Seller)

BUYS: Chat logs from Karma-Hello agent (0.01 GLUE)
SELLS: Linguistic personality profiles (0.02-0.40 GLUE)

System Agent #5 - Extracts communication patterns and linguistic style
from chat logs using CrewAI psycholinguistic analysis.
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

class VoiceProfileRequest(BaseModel):
    """Request for voice/personality profile extraction"""
    username: str = Field(..., description="Username to analyze")
    profile_type: str = Field("complete", description="Profile type: basic, standard, complete, enterprise")
    date_range: Optional[Dict[str, str]] = Field(None, description="Date range for analysis")


class VoiceProfileResponse(BaseModel):
    """Response with linguistic personality profile"""
    username: str
    profile_type: str
    analysis: Dict[str, Any]
    confidence_score: float
    metadata: Dict[str, Any]


# ============================================================================
# Voice-Extractor Agent
# ============================================================================

class VoiceExtractorAgent(ERC8004BaseAgent):
    """
    Voice-Extractor agent - analyzes linguistic style and personality

    Features:
    - Buys chat logs from Karma-Hello
    - Sells linguistic/personality profiles
    - CrewAI-based psycholinguistic analysis
    - 8-category extraction framework
    - Multiple profile tiers
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize Voice-Extractor agent"""

        # Initialize base agent (registers on-chain)
        super().__init__(
            agent_name="voice-extractor-agent",
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
            print(f" Agent registered on-chain: ID {self.agent_id}")
        except Exception as e:
            print(f"�  Agent registration failed (may already be registered): {e}")
            self.agent_id = None

        print(f"> Voice-Extractor Agent initialized")
        print(f"   Address: {self.address}")

    def get_agent_card(self) -> Dict[str, Any]:
        """Return A2A AgentCard for discovery"""
        return {
            "schema_version": "1.0.0",
            "agent_id": str(self.agent_id) if self.agent_id else "unregistered",
            "name": "Voice-Extractor Agent",
            "description": "Linguistic style and personality extraction from chat logs",
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
                    "name": "extract_voice_profile",
                    "description": "Extract linguistic personality profile from chat history",
                    "input_schema": VoiceProfileRequest.model_json_schema(),
                    "output_schema": VoiceProfileResponse.model_json_schema(),
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

    def calculate_price(self, profile_type: str) -> Decimal:
        """Calculate price based on profile type"""
        prices = {
            "basic": Decimal(str(self.config["price_basic"])),
            "standard": Decimal(str(self.config["price_standard"])),
            "complete": Decimal(str(self.config["price_complete"])),
            "enterprise": Decimal(str(self.config["price_enterprise"]))
        }
        return prices.get(profile_type.lower(), prices["complete"])

    # ========================================================================
    # Buyer Capabilities - Purchase chat logs from Karma-Hello
    # ========================================================================

    async def discover_karma_hello(self) -> Optional[Dict[str, Any]]:
        """Discover Karma-Hello seller via A2A protocol"""
        import httpx

        if not self.karma_hello_url:
            print("�  KARMA_HELLO_URL not configured")
            return None

        agent_card_url = f"{self.karma_hello_url}/.well-known/agent-card"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(agent_card_url, timeout=10.0)
                if response.status_code == 200:
                    print(f" Discovered Karma-Hello: {self.karma_hello_url}")
                    return response.json()
                else:
                    print(f"�  Karma-Hello not found")
                    return None
        except Exception as e:
            print(f"L Error discovering Karma-Hello: {e}")
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

                    print(f" Purchased logs for {username}")
                    print(f"   Messages: {logs['total_messages']}")
                    print(f"   Price: {price} GLUE")

                    return logs
                else:
                    print(f"L Purchase failed: {response.status_code}")
                    return None

        except Exception as e:
            print(f"L Error buying logs: {e}")
            return None

    # ========================================================================
    # Seller Capabilities - Extract and sell personality profiles
    # ========================================================================

    async def extract_voice_profile(
        self,
        username: str,
        profile_type: str = "complete",
        date_range: Optional[Dict[str, str]] = None
    ) -> VoiceProfileResponse:
        """
        Extract linguistic personality profile from user's chat history

        Args:
            username: Username to analyze
            profile_type: Type of profile (basic, standard, complete, enterprise)
            date_range: Optional date range for analysis

        Returns:
            VoiceProfileResponse with linguistic analysis
        """

        # Step 1: Buy chat logs from Karma-Hello
        print(f"Analyzing linguistic profile for {username}...")

        if not self.use_local_files:
            logs = await self.buy_user_logs(username, date_range)
            if not logs:
                raise HTTPException(status_code=404, detail=f"Could not obtain logs for {username}")
        else:
            # Use local test data
            logs = await self._load_local_logs(username)

        # Step 2: Analyze with CrewAI (simplified for now - would use actual CrewAI)
        analysis = self._analyze_linguistic_style(logs, profile_type)

        # Step 3: Build response
        response = VoiceProfileResponse(
            username=username,
            profile_type=profile_type,
            analysis=analysis,
            confidence_score=analysis.get("confidence_score", 0.85),
            metadata={
                "analyzed_messages": logs.get("total_messages", 0),
                "analysis_date": datetime.utcnow().isoformat(),
                "agent_id": str(self.agent_id),
                "seller": self.address
            }
        )

        # Step 4: Cache profile (optional)
        self._cache_profile(username, response)

        return response

    def _analyze_linguistic_style(
        self,
        logs: Dict[str, Any],
        profile_type: str
    ) -> Dict[str, Any]:
        """
        Analyze linguistic style from chat logs

        In production, this would use CrewAI with 8 specialized agents.
        For now, simplified analysis.
        """

        messages = logs.get("messages", [])
        total_messages = len(messages)

        # Extract basic patterns
        all_text = " ".join([m.get("message", "") for m in messages])

        # Simplified analysis (in production, use CrewAI)
        analysis = {
            "confidence_score": 0.85,
            "message_count": total_messages,
            "categories": {
                "modismos": {
                    "score": 0.75,
                    "signature_phrases": ["let's go", "awesome", "cool"],
                    "description": "Moderate use of signature expressions"
                },
                "formality": {
                    "score": 0.60,
                    "level": "casual",
                    "description": "Generally informal communication style"
                },
                "emojis_emoticons": {
                    "score": 0.70,
                    "usage_rate": 0.25,
                    "favorites": [":)", ":D", ";)"]
                },
                "technical_language": {
                    "score": 0.80,
                    "keywords": ["blockchain", "agent", "smart contract"],
                    "expertise_level": "advanced"
                },
                "sentence_structure": {
                    "avg_length": 12.5,
                    "complexity": "moderate",
                    "score": 0.65
                },
                "interaction_patterns": {
                    "responsiveness": "high",
                    "engagement_style": "collaborative",
                    "score": 0.82
                },
                "humor_sarcasm": {
                    "score": 0.55,
                    "usage_rate": 0.15,
                    "style": "lighthearted"
                },
                "question_patterns": {
                    "question_rate": 0.20,
                    "type": "clarifying",
                    "score": 0.70
                }
            }
        }

        # Adjust based on profile type
        if profile_type == "basic":
            # Only include top 3 categories
            analysis["categories"] = dict(list(analysis["categories"].items())[:3])
        elif profile_type == "standard":
            # Include top 5 categories
            analysis["categories"] = dict(list(analysis["categories"].items())[:5])
        # complete and enterprise include all

        return analysis

    async def _load_local_logs(self, username: str) -> Dict[str, Any]:
        """Load logs from local test files"""
        # Return sample data for testing
        return {
            "total_messages": 50,
            "unique_users": 1,
            "messages": [
                {"user": username, "message": "Sample message 1", "timestamp": "2025-10-23T10:00:00Z"},
                {"user": username, "message": "Sample message 2", "timestamp": "2025-10-23T10:01:00Z"},
            ]
        }

    def _cache_profile(self, username: str, profile: VoiceProfileResponse):
        """Cache extracted profile (simplified implementation)"""
        cache_dir = Path("profile_cache")
        cache_dir.mkdir(exist_ok=True)

        cache_file = cache_dir / f"{username}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, indent=2)

        print(f"=� Cached profile for {username}")


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
    "agent_domain": os.getenv("AGENT_DOMAIN", "voice-extractor.ultravioletadao.xyz"),
    "karma_hello_url": os.getenv("KARMA_HELLO_URL", "http://localhost:8002"),
    "use_local_files": os.getenv("USE_LOCAL_FILES", "false").lower() == "true",
    "price_basic": float(os.getenv("PRICE_BASIC", "0.02")),
    "price_standard": float(os.getenv("PRICE_STANDARD", "0.03")),
    "price_complete": float(os.getenv("PRICE_COMPLETE", "0.04")),
    "price_enterprise": float(os.getenv("PRICE_ENTERPRISE", "0.40"))
}

agent = VoiceExtractorAgent(config)

# Create FastAPI app
app = FastAPI(
    title="Voice-Extractor Agent",
    description="Linguistic personality profiler - buys logs, sells profiles",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Voice-Extractor Agent",
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


@app.post("/extract_voice_profile")
async def extract_voice_profile_endpoint(request: VoiceProfileRequest):
    """
    Extract linguistic personality profile

    Supports x402 payment protocol via X-Payment header.
    """
    try:
        profile = await agent.extract_voice_profile(
            username=request.username,
            profile_type=request.profile_type,
            date_range=request.date_range
        )

        # Calculate price
        price = agent.calculate_price(request.profile_type)

        return JSONResponse(
            content=profile.model_dump(),
            headers={
                "X-Price": str(price),
                "X-Currency": "GLUE",
                "X-Profile-Type": request.profile_type,
                "X-Confidence": str(profile.confidence_score)
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
    port = int(os.getenv("PORT", 8005))

    print(f"\n{'='*70}")
    print(f"  Voice-Extractor Agent")
    print(f"{'='*70}")
    print(f"  Address: {agent.address}")
    print(f"  Agent ID: {agent.agent_id}")
    print(f"  Balance: {agent.get_balance()} AVAX")
    print(f"  Data Source: {'Local Files' if agent.use_local_files else 'Karma-Hello'}")
    print(f"  Server: http://{host}:{port}")
    print(f"{'='*70}\n")

    uvicorn.run(app, host=host, port=port)
