#!/usr/bin/env python3
"""
Demo: Agent Card con Endpoints (EIP-8004 Compliant)

Demuestra cómo se verá un agent card completo con el nuevo campo endpoints.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shared.a2a_protocol import AgentCard, Endpoint, Skill, Price, Registration

# Crear un agent card de ejemplo para karma-hello
agent_card = AgentCard(
    agentId=2,
    name="Karma Hello",
    description="Twitch stream chat log seller - provides real-time and historical chat data",
    version="1.0.0",
    domain="karma-hello.karmacadabra.ultravioletadao.xyz",

    # ✅ NUEVO: Endpoints array (EIP-8004 compliant)
    endpoints=[
        Endpoint(
            name="A2A",
            endpoint="https://karma-hello.karmacadabra.ultravioletadao.xyz",
            version="1.0"
        ),
        Endpoint(
            name="agentWallet",
            endpoint="0x2C3e071df446B25B821F59425152838ae4931E75"
        )
    ],

    # Skills que el agente ofrece
    skills=[
        Skill(
            skillId="get-chat-logs",
            name="Get Chat Logs",
            description="Retrieve chat logs for a specific date",
            price=Price(amount="0.01", currency="GLUE"),
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "format": "date"},
                    "username": {"type": "string", "optional": True}
                },
                "required": ["date"]
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "logs": {"type": "array"},
                    "count": {"type": "integer"}
                }
            }
        )
    ],

    # Trust models y payment methods
    trustModels=["erc-8004"],
    paymentMethods=["x402-eip3009-GLUE"],

    # Registros on-chain
    registrations=[
        Registration(
            contract="IdentityRegistry",
            address="0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618",
            agentId=2,
            network="avalanche-fuji:43113"
        )
    ]
)

# Mostrar el agent card en formato JSON
print("=" * 80)
print("AGENT CARD (EIP-8004 COMPLIANT)")
print("=" * 80)
print("")
print(agent_card.to_json())
print("")
print("=" * 80)
print("KEY FEATURES:")
print("=" * 80)
print("")
print("✅ endpoints array incluido (EIP-8004 requirement)")
print("   - A2A endpoint: URL base del agente")
print("   - agentWallet: Dirección del wallet on-chain")
print("")
print("✅ skills array con pricing y schemas")
print("✅ trustModels: erc-8004 reputation system")
print("✅ paymentMethods: x402 gasless payments")
print("✅ registrations: on-chain identity registry")
print("")
print("📍 Publicado en: https://karma-hello.karmacadabra.ultravioletadao.xyz/.well-known/agent-card")
print("")
