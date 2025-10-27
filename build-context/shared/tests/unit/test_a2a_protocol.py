#!/usr/bin/env python3
"""
Unit tests for a2a_protocol.py - Agent-to-Agent communication
"""

import pytest
import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from a2a_protocol import (
    Price, Skill, Registration, AgentCard,
    A2AServer, A2AClient
)


@pytest.mark.unit
class TestPrice:
    """Test suite for Price model"""

    def test_price_creation(self):
        """Test Price model initialization"""
        price = Price(amount="0.01", currency="GLUE")
        assert price.amount == "0.01"
        assert price.currency == "GLUE"

    def test_price_to_glue_units(self):
        """Test conversion to GLUE units"""
        price = Price(amount="0.01", currency="GLUE")
        assert price.to_glue_units() == 10000

    def test_price_from_glue_units(self):
        """Test creation from GLUE units"""
        price = Price.from_glue_units(10000)
        assert price.amount == "0.01"


@pytest.mark.unit
class TestSkill:
    """Test suite for Skill model"""

    def test_skill_creation(self):
        """Test Skill model initialization"""
        skill = Skill(
            skillId="test_skill",
            name="Test Skill",
            description="Test description",
            price=Price(amount="0.01", currency="GLUE")
        )

        assert skill.skillId == "test_skill"
        assert skill.name == "Test Skill"
        assert skill.price.amount == "0.01"

    def test_skill_default_endpoint(self):
        """Test default endpoint generation"""
        skill = Skill(
            skillId="get_logs",
            name="Get Logs",
            description="Get stream logs",
            price=Price(amount="0.01", currency="GLUE")
        )

        assert skill.get_endpoint() == "/api/get_logs"

    def test_skill_custom_endpoint(self):
        """Test custom endpoint"""
        skill = Skill(
            skillId="get_logs",
            name="Get Logs",
            description="Get stream logs",
            price=Price(amount="0.01", currency="GLUE"),
            endpoint="/custom/logs"
        )

        assert skill.get_endpoint() == "/custom/logs"


@pytest.mark.unit
class TestRegistration:
    """Test suite for Registration model"""

    def test_registration_creation(self):
        """Test Registration model initialization"""
        reg = Registration(
            contract="IdentityRegistry",
            address="0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618",
            agentId=1
        )

        assert reg.contract == "IdentityRegistry"
        assert reg.address == "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618"
        assert reg.agentId == 1
        assert reg.network == "avalanche-fuji:43113"  # Default


@pytest.mark.unit
class TestAgentCard:
    """Test suite for AgentCard model"""

    def test_agent_card_creation(self, sample_agent_card):
        """Test AgentCard initialization from dict"""
        card = AgentCard(**sample_agent_card)

        assert card.agentId == 1
        assert card.name == "Test Agent"
        assert card.domain == "test-agent.ultravioletadao.xyz"
        assert len(card.skills) == 1
        assert "erc-8004" in card.trustModels
        assert "x402-eip3009-GLUE" in card.paymentMethods

    def test_agent_card_find_skill(self, sample_agent_card):
        """Test finding skill by ID"""
        card = AgentCard(**sample_agent_card)

        skill = card.find_skill("test_skill")
        assert skill is not None
        assert skill.skillId == "test_skill"

        # Test skill not found
        missing_skill = card.find_skill("nonexistent")
        assert missing_skill is None

    def test_agent_card_json_serialization(self, sample_agent_card):
        """Test JSON serialization"""
        card = AgentCard(**sample_agent_card)

        # Serialize
        json_str = card.to_json()
        assert isinstance(json_str, str)

        # Deserialize
        card2 = AgentCard.from_json(json_str)
        assert card2.agentId == card.agentId
        assert card2.name == card.name
        assert len(card2.skills) == len(card.skills)


@pytest.mark.unit
class TestA2AServer:
    """Test suite for A2AServer mixin"""

    def test_add_skill(self):
        """Test adding skills to server"""
        # Mock agent with required attributes
        class MockAgent(A2AServer):
            def __init__(self):
                self.agent_id = 1
                self.agent_domain = "test.ultravioletadao.xyz"
                self.identity_registry_address = "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618"
                super().__init__()

        agent = MockAgent()

        # Add skill
        skill = agent.add_skill(
            skill_id="test_skill",
            name="Test Skill",
            description="Test description",
            price_amount="0.01"
        )

        assert skill.skillId == "test_skill"
        assert skill.name == "Test Skill"
        assert skill.price.amount == "0.01"
        assert len(agent._skills) == 1

    def test_publish_agent_card(self):
        """Test publishing AgentCard"""
        class MockAgent(A2AServer):
            def __init__(self):
                self.agent_id = 1
                self.agent_domain = "test.ultravioletadao.xyz"
                self.identity_registry_address = "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618"
                super().__init__()

        agent = MockAgent()

        # Add skill
        agent.add_skill(
            skill_id="get_data",
            name="Get Data",
            description="Retrieve data",
            price_amount="0.01"
        )

        # Publish card
        card = agent.publish_agent_card(
            name="Test Agent",
            description="Test agent description"
        )

        assert card.agentId == 1
        assert card.name == "Test Agent"
        assert card.domain == "test.ultravioletadao.xyz"
        assert len(card.skills) == 1
        assert len(card.registrations) == 1

    def test_get_agent_card_json(self):
        """Test getting AgentCard as JSON"""
        class MockAgent(A2AServer):
            def __init__(self):
                self.agent_id = 1
                self.agent_domain = "test.ultravioletadao.xyz"
                self.identity_registry_address = "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618"
                super().__init__()

        agent = MockAgent()
        agent.add_skill("test", "Test", "Test skill", "0.01")
        agent.publish_agent_card("Test", "Test agent")

        json_str = agent.get_agent_card_json()
        assert isinstance(json_str, str)

        # Verify valid JSON
        data = json.loads(json_str)
        assert data["agentId"] == 1
        assert data["name"] == "Test"

    def test_publish_without_registration_fails(self):
        """Test publishing without agent_id fails"""
        class MockAgent(A2AServer):
            def __init__(self):
                super().__init__()

        agent = MockAgent()

        with pytest.raises(AttributeError, match="agent_id not set"):
            agent.publish_agent_card("Test", "Test agent")


@pytest.mark.unit
class TestA2AClient:
    """Test suite for A2AClient"""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test A2AClient initialization"""
        client = A2AClient()
        assert client.timeout == 30.0
        assert client.max_retries == 3
        await client.close()

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test A2AClient as context manager"""
        async with A2AClient() as client:
            assert client.http_client is not None
