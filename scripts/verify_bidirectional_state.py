#!/usr/bin/env python3
"""
Verify Bidirectional Trust Implementation State

Checks current implementation status of bidirectional trust pattern
across smart contracts, Python code, and tests.

Usage:
    python scripts/verify_bidirectional_state.py

Output:
    - Console report of current state
    - contribution/week1/0-verification-report.md
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def check_mark(condition: bool) -> str:
    """Return [OK] or [X] based on condition"""
    return f"{GREEN}[OK]{RESET}" if condition else f"{RED}[X]{RESET}"

def find_function_in_solidity(file_path: str, function_name: str) -> bool:
    """Check if a function exists in a Solidity file"""
    if not os.path.exists(file_path):
        return False

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Look for function definition
        pattern = rf'function\s+{function_name}\s*\('
        return bool(re.search(pattern, content))

def find_method_in_python(file_path: str, method_name: str) -> bool:
    """Check if a method exists in a Python file"""
    if not os.path.exists(file_path):
        return False

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Look for method definition
        pattern = rf'def\s+{method_name}\s*\('
        return bool(re.search(pattern, content))

def find_test_file(pattern: str, test_dir: str) -> List[str]:
    """Find test files matching pattern"""
    test_path = Path(test_dir)
    if not test_path.exists():
        return []

    matches = []
    for file in test_path.rglob('*'):
        if file.is_file() and pattern.lower() in file.name.lower():
            matches.append(str(file))
    return matches

def check_deployment(env_file: str) -> Dict[str, str]:
    """Check if contracts are deployed"""
    deployments = {}

    if not os.path.exists(env_file):
        return deployments

    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.strip().split('=', 1)
                if 'REGISTRY' in key.upper() and value:
                    deployments[key] = value

    return deployments

def generate_report(results: Dict) -> str:
    """Generate markdown report"""
    report = """# Bidirectional Trust Implementation - Verification Report

**Generated:** {timestamp}
**Purpose:** Assess current implementation state before Week 1

---

## Summary

{summary}

---

## Smart Contract Status

### ReputationRegistry.sol

**Location:** `erc-8004/contracts/src/ReputationRegistry.sol`

| Function | Exists | Status |
|----------|--------|--------|
| `rateClient()` | {rate_client} | {rate_client_status} |
| `rateValidator()` | {rate_validator} | {rate_validator_status} |
| `giveFeedback()` | {give_feedback} | {give_feedback_status} |

**Events:**
- `ClientRated`: {client_rated_event}
- `ValidatorRated`: {validator_rated_event}

**Metadata Tags:**
- `client-rating` tag: {client_tag}
- `validator-rating` tag: {validator_tag}
- `bidirectional` tag: {bidirectional_tag}

---

## Python Implementation Status

### base_agent.py

**Location:** `shared/base_agent.py`

| Method | Exists | Status |
|--------|--------|--------|
| `rate_client()` | {py_rate_client} | {py_rate_client_status} |
| `rate_validator()` | {py_rate_validator} | {py_rate_validator_status} |
| `get_bidirectional_ratings()` | {py_get_ratings} | {py_get_ratings_status} |

---

## Test Coverage Status

### Smart Contract Tests (Foundry)

**Location:** `erc-8004/contracts/test/`

| Test | Exists | Files |
|------|--------|-------|
| Bidirectional rating tests | {sol_tests} | {sol_test_files} |

### Python Tests (Pytest)

**Location:** `tests/`

| Test | Exists | Files |
|------|--------|-------|
| Bidirectional transaction tests | {py_tests} | {py_test_files} |

---

## Deployment Status

### Fuji Testnet Deployment

**Deployment file:** `erc-8004/.env.deployed`

{deployment_table}

---

## Week 1 Readiness Assessment

### What's Already Done

{done_list}

### What Needs to Be Built

{todo_list}

---

## Recommended Next Steps

{next_steps}

---

## Commands to Run

```bash
# Navigate to project root
cd z:\\ultravioleta\\dao\\karmacadabra

# Start Week 1 tasks
# See: contribution/week1/1.0-CHECKLIST.md

{commands}
```

---

**Status:** {overall_status}
**Estimated Remaining Work:** {estimated_hours} hours

Ready to begin Week 1? {ready}
"""

    from datetime import datetime

    # Build report data
    report_data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'summary': results.get('summary', ''),
        'rate_client': check_mark(results.get('rate_client', False)),
        'rate_client_status': 'Implemented' if results.get('rate_client', False) else 'Need to implement',
        'rate_validator': check_mark(results.get('rate_validator', False)),
        'rate_validator_status': 'Implemented' if results.get('rate_validator', False) else 'Need to implement',
        'give_feedback': check_mark(results.get('give_feedback', False)),
        'give_feedback_status': 'Baseline exists' if results.get('give_feedback', False) else 'Missing',
        'client_rated_event': check_mark(results.get('client_rated_event', False)),
        'validator_rated_event': check_mark(results.get('validator_rated_event', False)),
        'client_tag': check_mark(results.get('client_tag', False)),
        'validator_tag': check_mark(results.get('validator_tag', False)),
        'bidirectional_tag': check_mark(results.get('bidirectional_tag', False)),
        'py_rate_client': check_mark(results.get('py_rate_client', False)),
        'py_rate_client_status': 'Implemented' if results.get('py_rate_client', False) else 'Need to implement',
        'py_rate_validator': check_mark(results.get('py_rate_validator', False)),
        'py_rate_validator_status': 'Implemented' if results.get('py_rate_validator', False) else 'Need to implement',
        'py_get_ratings': check_mark(results.get('py_get_ratings', False)),
        'py_get_ratings_status': 'Implemented' if results.get('py_get_ratings', False) else 'Need to implement',
        'sol_tests': check_mark(results.get('sol_tests', False)),
        'sol_test_files': '\n'.join([f"- `{f}`" for f in results.get('sol_test_files', [])]) or 'None found',
        'py_tests': check_mark(results.get('py_tests', False)),
        'py_test_files': '\n'.join([f"- `{f}`" for f in results.get('py_test_files', [])]) or 'None found',
        'deployment_table': results.get('deployment_table', 'No deployments found'),
        'done_list': results.get('done_list', '- None'),
        'todo_list': results.get('todo_list', '- Everything!'),
        'next_steps': results.get('next_steps', ''),
        'commands': results.get('commands', ''),
        'overall_status': results.get('overall_status', ''),
        'estimated_hours': results.get('estimated_hours', 20),
        'ready': check_mark(results.get('ready', False))
    }

    return report.format(**report_data)

def main():
    """Main verification function"""
    print(f"\n{BLUE}=== Bidirectional Trust Implementation Verification ==={RESET}\n")

    results = {}

    # Check smart contract functions
    print(f"{YELLOW}Checking Smart Contracts...{RESET}")
    reputation_registry = "erc-8004/contracts/src/ReputationRegistry.sol"

    results['rate_client'] = find_function_in_solidity(reputation_registry, 'rateClient')
    results['rate_validator'] = find_function_in_solidity(reputation_registry, 'rateValidator')
    results['give_feedback'] = find_function_in_solidity(reputation_registry, 'giveFeedback')

    print(f"  rateClient():     {check_mark(results['rate_client'])}")
    print(f"  rateValidator():  {check_mark(results['rate_validator'])}")
    print(f"  giveFeedback():   {check_mark(results['give_feedback'])}")

    # Check for events
    if os.path.exists(reputation_registry):
        with open(reputation_registry, 'r', encoding='utf-8') as f:
            content = f.read()
            results['client_rated_event'] = 'ClientRated' in content
            results['validator_rated_event'] = 'ValidatorRated' in content
            results['client_tag'] = 'client-rating' in content
            results['validator_tag'] = 'validator-rating' in content
            results['bidirectional_tag'] = 'bidirectional' in content

    # Check Python implementation
    print(f"\n{YELLOW}Checking Python Implementation...{RESET}")
    base_agent = "shared/base_agent.py"

    results['py_rate_client'] = find_method_in_python(base_agent, 'rate_client')
    results['py_rate_validator'] = find_method_in_python(base_agent, 'rate_validator')
    results['py_get_ratings'] = find_method_in_python(base_agent, 'get_bidirectional_ratings')

    print(f"  rate_client():                {check_mark(results['py_rate_client'])}")
    print(f"  rate_validator():             {check_mark(results['py_rate_validator'])}")
    print(f"  get_bidirectional_ratings():  {check_mark(results['py_get_ratings'])}")

    # Check tests
    print(f"\n{YELLOW}Checking Tests...{RESET}")

    sol_test_files = find_test_file('bidirectional', 'erc-8004/contracts/test')
    results['sol_tests'] = len(sol_test_files) > 0
    results['sol_test_files'] = sol_test_files
    print(f"  Solidity tests:   {check_mark(results['sol_tests'])} ({len(sol_test_files)} files)")

    py_test_files = find_test_file('bidirectional', 'tests')
    results['py_tests'] = len(py_test_files) > 0
    results['py_test_files'] = py_test_files
    print(f"  Python tests:     {check_mark(results['py_tests'])} ({len(py_test_files)} files)")

    # Check deployment
    print(f"\n{YELLOW}Checking Deployment...{RESET}")
    deployments = check_deployment('erc-8004/.env.deployed')

    if deployments:
        deployment_table = "| Contract | Address |\n|----------|---------|"
        for key, value in deployments.items():
            deployment_table += f"\n| {key} | `{value}` |"
        results['deployment_table'] = deployment_table
        print(f"  Deployed contracts: {GREEN}[OK]{RESET} ({len(deployments)} found)")
    else:
        results['deployment_table'] = "No deployed contracts found in `erc-8004/.env.deployed`"
        print(f"  Deployed contracts: {RED}[X]{RESET}")

    # Calculate what's done vs. todo
    total_checks = 8  # rate_client, rate_validator, py_rate_client, py_rate_validator, py_get_ratings, sol_tests, py_tests, deployments
    done_count = sum([
        results.get('rate_client', False),
        results.get('rate_validator', False),
        results.get('py_rate_client', False),
        results.get('py_rate_validator', False),
        results.get('py_get_ratings', False),
        results.get('sol_tests', False),
        results.get('py_tests', False),
        bool(deployments)
    ])

    completion_pct = (done_count / total_checks) * 100

    # Generate done/todo lists
    done_items = []
    todo_items = []

    if results.get('give_feedback', False):
        done_items.append("[OK] Baseline `giveFeedback()` exists in ReputationRegistry.sol")
    if results.get('rate_client', False):
        done_items.append("[OK] `rateClient()` implemented in smart contract")
    else:
        todo_items.append("[TODO] Implement `rateClient()` in ReputationRegistry.sol")

    if results.get('rate_validator', False):
        done_items.append("[OK] `rateValidator()` implemented in smart contract")
    else:
        todo_items.append("[TODO] Implement `rateValidator()` in ReputationRegistry.sol")

    if results.get('py_rate_client', False):
        done_items.append("[OK] `rate_client()` implemented in base_agent.py")
    else:
        todo_items.append("[TODO] Implement `rate_client()` in base_agent.py")

    if results.get('py_rate_validator', False):
        done_items.append("[OK] `rate_validator()` implemented in base_agent.py")
    else:
        todo_items.append("[TODO] Implement `rate_validator()` in base_agent.py")

    if results.get('sol_tests', False):
        done_items.append(f"[OK] Solidity tests exist ({len(sol_test_files)} files)")
    else:
        todo_items.append("[TODO] Write Solidity tests for bidirectional rating")

    if results.get('py_tests', False):
        done_items.append(f"[OK] Python tests exist ({len(py_test_files)} files)")
    else:
        todo_items.append("[TODO] Write Python integration tests")

    if deployments:
        done_items.append(f"[OK] Contracts deployed to testnet ({len(deployments)} contracts)")
    else:
        todo_items.append("[TODO] Deploy contracts to Fuji testnet")

    results['done_list'] = '\n'.join([f"{item}" for item in done_items]) if done_items else "- Nothing implemented yet"
    results['todo_list'] = '\n'.join([f"{item}" for item in todo_items])

    # Calculate estimated remaining hours
    remaining_tasks = len(todo_items)
    estimated_hours = remaining_tasks * 2.5  # Rough estimate: 2.5 hours per task
    results['estimated_hours'] = int(estimated_hours)

    # Generate summary
    if completion_pct >= 80:
        results['summary'] = f"**Status:** {GREEN}Nearly Ready!{RESET} ({completion_pct:.0f}% complete)\n\nMost of the bidirectional pattern is implemented. You can skip ahead in Week 1 tasks."
        results['overall_status'] = f"{GREEN}Nearly Complete{RESET}"
        results['ready'] = True
    elif completion_pct >= 40:
        results['summary'] = f"**Status:** {YELLOW}Partially Implemented{RESET} ({completion_pct:.0f}% complete)\n\nSome components exist. Follow Week 1 checklist to complete the implementation."
        results['overall_status'] = f"{YELLOW}Partially Complete{RESET}"
        results['ready'] = False
    else:
        results['summary'] = f"**Status:** {RED}Starting from Scratch{RESET} ({completion_pct:.0f}% complete)\n\nBidirectional pattern not yet implemented. Follow Week 1 checklist from the beginning."
        results['overall_status'] = f"{RED}Not Started{RESET}"
        results['ready'] = False

    # Generate next steps
    if not results.get('rate_client', False):
        results['next_steps'] = """1. **Day 1:** Implement `rateClient()` and `rateValidator()` in ReputationRegistry.sol
2. **Day 2:** Write Solidity tests
3. **Day 3:** Implement Python methods in base_agent.py
4. **Day 4:** Write Python integration tests
5. **Day 5:** Deploy and execute testnet transactions"""
    elif not results.get('py_rate_client', False):
        results['next_steps'] = """1. **Skip to Day 3:** Implement Python methods in base_agent.py
2. **Day 4:** Write Python integration tests
3. **Day 5:** Deploy and execute testnet transactions"""
    else:
        results['next_steps'] = """1. **Verify tests pass:** Run all existing tests
2. **Day 5:** Deploy and execute testnet transactions
3. **Move to Week 2:** Begin data collection"""

    # Generate commands
    if not results.get('give_feedback', False):
        results['commands'] = """# Smart contract doesn't exist yet
cd erc-8004/contracts
# Create ReputationRegistry.sol first"""
    elif not results.get('sol_tests', False):
        results['commands'] = """# Compile contracts
cd erc-8004/contracts
forge build

# Write tests (see Week 1 Day 2)
forge test -vv"""
    else:
        results['commands'] = """# Run all tests
cd erc-8004/contracts
forge test -vv

cd ../..
pytest tests/test_bidirectional_transactions.py -v"""

    # Print summary
    print(f"\n{BLUE}=== Summary ==={RESET}")
    print(f"Completion: {completion_pct:.0f}%")
    print(f"Done: {done_count}/{total_checks} components")
    print(f"Estimated remaining work: {estimated_hours} hours")

    # Generate and save report
    report_content = generate_report(results)

    # Ensure directory exists
    os.makedirs('contribution/week1', exist_ok=True)

    report_path = 'contribution/week1/0-verification-report.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    print(f"\n{GREEN}[OK] Report saved to: {report_path}{RESET}")
    print(f"\n{BLUE}Next step: Review the report and start Week 1 tasks{RESET}")
    print(f"  >> Open: contribution/week1/1.0-CHECKLIST.md\n")

if __name__ == '__main__':
    main()
