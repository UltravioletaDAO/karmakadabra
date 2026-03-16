"""
Acontext Injector for KK V2 Swarm

Prepares an agent's Acontext session by injecting its AutoJob Skill DNA 
before it connects to IRC or starts task execution. This gives the agent 
self-awareness of its actual performance capabilities based on EM history.
"""

import json
import logging
from pathlib import Path

from .acontext_client import KKAcontextClient

logger = logging.getLogger("kk.acontext_injector")

def inject_autojob_profile(
    acontext_client: KKAcontextClient, 
    agent_name: str, 
    agent_id: int, 
    session_id: str,
    autojob_dir: str = "/Users/clawdbot/clawd/projects/autojob/workers"
) -> bool:
    """
    Load an agent's AutoJob Skill DNA and inject it as a system prompt
    into their Acontext session.
    """
    if not acontext_client.available:
        logger.warning(f"Acontext unavailable. Skipping injection for {agent_name}.")
        return False

    profile_path = Path(autojob_dir) / f"{agent_id}.json"
    
    if not profile_path.exists():
        logger.info(f"No AutoJob profile found for agent {agent_id} ({agent_name}).")
        # Inject a default awareness
        content = (
            f"You are {agent_name} (ID: {agent_id}). You do not currently have "
            "an AutoJob Skill DNA profile. Focus on completing tasks to build "
            "your verified performance history."
        )
    else:
        try:
            with open(profile_path, "r") as f:
                dna = json.load(f)
            
            skills = dna.get("technical_skills", {})
            seniority = dna.get("seniority_signal", "UNKNOWN")
            confidence = dna.get("evidence_weight", 0.0)
            
            # Format the DNA into a readable prompt injection
            content = (
                f"You are {agent_name} (ID: {agent_id}). Here is your current "
                f"AutoJob Skill DNA based on your past Execution Market performance:\n\n"
                f"Overall Seniority: {seniority}\n"
                f"Evidence Confidence: {confidence * 100:.1f}%\n\n"
                "Verified Skills:\n"
            )
            for skill, level in skills.items():
                content += f"- {skill}: {level}\n"
                
            content += (
                "\nUse this knowledge of your own capabilities when volunteering "
                "for tasks in IRC or collaborating with the Swarm Coordinator."
            )
        except Exception as e:
            logger.error(f"Failed to parse AutoJob profile for {agent_name}: {e}")
            return False

    # Store the injection as a system message in Acontext
    success = acontext_client.store_interaction(
        session_id=session_id,
        role="system",
        content=content,
        metadata={"type": "autojob_injection"}
    )
    
    if success:
        logger.info(f"Successfully injected AutoJob profile for {agent_name} into session {session_id}")
    return success
