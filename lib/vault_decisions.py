"""
Vault-based decision engine for KK agents.

Agents read the shared vault state to prioritize their actions on each
heartbeat. Instead of blindly browsing EM every cycle, they check what
peers are doing and decide whether to buy, process, or sell.

Usage:
    from lib.vault_decisions import prioritize_actions
    from lib.vault_sync import VaultSync

    vault = VaultSync("/app/vault", "kk-skill-extractor")
    priorities = prioritize_actions(vault, "kk-skill-extractor")
    # priorities = ["buy", "process", "sell"] or ["process", "sell"] etc.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Agent roles for decision context
AGENT_ROLES = {
    "kk-karma-hello": "producer",
    "kk-skill-extractor": "refiner",
    "kk-voice-extractor": "refiner",
    "kk-soul-extractor": "aggregator",
    "kk-coordinator": "orchestrator",
    "kk-validator": "validator",
}

# Upstream dependencies: who each agent buys from
UPSTREAM = {
    "kk-skill-extractor": ["kk-karma-hello"],
    "kk-voice-extractor": ["kk-karma-hello"],
    "kk-soul-extractor": ["kk-skill-extractor", "kk-voice-extractor"],
}

# Default action = community buyer
DEFAULT_ROLE = "buyer"


def prioritize_actions(vault, agent_name: str) -> list[str]:
    """Decide action priority based on vault state.

    Reads peer states and supply chain status to determine what the
    agent should focus on this heartbeat.

    Returns:
        Ordered list of action priorities. First item is highest priority.
        Possible values: "buy", "process", "sell", "idle", "monitor"
    """
    role = AGENT_ROLES.get(agent_name, DEFAULT_ROLE)

    if role == "orchestrator":
        return ["monitor"]
    if role == "validator":
        return ["validate"]
    if role == "producer":
        return _prioritize_producer(vault, agent_name)
    if role in ("refiner", "aggregator"):
        return _prioritize_refiner(vault, agent_name)

    # Community buyers
    return _prioritize_buyer(vault, agent_name)


def _prioritize_producer(vault, agent_name: str) -> list[str]:
    """Producer (karma-hello): always collect + publish + fulfill."""
    # Check if there are buyers waiting (from supply chain status)
    chain_status = vault.read_supply_chain_status()

    # If extractors are idle/waiting, prioritize publishing
    extractors_waiting = any(
        "idle" in chain_status.get(name, "").lower()
        or "waiting" in chain_status.get(name, "").lower()
        for name in ["kk-skill-extractor", "kk-voice-extractor"]
    )

    if extractors_waiting:
        logger.info(f"[{agent_name}] Extractors waiting — prioritize publish+fulfill")
        return ["publish", "fulfill", "collect", "sell"]

    return ["collect", "publish", "fulfill", "sell"]


def _prioritize_refiner(vault, agent_name: str) -> list[str]:
    """Refiner/aggregator: buy if upstream has data, process if local data exists, sell if products ready."""
    upstream_agents = UPSTREAM.get(agent_name, [])
    priorities = []

    # Check if upstream has offerings
    has_upstream_data = False
    for upstream in upstream_agents:
        offerings = vault.read_peer_offerings(upstream)
        if offerings:
            has_upstream_data = True
            logger.info(
                f"[{agent_name}] Upstream {upstream} has {len(offerings)} offerings — prioritize buy"
            )
            break

    # Check upstream status from supply chain
    chain_status = vault.read_supply_chain_status()
    upstream_active = any(
        "publish" in chain_status.get(name, "").lower()
        or "active" in chain_status.get(name, "").lower()
        for name in upstream_agents
    )

    if has_upstream_data or upstream_active:
        priorities.append("buy")

    # Always try to process local data
    priorities.append("process")

    # Sell if we have products
    priorities.append("sell")

    if not priorities:
        priorities = ["buy", "process", "sell"]

    return priorities


def _prioritize_buyer(vault, agent_name: str) -> list[str]:
    """Community buyer: check offerings, buy what's available."""
    # Check what's available from the supply chain
    chain_status = vault.read_supply_chain_status()

    # Check karma-hello offerings specifically
    offerings = vault.read_peer_offerings("kk-karma-hello")
    if offerings:
        logger.info(
            f"[{agent_name}] karma-hello has {len(offerings)} offerings — buy"
        )
        return ["buy"]

    # Check if any seller has active products
    has_active_sellers = any(
        "publish" in status.lower() or "active" in status.lower()
        for name, status in chain_status.items()
        if name != agent_name
    )

    if has_active_sellers:
        return ["buy"]

    return ["buy", "idle"]
