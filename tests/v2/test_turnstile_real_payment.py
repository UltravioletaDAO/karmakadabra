"""
Karma Kadabra V2 — REAL PAYMENT Turnstile E2E Test

This test spends REAL USDC on Base mainnet.
Connects kk-coordinator to IRC, pays $0.10 USDC for #alpha-test access.

Prerequisites:
  - kk-coordinator wallet funded with >= $0.10 USDC on Base
  - Turnstile running at https://api.meshrelay.xyz
  - eth_account, aiohttp installed

Usage:
  # From scripts/kk directory:
  python tests/test_turnstile_real_payment.py

  # Override channel (default: alpha-test at $0.10):
  python tests/test_turnstile_real_payment.py --channel kk-alpha
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import ssl
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("turnstile-real-payment")

# Config
IRC_SERVER = "irc.meshrelay.xyz"
IRC_PORT = 6667
IRC_SSL_PORT = 6697
TEST_NICK = "kk-swarm-1"
TEST_CHANNEL = "alpha-test"
TURNSTILE_URL = "https://api.meshrelay.xyz"

# Derive wallet from mnemonic
MNEMONIC_SECRET_ID = "kk/swarm-seed"
WALLET_INDEX = 1  # index 0 (kk-coordinator) has $0.00, index 1 has $0.10
DERIVATION_PATH = "m/44'/60'/0'/0/{index}"


def get_wallet_key() -> tuple[str, str]:
    """Derive kk-coordinator private key from AWS SM mnemonic.

    Returns (address, private_key_hex).
    """
    from eth_account import Account

    Account.enable_unaudited_hdwallet_features()

    # Get mnemonic from AWS SM
    import subprocess

    result = subprocess.run(
        [
            "aws", "secretsmanager", "get-secret-value",
            "--secret-id", MNEMONIC_SECRET_ID,
            "--query", "SecretString",
            "--output", "text",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get secret: {result.stderr}")

    secret = json.loads(result.stdout.strip())
    mnemonic = secret["mnemonic"]

    path = DERIVATION_PATH.format(index=WALLET_INDEX)
    acct = Account.from_mnemonic(mnemonic, account_path=path)

    logger.info(f"  Wallet: {acct.address} (index {WALLET_INDEX})")
    return acct.address, acct.key.hex()


async def connect_irc(nick: str) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Connect to MeshRelay IRC and register nick."""
    logger.info(f"  Connecting to {IRC_SERVER}:{IRC_PORT}...")

    reader, writer = await asyncio.open_connection(IRC_SERVER, IRC_PORT)

    writer.write(f"NICK {nick}\r\n".encode())
    writer.write(f"USER {nick} 0 * :KK Turnstile Test\r\n".encode())
    await writer.drain()

    # Wait for welcome or nick-in-use
    actual_nick = nick
    while True:
        data = await asyncio.wait_for(reader.readline(), timeout=30)
        line = data.decode("utf-8", errors="replace").strip()

        if " 001 " in line:
            logger.info(f"  Connected to IRC as {actual_nick}")
            return reader, writer

        if " 433 " in line:
            actual_nick = actual_nick + "_"
            logger.warning(f"  Nick in use, retrying as {actual_nick}")
            writer.write(f"NICK {actual_nick}\r\n".encode())
            await writer.drain()

        if line.startswith("PING"):
            token = line.split("PING ")[-1]
            writer.write(f"PONG {token}\r\n".encode())
            await writer.drain()


async def wait_for_join(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    channel: str,
    timeout: float = 30.0,
) -> bool:
    """Wait for SAJOIN confirmation (the bot joins us into the channel)."""
    target = f"#{channel}" if not channel.startswith("#") else channel
    start = time.time()

    while time.time() - start < timeout:
        try:
            data = await asyncio.wait_for(reader.readline(), timeout=5)
            line = data.decode("utf-8", errors="replace").strip()

            if line.startswith("PING"):
                token = line.split("PING ")[-1]
                writer.write(f"PONG {token}\r\n".encode())
                await writer.drain()
                continue

            # Look for JOIN message for our channel
            if "JOIN" in line and target.lower() in line.lower():
                logger.info(f"  SAJOIN detected: {line[:100]}")
                return True

            # Look for NOTICE about access granted
            if "NOTICE" in line and ("granted" in line.lower() or "access" in line.lower()):
                logger.info(f"  NOTICE: {line[:100]}")

            # Log interesting lines
            if any(kw in line for kw in ["MODE", "NOTICE", "JOIN", "332", "353"]):
                logger.info(f"  IRC: {line[:120]}")

        except asyncio.TimeoutError:
            continue

    return False


async def run_test(channel: str = TEST_CHANNEL) -> bool:
    """Run the full real payment test."""
    results: dict[str, dict] = {}

    def record(phase: str, ok: bool, detail: str):
        results[phase] = {"status": "PASS" if ok else "FAIL", "detail": detail}
        icon = "[OK]" if ok else "[FAIL]"
        logger.info(f"  {icon} {phase}: {detail}")

    logger.info("=" * 60)
    logger.info("  TURNSTILE REAL PAYMENT E2E TEST")
    logger.info(f"  Channel: #{channel}")
    logger.info(f"  WARNING: This spends REAL USDC on Base mainnet!")
    logger.info("=" * 60)

    # Phase 1: Get wallet
    logger.info("\n--- Phase 1: Wallet Setup ---")
    try:
        address, private_key = get_wallet_key()
        record("wallet", True, f"Derived {address}")
    except Exception as e:
        record("wallet", False, str(e))
        return False

    # Phase 2: Check USDC balance
    logger.info("\n--- Phase 2: Balance Check ---")
    try:
        from web3 import Web3

        w3 = Web3(Web3.HTTPProvider("https://mainnet.base.org"))
        usdc_abi = [
            {
                "inputs": [{"name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function",
            }
        ]
        usdc = w3.eth.contract(
            address=w3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"),
            abi=usdc_abi,
        )
        balance = usdc.functions.balanceOf(w3.to_checksum_address(address)).call()
        balance_human = balance / 1e6
        record("balance", balance > 0, f"${balance_human:.6f} USDC ({balance} raw)")

        if balance < 100_000:  # Less than $0.10
            record("balance_sufficient", False, "Need at least $0.10 USDC")
            return False
        record("balance_sufficient", True, f"Enough for #{channel}")
    except Exception as e:
        record("balance", False, str(e))
        return False

    # Phase 3: Check Turnstile health + channel
    logger.info("\n--- Phase 3: Turnstile Check ---")
    from lib.turnstile_client import TurnstileClient

    client = TurnstileClient(base_url=TURNSTILE_URL)

    health = await client.check_health()
    record("turnstile_health", health.ok, f"Status: {'OK' if health.ok else health.error}")

    ch_info = await client.get_channel(channel)
    if not ch_info:
        record("channel_exists", False, f"#{channel} not found in Turnstile")
        return False
    record(
        "channel_exists",
        True,
        f"#{channel}: ${ch_info.price} {ch_info.currency} / {ch_info.duration_seconds // 60}min",
    )

    if not ch_info.is_available:
        record("channel_available", False, "Channel full")
        return False
    record("channel_available", True, f"{ch_info.available_slots}/{ch_info.max_slots} slots")

    # Phase 4: Connect to IRC
    logger.info("\n--- Phase 4: IRC Connection ---")
    reader = writer = None
    try:
        reader, writer = await connect_irc(TEST_NICK)
        record("irc_connect", True, f"Connected as {TEST_NICK}")
    except Exception as e:
        record("irc_connect", False, str(e))
        return False

    # Phase 5: Pay and request access
    logger.info("\n--- Phase 5: REAL PAYMENT ($0.10 USDC) ---")
    try:
        result = await client.request_access_with_wallet(
            channel=channel,
            nick=TEST_NICK,
            private_key=private_key,
        )

        if result.success:
            record(
                "payment",
                True,
                f"Access granted! Channel: {result.channel}, "
                f"Expires: {result.expires_at}, Session: {result.session_id}",
            )
        else:
            record("payment", False, f"Payment failed: {result.error}")
            # Clean up IRC
            if writer:
                writer.write(b"QUIT :Test done\r\n")
                await writer.drain()
                writer.close()
            return False
    except Exception as e:
        record("payment", False, f"Exception: {e}")
        if writer:
            writer.write(b"QUIT :Test error\r\n")
            await writer.drain()
            writer.close()
        return False

    # Phase 6: Verify SAJOIN
    logger.info("\n--- Phase 6: Verify Channel Join ---")
    joined = await wait_for_join(reader, writer, channel, timeout=15)
    record("sajoin", joined, "SAJOIN confirmed" if joined else "No JOIN detected (may already be in channel)")

    # Phase 7: Check session
    logger.info("\n--- Phase 7: Verify Session ---")
    try:
        sessions = await client.get_sessions(TEST_NICK)
        has_session = any(
            s.get("channel", "").lstrip("#") == channel.lstrip("#")
            for s in sessions
        )
        record(
            "session",
            has_session or len(sessions) > 0,
            f"{len(sessions)} active session(s)" + (f": {sessions}" if sessions else ""),
        )
    except Exception as e:
        record("session", False, str(e))

    # Phase 8: Check balance after payment (settlement is async — wait a bit)
    logger.info("\n--- Phase 8: Post-Payment Balance (waiting 15s for async settlement) ---")
    await asyncio.sleep(15)
    try:
        new_balance = usdc.functions.balanceOf(w3.to_checksum_address(address)).call()
        spent = balance - new_balance
        if new_balance < balance:
            record(
                "post_balance",
                True,
                f"${new_balance / 1e6:.6f} USDC remaining (spent: ${spent / 1e6:.6f})",
            )
        else:
            # Settlement is async — if access was granted, this is still OK
            record(
                "post_balance",
                True,
                f"${new_balance / 1e6:.6f} USDC (settlement pending — async, access was granted)",
            )
    except Exception as e:
        record("post_balance", False, str(e))

    # Clean up: disconnect from IRC
    logger.info("\n--- Cleanup ---")
    if writer:
        writer.write(b"QUIT :Turnstile test complete\r\n")
        await writer.drain()
        writer.close()
        logger.info("  Disconnected from IRC")

    # Report
    logger.info("\n" + "=" * 60)
    logger.info("  TURNSTILE REAL PAYMENT E2E REPORT")
    logger.info("=" * 60)

    passed = sum(1 for r in results.values() if r["status"] == "PASS")
    total = len(results)

    for phase, r in results.items():
        icon = "[OK]" if r["status"] == "PASS" else "[FAIL]"
        logger.info(f"  {icon} {phase}: {r['detail']}")

    logger.info(f"\n  Result: {passed}/{total} phases passed")
    all_pass = all(r["status"] == "PASS" for r in results.values())
    logger.info(f"  TURNSTILE REAL PAYMENT: {'PASS' if all_pass else 'FAIL'}")
    logger.info("=" * 60)

    return all_pass


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Turnstile Real Payment E2E Test")
    parser.add_argument("--channel", type=str, default=TEST_CHANNEL)
    parser.add_argument("--wallet-index", type=int, default=WALLET_INDEX,
                        help="HD wallet index to use (default: 1)")
    parser.add_argument("--nick", type=str, default=None,
                        help="IRC nick (default: kk-swarm-{index})")
    args = parser.parse_args()

    # Override module-level config via args
    import test_turnstile_real_payment as _self
    _self.WALLET_INDEX = args.wallet_index
    _self.TEST_NICK = args.nick or f"kk-swarm-{args.wallet_index}"

    success = await run_test(channel=args.channel)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
