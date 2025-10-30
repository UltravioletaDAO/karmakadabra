#!/usr/bin/env python3
"""
Verify System Ready Script
Checks that all 54 agents are registered, funded, and ready for marketplace simulation.

Verifies:
- Agent registration on Identity Registry
- AVAX balance for gas fees
- GLUE token balance for transactions
- Bidirectional rating methods available

Usage:
    python verify_system_ready.py              # Full check
    python verify_system_ready.py --quick      # Quick check (no blockchain queries)
    python verify_system_ready.py --agent karma-hello  # Check specific agent
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional

# Add lib to path
LIB_PATH = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(LIB_PATH))

# Add utils to path
UTILS_PATH = Path(__file__).parent / "utils"
sys.path.insert(0, str(UTILS_PATH))

from utils.agent_loader import AgentInfo, load_all_agents, load_agent_by_name
from utils.web3_helper import (
    get_w3,
    get_agent_info,
    get_avax_balance,
    get_glue_balance,
    format_address
)


# Minimum required balances
MIN_AVAX_BALANCE = 0.01  # Minimum AVAX for gas
MIN_GLUE_BALANCE = 100   # Minimum GLUE for transactions

# Color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text: str, width: int = 80):
    """Print formatted header"""
    print("\n" + "=" * width)
    print(text.center(width))
    print("=" * width + "\n")


def print_section(text: str):
    """Print section header"""
    print(f"\n{BLUE}{text}{RESET}")
    print("-" * len(text))


def check_agent(agent: AgentInfo, w3=None, detailed: bool = True) -> Dict:
    """
    Check single agent status

    Args:
        agent: AgentInfo object
        w3: Web3 instance (optional for quick check)
        detailed: Show detailed output

    Returns:
        Dictionary with check results
    """
    result = {
        'name': agent.name,
        'type': agent.type,
        'address': agent.address,
        'has_address': bool(agent.address and agent.address.strip()),
        'registered': False,
        'agent_id': None,
        'domain': None,
        'avax_balance': 0.0,
        'glue_balance': 0.0,
        'avax_ok': False,
        'glue_ok': False,
        'all_ok': False
    }

    # Check if address configured
    if not result['has_address']:
        if detailed:
            print(f"{RED}❌{RESET} {agent.name:20} NO ADDRESS CONFIGURED")
        return result

    # Quick check mode (no blockchain queries)
    if not w3:
        if detailed:
            print(f"{YELLOW}⚠️{RESET}  {agent.name:20} {format_address(agent.address)} (not verified on-chain)")
        result['all_ok'] = True  # Assume OK in quick mode
        return result

    # Check registration on-chain
    try:
        on_chain_info = get_agent_info(w3, agent.address)
        if on_chain_info:
            result['registered'] = True
            result['agent_id'] = on_chain_info['agent_id']
            result['domain'] = on_chain_info['domain']
        else:
            if detailed:
                print(f"{RED}❌{RESET} {agent.name:20} NOT REGISTERED on-chain")
            return result
    except Exception as e:
        if detailed:
            print(f"{RED}❌{RESET} {agent.name:20} ERROR checking registration: {e}")
        return result

    # Check AVAX balance
    try:
        result['avax_balance'] = get_avax_balance(w3, agent.address)
        result['avax_ok'] = result['avax_balance'] >= MIN_AVAX_BALANCE
    except Exception as e:
        if detailed:
            print(f"{YELLOW}⚠️{RESET}  {agent.name:20} ERROR checking AVAX: {e}")

    # Check GLUE balance
    try:
        result['glue_balance'] = get_glue_balance(w3, agent.address)
        result['glue_ok'] = result['glue_balance'] >= MIN_GLUE_BALANCE
    except Exception as e:
        if detailed:
            print(f"{YELLOW}⚠️{RESET}  {agent.name:20} ERROR checking GLUE: {e}")

    # Overall status
    result['all_ok'] = (
        result['has_address'] and
        result['registered'] and
        result['avax_ok'] and
        result['glue_ok']
    )

    # Print detailed status
    if detailed:
        status = f"{GREEN}✅{RESET}" if result['all_ok'] else f"{YELLOW}⚠️{RESET}"
        avax_str = f"{result['avax_balance']:.4f}" if result['avax_ok'] else f"{RED}{result['avax_balance']:.4f}{RESET}"
        glue_str = f"{result['glue_balance']:,.0f}" if result['glue_ok'] else f"{RED}{result['glue_balance']:,.0f}{RESET}"

        print(f"{status} {agent.name:20} | ID: {result['agent_id']:3} | AVAX: {avax_str:>8} | GLUE: {glue_str:>10}")

    return result


def verify_all_agents(quick: bool = False) -> Dict:
    """
    Verify all 54 agents

    Args:
        quick: Skip blockchain queries (faster)

    Returns:
        Dictionary with summary results
    """
    print_header("KARMACADABRA SYSTEM VERIFICATION")

    # Load agents
    print("Loading agent configurations...")
    agents = load_all_agents()
    print(f"Found {len(agents)} agents\n")

    # Connect to blockchain (unless quick mode)
    w3 = None
    if not quick:
        try:
            print("Connecting to Avalanche Fuji...")
            w3 = get_w3()
        except Exception as e:
            print(f"{RED}❌ Failed to connect to blockchain: {e}{RESET}")
            print("Continuing in quick mode (no on-chain verification)\n")

    # Check each agent by type
    results_by_type = {}

    for agent_type in ['system', 'client', 'user']:
        type_agents = [a for a in agents if a.type == agent_type]

        if not type_agents:
            continue

        print_section(f"{agent_type.upper()} AGENTS ({len(type_agents)})")

        type_results = []
        for agent in type_agents:
            result = check_agent(agent, w3, detailed=True)
            type_results.append(result)

        results_by_type[agent_type] = type_results

    # Calculate summary
    all_results = []
    for results in results_by_type.values():
        all_results.extend(results)

    total = len(all_results)
    with_address = sum(1 for r in all_results if r['has_address'])
    registered = sum(1 for r in all_results if r['registered'])
    avax_ok = sum(1 for r in all_results if r['avax_ok'])
    glue_ok = sum(1 for r in all_results if r['glue_ok'])
    all_ok = sum(1 for r in all_results if r['all_ok'])

    # Print summary
    print_section("SUMMARY")
    print(f"Total agents:          {total}")
    print(f"With address:          {with_address}/{total} ({with_address/total*100:.0f}%)")

    if not quick:
        print(f"Registered on-chain:   {registered}/{total} ({registered/total*100:.0f}%)")
        print(f"AVAX balance OK:       {avax_ok}/{total} ({avax_ok/total*100:.0f}%)")
        print(f"GLUE balance OK:       {glue_ok}/{total} ({glue_ok/total*100:.0f}%)")
        print(f"{GREEN}✅ ALL CHECKS PASSED:  {all_ok}/{total} ({all_ok/total*100:.0f}%){RESET}")

        if all_ok == total:
            print(f"\n{GREEN}🎉 ALL AGENTS READY FOR MARKETPLACE SIMULATION!{RESET}")
        else:
            print(f"\n{YELLOW}⚠️  {total - all_ok} agents need attention{RESET}")

            # List problem agents
            problem_agents = [r for r in all_results if not r['all_ok']]
            if problem_agents:
                print("\nAgents with issues:")
                for r in problem_agents:
                    issues = []
                    if not r['has_address']:
                        issues.append("no address")
                    if not r['registered']:
                        issues.append("not registered")
                    if not r['avax_ok']:
                        issues.append(f"low AVAX ({r['avax_balance']:.4f})")
                    if not r['glue_ok']:
                        issues.append(f"low GLUE ({r['glue_balance']:.0f})")

                    print(f"  - {r['name']:20} {', '.join(issues)}")

    return {
        'total': total,
        'with_address': with_address,
        'registered': registered,
        'avax_ok': avax_ok,
        'glue_ok': glue_ok,
        'all_ok': all_ok,
        'results': all_results
    }


def verify_single_agent(agent_name: str) -> bool:
    """
    Verify single agent

    Args:
        agent_name: Agent name

    Returns:
        True if agent is ready
    """
    print_header(f"VERIFYING AGENT: {agent_name}")

    # Load agent
    agent = load_agent_by_name(agent_name)
    if not agent:
        print(f"{RED}❌ Agent '{agent_name}' not found{RESET}")
        return False

    print(f"Type: {agent.type}")
    print(f"Config path: {agent.config_path}")
    print(f"Address: {agent.address}\n")

    # Connect to blockchain
    try:
        w3 = get_w3()
    except Exception as e:
        print(f"{RED}❌ Failed to connect to blockchain: {e}{RESET}")
        return False

    # Check agent
    result = check_agent(agent, w3, detailed=False)

    # Print detailed results
    print(f"\nRegistration:")
    if result['registered']:
        print(f"  {GREEN}✅{RESET} Registered on-chain")
        print(f"     Agent ID: {result['agent_id']}")
        print(f"     Domain: {result['domain']}")
    else:
        print(f"  {RED}❌{RESET} Not registered")

    print(f"\nBalances:")
    avax_status = f"{GREEN}✅{RESET}" if result['avax_ok'] else f"{RED}❌{RESET}"
    glue_status = f"{GREEN}✅{RESET}" if result['glue_ok'] else f"{RED}❌{RESET}"
    print(f"  {avax_status} AVAX: {result['avax_balance']:.4f} (min: {MIN_AVAX_BALANCE})")
    print(f"  {glue_status} GLUE: {result['glue_balance']:,.0f} (min: {MIN_GLUE_BALANCE})")

    print(f"\nOverall Status:")
    if result['all_ok']:
        print(f"  {GREEN}✅ READY FOR MARKETPLACE{RESET}")
    else:
        print(f"  {RED}❌ NOT READY - See issues above{RESET}")

    return result['all_ok']


# CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Verify all agents are registered and funded",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python verify_system_ready.py              # Full verification
  python verify_system_ready.py --quick      # Quick check (no blockchain)
  python verify_system_ready.py --agent karma-hello  # Single agent
        """
    )

    parser.add_argument("--quick", action="store_true", help="Quick check (no blockchain queries)")
    parser.add_argument("--agent", help="Check specific agent by name")

    args = parser.parse_args()

    try:
        if args.agent:
            # Single agent check
            success = verify_single_agent(args.agent)
            sys.exit(0 if success else 1)
        else:
            # All agents check
            summary = verify_all_agents(quick=args.quick)
            sys.exit(0 if summary['all_ok'] == summary['total'] else 1)

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}⚠️  Interrupted by user{RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{RED}❌ ERROR: {e}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
