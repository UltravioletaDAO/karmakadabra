#!/usr/bin/env python3
"""
IRC Command Signer for Karmacadabra

Signs IRC commands with HMAC-SHA256 for secure agent control.

Usage:
    # Set your secret (same as IRC_HMAC_SECRET in docker-compose)
    export IRC_HMAC_SECRET=your-secret-here

    # Sign commands
    python scripts/irc_sign.py "!ping agent:all"
    python scripts/irc_sign.py "!dispatch karma-hello summarize {\"stream_id\":\"2026-01-08\"}"
    python scripts/irc_sign.py "!halt karma-cabra:all"

    # Generate a new secret
    python scripts/irc_sign.py --generate-secret

Output:
    Copy the signed command and paste it into IRC.
"""

import os
import sys
import argparse
import secrets

# Add shared to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.irc_protocol import format_signed_command, sign_command


def generate_secret():
    """Generate a new HMAC secret"""
    secret = secrets.token_hex(32)
    print("\nGenerated HMAC Secret (save this securely):")
    print("-" * 64)
    print(secret)
    print("-" * 64)
    print("\nAdd to your environment:")
    print(f'  export IRC_HMAC_SECRET="{secret}"')
    print("\nOr add to docker-compose.irc.yml:")
    print(f'  - IRC_HMAC_SECRET={secret}')


def sign_single_command(raw: str, secret: str):
    """Sign a single command"""
    signed = format_signed_command(raw, secret)

    print("\n" + "=" * 60)
    print("SIGNED IRC COMMAND")
    print("=" * 60)
    print(f"\nOriginal:  {raw}")
    print(f"\nSigned (copy this to IRC):")
    print("-" * 60)
    print(signed)
    print("-" * 60)

    # Verify
    from shared.irc_protocol import parse_irc_command, verify_command
    raw_check, sig = parse_irc_command(signed)
    is_valid = verify_command(secret, raw_check, sig)
    print(f"\nVerification: {'PASS' if is_valid else 'FAIL'}")


def interactive_mode(secret: str):
    """Interactive command signing"""
    print("\n" + "=" * 60)
    print("IRC COMMAND SIGNER - Interactive Mode")
    print("=" * 60)
    print("Type commands without |sig=... and press Enter to sign.")
    print("Type 'quit' or Ctrl+C to exit.\n")

    print("Examples:")
    print('  !ping agent:all')
    print('  !status karma-hello')
    print('  !dispatch validator validate {"data_type":"chat_log"}')
    print('  !halt karma-cabra:all')
    print()

    while True:
        try:
            raw = input("Command> ").strip()
            if not raw:
                continue
            if raw.lower() in ('quit', 'exit', 'q'):
                break
            if not raw.startswith("!"):
                raw = "!" + raw

            signed = format_signed_command(raw, secret)
            print(f"\nSigned:\n{signed}\n")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break


def main():
    parser = argparse.ArgumentParser(
        description="Sign IRC commands for Karmacadabra agent control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/irc_sign.py "!ping agent:all"
  python scripts/irc_sign.py "!dispatch karma-hello summarize {}"
  python scripts/irc_sign.py --interactive
  python scripts/irc_sign.py --generate-secret
        """
    )

    parser.add_argument(
        "command",
        nargs="?",
        help="IRC command to sign (e.g., '!ping agent:all')"
    )

    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Enter interactive mode for signing multiple commands"
    )

    parser.add_argument(
        "-g", "--generate-secret",
        action="store_true",
        help="Generate a new HMAC secret"
    )

    parser.add_argument(
        "-s", "--secret",
        help="HMAC secret (overrides IRC_HMAC_SECRET env var)"
    )

    args = parser.parse_args()

    # Generate secret mode
    if args.generate_secret:
        generate_secret()
        return

    # Get secret
    secret = args.secret or os.getenv("IRC_HMAC_SECRET")
    if not secret:
        print("ERROR: No HMAC secret provided.")
        print("Either set IRC_HMAC_SECRET environment variable or use --secret")
        print("Generate a new secret with: python scripts/irc_sign.py --generate-secret")
        sys.exit(1)

    # Interactive mode
    if args.interactive:
        interactive_mode(secret)
        return

    # Single command mode
    if args.command:
        sign_single_command(args.command, secret)
        return

    # No command given - show help
    parser.print_help()


if __name__ == "__main__":
    main()
