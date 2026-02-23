"""
Abracadabra Agent (Seller + Buyer)

SELLS: Stream transcriptions via x402 protocol
BUYS: Chat logs from Karma-Hello agent

Supports both local file testing and SQLite/direct purchase for production.
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

class TranscriptionRequest(BaseModel):
    """Request for transcription"""
    stream_id: Optional[str] = Field(None, description="Specific stream ID")
    date: Optional[str] = Field(None, description="Date in YYYY-MM-DD format")
    include_summary: bool = Field(False, description="Include AI summary")
    include_topics: bool = Field(False, description="Include extracted topics")
    language: Optional[str] = Field(None, description="Filter by language")


class TranscriptionResponse(BaseModel):
    """Response with transcription"""
    stream_id: str
    duration_seconds: int
    language: str
    transcript: List[Dict[str, Any]]
    summary: Optional[str] = None
    key_topics: Optional[List[str]] = None
    metadata: Dict[str, Any]


# ============================================================================
# Abracadabra Seller Agent
# ============================================================================

class AbracadabraSeller(ERC8004BaseAgent):
    """
    Abracadabra seller agent - sells stream transcriptions

    Features:
    - Local file fallback for testing (reads from data/abracadabra/)
    - SQLite integration for production
    - x402 payment protocol
    - A2A protocol discovery
    - Multiple service tiers
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize Abracadabra seller agent"""

        # Initialize base agent (registers on-chain)
        super().__init__(
            agent_name="abracadabra-agent",
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
        self.karma_hello_url = config.get("karma_hello_url")

        # Setup data source
        if self.use_local_files:
            self.local_data_path = Path(config.get("local_data_path", "../data/abracadabra"))
            print(f"=� Using local files from: {self.local_data_path}")
        else:
            # SQLite setup for production
            import sqlite3
            self.db_path = config["sqlite_db_path"]
            print(f"=�  Using SQLite database: {self.db_path}")

        # Register agent identity
        try:
            self.agent_id = self.register_agent()
            print(f" Agent registered on-chain: ID {self.agent_id}")
        except Exception as e:
            print(f"�  Agent registration failed (may already be registered): {e}")
            self.agent_id = None

        print(f"> Abracadabra Seller initialized")
        print(f"   Address: {self.address}")

    def get_agent_card(self) -> Dict[str, Any]:
        """Return A2A AgentCard for discovery"""
        return {
            "schema_version": "1.0.0",
            "agent_id": str(self.agent_id) if self.agent_id else "unregistered",
            "name": "Abracadabra Seller",
            "description": "Stream transcription seller - provides AI-transcribed audio from streams",
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
                    "name": "get_transcription",
                    "description": "Get AI transcription for a specific stream or date",
                    "input_schema": TranscriptionRequest.model_json_schema(),
                    "output_schema": TranscriptionResponse.model_json_schema(),
                    "pricing": {
                        "currency": "GLUE",
                        "base_price": str(self.config["base_price"]),
                        "price_per_segment": str(self.config["price_per_segment"]),
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

    def calculate_price(self, segment_count: int) -> Decimal:
        """Calculate price based on segment count"""
        base = Decimal(str(self.config["base_price"]))
        per_segment = Decimal(str(self.config["price_per_segment"]))
        max_price = Decimal(str(self.config["max_price"]))

        price = base + (per_segment * segment_count)
        return min(price, max_price)

    async def get_transcription_from_file(self, request: TranscriptionRequest) -> TranscriptionResponse:
        """Get transcription from local JSON files"""

        # Try to find matching file
        if request.date:
            # Format: transcription_YYYYMMDD.json
            date_str = request.date.replace("-", "")
            filename = f"transcription_{date_str}.json"
        else:
            # Use most recent file
            files = sorted(self.local_data_path.glob("transcription_*.json"))
            if not files:
                raise HTTPException(status_code=404, detail="No transcriptions found")
            filename = files[-1].name

        filepath = self.local_data_path / filename

        if not filepath.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")

        # Load data
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Build response
        response_data = {
            "stream_id": data["stream_id"],
            "duration_seconds": data["duration_seconds"],
            "language": data.get("language", "en"),
            "transcript": data["transcript"],
            "metadata": {
                "source": "local_file",
                "filename": filename,
                "seller": self.address,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        # Add optional fields if requested
        if request.include_summary and "summary" in data:
            response_data["summary"] = data["summary"]

        if request.include_topics and "key_topics" in data:
            response_data["key_topics"] = data["key_topics"]

        return TranscriptionResponse(**response_data)

    async def get_transcription_from_sqlite(self, request: TranscriptionRequest) -> TranscriptionResponse:
        """Get transcription from SQLite database"""

        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Build query
        query = "SELECT * FROM transcriptions WHERE 1=1"
        params = []

        if request.stream_id:
            query += " AND stream_id = ?"
            params.append(request.stream_id)

        if request.date:
            query += " AND date = ?"
            params.append(request.date)

        if request.language:
            query += " AND language = ?"
            params.append(request.language)

        query += " LIMIT 1"

        cursor.execute(query, params)
        row = cursor.fetchone()

        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Transcription not found")

        # Parse row (assumes specific schema)
        # Adjust column indices based on your actual schema
        transcript_data = json.loads(row[3]) if isinstance(row[3], str) else row[3]

        response_data = {
            "stream_id": row[0],
            "duration_seconds": row[1],
            "language": row[2],
            "transcript": transcript_data,
            "metadata": {
                "source": "sqlite",
                "seller": self.address,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        # Add optional fields
        if request.include_summary and len(row) > 4:
            response_data["summary"] = row[4]

        if request.include_topics and len(row) > 5:
            response_data["key_topics"] = json.loads(row[5]) if isinstance(row[5], str) else row[5]

        conn.close()

        return TranscriptionResponse(**response_data)

    # ========================================================================
    # Buyer Capabilities - Purchase chat logs from Karma-Hello
    # ========================================================================

    async def discover_karma_hello(self, karma_hello_url: str) -> Optional[Dict[str, Any]]:
        """
        Discover Karma-Hello seller via A2A protocol

        Args:
            karma_hello_url: URL of Karma-Hello agent

        Returns:
            Agent card data or None if not found
        """
        import httpx

        agent_card_url = f"{karma_hello_url}/.well-known/agent-card"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(agent_card_url, timeout=10.0)
                if response.status_code == 200:
                    print(f"✅ Discovered Karma-Hello seller: {karma_hello_url}")
                    return response.json()
                else:
                    print(f"⚠️  Karma-Hello not found at {karma_hello_url}")
                    return None
        except Exception as e:
            print(f"❌ Error discovering Karma-Hello: {e}")
            return None

    async def buy_chat_logs(
        self,
        karma_hello_url: str,
        stream_id: Optional[str] = None,
        date: Optional[str] = None,
        users: Optional[List[str]] = None,
        limit: int = 1000,
        include_stats: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Buy chat logs from Karma-Hello agent

        Args:
            karma_hello_url: URL of Karma-Hello agent
            stream_id: Specific stream ID to purchase
            date: Date in YYYY-MM-DD format
            users: Filter by specific users
            limit: Max messages to return
            include_stats: Include statistics

        Returns:
            Chat log data or None if purchase failed
        """
        import httpx

        # Discover seller first
        agent_card = await self.discover_karma_hello(karma_hello_url)
        if not agent_card:
            return None

        # Build request
        request_data = {"limit": limit, "include_stats": include_stats}
        if stream_id:
            request_data["stream_id"] = stream_id
        if date:
            request_data["date"] = date
        if users:
            request_data["users"] = users

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{karma_hello_url}/get_chat_logs",
                    json=request_data,
                    timeout=30.0
                )

                if response.status_code == 200:
                    chat_logs = response.json()
                    price = response.headers.get("X-Price", "unknown")

                    print(f"✅ Purchased chat logs from Karma-Hello")
                    print(f"   Stream ID: {chat_logs['stream_id']}")
                    print(f"   Messages: {chat_logs['total_messages']}")
                    print(f"   Price: {price} GLUE")

                    # Store chat logs
                    self.save_purchased_chat_logs(chat_logs)

                    return chat_logs
                else:
                    print(f"❌ Purchase failed: {response.status_code}")
                    print(f"   {response.text}")
                    return None

        except Exception as e:
            print(f"❌ Error buying chat logs: {e}")
            return None

    def save_purchased_chat_logs(self, chat_logs: Dict[str, Any]):
        """
        Save purchased chat logs to local storage

        Args:
            chat_logs: Chat log data from Karma-Hello
        """
        # Create storage directory
        storage_dir = Path("purchased_chat_logs")
        storage_dir.mkdir(exist_ok=True)

        # Save to file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        stream_id = chat_logs.get("stream_id", "unknown")
        filename = f"{stream_id}_{timestamp}.json"
        filepath = storage_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "purchased_at": datetime.utcnow().isoformat(),
                "seller": chat_logs.get("metadata", {}).get("seller"),
                "chat_logs": chat_logs
            }, f, indent=2)

        print(f"💾 Saved chat logs to: {filepath}")


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
    "agent_domain": os.getenv("AGENT_DOMAIN", "abracadabra.ultravioletadao.xyz"),
    "sqlite_db_path": os.getenv("SQLITE_DB_PATH"),
    "use_local_files": os.getenv("USE_LOCAL_FILES", "true").lower() == "true",
    "local_data_path": os.getenv("LOCAL_DATA_PATH", "/app/data/abracadabra"),
    "base_price": float(os.getenv("BASE_PRICE", "0.02")),
    "price_per_segment": float(os.getenv("PRICE_PER_SEGMENT", "0.001")),
    "max_price": float(os.getenv("MAX_PRICE", "300.0"))
}

agent = AbracadabraSeller(config)

# Create FastAPI app
app = FastAPI(
    title="Abracadabra Agent",
    description="Stream transcription seller + chat log buyer",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Abracadabra Seller",
        "status": "healthy",
        "agent_id": str(agent.agent_id) if agent.agent_id else "unregistered",
        "address": agent.address,
        "balance": f"{agent.get_balance()} AVAX",
        "data_source": "local_files" if agent.use_local_files else "sqlite"
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    return await root()


@app.get("/.well-known/agent-card")
async def agent_card():
    """A2A protocol - return agent capabilities"""
    return agent.get_agent_card()


@app.post("/get_transcription")
async def get_transcription(request: TranscriptionRequest):
    """
    Get transcription endpoint

    Supports x402 payment protocol via X-Payment header.
    """
    try:
        # Get data from appropriate source
        if agent.use_local_files:
            response = await agent.get_transcription_from_file(request)
        else:
            response = await agent.get_transcription_from_sqlite(request)

        # Calculate price
        segment_count = len(response.transcript)
        price = agent.calculate_price(segment_count)

        return JSONResponse(
            content=response.model_dump(),
            headers={
                "X-Price": str(price),
                "X-Currency": "GLUE",
                "X-Segment-Count": str(segment_count),
                "X-Duration": str(response.duration_seconds)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving transcription: {str(e)}")


@app.post("/buy_chat_logs")
async def buy_chat_logs_endpoint(
    karma_hello_url: str,
    stream_id: Optional[str] = None,
    date: Optional[str] = None,
    users: Optional[List[str]] = None,
    limit: int = 1000,
    include_stats: bool = True
):
    """
    Buy chat logs from Karma-Hello agent

    This endpoint allows Abracadabra to purchase chat logs
    to enrich transcriptions with chat context.
    """
    try:
        chat_logs = await agent.buy_chat_logs(
            karma_hello_url=karma_hello_url,
            stream_id=stream_id,
            date=date,
            users=users,
            limit=limit,
            include_stats=include_stats
        )

        if chat_logs:
            return {
                "success": True,
                "message": "Chat logs purchased successfully",
                "chat_logs": chat_logs
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to purchase chat logs")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error buying chat logs: {str(e)}")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8003))

    print(f"\n{'='*70}")
    print(f"  Abracadabra Seller Agent")
    print(f"{'='*70}")
    print(f"  Address: {agent.address}")
    print(f"  Agent ID: {agent.agent_id}")
    print(f"  Balance: {agent.get_balance()} AVAX")
    print(f"  Data Source: {'Local Files' if agent.use_local_files else 'SQLite'}")
    print(f"  Server: http://{host}:{port}")
    print(f"{'='*70}\n")

    uvicorn.run(app, host=host, port=port)
