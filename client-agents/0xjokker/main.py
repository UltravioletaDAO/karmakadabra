"""
User Agent Template
Base implementation for marketplace participant agents

Sprint 3, Task 3: User agent template
Each of the 48 users gets an instance of this agent
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
import uvicorn
from dotenv import load_dotenv

# Add parent directory to path for shared imports
sys.path.append(str(Path(__file__).parent.parent))

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

class ServiceRequest(BaseModel):
    """Generic service request"""
    service_id: str = Field(..., description="Service ID from agent card")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Service-specific parameters")


class ServiceResponse(BaseModel):
    """Generic service response"""
    service_id: str
    result: Any
    status: str = "success"
    timestamp: str


# ============================================================================
# User Agent
# ============================================================================

class UserAgent(ERC8004BaseAgent):
    """
    User marketplace agent

    Features:
    - Serves Agent Card at /.well-known/agent-card
    - Provides services defined in agent card
    - Accepts payments via x402 protocol
    - Inherits buyer capabilities from base agent
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize user agent"""

        # Initialize base agent (registers on-chain)
        super().__init__(
            agent_name=config["agent_name"],
            agent_domain=config["agent_domain"],
            rpc_url=config["rpc_url_fuji"],
            chain_id=config["chain_id"],
            identity_registry_address=config["identity_registry"],
            reputation_registry_address=config["reputation_registry"],
            validation_registry_address=config["validation_registry"],
            private_key=config.get("private_key")
        )

        self.config = config
        self.username = config["username"]
        self.port = config.get("port", 9000)

        # Load agent card
        agent_card_path = Path(config["agent_card_path"])
        if not agent_card_path.exists():
            raise ValueError(f"Agent card not found: {agent_card_path}")

        with open(agent_card_path, 'r', encoding='utf-8') as f:
            self.agent_card = json.load(f)

        # Load user profile
        profile_path = Path(config["profile_path"])
        if not profile_path.exists():
            raise ValueError(f"Profile not found: {profile_path}")

        with open(profile_path, 'r', encoding='utf-8') as f:
            self.profile = json.load(f)

        print(f"✅ User Agent initialized for {self.username}")
        print(f"   Services: {len(self.agent_card['services'])}")
        print(f"   Engagement: {self.profile['interaction_style']['engagement_level']}")

    def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get service configuration by ID"""
        for service in self.agent_card["services"]:
            if service["id"] == service_id:
                return service
        return None

    def calculate_service_price(self, service_id: str) -> Decimal:
        """Calculate price for a service"""
        service = self.get_service(service_id)
        if not service:
            raise ValueError(f"Service not found: {service_id}")

        pricing = service.get("pricing", {})
        amount = pricing.get("amount", "0.05")
        return Decimal(amount)

    async def execute_service(
        self,
        service_id: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a service based on service ID

        In a full implementation, this would:
        - Route to specific service handlers
        - Use CrewAI for complex tasks
        - Interface with external APIs/data sources

        For MVP, returns simulated responses
        """

        service = self.get_service(service_id)
        if not service:
            raise ValueError(f"Service not found: {service_id}")

        # Simulate service execution
        result = {
            "service_id": service_id,
            "service_name": service["name"],
            "provider": f"@{self.username}",
            "status": "completed",
            "result": {
                "message": f"Service '{service['name']}' executed successfully",
                "details": f"This is a simulated response. In production, this would provide actual {service['name'].lower()} results.",
                "confidence": service.get("confidence", 0.5),
                "parameters_received": parameters
            }
        }

        return result


# ============================================================================
# FastAPI Application
# ============================================================================

# Global agent instance
agent: Optional[UserAgent] = None

# Create FastAPI app
app = FastAPI(
    title="User Agent",
    description="Marketplace participant agent providing services",
    version="1.0.0"
)


@app.on_event("startup")
async def startup_event():
    """Initialize agent on startup"""
    global agent

    # Read config from environment
    config = {
        "agent_name": os.getenv("AGENT_NAME", "user-agent"),
        "username": os.getenv("USERNAME", "default_user"),
        "agent_domain": os.getenv("AGENT_DOMAIN", "user.karmacadabra.ultravioletadao.xyz"),
        "port": int(os.getenv("PORT", "9000")),
        "rpc_url_fuji": os.getenv("RPC_URL_FUJI", "https://avalanche-fuji-c-chain-rpc.publicnode.com"),
        "chain_id": 43113,
        "identity_registry": os.getenv("IDENTITY_REGISTRY"),
        "reputation_registry": os.getenv("REPUTATION_REGISTRY"),
        "validation_registry": os.getenv("VALIDATION_REGISTRY"),
        "glue_token_address": os.getenv("GLUE_TOKEN_ADDRESS"),
        "facilitator_url": os.getenv("FACILITATOR_URL", "http://localhost:8080"),
        "private_key": os.getenv("PRIVATE_KEY"),
        "agent_card_path": os.getenv("AGENT_CARD_PATH", "agent-card.json"),
        "profile_path": os.getenv("PROFILE_PATH", "profile.json")
    }

    agent = UserAgent(config)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return {
        "status": "healthy",
        "agent": agent.username,
        "services": len(agent.agent_card["services"]),
        "registered": True,
        "agent_id": agent.agent_id
    }


@app.get("/.well-known/agent-card")
async def get_agent_card():
    """Serve A2A protocol agent card"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return JSONResponse(content=agent.agent_card)


@app.get("/services")
async def list_services():
    """List all available services"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return {
        "agent": f"@{agent.username}",
        "services": agent.agent_card["services"]
    }


@app.post("/services/{service_id}")
async def execute_service_endpoint(
    service_id: str,
    request: ServiceRequest
):
    """
    Execute a service

    In production, this would require x402 payment via middleware
    For MVP, accepts requests directly
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    # Verify service exists
    service = agent.get_service(service_id)
    if not service:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_id}")

    # Execute service
    try:
        result = await agent.execute_service(service_id, request.parameters)
        return ServiceResponse(
            service_id=service_id,
            result=result,
            status="success",
            timestamp=str(asyncio.get_event_loop().time())
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Service execution failed: {str(e)}")


@app.get("/profile")
async def get_profile():
    """Get user profile (for debugging)"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return agent.profile


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run the user agent server"""
    port = int(os.getenv("PORT", "9000"))

    print("="*80)
    print(f"User Agent - {os.getenv('USERNAME', 'default_user')}")
    print("="*80)
    print(f"Port: {port}")
    print(f"Agent Card: {os.getenv('AGENT_CARD_PATH', 'agent-card.json')}")
    print(f"Profile: {os.getenv('PROFILE_PATH', 'profile.json')}")
    print("="*80)
    print()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
