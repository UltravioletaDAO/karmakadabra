#!/usr/bin/env python3
"""
Simple Demo: Client Agent Buyer-Seller Pattern

Demonstrates:
1. Client agent buys chat logs from karma-hello (0.01 GLUE)
2. Client agent buys skill profile from skill-extractor (0.05 GLUE)
   - skill-extractor buys logs from karma-hello (0.01 GLUE)
3. Client agent buys personality profile from voice-extractor (0.05 GLUE)
   - voice-extractor buys logs from karma-hello (0.01 GLUE)

This shows the complete value chain and buyer+seller pattern.
"""

import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def print_banner():
    """Print demo banner"""
    print("\n" + "=" * 80)
    print("   KARMACADABRA CLIENT AGENT DEMO")
    print("   Buyer-Seller Pattern in Action")
    print("=" * 80)
    print()
    print("This demo shows:")
    print("  1. Client buys chat logs from karma-hello (0.01 GLUE)")
    print("  2. Client buys skill profile from skill-extractor (0.05 GLUE)")
    print("     └─> skill-extractor buys logs from karma-hello (0.01 GLUE)")
    print("  3. Client buys personality from voice-extractor (0.05 GLUE)")
    print("     └─> voice-extractor buys logs from karma-hello (0.01 GLUE)")
    print()
    print("  Total client spent: 0.11 GLUE")
    print("  karma-hello earned: 0.03 GLUE")
    print("  skill-extractor profit: 0.04 GLUE (0.05 revenue - 0.01 cost)")
    print("  voice-extractor profit: 0.04 GLUE (0.05 revenue - 0.01 cost)")
    print()
    print("=" * 80)
    print()

class SimpleDemo:
    """Simplified demo without full agent infrastructure"""

    def __init__(self):
        self.username = "0xultravioleta"  # Demo user
        self.results = {}

    async def step1_buy_logs(self):
        """Step 1: Client buys logs from karma-hello"""
        print("\n[STEP 1] Client → karma-hello (buy chat logs)")
        print("-" * 80)

        # In real implementation, this would be an HTTP request with x402 payment
        # For demo, we simulate the transaction
        print(f"  Request: GET /logs/{self.username}")
        print(f"  Payment: 0.01 GLUE via x402")
        print(f"  Status: ✅ Simulated purchase")

        # Simulate response
        self.results['logs'] = {
            'username': self.username,
            'message_count': 1234,
            'date_range': '2024-10-01 to 2024-10-24',
            'sample': '[10/24/2024 3:00 PM] 0xultravioleta: building agent economy...'
        }

        print(f"  Response: {self.results['logs']['message_count']} messages")
        print(f"  karma-hello balance: +0.01 GLUE")

    async def step2_buy_skills(self):
        """Step 2: Client buys skill profile from skill-extractor"""
        print("\n[STEP 2] Client → skill-extractor (buy skill profile)")
        print("-" * 80)

        print(f"  Request: POST /extract-skills")
        print(f"  Payment: 0.05 GLUE via x402")
        print(f"  Payload: {{'username': '{self.username}', 'level': 'complete'}}")

        # Skill-extractor now buys logs from karma-hello
        print(f"\n  [STEP 2.1] skill-extractor → karma-hello (buy logs)")
        print(f"    Request: GET /logs/{self.username}")
        print(f"    Payment: 0.01 GLUE via x402")
        print(f"    Status: ✅ Simulated purchase")
        print(f"    karma-hello balance: +0.01 GLUE (total: 0.02 GLUE)")

        print(f"\n  [STEP 2.2] skill-extractor processes logs with CrewAI")
        print(f"    Analysis: Extracting skills, interests, tools...")
        print(f"    Status: ✅ Simulated analysis")

        # Simulate response
        self.results['skills'] = {
            'interests': [
                {'domain': 'Blockchain Development', 'score': 0.87},
                {'domain': 'AI Agent Systems', 'score': 0.82},
                {'domain': 'Decentralized Identity', 'score': 0.76}
            ],
            'skills': [
                {'name': 'Solidity', 'level': 'advanced', 'score': 0.84},
                {'name': 'Python', 'level': 'advanced', 'score': 0.89},
                {'name': 'Smart Contract Design', 'level': 'expert', 'score': 0.91}
            ],
            'monetization': ['Smart Contract Auditing', 'Agent System Consulting']
        }

        print(f"  Response: {len(self.results['skills']['skills'])} skills identified")
        print(f"  skill-extractor profit: +0.04 GLUE (0.05 revenue - 0.01 cost)")

    async def step3_buy_personality(self):
        """Step 3: Client buys personality profile from voice-extractor"""
        print("\n[STEP 3] Client → voice-extractor (buy personality profile)")
        print("-" * 80)

        print(f"  Request: POST /extract-voice")
        print(f"  Payment: 0.05 GLUE via x402")
        print(f"  Payload: {{'username': '{self.username}', 'level': 'complete'}}")

        # Voice-extractor now buys logs from karma-hello
        print(f"\n  [STEP 3.1] voice-extractor → karma-hello (buy logs)")
        print(f"    Request: GET /logs/{self.username}")
        print(f"    Payment: 0.01 GLUE via x402")
        print(f"    Status: ✅ Simulated purchase")
        print(f"    karma-hello balance: +0.01 GLUE (total: 0.03 GLUE)")

        print(f"\n  [STEP 3.2] voice-extractor processes logs with CrewAI")
        print(f"    Analysis: Extracting tone, style, patterns...")
        print(f"    Status: ✅ Simulated analysis")

        # Simulate response
        self.results['personality'] = {
            'tone': 'technical',
            'style': 'concise',
            'communication_pattern': 'direct_and_informative',
            'emoji_usage': 'minimal',
            'personality_type': 'builder'
        }

        print(f"  Response: Personality type '{self.results['personality']['personality_type']}'")
        print(f"  voice-extractor profit: +0.04 GLUE (0.05 revenue - 0.01 cost)")

    def print_summary(self):
        """Print final summary"""
        print("\n" + "=" * 80)
        print("DEMO SUMMARY")
        print("=" * 80)

        print("\n📊 Economic Summary:")
        print(f"  Client spent: 0.11 GLUE")
        print(f"    - karma-hello: 0.01 GLUE")
        print(f"    - skill-extractor: 0.05 GLUE")
        print(f"    - voice-extractor: 0.05 GLUE")

        print(f"\n  karma-hello earned: 0.03 GLUE")
        print(f"    - Direct sale to client: 0.01 GLUE")
        print(f"    - Sale to skill-extractor: 0.01 GLUE")
        print(f"    - Sale to voice-extractor: 0.01 GLUE")

        print(f"\n  skill-extractor profit: 0.04 GLUE (400% margin)")
        print(f"    Revenue: 0.05 GLUE | Cost: 0.01 GLUE")

        print(f"\n  voice-extractor profit: 0.04 GLUE (400% margin)")
        print(f"    Revenue: 0.05 GLUE | Cost: 0.01 GLUE")

        print("\n📦 Data Acquired by Client:")
        print(f"  - Chat logs: {self.results['logs']['message_count']} messages")
        print(f"  - Skills: {len(self.results['skills']['skills'])} identified")
        print(f"  - Interests: {len(self.results['skills']['interests'])} domains")
        print(f"  - Personality: {self.results['personality']['personality_type']}")

        print("\n✅ Value Chain Demonstrated:")
        print("  Raw Data (karma-hello) → Processing (skill/voice extractors) → Insights (client)")

        print("\n" + "=" * 80)

    async def run(self):
        """Run complete demo"""
        print_banner()

        await self.step1_buy_logs()
        await self.step2_buy_skills()
        await self.step3_buy_personality()

        self.print_summary()

        print("\n💡 To Run Real Demo:")
        print("  1. Ensure agents are funded and registered:")
        print("     python scripts/check_system_ready.py")
        print()
        print("  2. Start service agents (in separate terminals):")
        print("     cd agents/karma-hello && python main.py")
        print("     cd agents/skill-extractor && python main.py")
        print("     cd agents/voice-extractor && python main.py")
        print()
        print("  3. Run client agent:")
        print("     cd client-agents/template && python main.py")
        print()

def main():
    demo = SimpleDemo()
    asyncio.run(demo.run())

if __name__ == "__main__":
    main()
