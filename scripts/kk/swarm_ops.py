#!/usr/bin/env python3
"""
KK Swarm Operations CLI — Unified monitoring, diagnostics, and ops for the
KarmaCadabra agent swarm.

Usage:
  python swarm_ops.py status              # Full swarm status overview
  python swarm_ops.py balances            # Check all wallet balances (Base USDC + ETH)
  python swarm_ops.py auth-test           # Test EIP-8128 auth for all agents
  python swarm_ops.py irc-check           # Check IRC presence on MeshRelay
  python swarm_ops.py health              # EM API + facilitator health
  python swarm_ops.py agents [--type system|user]  # List agents with details
  python swarm_ops.py report              # Generate markdown status report
  python swarm_ops.py fund-estimate       # Estimate funding needed
  python swarm_ops.py terraform-status    # Check Terraform infrastructure
  python swarm_ops.py deploy-checklist    # Pre-deployment verification

Designed to run locally (Mac mini) or on EC2 instances.
No private keys required — read-only operations only.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

# Optional imports (graceful degradation)
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    import urllib.request
    import urllib.error

# ============================================================================
# Configuration
# ============================================================================

REPO_ROOT = Path(__file__).parent.parent.parent
CONFIG_DIR = REPO_ROOT / "data" / "config"
TERRAFORM_DIR = REPO_ROOT / "terraform" / "openclaw"

EM_API = "https://api.execution.market"
EM_API_V1 = f"{EM_API}/api/v1"
FACILITATOR = "https://facilitator.ultravioletadao.xyz"
BASE_RPC = "https://mainnet.base.org"
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

IRC_SERVER = "irc.meshrelay.xyz"
IRC_PORT = 6667

# ERC-20 balanceOf(address) selector
BALANCE_OF_SELECTOR = "0x70a08231"

# ============================================================================
# Helpers
# ============================================================================

def load_wallets() -> list[dict]:
    """Load wallet config from data/config/wallets.json."""
    path = CONFIG_DIR / "wallets.json"
    if not path.exists():
        print(f"❌ Wallet config not found: {path}")
        sys.exit(1)
    with open(path) as f:
        data = json.load(f)
    return data["wallets"]


def load_identities() -> dict[str, dict]:
    """Load identity config, keyed by agent name."""
    path = CONFIG_DIR / "identities.json"
    if not path.exists():
        return {}
    with open(path) as f:
        data = json.load(f)
    return {a["name"]: a for a in data.get("agents", [])}


def _http_get(url: str, timeout: float = 10.0) -> dict | str:
    """Simple synchronous HTTP GET (no external deps needed)."""
    if HAS_HTTPX:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            try:
                return resp.json()
            except Exception:
                return resp.text
    else:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            try:
                return json.loads(body)
            except Exception:
                return body


def _rpc_call(method: str, params: list, rpc_url: str = BASE_RPC) -> Any:
    """Make a JSON-RPC call to Base mainnet."""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
    if HAS_HTTPX:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(rpc_url, json=payload)
            data = resp.json()
    else:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            rpc_url,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data.get("result")


def get_eth_balance(address: str) -> float:
    """Get ETH balance on Base mainnet (in ETH)."""
    try:
        result = _rpc_call("eth_getBalance", [address, "latest"])
        wei = int(result, 16)
        return wei / 1e18
    except Exception as e:
        return -1.0


def get_usdc_balance(address: str) -> float:
    """Get USDC balance on Base mainnet (in USDC, 6 decimals)."""
    try:
        # balanceOf(address) — pad address to 32 bytes
        padded = address.lower().replace("0x", "").zfill(64)
        call_data = BALANCE_OF_SELECTOR + padded
        result = _rpc_call("eth_call", [
            {"to": USDC_ADDRESS, "data": call_data},
            "latest",
        ])
        raw = int(result, 16)
        return raw / 1e6
    except Exception as e:
        return -1.0


def format_usd(amount: float) -> str:
    if amount < 0:
        return "❓ error"
    if amount == 0:
        return "$0.00"
    if amount < 0.01:
        return f"${amount:.6f}"
    return f"${amount:.2f}"


def format_eth(amount: float) -> str:
    if amount < 0:
        return "❓ error"
    if amount == 0:
        return "0 ETH"
    if amount < 0.001:
        return f"{amount:.8f} ETH"
    return f"{amount:.6f} ETH"


# ============================================================================
# Commands
# ============================================================================

def cmd_agents(args):
    """List all agents with details."""
    wallets = load_wallets()
    identities = load_identities()

    filter_type = getattr(args, "type", None)

    print(f"\n🤖 KK Swarm Agents — {len(wallets)} total\n")
    print(f"{'#':>3}  {'Type':>6}  {'Name':<25}  {'Address':<44}  {'ERC-8004':>8}  {'Executor ID'}")
    print("─" * 120)

    for w in wallets:
        if filter_type and w["type"] != filter_type:
            continue
        identity = identities.get(w["name"], {})
        agent_id = ""
        regs = identity.get("registrations", {})
        if "base" in regs:
            agent_id = str(regs["base"].get("agent_id", ""))
        executor = identity.get("executor_id", "—")

        icon = "⚙️" if w["type"] == "system" else "👤"
        print(f"{w['index']:3d}  {icon} {w['type']:>5}  {w['name']:<25}  {w['address']}  {agent_id:>8}  {executor}")

    system_count = sum(1 for w in wallets if w["type"] == "system")
    user_count = sum(1 for w in wallets if w["type"] == "user")
    registered = sum(1 for w in wallets if identities.get(w["name"], {}).get("registrations"))
    print(f"\n📊 {system_count} system + {user_count} user agents | {registered} registered on ERC-8004")


def cmd_balances(args):
    """Check all wallet balances on Base mainnet."""
    wallets = load_wallets()

    print(f"\n💰 Wallet Balances — Base Mainnet (USDC + ETH)\n")
    print(f"{'#':>3}  {'Name':<25}  {'USDC':>14}  {'ETH':>16}  {'Status'}")
    print("─" * 85)

    total_usdc = 0.0
    total_eth = 0.0
    funded = 0
    errors = 0

    for w in wallets:
        usdc = get_usdc_balance(w["address"])
        eth = get_eth_balance(w["address"])

        if usdc < 0 or eth < 0:
            status = "❌ RPC error"
            errors += 1
        elif usdc == 0 and eth == 0:
            status = "⚪ unfunded"
        elif usdc > 0 and eth > 0:
            status = "🟢 ready"
            funded += 1
        elif usdc > 0:
            status = "🟡 needs gas"
            funded += 1
        else:
            status = "🟠 has gas only"

        if usdc > 0:
            total_usdc += usdc
        if eth > 0:
            total_eth += eth

        print(f"{w['index']:3d}  {w['name']:<25}  {format_usd(usdc):>14}  {format_eth(eth):>16}  {status}")

    print(f"\n📊 Total: {format_usd(total_usdc)} USDC + {format_eth(total_eth)} ETH")
    print(f"   {funded}/{len(wallets)} funded | {errors} errors")


def cmd_health(args):
    """Check EM API and facilitator health."""
    print("\n🏥 System Health Check\n")

    # EM API
    try:
        data = _http_get(f"{EM_API}/health")
        status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
        uptime = data.get("uptime_seconds", 0) if isinstance(data, dict) else 0
        uptime_h = uptime / 3600
        print(f"  EM API:        {'🟢' if status == 'healthy' else '🔴'} {status} (uptime: {uptime_h:.1f}h)")

        if isinstance(data, dict):
            components = data.get("components", {})
            for name, comp in components.items():
                cs = comp.get("status", "unknown")
                msg = comp.get("message", "")[:50]
                latency = comp.get("latency_ms")
                lat_str = f" ({latency:.0f}ms)" if latency else ""
                icon = "✅" if cs == "healthy" else "⚠️"
                print(f"    {icon} {name:<15} {msg}{lat_str}")
    except Exception as e:
        print(f"  EM API:        🔴 unreachable ({e})")

    # ERC-8128 nonce endpoint
    try:
        data = _http_get(f"{EM_API_V1}/auth/nonce")
        if isinstance(data, dict) and "nonce" in data:
            print(f"  ERC-8128:      🟢 nonce endpoint working (nonce: {data['nonce'][:16]}...)")
        else:
            print(f"  ERC-8128:      🟡 unexpected response: {str(data)[:60]}")
    except Exception as e:
        print(f"  ERC-8128:      🔴 nonce endpoint failed ({e})")

    # Facilitator
    try:
        data = _http_get(f"{FACILITATOR}/health")
        status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
        print(f"  Facilitator:   {'🟢' if status == 'healthy' else '🔴'} {status}")
    except Exception as e:
        print(f"  Facilitator:   🔴 unreachable ({e})")

    # Base RPC
    try:
        block = _rpc_call("eth_blockNumber", [])
        block_num = int(block, 16)
        print(f"  Base RPC:      🟢 block {block_num:,}")
    except Exception as e:
        print(f"  Base RPC:      🔴 unreachable ({e})")

    # Skill file
    try:
        if HAS_HTTPX:
            with httpx.Client(timeout=10) as client:
                resp = client.head("https://execution.market/skill.md")
                ct = resp.headers.get("content-type", "")
                if "markdown" in ct or "text" in ct:
                    print(f"  Skill file:    🟢 served ({ct})")
                else:
                    print(f"  Skill file:    🟡 unexpected type: {ct}")
        else:
            req = urllib.request.Request(
                "https://execution.market/skill.md",
                method="HEAD",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                ct = resp.headers.get("Content-Type", "")
                print(f"  Skill file:    🟢 served ({ct})")
    except Exception as e:
        print(f"  Skill file:    🔴 unreachable ({e})")


def cmd_irc_check(args):
    """Check IRC connectivity to MeshRelay."""
    import socket

    print(f"\n📡 IRC Connectivity — {IRC_SERVER}:{IRC_PORT}\n")

    try:
        sock = socket.create_connection((IRC_SERVER, IRC_PORT), timeout=10)
        # Read welcome
        data = sock.recv(4096).decode("utf-8", errors="replace")
        print(f"  Connection:    🟢 connected")

        # Register with a test nick
        test_nick = f"kk-ops-{int(time.time()) % 10000}"
        sock.sendall(f"NICK {test_nick}\r\n".encode())
        sock.sendall(f"USER {test_nick} 0 * :KK Swarm Ops Check\r\n".encode())

        # Wait for RPL_WELCOME or nick collision
        sock.settimeout(15)
        buffer = ""
        registered = False
        names_in_channel = []

        for _ in range(20):
            try:
                chunk = sock.recv(4096).decode("utf-8", errors="replace")
                buffer += chunk
            except socket.timeout:
                break

            lines = buffer.split("\r\n")
            buffer = lines[-1]

            for line in lines[:-1]:
                if line.startswith("PING"):
                    token = line.split("PING ")[-1]
                    sock.sendall(f"PONG {token}\r\n".encode())

                if " 001 " in line:
                    registered = True
                    print(f"  Registration:  🟢 registered as {test_nick}")
                    # Join #Agents to check who's there
                    sock.sendall(b"JOIN #Agents\r\n")
                    sock.sendall(b"NAMES #Agents\r\n")

                # RPL_NAMREPLY (353) — list of users in channel
                if " 353 " in line:
                    parts = line.split(":")
                    if len(parts) >= 3:
                        names = parts[-1].strip().split()
                        names_in_channel.extend(names)

                # RPL_ENDOFNAMES (366)
                if " 366 " in line and names_in_channel:
                    break

        if names_in_channel:
            kk_agents = [n.lstrip("@+") for n in names_in_channel if n.lstrip("@+").startswith("kk-")]
            other = [n.lstrip("@+") for n in names_in_channel if not n.lstrip("@+").startswith("kk-")]
            print(f"  #Agents:       🟢 {len(names_in_channel)} users online")
            if kk_agents:
                print(f"    KK agents:   {', '.join(kk_agents)}")
            if other:
                print(f"    Others:      {', '.join(other[:10])}")
        elif registered:
            print(f"  #Agents:       🟡 joined but no names received")

        # Clean disconnect
        sock.sendall(b"QUIT :Swarm ops check complete\r\n")
        sock.close()

    except socket.timeout:
        print(f"  Connection:    🔴 timeout connecting to {IRC_SERVER}:{IRC_PORT}")
    except ConnectionRefusedError:
        print(f"  Connection:    🔴 connection refused")
    except Exception as e:
        print(f"  Connection:    🔴 error: {e}")


def cmd_auth_test(args):
    """Test EIP-8128 auth against EM API (requires agents to have nonce access)."""
    print("\n🔐 ERC-8128 Auth Test\n")
    print("  Testing nonce acquisition for each agent...\n")

    # We can't sign without private keys (which we don't have locally),
    # but we CAN verify the auth infrastructure is working.
    identities = load_identities()
    wallets = load_wallets()

    # Test 1: Nonce endpoint
    try:
        nonce_data = _http_get(f"{EM_API_V1}/auth/nonce")
        nonce = nonce_data.get("nonce", "") if isinstance(nonce_data, dict) else ""
        print(f"  Nonce endpoint: 🟢 working (nonce: {nonce[:16]}...)")
    except Exception as e:
        print(f"  Nonce endpoint: 🔴 failed ({e})")
        return

    # Test 2: ERC-8128 info
    try:
        info = _http_get(f"{EM_API_V1}/auth/erc8128/info")
        if isinstance(info, dict):
            chains = info.get("supported_chains", [])
            max_validity = info.get("max_validity_seconds", "?")
            print(f"  ERC-8128 info:  🟢 {len(chains)} chains supported, max validity {max_validity}s")
        else:
            print(f"  ERC-8128 info:  🟡 unexpected response")
    except Exception as e:
        print(f"  ERC-8128 info:  🔴 failed ({e})")

    # Test 3: Check which agents have executor IDs (required for auth)
    print(f"\n  Agent Auth Readiness:")
    print(f"  {'Name':<25}  {'Wallet':<12}  {'ERC-8004':>8}  {'Executor ID':>12}  Status")
    print("  " + "─" * 80)

    ready = 0
    for w in wallets:
        identity = identities.get(w["name"], {})
        regs = identity.get("registrations", {})
        agent_id = regs.get("base", {}).get("agent_id", "")
        executor = identity.get("executor_id", "")

        if agent_id and executor:
            status = "🟢 ready"
            ready += 1
        elif agent_id:
            status = "🟡 no executor_id"
        elif executor:
            status = "🟡 not registered"
        else:
            status = "⚪ not configured"

        print(f"  {w['name']:<25}  {w['address'][:10]}..  {str(agent_id):>8}  {executor[:12] if executor else '—':>12}  {status}")

    print(f"\n  📊 {ready}/{len(wallets)} agents auth-ready")
    print(f"\n  ⚠️  Full auth test requires private keys (only available on EC2 instances)")
    print(f"      Use `restart_agent.sh` to test auth on deployed agents")


def cmd_fund_estimate(args):
    """Estimate funding needed for the swarm."""
    wallets = load_wallets()

    print("\n💸 Funding Estimate\n")

    # Check current balances
    total_usdc = 0.0
    total_eth = 0.0
    unfunded = 0

    for w in wallets:
        usdc = get_usdc_balance(w["address"])
        eth = get_eth_balance(w["address"])
        if usdc >= 0:
            total_usdc += usdc
        if eth >= 0:
            total_eth += eth
        if usdc <= 0 and eth <= 0:
            unfunded += 1

    print(f"  Current totals:")
    print(f"    USDC: {format_usd(total_usdc)}")
    print(f"    ETH:  {format_eth(total_eth)}")
    print(f"    Unfunded wallets: {unfunded}/{len(wallets)}")

    # Estimated needs
    usdc_per_agent = 0.10  # $0.10 USDC starting balance
    eth_per_agent = 0.0001  # ~$0.05 in gas (more than enough for Base L2)
    num_agents = len(wallets)

    needed_usdc = max(0, usdc_per_agent * num_agents - total_usdc)
    needed_eth = max(0, eth_per_agent * num_agents - total_eth)

    print(f"\n  Funding requirements:")
    print(f"    Per agent:  {format_usd(usdc_per_agent)} USDC + {format_eth(eth_per_agent)}")
    print(f"    Agents:     {num_agents}")
    print(f"    Total needed:  {format_usd(usdc_per_agent * num_agents)} USDC + {format_eth(eth_per_agent * num_agents)}")
    print(f"    Already have:  {format_usd(total_usdc)} USDC + {format_eth(total_eth)}")
    print(f"    Still needed:  {format_usd(needed_usdc)} USDC + {format_eth(needed_eth)}")

    # Daily budget estimate
    daily_budget = 2.0  # From SOUL.md
    daily_total = daily_budget * num_agents
    print(f"\n  Daily budget (from SOUL.md):")
    print(f"    Per agent: {format_usd(daily_budget)}/day")
    print(f"    Swarm max: {format_usd(daily_total)}/day ({num_agents} agents)")
    print(f"    Current USDC covers: {total_usdc / daily_total:.1f} days (at max spend)")

    # ERC-8004 registration costs
    print(f"\n  ERC-8004 registration:")
    identities = load_identities()
    registered = sum(1 for w in wallets if identities.get(w["name"], {}).get("registrations"))
    unregistered = len(wallets) - registered
    print(f"    Registered: {registered}/{len(wallets)}")
    print(f"    Unregistered: {unregistered}")
    print(f"    Cost per registration: ~$0.002 (Base L2)")
    print(f"    Total registration cost: ~{format_usd(unregistered * 0.002)}")


def cmd_deploy_checklist(args):
    """Pre-deployment verification checklist."""
    wallets = load_wallets()
    identities = load_identities()

    print("\n📋 Deploy Checklist — KK Swarm\n")

    checks = []

    # 1. Config files exist
    wallets_ok = (CONFIG_DIR / "wallets.json").exists()
    identities_ok = (CONFIG_DIR / "identities.json").exists()
    checks.append(("Config: wallets.json", wallets_ok))
    checks.append(("Config: identities.json", identities_ok))

    # 2. Agent identities exist
    agents_dir = REPO_ROOT / "openclaw" / "agents"
    for w in wallets[:7]:  # Check first 7 (deployed agents)
        soul_ok = (agents_dir / w["name"] / "SOUL.md").exists()
        checks.append((f"Identity: {w['name']}/SOUL.md", soul_ok))

    # 3. Docker
    dockerfile_ok = (REPO_ROOT / "Dockerfile.openclaw").exists()
    checks.append(("Dockerfile.openclaw exists", dockerfile_ok))

    # 4. Terraform
    tf_main = (TERRAFORM_DIR / "main.tf").exists()
    tf_vars = (TERRAFORM_DIR / "variables.tf").exists()
    checks.append(("Terraform: main.tf", tf_main))
    checks.append(("Terraform: variables.tf", tf_vars))

    # 5. Scripts
    scripts_dir = REPO_ROOT / "scripts" / "kk"
    for script in ["restart_agent.sh", "update_agent.sh", "irc_chat.py"]:
        checks.append((f"Script: {script}", (scripts_dir / script).exists()))

    # 6. Services
    services_dir = REPO_ROOT / "services"
    for svc in ["em_client.py", "coordinator_service.py", "karma_hello_service.py"]:
        checks.append((f"Service: {svc}", (services_dir / svc).exists()))

    # 7. Libraries
    lib_dir = REPO_ROOT / "lib"
    for lib in ["eip8128_signer.py", "memory.py", "swarm_state.py", "working_state.py"]:
        checks.append((f"Library: {lib}", (lib_dir / lib).exists()))

    # 8. Entrypoint
    entrypoint = REPO_ROOT / "openclaw" / "entrypoint.sh"
    checks.append(("Entrypoint: openclaw/entrypoint.sh", entrypoint.exists()))

    # Print results
    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)

    for label, ok in checks:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {label}")

    print(f"\n  📊 {passed}/{total} checks passed")

    # Remote checks
    print(f"\n  🌐 Remote checks (live):")
    try:
        data = _http_get(f"{EM_API}/health")
        status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
        print(f"  {'✅' if status == 'healthy' else '❌'} EM API healthy: {status}")
    except Exception:
        print(f"  ❌ EM API unreachable")

    try:
        data = _http_get(f"{EM_API_V1}/auth/nonce")
        has_nonce = isinstance(data, dict) and "nonce" in data
        print(f"  {'✅' if has_nonce else '❌'} ERC-8128 nonce endpoint")
    except Exception:
        print(f"  ❌ ERC-8128 nonce endpoint unreachable")

    # Funding status
    print(f"\n  💰 Funding status (quick check — first 3 agents):")
    for w in wallets[:3]:
        usdc = get_usdc_balance(w["address"])
        eth = get_eth_balance(w["address"])
        funded = usdc > 0 and eth > 0
        print(f"  {'✅' if funded else '❌'} {w['name']}: {format_usd(usdc)} USDC + {format_eth(eth)}")

    print(f"\n  ⚠️  Remaining pre-launch blockers:")
    print(f"     • Fund all 24 wallets ($3 total: $2.40 USDC + $0.60 ETH)")
    print(f"     • Build & push Docker image to ECR")
    print(f"     • terraform apply (create EC2 instances)")
    print(f"     • Verify agent startup (check Docker logs)")


def cmd_status(args):
    """Full swarm status overview."""
    wallets = load_wallets()
    identities = load_identities()

    now = datetime.now(timezone.utc)
    print(f"\n{'='*70}")
    print(f"  🌀 KK SWARM STATUS — {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'='*70}\n")

    # Agent summary
    system_count = sum(1 for w in wallets if w["type"] == "system")
    user_count = sum(1 for w in wallets if w["type"] == "user")
    registered = sum(1 for w in wallets if identities.get(w["name"], {}).get("registrations"))
    with_executor = sum(1 for w in wallets if identities.get(w["name"], {}).get("executor_id"))

    print(f"  🤖 Agents:     {len(wallets)} total ({system_count} system + {user_count} user)")
    print(f"  📋 Registered: {registered}/{len(wallets)} on ERC-8004 (Base)")
    print(f"  🔑 Executors:  {with_executor}/{len(wallets)} have executor IDs")

    # Identity files
    agents_dir = REPO_ROOT / "openclaw" / "agents"
    soul_count = sum(1 for w in wallets if (agents_dir / w["name"] / "SOUL.md").exists())
    print(f"  🧬 SOULs:      {soul_count}/{len(wallets)} have SOUL.md")

    # Quick balance check (first 3 + platform)
    print(f"\n  💰 Balance Snapshot (first 3 agents):")
    for w in wallets[:3]:
        usdc = get_usdc_balance(w["address"])
        eth = get_eth_balance(w["address"])
        print(f"     {w['name']:<22} {format_usd(usdc):>10} USDC  {format_eth(eth):>15}")

    # EM API health
    print(f"\n  🏥 Infrastructure:")
    try:
        data = _http_get(f"{EM_API}/health")
        status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
        uptime = data.get("uptime_seconds", 0) if isinstance(data, dict) else 0
        print(f"     EM API:         {'🟢' if status == 'healthy' else '🔴'} {status} (up {uptime/3600:.1f}h)")
    except Exception:
        print(f"     EM API:         🔴 unreachable")

    try:
        data = _http_get(f"{FACILITATOR}/health")
        status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
        print(f"     Facilitator:    {'🟢' if status == 'healthy' else '🔴'} {status}")
    except Exception:
        print(f"     Facilitator:    🔴 unreachable")

    try:
        block = _rpc_call("eth_blockNumber", [])
        block_num = int(block, 16)
        print(f"     Base chain:     🟢 block {block_num:,}")
    except Exception:
        print(f"     Base chain:     🔴 unreachable")

    # Code status
    print(f"\n  📦 Codebase:")
    svc_count = len(list((REPO_ROOT / "services").glob("*.py")))
    lib_count = len(list((REPO_ROOT / "lib").glob("*.py")))
    script_count = len(list((REPO_ROOT / "scripts" / "kk").glob("*")))
    print(f"     Services:       {svc_count} files")
    print(f"     Libraries:      {lib_count} files")
    print(f"     Scripts:        {script_count} files")

    # Blockers
    print(f"\n  🚧 Blockers:")
    print(f"     1. Wallet funding ($3 total for 24 agents)")
    print(f"     2. Docker image build + ECR push")
    print(f"     3. Terraform apply (EC2 instances)")

    print(f"\n{'='*70}\n")


def cmd_report(args):
    """Generate markdown status report."""
    wallets = load_wallets()
    identities = load_identities()
    now = datetime.now(timezone.utc)

    lines = []
    lines.append(f"# KK Swarm Status Report")
    lines.append(f"**Generated:** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")

    # Agents
    system_count = sum(1 for w in wallets if w["type"] == "system")
    user_count = sum(1 for w in wallets if w["type"] == "user")
    registered = sum(1 for w in wallets if identities.get(w["name"], {}).get("registrations"))

    lines.append(f"## Agents")
    lines.append(f"- **Total:** {len(wallets)} ({system_count} system + {user_count} user)")
    lines.append(f"- **ERC-8004 registered:** {registered}/{len(wallets)}")
    lines.append("")

    lines.append(f"| # | Type | Name | Address | Agent ID |")
    lines.append(f"|---|------|------|---------|----------|")
    for w in wallets:
        identity = identities.get(w["name"], {})
        agent_id = identity.get("registrations", {}).get("base", {}).get("agent_id", "—")
        lines.append(f"| {w['index']} | {w['type']} | {w['name']} | `{w['address'][:10]}...` | {agent_id} |")

    lines.append("")

    # Balances
    lines.append(f"## Balances")
    lines.append(f"| # | Name | USDC | ETH | Status |")
    lines.append(f"|---|------|------|-----|--------|")

    total_usdc = 0.0
    total_eth = 0.0

    for w in wallets:
        usdc = get_usdc_balance(w["address"])
        eth = get_eth_balance(w["address"])
        if usdc > 0:
            total_usdc += usdc
        if eth > 0:
            total_eth += eth

        if usdc > 0 and eth > 0:
            status = "🟢 ready"
        elif usdc > 0:
            status = "🟡 needs gas"
        elif eth > 0:
            status = "🟠 gas only"
        else:
            status = "⚪ unfunded"

        lines.append(f"| {w['index']} | {w['name']} | {format_usd(usdc)} | {format_eth(eth)} | {status} |")

    lines.append(f"\n**Totals:** {format_usd(total_usdc)} USDC + {format_eth(total_eth)} ETH")
    lines.append("")

    # Health
    lines.append(f"## Infrastructure Health")
    try:
        data = _http_get(f"{EM_API}/health")
        status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
        lines.append(f"- EM API: **{status}**")
    except Exception:
        lines.append(f"- EM API: **unreachable**")

    try:
        data = _http_get(f"{FACILITATOR}/health")
        status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
        lines.append(f"- Facilitator: **{status}**")
    except Exception:
        lines.append(f"- Facilitator: **unreachable**")

    lines.append("")

    # Output
    report = "\n".join(lines)

    if getattr(args, "output", None):
        with open(args.output, "w") as f:
            f.write(report)
        print(f"📝 Report written to {args.output}")
    else:
        print(report)


def cmd_terraform_status(args):
    """Check Terraform infrastructure configuration."""
    print(f"\n🏗️ Terraform Status\n")

    if not TERRAFORM_DIR.exists():
        print(f"  ❌ Terraform directory not found: {TERRAFORM_DIR}")
        return

    # Check files
    files = list(TERRAFORM_DIR.glob("*.tf")) + list(TERRAFORM_DIR.glob("*.tpl"))
    print(f"  📁 Directory: {TERRAFORM_DIR}")
    print(f"  📄 Files: {len(files)}")
    for f in sorted(files):
        size = f.stat().st_size
        print(f"     {f.name:<30} {size:>6} bytes")

    # Check state file
    state_file = TERRAFORM_DIR / "terraform.tfstate"
    if state_file.exists():
        try:
            with open(state_file) as f:
                state = json.load(f)
            resources = state.get("resources", [])
            print(f"\n  📊 State: {len(resources)} resources")
            for r in resources:
                rtype = r.get("type", "")
                name = r.get("name", "")
                instances = len(r.get("instances", []))
                print(f"     {rtype}.{name} ({instances} instances)")
        except Exception as e:
            print(f"\n  ⚠️  State file unreadable: {e}")
    else:
        print(f"\n  ⚠️  No terraform.tfstate found (not yet applied)")
        print(f"     Run: cd {TERRAFORM_DIR} && terraform init && terraform plan")

    # Check if tfvars exists
    tfvars = list(TERRAFORM_DIR.glob("*.tfvars"))
    if tfvars:
        print(f"\n  📋 Variable files: {', '.join(f.name for f in tfvars)}")
    else:
        print(f"\n  ⚠️  No .tfvars files — need to create terraform.tfvars before apply")


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="KK Swarm Operations CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python swarm_ops.py status              # Full overview
  python swarm_ops.py balances            # Check all wallet balances
  python swarm_ops.py health              # System health check
  python swarm_ops.py irc-check           # IRC connectivity
  python swarm_ops.py auth-test           # ERC-8128 auth readiness
  python swarm_ops.py deploy-checklist    # Pre-deployment checks
  python swarm_ops.py report -o report.md # Generate markdown report
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # status
    subparsers.add_parser("status", help="Full swarm status overview")

    # agents
    agents_p = subparsers.add_parser("agents", help="List agents with details")
    agents_p.add_argument("--type", choices=["system", "user"], help="Filter by type")

    # balances
    subparsers.add_parser("balances", help="Check all wallet balances")

    # health
    subparsers.add_parser("health", help="EM API + facilitator health")

    # irc-check
    subparsers.add_parser("irc-check", help="Check IRC presence on MeshRelay")

    # auth-test
    subparsers.add_parser("auth-test", help="Test ERC-8128 auth readiness")

    # fund-estimate
    subparsers.add_parser("fund-estimate", help="Estimate funding needed")

    # deploy-checklist
    subparsers.add_parser("deploy-checklist", help="Pre-deployment verification")

    # terraform-status
    subparsers.add_parser("terraform-status", help="Check Terraform infrastructure")

    # report
    report_p = subparsers.add_parser("report", help="Generate markdown status report")
    report_p.add_argument("-o", "--output", help="Output file (default: stdout)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "status": cmd_status,
        "agents": cmd_agents,
        "balances": cmd_balances,
        "health": cmd_health,
        "irc-check": cmd_irc_check,
        "auth-test": cmd_auth_test,
        "fund-estimate": cmd_fund_estimate,
        "deploy-checklist": cmd_deploy_checklist,
        "terraform-status": cmd_terraform_status,
        "report": cmd_report,
    }

    cmd = commands.get(args.command)
    if cmd:
        cmd(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
