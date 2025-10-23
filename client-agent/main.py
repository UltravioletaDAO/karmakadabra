"""
Client Agent - Generic data buyer

This agent demonstrates how to buy data in the Karmacadabra marketplace.
"""

import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, Any
import logging

from dotenv import load_dotenv
from shared.base_agent import ERC8004BaseAgent
from shared.x402_client import X402Client
from shared.a2a_protocol import AgentCard
import httpx

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

CONFIG = {
    "agent_name": os.getenv("AGENT_NAME", "client-agent"),
    "agent_domain": os.getenv("AGENT_DOMAIN", "client.ultravioletadao.xyz"),
    "private_key": os.getenv("PRIVATE_KEY", ""),
    "rpc_url": os.getenv("RPC_URL_FUJI"),
    "chain_id": int(os.getenv("CHAIN_ID", "43113")),
    "identity_registry": os.getenv("IDENTITY_REGISTRY"),
    "reputation_registry": os.getenv("REPUTATION_REGISTRY"),
    "validation_registry": os.getenv("VALIDATION_REGISTRY"),
    "glue_token": os.getenv("GLUE_TOKEN_ADDRESS"),
    "facilitator_url": os.getenv("FACILITATOR_URL"),
    "max_price": float(os.getenv("MAX_PRICE_GLUE", "1.0")),
    "request_validation": os.getenv("REQUEST_VALIDATION", "true").lower() == "true",
    "min_validation_score": float(os.getenv("MIN_VALIDATION_SCORE", "0.7")),
    "data_dir": os.getenv("DATA_DIR", "./purchased_data"),
    "validator_url": os.getenv("VALIDATOR_URL", "http://localhost:8001")
}


class ClientAgent(ERC8004BaseAgent):
    """Client Agent - Generic buyer for data marketplace"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(
            agent_name=config["agent_name"],
            private_key=config["private_key"],
            rpc_url=config["rpc_url"],
            chain_id=config["chain_id"],
            identity_registry_address=config["identity_registry"],
            reputation_registry_address=config["reputation_registry"],
            validation_registry_address=config["validation_registry"],
            glue_token_address=config["glue_token"]
        )

        self.config = config
        self.data_dir = Path(config["data_dir"])
        self.data_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Client agent initialized: {self.address}")
        logger.info(f"Data directory: {self.data_dir}")

    async def discover_seller(self, seller_url: str) -> Optional[AgentCard]:
        try:
            agent_card_url = f"{seller_url}/.well-known/agent-card"
            logger.info(f"Discovering seller at {agent_card_url}")

            async with httpx.AsyncClient() as client:
                response = await client.get(agent_card_url, timeout=10.0)
                
                if response.status_code == 200:
                    card_data = response.json()
                    agent_card = AgentCard(**card_data)
                    logger.info(f"Discovered: {agent_card.name}")
                    return agent_card
                else:
                    logger.error(f"Failed to discover: {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            return None

    async def request_validation(
        self, data: Dict, data_type: str, seller_address: str, price_glue: str
    ) -> Optional[Dict]:
        if not self.config["request_validation"]:
            return None

        logger.info(f"Requesting validation for {data_type}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.config['validator_url']}/validate",
                    json={
                        "data_type": data_type,
                        "data_content": data,
                        "seller_address": seller_address,
                        "buyer_address": self.address,
                        "price_glue": price_glue
                    },
                    timeout=120.0
                )

                if response.status_code == 200:
                    validation = response.json()
                    logger.info(f"Validation: {validation['overall_score']:.2f}")
                    return validation
        except Exception as e:
            logger.error(f"Validation failed: {e}")
        return None

    def save_data(self, seller_url: str, data: Dict):
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        seller_name = seller_url.split("//")[-1].split(".")[0]
        filename = f"{seller_name}_{timestamp}.json"
        filepath = self.data_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "seller": seller_url,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data
            }, f, indent=2)

        logger.info(f"Data saved: {filepath}")


async def demo():
    print("
" + "="*70)
    print("  CLIENT AGENT - Demo")
    print("="*70 + "
")

    client = ClientAgent(CONFIG)
    print(f"Client Address: {client.address}")
    print(f"Data Directory: {client.data_dir}
")

    # Demo: Discover Validator
    print("Demo: Discovering Validator")
    print("-" * 70)
    validator_card = await client.discover_seller(CONFIG["validator_url"])
    if validator_card:
        print(f"Found: {validator_card.name}")
        print(f"Skills: {len(validator_card.skills)}")
    
    print("
Demo complete!")


if __name__ == "__main__":
    asyncio.run(demo())
