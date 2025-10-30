"""
Karma-Hello Agent (Seller + Buyer)

SELLS: Twitch chat logs via x402 protocol
BUYS: Stream transcriptions from Abracadabra agent

Supports both local file testing and MongoDB/direct purchase for production.
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
from x402_middleware import x402_required

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

class ChatLogRequest(BaseModel):
    """Request for chat logs"""
    stream_id: Optional[str] = Field(None, description="Specific stream ID")
    date: Optional[str] = Field(None, description="Date in YYYY-MM-DD format")
    start_time: Optional[str] = Field(None, description="Start time ISO 8601")
    end_time: Optional[str] = Field(None, description="End time ISO 8601")
    users: Optional[List[str]] = Field(None, description="Filter by specific users")
    limit: int = Field(1000, description="Max messages to return")
    include_stats: bool = Field(True, description="Include statistics")


class ChatLogResponse(BaseModel):
    """Response with chat logs"""
    stream_id: str
    stream_date: str
    total_messages: int
    unique_users: int
    messages: List[Dict[str, Any]]
    statistics: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any]


# ============================================================================
# Karma-Hello Seller Agent
# ============================================================================

class KarmaHelloSeller(ERC8004BaseAgent):
    """
    Karma-Hello seller agent - sells Twitch chat logs

    Features:
    - Local file fallback for testing (reads from data/karma-hello/)
    - MongoDB integration for production
    - x402 payment protocol
    - A2A protocol discovery
    - Multiple service tiers
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize Karma-Hello seller agent"""

        # Initialize base agent (registers on-chain)
        super().__init__(
            agent_name="karma-hello-agent",
            agent_domain=config["agent_domain"],
            rpc_url=config["rpc_url_fuji"],
            chain_id=config["chain_id"],
            identity_registry_address=config["identity_registry"],
            reputation_registry_address=config["reputation_registry"],
            validation_registry_address=config["validation_registry"],
            private_key=config.get("private_key")
        )

        self.config = config
        self.use_local_files = config.get("use_local_files", True)
        self.glue_token_address = config["glue_token_address"]
        self.facilitator_url = config["facilitator_url"]
        self.abracadabra_url = config.get("abracadabra_url")

        # Setup data source
        if self.use_local_files:
            self.local_data_path = Path(config.get("local_data_path", "../data/karma-hello"))
            print(f"=� Using local files from: {self.local_data_path}")
        else:
            # MongoDB setup for production
            from pymongo import MongoClient
            self.mongo_client = MongoClient(config["mongo_uri"])
            self.db = self.mongo_client[config["mongo_db"]]
            self.collection = self.db[config["mongo_collection"]]
            print(f"=�  Connected to MongoDB: {config['mongo_db']}")

        # Register agent identity
        try:
            self.agent_id = self.register_agent()
            print(f" Agent registered on-chain: ID {self.agent_id}")
        except Exception as e:
            print(f"�  Agent registration failed (may already be registered): {e}")
            self.agent_id = None

        print(f"> Karma-Hello Seller initialized")
        print(f"   Address: {self.address}")

    def get_agent_card(self) -> Dict[str, Any]:
        """Return A2A AgentCard for discovery"""
        return {
            "schema_version": "1.0.0",
            "agent_id": str(self.agent_id) if self.agent_id else "unregistered",
            "name": "Karma-Hello Seller",
            "description": "Twitch chat log seller - provides historical chat data from streams",
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
                "network": "avalanche-fuji",
                "chain_id": self.config["chain_id"],
                "contracts": {
                    "identity_registry": self.config["identity_registry"],
                    "reputation_registry": self.config["reputation_registry"]
                }
            },
            "skills": [
                {
                    "name": "get_chat_logs",
                    "description": "Get Twitch chat logs for a specific stream or date range",
                    "input_schema": ChatLogRequest.model_json_schema(),
                    "output_schema": ChatLogResponse.model_json_schema(),
                    "pricing": {
                        "currency": "GLUE",
                        "base_price": str(self.config["base_price"]),
                        "price_per_message": str(self.config["price_per_message"]),
                        "max_price": str(self.config["max_price"])
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

    def calculate_price(self, message_count: int) -> Decimal:
        """Calculate price based on message count"""
        base = Decimal(str(self.config["base_price"]))
        per_message = Decimal(str(self.config["price_per_message"]))
        max_price = Decimal(str(self.config["max_price"]))

        price = base + (per_message * message_count)
        return min(price, max_price)

    async def get_chat_logs_from_file(self, request: ChatLogRequest) -> ChatLogResponse:
        """Get chat logs from local JSON files"""

        # Try to find matching file
        if request.date:
            # Format: chat_logs_YYYYMMDD.json
            date_str = request.date.replace("-", "")
            filename = f"chat_logs_{date_str}.json"
        else:
            # Use most recent file
            files = sorted(self.local_data_path.glob("chat_logs_*.json"))
            if not files:
                raise HTTPException(status_code=404, detail="No chat logs found")
            filename = files[-1].name

        filepath = self.local_data_path / filename

        if not filepath.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")

        # Load data
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Filter messages if needed
        messages = data["messages"]

        if request.users:
            messages = [m for m in messages if m["user"] in request.users]

        if request.start_time:
            messages = [m for m in messages if m["timestamp"] >= request.start_time]

        if request.end_time:
            messages = [m for m in messages if m["timestamp"] <= request.end_time]

        # Limit results
        messages = messages[:request.limit]

        # Build response
        response_data = {
            "stream_id": data["stream_id"],
            "stream_date": data["stream_date"],
            "total_messages": len(messages),
            "unique_users": len(set(m["user"] for m in messages)),
            "messages": messages,
            "metadata": {
                "source": "local_file",
                "filename": filename,
                "seller": self.address,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        if request.include_stats:
            response_data["statistics"] = data.get("statistics", {})

        return ChatLogResponse(**response_data)

    async def get_chat_logs_from_mongo(self, request: ChatLogRequest) -> ChatLogResponse:
        """Get chat logs from MongoDB"""

        # Build query
        query = {}

        if request.stream_id:
            query["stream_id"] = request.stream_id

        if request.date:
            query["stream_date"] = request.date

        if request.users:
            query["messages.user"] = {"$in": request.users}

        # Find matching stream
        stream_doc = self.collection.find_one(query)

        if not stream_doc:
            raise HTTPException(status_code=404, detail="Stream not found")

        messages = stream_doc["messages"]

        # Filter by time range
        if request.start_time:
            messages = [m for m in messages if m["timestamp"] >= request.start_time]

        if request.end_time:
            messages = [m for m in messages if m["timestamp"] <= request.end_time]

        # Limit results
        messages = messages[:request.limit]

        # Build response
        response_data = {
            "stream_id": stream_doc["stream_id"],
            "stream_date": stream_doc["stream_date"],
            "total_messages": len(messages),
            "unique_users": len(set(m["user"] for m in messages)),
            "messages": messages,
            "metadata": {
                "source": "mongodb",
                "seller": self.address,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        if request.include_stats:
            response_data["statistics"] = stream_doc.get("statistics", {})

        return ChatLogResponse(**response_data)

    # ========================================================================
    # Buyer Capabilities - Purchase transcriptions from Abracadabra
    # ========================================================================

    async def discover_abracadabra(self, abracadabra_url: str) -> Optional[Dict[str, Any]]:
        """
        Discover Abracadabra seller via A2A protocol

        Args:
            abracadabra_url: URL of Abracadabra agent

        Returns:
            Agent card data or None if not found
        """
        import httpx

        agent_card_url = f"{abracadabra_url}/.well-known/agent-card"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(agent_card_url, timeout=10.0)
                if response.status_code == 200:
                    print(f"✅ Discovered Abracadabra seller: {abracadabra_url}")
                    return response.json()
                else:
                    print(f"⚠️  Abracadabra not found at {abracadabra_url}")
                    return None
        except Exception as e:
            print(f"❌ Error discovering Abracadabra: {e}")
            return None

    async def buy_transcription(
        self,
        abracadabra_url: str,
        stream_id: Optional[str] = None,
        date: Optional[str] = None,
        include_summary: bool = False,
        include_topics: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Buy transcription from Abracadabra agent

        Args:
            abracadabra_url: URL of Abracadabra agent
            stream_id: Specific stream ID to purchase
            date: Date in YYYY-MM-DD format
            include_summary: Include AI summary
            include_topics: Include extracted topics

        Returns:
            Transcription data or None if purchase failed
        """
        import httpx

        # Discover seller first
        agent_card = await self.discover_abracadabra(abracadabra_url)
        if not agent_card:
            return None

        # Build request
        request_data = {}
        if stream_id:
            request_data["stream_id"] = stream_id
        if date:
            request_data["date"] = date
        if include_summary:
            request_data["include_summary"] = True
        if include_topics:
            request_data["include_topics"] = True

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{abracadabra_url}/get_transcription",
                    json=request_data,
                    timeout=30.0
                )

                if response.status_code == 200:
                    transcription = response.json()
                    price = response.headers.get("X-Price", "unknown")

                    print(f"✅ Purchased transcription from Abracadabra")
                    print(f"   Stream ID: {transcription['stream_id']}")
                    print(f"   Duration: {transcription['duration_seconds']}s")
                    print(f"   Price: {price} GLUE")

                    # Store transcription
                    self.save_purchased_transcription(transcription)

                    return transcription
                else:
                    print(f"❌ Purchase failed: {response.status_code}")
                    print(f"   {response.text}")
                    return None

        except Exception as e:
            print(f"❌ Error buying transcription: {e}")
            return None

    def save_purchased_transcription(self, transcription: Dict[str, Any]):
        """
        Save purchased transcription to local storage

        Args:
            transcription: Transcription data from Abracadabra
        """
        # Create storage directory
        storage_dir = Path("purchased_transcriptions")
        storage_dir.mkdir(exist_ok=True)

        # Save to file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        stream_id = transcription.get("stream_id", "unknown")
        filename = f"{stream_id}_{timestamp}.json"
        filepath = storage_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "purchased_at": datetime.utcnow().isoformat(),
                "seller": transcription.get("metadata", {}).get("seller"),
                "transcription": transcription
            }, f, indent=2)

        print(f"💾 Saved transcription to: {filepath}")


# ============================================================================
# FastAPI Application
# ============================================================================

# Initialize agent
config = {
    "private_key": os.getenv("PRIVATE_KEY", "").strip() or None,
    "rpc_url_fuji": os.getenv("RPC_URL_FUJI"),
    "chain_id": int(os.getenv("CHAIN_ID", 43113)),
    "identity_registry": os.getenv("IDENTITY_REGISTRY"),
    "reputation_registry": os.getenv("REPUTATION_REGISTRY"),
    "validation_registry": os.getenv("VALIDATION_REGISTRY"),
    "glue_token_address": os.getenv("GLUE_TOKEN_ADDRESS"),
    "facilitator_url": os.getenv("FACILITATOR_URL"),
    "agent_domain": os.getenv("AGENT_DOMAIN", "karma-hello.ultravioletadao.xyz"),
    "mongo_uri": os.getenv("MONGO_URI"),
    "mongo_db": os.getenv("MONGO_DB", "karma_hello"),
    "mongo_collection": os.getenv("MONGO_COLLECTION", "chat_logs"),
    "use_local_files": os.getenv("USE_LOCAL_FILES", "true").lower() == "true",
    "local_data_path": os.getenv("LOCAL_DATA_PATH", "/app/data/karma-hello"),
    "base_price": float(os.getenv("BASE_PRICE", "0.01")),
    "price_per_message": float(os.getenv("PRICE_PER_MESSAGE", "0.0001")),
    "max_price": float(os.getenv("MAX_PRICE", "200.0"))
}

agent = KarmaHelloSeller(config)

# Create FastAPI app
app = FastAPI(
    title="Karma-Hello Agent",
    description="Twitch chat log seller + transcription buyer",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Karma-Hello Seller",
        "status": "healthy",
        "agent_id": str(agent.agent_id) if agent.agent_id else "unregistered",
        "address": agent.address,
        "balance": f"{agent.get_balance()} AVAX",
        "data_source": "local_files" if agent.use_local_files else "mongodb"
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    return await root()


@app.get("/.well-known/agent-card")
async def agent_card():
    """A2A protocol - return agent capabilities"""
    return agent.get_agent_card()


@app.post("/get_chat_logs")
@x402_required(price=0.01, currency="GLUE")
async def get_chat_logs(request: Request, chat_request: ChatLogRequest):
    """
    Get chat logs endpoint - PROTECTED by x402 payment

    Requires valid x402 payment authorization in Authorization header.
    Price: 0.01 GLUE per request
    """
    try:
        # Get data from appropriate source
        if agent.use_local_files:
            response = await agent.get_chat_logs_from_file(chat_request)
        else:
            response = await agent.get_chat_logs_from_mongo(chat_request)

        # Calculate actual price based on messages
        actual_price = agent.calculate_price(response.total_messages)

        return JSONResponse(
            content=response.model_dump(),
            headers={
                "X-Price": str(actual_price),
                "X-Currency": "GLUE",
                "X-Message-Count": str(response.total_messages)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving logs: {str(e)}")


@app.post("/buy_transcription")
async def buy_transcription_endpoint(
    abracadabra_url: str,
    stream_id: Optional[str] = None,
    date: Optional[str] = None,
    include_summary: bool = False,
    include_topics: bool = False
):
    """
    Buy transcription from Abracadabra agent

    This endpoint allows Karma-Hello to purchase transcriptions
    to enrich its data with audio context.
    """
    try:
        transcription = await agent.buy_transcription(
            abracadabra_url=abracadabra_url,
            stream_id=stream_id,
            date=date,
            include_summary=include_summary,
            include_topics=include_topics
        )

        if transcription:
            return {
                "success": True,
                "message": "Transcription purchased successfully",
                "transcription": transcription
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to purchase transcription")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error buying transcription: {str(e)}")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8002))

    print(f"\n{'='*70}")
    print(f"  Karma-Hello Seller Agent")
    print(f"{'='*70}")
    print(f"  Address: {agent.address}")
    print(f"  Agent ID: {agent.agent_id}")
    print(f"  Balance: {agent.get_balance()} AVAX")
    print(f"  Data Source: {'Local Files' if agent.use_local_files else 'MongoDB'}")
    print(f"  Server: http://{host}:{port}")
    print(f"{'='*70}\n")

    uvicorn.run(app, host=host, port=port)
