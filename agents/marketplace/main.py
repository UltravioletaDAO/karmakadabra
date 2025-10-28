"""
Karmacadabra Marketplace API
Central discovery service for 48 user agents + 5 system agents

Serves static agent cards and profiles for discovery
Agents can be spun up on-demand when needed

Sprint 4, Task 1: Central Marketplace API
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).parent.parent.parent
PROFILES_DIR = BASE_DIR / "demo/profiles"
CARDS_DIR = BASE_DIR / "demo/cards"

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Karmacadabra Marketplace",
    description="Central discovery service for AI agent marketplace",
    version="1.0.0"
)

# CORS for web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Data Loading
# ============================================================================

def load_profiles() -> Dict[str, Dict]:
    """Load all user profiles"""
    profiles = {}
    for profile_file in PROFILES_DIR.glob("*.json"):
        with open(profile_file, 'r', encoding='utf-8') as f:
            profile = json.load(f)
            username = profile_file.stem
            profiles[username] = profile
    return profiles


def load_agent_cards() -> Dict[str, Dict]:
    """Load all agent cards"""
    cards = {}
    for card_file in CARDS_DIR.glob("*.json"):
        with open(card_file, 'r', encoding='utf-8') as f:
            card = json.load(f)
            username = card_file.stem
            cards[username] = card
    return cards


# Cache data on startup
PROFILES = load_profiles()
CARDS = load_agent_cards()


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/")
async def root():
    """API information"""
    return {
        "name": "Karmacadabra Marketplace",
        "version": "1.0.0",
        "description": "Central discovery service for AI agent marketplace",
        "total_agents": len(CARDS),
        "endpoints": {
            "agents": "/agents - List all agents",
            "agent_details": "/agents/{username} - Get agent details",
            "agent_card": "/agents/{username}/card - Get A2A agent card",
            "search": "/search?q=keyword - Search agents",
            "stats": "/stats - Marketplace statistics"
        }
    }


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "agents_loaded": len(CARDS)
    }


@app.get("/agents")
async def list_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    engagement: Optional[str] = Query(None, description="Filter by engagement level: low, medium, high")
):
    """List all agents with pagination"""

    agents = []
    for username, card in CARDS.items():
        profile = PROFILES.get(username, {})

        # Filter by engagement if specified
        if engagement:
            profile_engagement = profile.get("interaction_style", {}).get("engagement_level", "").lower()
            if profile_engagement != engagement.lower():
                continue

        agents.append({
            "username": username,
            "name": card.get("agent", {}).get("name"),
            "description": card.get("agent", {}).get("description"),
            "services_count": len(card.get("services", [])),
            "engagement_level": profile.get("interaction_style", {}).get("engagement_level", "unknown"),
            "message_count": profile.get("data_coverage", {}).get("message_count", 0),
            "endpoint": card.get("contact", {}).get("endpoint"),
            "tags": card.get("discovery", {}).get("tags", [])
        })

    # Sort by message count (most active first)
    agents.sort(key=lambda x: x["message_count"], reverse=True)

    # Paginate
    total = len(agents)
    paginated = agents[skip:skip + limit]

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "agents": paginated
    }


@app.get("/agents/{username}")
async def get_agent(username: str):
    """Get detailed information about a specific agent"""

    if username not in CARDS:
        raise HTTPException(status_code=404, detail=f"Agent '{username}' not found")

    card = CARDS[username]
    profile = PROFILES.get(username, {})

    return {
        "username": username,
        "card": card,
        "profile": profile,
        "metadata": {
            "card_available": True,
            "profile_available": username in PROFILES,
            "last_updated": datetime.utcnow().isoformat()
        }
    }


@app.get("/agents/{username}/card")
async def get_agent_card(username: str):
    """Get A2A protocol agent card for discovery"""

    if username not in CARDS:
        raise HTTPException(status_code=404, detail=f"Agent '{username}' not found")

    return CARDS[username]


@app.get("/search")
async def search_agents(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=50)
):
    """Search agents by keywords (skills, interests, tags)"""

    query = q.lower()
    results = []

    for username, card in CARDS.items():
        profile = PROFILES.get(username, {})

        # Search in tags
        tags = card.get("discovery", {}).get("tags", [])
        if any(query in tag.lower() for tag in tags):
            score = 3  # High priority for tag matches
        else:
            score = 0

        # Search in description
        description = card.get("agent", {}).get("description", "").lower()
        if query in description:
            score += 2

        # Search in service names
        services = card.get("services", [])
        for service in services:
            service_name = service.get("name", "").lower()
            if query in service_name:
                score += 1

        # Search in interests
        interests = profile.get("interests", [])
        for interest in interests:
            domain = interest.get("domain", "").lower()
            if query in domain:
                score += 2

        if score > 0:
            results.append({
                "username": username,
                "name": card.get("agent", {}).get("name"),
                "description": card.get("agent", {}).get("description"),
                "services_count": len(services),
                "relevance_score": score,
                "endpoint": card.get("contact", {}).get("endpoint"),
                "matching_tags": [tag for tag in tags if query in tag.lower()]
            })

    # Sort by relevance
    results.sort(key=lambda x: x["relevance_score"], reverse=True)

    return {
        "query": q,
        "total_results": len(results),
        "results": results[:limit]
    }


@app.get("/stats")
async def get_stats():
    """Get marketplace statistics"""

    # Engagement distribution
    engagement_counts = {"low": 0, "medium": 0, "high": 0, "unknown": 0}
    for profile in PROFILES.values():
        level = profile.get("interaction_style", {}).get("engagement_level", "unknown").lower()
        engagement_counts[level] = engagement_counts.get(level, 0) + 1

    # Service type distribution
    service_counts = {}
    for card in CARDS.values():
        for service in card.get("services", []):
            service_name = service.get("name", "Unknown")
            service_counts[service_name] = service_counts.get(service_name, 0) + 1

    # Top services
    top_services = sorted(service_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Tag distribution
    tag_counts = {}
    for card in CARDS.values():
        for tag in card.get("discovery", {}).get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:15]

    # Calculate network capacity
    n = len(CARDS)
    potential_trades = n * (n - 1)

    return {
        "total_agents": len(CARDS),
        "total_profiles": len(PROFILES),
        "engagement_distribution": engagement_counts,
        "top_services": [{"name": name, "agent_count": count} for name, count in top_services],
        "top_tags": [{"tag": tag, "agent_count": count} for tag, count in top_tags],
        "network_capacity": {
            "total_agents": n,
            "potential_connections": potential_trades,
            "description": f"{n} agents can form {potential_trades:,} potential trade connections"
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/categories")
async def get_categories():
    """Get all available categories and their agent counts"""

    categories = {}
    for card in CARDS.values():
        for category in card.get("discovery", {}).get("categories", []):
            categories[category] = categories.get(category, 0) + 1

    return {
        "total_categories": len(categories),
        "categories": [
            {"name": name, "agent_count": count}
            for name, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)
        ]
    }


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=9000,
        reload=True
    )
