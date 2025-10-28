"""
Level 2 Integration Tests - Sprint 2 Agents

Tests agents as running HTTP servers with local data.
No payment verification, no blockchain transactions.

Usage:
    python test_integration_level2.py --agent karma-hello
    python test_integration_level2.py --all
"""

import asyncio
import httpx
import sys
import subprocess
import time
import signal
from typing import Optional, Dict, Any
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass


# ============================================================================
# Agent Configuration
# ============================================================================

AGENTS = {
    "karma-hello": {
        "name": "Karma-Hello Agent",
        "port": 8002,
        "dir": "karma-hello-agent",
        "endpoints": ["/", "/health", "/.well-known/agent-card"]
    },
    "abracadabra": {
        "name": "Abracadabra Agent",
        "port": 8003,
        "dir": "abracadabra-agent",
        "endpoints": ["/", "/health", "/.well-known/agent-card"]
    },
    "voice-extractor": {
        "name": "Voice-Extractor Agent",
        "port": 8005,
        "dir": "voice-extractor-agent",
        "endpoints": ["/", "/health", "/.well-known/agent-card"]
    },
    "skill-extractor": {
        "name": "Skill-Extractor Agent",
        "port": 8085,
        "dir": "skill-extractor-agent",
        "endpoints": ["/", "/health", "/.well-known/agent-card"]
    }
}


# ============================================================================
# Test Functions
# ============================================================================

async def test_health_endpoint(base_url: str) -> bool:
    """Test / and /health endpoints"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Test root endpoint
            response = await client.get(f"{base_url}/")
            if response.status_code != 200:
                print(f"      ❌ Root endpoint returned {response.status_code}")
                return False

            data = response.json()
            if "service" not in data or "status" not in data:
                print(f"      ❌ Root endpoint missing required fields")
                return False

            print(f"      ✅ Health endpoint: {data.get('status')}")
            return True
    except Exception as e:
        print(f"      ❌ Health endpoint error: {e}")
        return False


async def test_agent_card(base_url: str) -> bool:
    """Test /.well-known/agent-card endpoint"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/.well-known/agent-card")
            if response.status_code != 200:
                print(f"      ❌ AgentCard returned {response.status_code}")
                return False

            card = response.json()

            # Verify required fields
            required = ["schema_version", "name", "description", "skills", "payment_methods"]
            missing = [f for f in required if f not in card]

            if missing:
                print(f"      ❌ AgentCard missing fields: {missing}")
                return False

            print(f"      ✅ AgentCard: {card.get('name')} ({len(card.get('skills', []))} skills)")
            return True
    except Exception as e:
        print(f"      ❌ AgentCard error: {e}")
        return False


async def wait_for_server(base_url: str, max_retries: int = 30) -> bool:
    """Wait for server to be ready"""
    for i in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{base_url}/health")
                if response.status_code == 200:
                    return True
        except:
            pass
        await asyncio.sleep(1)
    return False


async def test_agent(agent_key: str, agent_config: Dict[str, Any]) -> Dict[str, Any]:
    """Test a single agent"""
    print(f"\n{'='*60}")
    print(f"  Testing {agent_config['name']}")
    print(f"{'='*60}")

    base_url = f"http://localhost:{agent_config['port']}"
    agent_dir = agent_config['dir']

    # Start the agent server
    print(f"\n   🚀 Starting {agent_config['name']}...")
    print(f"      Port: {agent_config['port']}")
    print(f"      Directory: {agent_dir}")

    # Check if agent main.py exists
    main_file = Path(agent_dir) / "main.py"
    if not main_file.exists():
        print(f"      ❌ main.py not found in {agent_dir}")
        return {"agent": agent_key, "status": "ERROR", "error": "main.py not found"}

    # Start server process
    try:
        # Use subprocess instead of background process for better control
        if sys.platform == 'win32':
            process = subprocess.Popen(
                ["python", "main.py"],
                cwd=agent_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            process = subprocess.Popen(
                ["python", "main.py"],
                cwd=agent_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_IGN)
            )

        # Wait for server to be ready
        print(f"      ⏳ Waiting for server to start...")
        if not await wait_for_server(base_url):
            print(f"      ❌ Server did not start within timeout")
            process.terminate()
            process.wait(timeout=5)
            return {"agent": agent_key, "status": "ERROR", "error": "Server timeout"}

        print(f"      ✅ Server started successfully")

        # Run tests
        results = []

        # Test 1: Health endpoint
        print(f"\n   📋 Test 1: Health Endpoint")
        health_ok = await test_health_endpoint(base_url)
        results.append(("Health Endpoint", health_ok))

        # Test 2: AgentCard
        print(f"\n   📋 Test 2: AgentCard Discovery")
        card_ok = await test_agent_card(base_url)
        results.append(("AgentCard", card_ok))

        # Calculate results
        passed = sum(1 for _, ok in results if ok)
        total = len(results)

        # Cleanup
        print(f"\n   🛑 Stopping server...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

        print(f"\n   📊 Results: {passed}/{total} tests passed")

        return {
            "agent": agent_key,
            "status": "PASS" if passed == total else "PARTIAL",
            "passed": passed,
            "total": total,
            "results": results
        }

    except Exception as e:
        print(f"      ❌ Error: {e}")
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            pass
        return {"agent": agent_key, "status": "ERROR", "error": str(e)}


async def test_all_agents():
    """Test all agents"""
    print("\n" + "="*60)
    print("  LEVEL 2 INTEGRATION TESTS - Sprint 2 Agents")
    print("="*60)
    print("\n  Testing agents as running HTTP servers")
    print("  No payment verification, no blockchain transactions")
    print("")

    all_results = []

    for agent_key, agent_config in AGENTS.items():
        result = await test_agent(agent_key, agent_config)
        all_results.append(result)

    # Print summary
    print("\n" + "="*60)
    print("  FINAL SUMMARY - LEVEL 2 INTEGRATION TESTS")
    print("="*60)

    total_tests = 0
    total_passed = 0

    for result in all_results:
        agent_name = AGENTS[result['agent']]['name']
        if result['status'] == 'PASS':
            print(f"  ✅ {agent_name}: {result['passed']}/{result['total']} PASS")
            total_tests += result['total']
            total_passed += result['passed']
        elif result['status'] == 'PARTIAL':
            print(f"  ⚠️  {agent_name}: {result['passed']}/{result['total']} PARTIAL")
            total_tests += result['total']
            total_passed += result['passed']
        else:
            print(f"  ❌ {agent_name}: ERROR - {result.get('error', 'Unknown')}")

    print("\n" + "="*60)
    print(f"  Total: {total_tests} tests | Passed: {total_passed}")

    if total_passed == total_tests and total_tests > 0:
        print(f"  ✅ ALL INTEGRATION TESTS PASSED")
        print(f"  Ready for Level 3 (End-to-End Tests)")
    else:
        print(f"  ⚠️  Some tests failed or had errors")

    print("="*60)

    return total_passed == total_tests and total_tests > 0


# ============================================================================
# Main
# ============================================================================

async def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            success = await test_all_agents()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == "--agent":
            if len(sys.argv) < 3:
                print("Usage: python test_integration_level2.py --agent <agent-name>")
                sys.exit(1)
            agent_key = sys.argv[2]
            if agent_key not in AGENTS:
                print(f"Unknown agent: {agent_key}")
                print(f"Available: {', '.join(AGENTS.keys())}")
                sys.exit(1)
            result = await test_agent(agent_key, AGENTS[agent_key])
            sys.exit(0 if result['status'] == 'PASS' else 1)
        else:
            print("Usage:")
            print("  python test_integration_level2.py --all")
            print("  python test_integration_level2.py --agent <agent-name>")
            sys.exit(1)
    else:
        # Default: test all
        success = await test_all_agents()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
