#!/usr/bin/env python3
"""
A2A (Agent-to-Agent) Protocol for Karmacadabra

Implements agent discovery and skill invocation protocol compatible with:
- Pydantic AI A2A standard
- x402 payment protocol
- ERC-8004 reputation system

Protocol Flow:
1. Seller publishes AgentCard at /.well-known/agent-card
2. Buyer discovers seller via HTTP GET to discovery endpoint
3. Buyer invokes skill with signed payment (x402 + EIP-712)
4. Seller verifies payment and returns data

Reference:
- A2A Spec: https://ai.pydantic.dev/a2a/
- AgentCard: https://google.github.io/A2A/
"""

import json
from typing import List, Dict, Any, Optional, Callable
from decimal import Decimal
from pydantic import BaseModel, Field
import httpx


# =============================================================================
# DATA MODELS
# =============================================================================

class Price(BaseModel):
    """
    Price specification for a skill

    Attributes:
        amount: Price amount as string (e.g., "0.01")
        currency: Currency code (e.g., "GLUE", "UVD")
    """
    amount: str = Field(..., description="Price amount in currency units")
    currency: str = Field(default="GLUE", description="Currency code")

    def to_glue_units(self, decimals: int = 6) -> int:
        """Convert to smallest token units"""
        return int(Decimal(self.amount) * (10 ** decimals))

    @classmethod
    def from_glue_units(cls, amount: int, decimals: int = 6) -> "Price":
        """Create from smallest token units"""
        human_amount = str(Decimal(amount) / (10 ** decimals))
        return cls(amount=human_amount, currency="GLUE")


class Skill(BaseModel):
    """
    Skill definition for an agent capability

    A skill represents a single callable operation that an agent can perform,
    with defined input/output schemas and pricing.

    Attributes:
        skillId: Unique identifier for the skill
        name: Human-readable skill name
        description: Detailed description of what the skill does
        price: Payment required to invoke this skill
        inputSchema: JSON schema for input parameters
        outputSchema: JSON schema for expected output
        endpoint: Optional HTTP endpoint path (default: /api/{skillId})
    """
    skillId: str = Field(..., description="Unique skill identifier")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Skill description")
    price: Price = Field(..., description="Payment requirement")
    inputSchema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON schema for input parameters"
    )
    outputSchema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON schema for output"
    )
    endpoint: Optional[str] = Field(
        default=None,
        description="HTTP endpoint (default: /api/{skillId})"
    )

    def get_endpoint(self) -> str:
        """Get HTTP endpoint for this skill"""
        return self.endpoint or f"/api/{self.skillId}"


class Registration(BaseModel):
    """
    On-chain registration information

    Attributes:
        contract: Registry contract name (e.g., "IdentityRegistry")
        address: Contract address
        agentId: On-chain agent ID
        network: Network identifier (e.g., "avalanche-fuji:43113")
    """
    contract: str = Field(..., description="Registry contract name")
    address: str = Field(..., description="Contract address")
    agentId: int = Field(..., description="On-chain agent ID")
    network: str = Field(
        default="avalanche-fuji:43113",
        description="Network identifier"
    )


class AgentCard(BaseModel):
    """
    Agent discovery card (A2A protocol)

    Published at /.well-known/agent-card for agent discovery.
    Contains all metadata needed for other agents to interact.

    Attributes:
        agentId: On-chain agent ID (from IdentityRegistry)
        name: Agent display name
        description: What this agent does
        version: Agent version (e.g., "1.0.0")
        domain: Agent domain (e.g., "karma-hello.ultravioletadao.xyz")
        skills: List of available skills
        trustModels: Supported trust mechanisms (e.g., ["erc-8004"])
        paymentMethods: Supported payment protocols (e.g., ["x402-eip3009-GLUE"])
        registrations: On-chain registry registrations
    """
    agentId: int = Field(..., description="On-chain agent ID")
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    version: str = Field(default="1.0.0", description="Agent version")
    domain: str = Field(..., description="Agent domain")
    skills: List[Skill] = Field(default_factory=list, description="Available skills")
    trustModels: List[str] = Field(
        default_factory=lambda: ["erc-8004"],
        description="Trust mechanisms (e.g., erc-8004)"
    )
    paymentMethods: List[str] = Field(
        default_factory=lambda: ["x402-eip3009-GLUE"],
        description="Payment protocols"
    )
    registrations: List[Registration] = Field(
        default_factory=list,
        description="On-chain registrations"
    )

    def find_skill(self, skill_id: str) -> Optional[Skill]:
        """Find skill by ID"""
        for skill in self.skills:
            if skill.skillId == skill_id:
                return skill
        return None

    def to_json(self) -> str:
        """Serialize to JSON for HTTP response"""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "AgentCard":
        """Deserialize from JSON"""
        return cls.model_validate_json(json_str)


# =============================================================================
# A2A SERVER (for Seller Agents)
# =============================================================================

class A2AServer:
    """
    Mixin for agents that sell services

    Provides:
    - AgentCard publication
    - Skill registration
    - Discovery endpoint serving

    Usage:
        class MySellerAgent(ERC8004BaseAgent, A2AServer):
            def __init__(self):
                super().__init__(...)
                self.publish_agent_card()
    """

    def __init__(self, *args, **kwargs):
        """Initialize A2A server capabilities"""
        super().__init__(*args, **kwargs)
        self._agent_card: Optional[AgentCard] = None
        self._skills: List[Skill] = []

    def add_skill(
        self,
        skill_id: str,
        name: str,
        description: str,
        price_amount: str,
        price_currency: str = "GLUE",
        input_schema: Optional[Dict] = None,
        output_schema: Optional[Dict] = None,
        endpoint: Optional[str] = None
    ) -> Skill:
        """
        Register a new skill

        Args:
            skill_id: Unique skill identifier
            name: Human-readable name
            description: What the skill does
            price_amount: Price as string (e.g., "0.01")
            price_currency: Currency code (default: "GLUE")
            input_schema: JSON schema for inputs
            output_schema: JSON schema for outputs
            endpoint: Custom endpoint path

        Returns:
            Skill: Created skill object
        """
        skill = Skill(
            skillId=skill_id,
            name=name,
            description=description,
            price=Price(amount=price_amount, currency=price_currency),
            inputSchema=input_schema or {},
            outputSchema=output_schema or {},
            endpoint=endpoint
        )
        self._skills.append(skill)
        return skill

    def create_agent_card(
        self,
        agent_id: int,
        name: str,
        description: str,
        domain: str,
        version: str = "1.0.0",
        registrations: Optional[List[Registration]] = None
    ) -> AgentCard:
        """
        Create and store AgentCard

        Args:
            agent_id: On-chain agent ID
            name: Agent display name
            description: Agent description
            domain: Agent domain
            version: Agent version
            registrations: On-chain registrations

        Returns:
            AgentCard: Created agent card
        """
        self._agent_card = AgentCard(
            agentId=agent_id,
            name=name,
            description=description,
            version=version,
            domain=domain,
            skills=self._skills,
            registrations=registrations or []
        )
        return self._agent_card

    def publish_agent_card(
        self,
        name: str,
        description: str,
        version: str = "1.0.0"
    ) -> AgentCard:
        """
        Publish AgentCard for discovery

        Creates AgentCard from current agent state (requires ERC8004BaseAgent).

        Args:
            name: Agent display name
            description: What this agent does
            version: Agent version

        Returns:
            AgentCard: Published agent card

        Raises:
            AttributeError: If agent_id or agent_domain not set
        """
        if not hasattr(self, 'agent_id') or not self.agent_id:
            raise AttributeError("agent_id not set - register agent first")
        if not hasattr(self, 'agent_domain'):
            raise AttributeError("agent_domain not set")

        # Build registrations from ERC8004BaseAgent properties
        registrations = []
        if hasattr(self, 'identity_registry_address'):
            registrations.append(Registration(
                contract="IdentityRegistry",
                address=self.identity_registry_address,
                agentId=self.agent_id
            ))

        return self.create_agent_card(
            agent_id=self.agent_id,
            name=name,
            description=description,
            domain=self.agent_domain,
            version=version,
            registrations=registrations
        )

    def get_agent_card(self) -> Optional[AgentCard]:
        """Get published AgentCard"""
        return self._agent_card

    def get_agent_card_json(self) -> str:
        """Get AgentCard as JSON string"""
        if not self._agent_card:
            raise ValueError("AgentCard not published - call publish_agent_card() first")
        return self._agent_card.to_json()


# =============================================================================
# A2A CLIENT (for Buyer Agents)
# =============================================================================

class A2AClient:
    """
    Client for discovering and invoking agent skills

    Features:
    - AgentCard discovery via /.well-known/agent-card
    - Skill invocation with x402 payments
    - Async HTTP operations

    Usage:
        client = A2AClient()
        card = await client.discover("karma-hello.ultravioletadao.xyz")
        result = await client.invoke_skill(
            agent_card=card,
            skill_id="get_logs",
            params={"stream_id": "12345"},
            payment_header="base64-encoded-payment"
        )
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3
    ):
        """
        Initialize A2A client

        Args:
            timeout: HTTP timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.http_client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def discover(self, domain: str, https: bool = True) -> AgentCard:
        """
        Discover agent via AgentCard

        Fetches /.well-known/agent-card from the agent's domain.

        Args:
            domain: Agent domain (e.g., "karma-hello.ultravioletadao.xyz")
            https: Use HTTPS (default: True)

        Returns:
            AgentCard: Agent metadata

        Raises:
            httpx.HTTPStatusError: If request fails
            ValueError: If AgentCard invalid
        """
        protocol = "https" if https else "http"
        url = f"{protocol}://{domain}/.well-known/agent-card"

        response = await self.http_client.get(url)
        response.raise_for_status()

        try:
            return AgentCard.from_json(response.text)
        except Exception as e:
            raise ValueError(f"Invalid AgentCard from {domain}: {e}")

    async def invoke_skill(
        self,
        agent_card: AgentCard,
        skill_id: str,
        params: Optional[Dict[str, Any]] = None,
        payment_header: Optional[str] = None,
        method: str = "POST"
    ) -> httpx.Response:
        """
        Invoke an agent skill

        Args:
            agent_card: Target agent's AgentCard
            skill_id: Skill ID to invoke
            params: Skill input parameters
            payment_header: Base64-encoded X-Payment header value
            method: HTTP method (default: POST)

        Returns:
            httpx.Response: Skill execution result

        Raises:
            ValueError: If skill not found
            httpx.HTTPStatusError: If request fails
        """
        # Find skill
        skill = agent_card.find_skill(skill_id)
        if not skill:
            raise ValueError(
                f"Skill '{skill_id}' not found in {agent_card.name}"
            )

        # Build request URL
        endpoint = skill.get_endpoint()
        url = f"https://{agent_card.domain}{endpoint}"

        # Build headers
        headers = {"Content-Type": "application/json"}
        if payment_header:
            headers["X-Payment"] = payment_header

        # Send request
        if method.upper() == "GET":
            response = await self.http_client.get(url, headers=headers)
        elif method.upper() == "POST":
            response = await self.http_client.post(
                url,
                headers=headers,
                json=params or {}
            )
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response

    async def invoke_skill_with_payment(
        self,
        agent_card: AgentCard,
        skill_id: str,
        params: Optional[Dict[str, Any]],
        x402_client: Any,  # X402Client instance
        buyer_address: str,
        buyer_private_key: str
    ) -> tuple:
        """
        Invoke skill with automatic x402 payment

        Convenience method that creates payment and invokes skill.

        Args:
            agent_card: Target agent's AgentCard
            skill_id: Skill to invoke
            params: Skill parameters
            x402_client: X402Client instance for payment
            buyer_address: Buyer's wallet address
            buyer_private_key: Buyer's private key

        Returns:
            tuple: (response, settlement_result)
        """
        # Find skill
        skill = agent_card.find_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill '{skill_id}' not found")

        # Get seller address from registrations
        seller_address = None
        for reg in agent_card.registrations:
            if reg.contract == "IdentityRegistry":
                # In a real implementation, query the contract for the agent's address
                # For now, this is a placeholder
                pass

        if not seller_address:
            raise ValueError("Could not determine seller address from AgentCard")

        # Build URL
        endpoint = skill.get_endpoint()
        url = f"https://{agent_card.domain}{endpoint}"

        # Use x402_client to buy with payment
        response, settlement = await x402_client.buy_with_payment(
            seller_url=url,
            seller_address=seller_address,
            amount_glue=skill.price.amount,
            method="POST",
            json_data=params
        )

        return response, settlement


# Convenience function

async def discover_agent(domain: str) -> AgentCard:
    """
    Convenience function to discover an agent

    Args:
        domain: Agent domain

    Returns:
        AgentCard: Agent metadata

    Example:
        >>> card = await discover_agent("karma-hello.ultravioletadao.xyz")
        >>> print(card.name)
    """
    async with A2AClient() as client:
        return await client.discover(domain)


# Example usage
if __name__ == "__main__":
    import asyncio

    async def main():
        print("=" * 70)
        print("A2A Protocol Example")
        print("=" * 70)
        print()

        # Example 1: Create AgentCard as a seller
        print("[1] Creating AgentCard for seller agent...")

        # Simulate A2AServer usage
        class MockAgent:
            agent_id = 1
            agent_domain = "karma-hello.ultravioletadao.xyz"
            identity_registry_address = "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618"

        # Mix in A2AServer
        class SellerAgent(MockAgent, A2AServer):
            pass

        seller = SellerAgent()

        # Add skills
        seller.add_skill(
            skill_id="get_logs",
            name="Get Stream Logs",
            description="Retrieve chat logs from a specific stream",
            price_amount="0.01",
            input_schema={
                "type": "object",
                "properties": {
                    "stream_id": {"type": "string"}
                }
            }
        )

        # Publish AgentCard
        card = seller.publish_agent_card(
            name="Karma-Hello Stream Logs Seller",
            description="Sells Twitch stream chat logs and events"
        )

        print(f"    Agent ID: {card.agentId}")
        print(f"    Name: {card.name}")
        print(f"    Skills: {len(card.skills)}")
        print(f"    Domain: {card.domain}")
        print()

        # Example 2: Serialize AgentCard
        print("[2] AgentCard JSON:")
        print(card.to_json())
        print()

        # Example 3: Client discovery (simulated)
        print("[3] A2A Client usage (simulated):")
        print("    client = A2AClient()")
        print(f"    card = await client.discover('{card.domain}')")
        print(f"    skill = card.find_skill('get_logs')")
        print(f"    response = await client.invoke_skill(...)")

        print()
        print("=" * 70)
        print("Example complete!")
        print("=" * 70)

    asyncio.run(main())
