#!/usr/bin/env python3
"""
Balance Monitoring Script for Karmacadabra Ecosystem
=====================================================
Checks balances for all wallets across multiple chains and tokens:
- Native tokens (AVAX, ETH)
- ERC-20 tokens (GLUE, USDC)
- System agents, facilitators, user agents

Usage:
    python scripts/check_all_balances.py                          # Check all chains (testnets + mainnets)
    python scripts/check_all_balances.py --chain testnets         # Check only testnets
    python scripts/check_all_balances.py --chain mainnets         # Check only mainnets
    python scripts/check_all_balances.py --chain fuji             # Check Fuji only
    python scripts/check_all_balances.py --wallet-type system     # Check only system agents
    python scripts/check_all_balances.py --show-empty             # Show wallets with 0 balance
"""

import os
import sys
import json
import argparse
import boto3
from web3 import Web3
from typing import Dict, List, Tuple
from decimal import Decimal

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Chain configurations
CHAINS = {
    # Testnets
    'fuji': {
        'name': 'Avalanche Fuji (Testnet)',
        'rpc': 'https://avalanche-fuji-c-chain-rpc.publicnode.com',
        'chain_id': 43113,
        'native_symbol': 'AVAX',
        'explorer': 'https://testnet.snowtrace.io',
        'is_testnet': True
    },
    'base-sepolia': {
        'name': 'Base Sepolia (Testnet)',
        'rpc': 'https://base-testnet.rpc.grove.city/v1/01fdb492',
        'chain_id': 84532,
        'native_symbol': 'ETH',
        'explorer': 'https://sepolia.basescan.org',
        'is_testnet': True
    },
    'celo-sepolia': {
        'name': 'Celo Sepolia (Testnet)',
        'rpc': 'https://rpc.ankr.com/celo_sepolia',
        'chain_id': 44787,
        'native_symbol': 'CELO',
        'explorer': 'https://sepolia.celoscan.io',
        'is_testnet': True
    },

    # Mainnets
    'avalanche': {
        'name': 'Avalanche C-Chain (Mainnet)',
        'rpc': 'https://avalanche-c-chain-rpc.publicnode.com',
        'chain_id': 43114,
        'native_symbol': 'AVAX',
        'explorer': 'https://snowtrace.io',
        'is_testnet': False
    },
    'base': {
        'name': 'Base Mainnet',
        'rpc': 'https://mainnet.base.org',
        'chain_id': 8453,
        'native_symbol': 'ETH',
        'explorer': 'https://basescan.org',
        'is_testnet': False
    },
    'celo': {
        'name': 'Celo Mainnet',
        'rpc': 'https://forno.celo.org',
        'chain_id': 42220,
        'native_symbol': 'CELO',
        'explorer': 'https://celoscan.io',
        'is_testnet': False
    }
}

# Known token contracts per chain
TOKEN_CONTRACTS = {
    # Testnets
    'fuji': {
        'GLUE': {
            'address': '0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743',
            'decimals': 6
        }
    },
    'base-sepolia': {
        'USDC': {
            'address': '0x036CbD53842c5426634e7929541eC2318f3dCF7e',
            'decimals': 6
        }
    },
    # Note: Celo Sepolia token contracts may not be deployed yet

    # Mainnets
    'avalanche': {
        'USDC': {
            'address': '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',
            'decimals': 6
        }
    },
    'base': {
        'USDC': {
            'address': '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
            'decimals': 6
        }
    },
    'celo': {
        'cUSD': {
            'address': '0x765DE816845861e75A25fCA122bb6898B8B1282a',
            'decimals': 18
        },
        'USDC': {
            'address': '0xcebA9300f2b948710d2653dD7B07f33A8B32118C',
            'decimals': 6
        }
    }
}

# Minimal ERC-20 ABI
ERC20_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    }
]

def get_all_wallets_from_aws() -> Dict[str, Dict]:
    """
    Fetch all wallet addresses from AWS Secrets Manager
    Derives addresses from private keys when not explicitly stored

    Returns:
        Dict with wallet categories and their addresses
    """
    try:
        from eth_account import Account

        client = boto3.client('secretsmanager', region_name='us-east-1')
        response = client.get_secret_value(SecretId='karmacadabra')
        secrets = json.loads(response['SecretString'])

        wallets = {
            'system_agents': {},
            'facilitators': {},
            'deployers': {},
            'user_agents': {},
            'other': {}
        }

        # Known system agent names
        system_agents = [
            'validator-agent', 'karma-hello-agent', 'abracadabra-agent',
            'skill-extractor-agent', 'voice-extractor-agent', 'client-agent',
            'marketplace-agent'
        ]

        # Deployers
        deployers = ['erc-20', 'erc-8004']

        for key, value in secrets.items():
            if not isinstance(value, dict):
                continue

            # Get address or derive from private key
            address = value.get('address')
            if not address:
                # Try to derive from private key
                private_key = value.get('private_key')
                if private_key:
                    try:
                        account = Account.from_key(private_key)
                        address = account.address
                        print(f"{Colors.WARNING}[INFO] Derived address for {key}: {address}{Colors.ENDC}")
                    except Exception as e:
                        print(f"{Colors.WARNING}[WARN] Could not derive address for {key}: {e}{Colors.ENDC}")
                        continue
                else:
                    continue

            # Categorize wallet
            if key in system_agents:
                wallets['system_agents'][key] = {
                    'address': address,
                    'description': value.get('description', key)
                }
            elif key in deployers:
                wallets['deployers'][key] = {
                    'address': address,
                    'description': value.get('description', f'{key.upper()} contract deployer')
                }
            elif key == 'user-agents':
                # Skip, will be processed separately
                continue
            else:
                wallets['other'][key] = {
                    'address': address,
                    'description': value.get('description', key)
                }

        # Process user agents
        if 'user-agents' in secrets:
            for username, user_data in secrets['user-agents'].items():
                if not isinstance(user_data, dict):
                    continue

                address = user_data.get('address')
                if not address:
                    # Try to derive from private key
                    private_key = user_data.get('private_key')
                    if private_key:
                        try:
                            account = Account.from_key(private_key)
                            address = account.address
                        except Exception:
                            continue
                    else:
                        continue

                wallets['user_agents'][username] = {
                    'address': address,
                    'description': f'User agent: {username}'
                }

        # Fetch facilitator wallets from separate AWS secrets
        for facilitator_secret in ['karmacadabra-facilitator-testnet', 'karmacadabra-facilitator-mainnet']:
            try:
                fac_response = client.get_secret_value(SecretId=facilitator_secret)
                fac_data = json.loads(fac_response['SecretString'])

                address = fac_data.get('address')
                if not address and 'private_key' in fac_data:
                    try:
                        account = Account.from_key(fac_data['private_key'])
                        address = account.address
                    except Exception:
                        continue

                if address:
                    # Use friendly name
                    name = facilitator_secret.replace('karmacadabra-', '')
                    wallets['facilitators'][name] = {
                        'address': address,
                        'description': f'x402 payment facilitator ({facilitator_secret})'
                    }
            except Exception as e:
                print(f"{Colors.WARNING}[WARN] Could not fetch {facilitator_secret}: {str(e)[:50]}{Colors.ENDC}")

        return wallets

    except Exception as e:
        print(f"{Colors.FAIL}[ERROR] Failed to fetch wallets from AWS: {e}{Colors.ENDC}")
        sys.exit(1)

def get_native_balance(w3: Web3, address: str) -> Decimal:
    """Get native token balance (ETH/AVAX/CELO)"""
    try:
        balance_wei = w3.eth.get_balance(address)
        return Decimal(w3.from_wei(balance_wei, 'ether'))
    except Exception:
        # Silently return 0 if RPC fails
        return Decimal('0')

def get_token_balance(w3: Web3, token_address: str, wallet_address: str, decimals: int) -> Decimal:
    """Get ERC-20 token balance"""
    try:
        contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
        balance = contract.functions.balanceOf(wallet_address).call(timeout=10)
        return Decimal(balance) / Decimal(10 ** decimals)
    except Exception as e:
        # Silently return 0 if token contract doesn't exist or RPC fails
        return Decimal('0')

def format_balance(balance: Decimal, symbol: str, width: int = 15) -> str:
    """Format balance with color coding"""
    balance_str = f"{balance:.6f}".rstrip('0').rstrip('.')
    formatted = f"{balance_str} {symbol}".ljust(width)

    if balance == 0:
        return f"{Colors.FAIL}{formatted}{Colors.ENDC}"
    elif balance < Decimal('0.05'):
        return f"{Colors.WARNING}{formatted}{Colors.ENDC}"
    else:
        return f"{Colors.OKGREEN}{formatted}{Colors.ENDC}"

def get_all_balances_matrix(wallets: Dict, chains_to_check: List[str], show_empty: bool = False) -> Dict:
    """
    Get balances for all wallets across all chains in a matrix format

    Returns:
        Dict with structure: {category: {wallet_name: {chain: {native: x, tokens: {symbol: y}}}}}
    """
    matrix = {}

    # Connect to all chains first
    chain_connections = {}
    for chain_name in chains_to_check:
        if chain_name not in CHAINS:
            continue

        chain_config = CHAINS[chain_name]
        print(f"{Colors.OKBLUE}[INFO] Connecting to {chain_config['name']}...{Colors.ENDC}")

        try:
            w3 = Web3(Web3.HTTPProvider(chain_config['rpc'], request_kwargs={'timeout': 15}))
            if w3.is_connected():
                chain_connections[chain_name] = w3
                print(f"{Colors.OKGREEN}  ✓ Connected (Chain ID: {w3.eth.chain_id}){Colors.ENDC}")
            else:
                print(f"{Colors.FAIL}  ✗ Failed to connect{Colors.ENDC}")
        except KeyboardInterrupt:
            raise  # Allow user to interrupt
        except Exception as e:
            print(f"{Colors.FAIL}  ✗ Connection error: {str(e)[:50]}{Colors.ENDC}")

    print()

    # Get balances for all wallets across all chains
    for category, category_wallets in wallets.items():
        if not category_wallets:
            continue

        matrix[category] = {}

        for name, wallet_info in category_wallets.items():
            address = wallet_info['address']
            matrix[category][name] = {
                'address': address,
                'description': wallet_info.get('description', name),
                'chains': {}
            }

            # Get balances for each chain
            for chain_name, w3 in chain_connections.items():
                try:
                    chain_config = CHAINS[chain_name]
                    tokens = TOKEN_CONTRACTS.get(chain_name, {})

                    # Get native balance
                    native_balance = get_native_balance(w3, address)

                    # Get token balances
                    token_balances = {}
                    for token_symbol, token_config in tokens.items():
                        try:
                            token_balance = get_token_balance(
                                w3,
                                token_config['address'],
                                address,
                                token_config['decimals']
                            )
                            token_balances[token_symbol] = token_balance
                        except KeyboardInterrupt:
                            raise  # Allow user to interrupt
                        except Exception:
                            token_balances[token_symbol] = Decimal('0')

                    matrix[category][name]['chains'][chain_name] = {
                        'native': native_balance,
                        'native_symbol': chain_config['native_symbol'],
                        'tokens': token_balances
                    }
                except KeyboardInterrupt:
                    raise  # Allow user to interrupt
                except Exception as e:
                    # Skip this chain for this wallet if there's an error
                    print(f"{Colors.WARNING}[WARN] Error checking {name} on {chain_name}: {str(e)[:50]}{Colors.ENDC}")

    return matrix


def format_balance_compact(balance: Decimal, symbol: str) -> str:
    """Format balance in compact form with color coding"""
    if balance == 0:
        return f"{Colors.FAIL}0{Colors.ENDC}"
    elif balance < Decimal('0.05'):
        balance_str = f"{balance:.3f}".rstrip('0').rstrip('.')
        return f"{Colors.WARNING}{balance_str}{Colors.ENDC}"
    else:
        balance_str = f"{balance:.3f}".rstrip('0').rstrip('.')
        return f"{Colors.OKGREEN}{balance_str}{Colors.ENDC}"


def print_balance_matrix(matrix: Dict, chains_to_check: List[str], show_empty: bool = False):
    """Print balances in matrix/table format"""

    for category, category_wallets in matrix.items():
        if not category_wallets:
            continue

        # Category header
        category_display = category.replace('_', ' ').title()
        print(f"\n{Colors.OKCYAN}{Colors.BOLD}## {category_display} ({len(category_wallets)} wallets){Colors.ENDC}")

        # Calculate width based on number of chains
        table_width = 70 + (len(chains_to_check) * 22)
        print(f"{Colors.OKCYAN}{'─' * table_width}{Colors.ENDC}\n")

        # Build header row
        header = f"{'Wallet':<25} | {'Address':<42} |"
        for chain_name in chains_to_check:
            if chain_name in CHAINS:
                chain_config = CHAINS[chain_name]
                header += f" {chain_name:<20} |"

        print(f"{Colors.BOLD}{header}{Colors.ENDC}")
        print('─' * len(header.replace(Colors.BOLD, '').replace(Colors.ENDC, '')))

        # Print each wallet
        for name, wallet_data in sorted(category_wallets.items()):
            address = wallet_data['address']
            chains_data = wallet_data['chains']

            # Skip if all balances are 0 and show_empty is False
            if not show_empty:
                has_balance = False
                for chain_data in chains_data.values():
                    if chain_data['native'] > 0 or any(chain_data['tokens'].values()):
                        has_balance = True
                        break
                if not has_balance:
                    continue

            # First row: wallet name, address, native balances
            row = f"{name:<25} | {address:<42} |"
            for chain_name in chains_to_check:
                if chain_name in chains_data:
                    chain_data = chains_data[chain_name]
                    native_str = format_balance_compact(chain_data['native'], chain_data['native_symbol'])
                    symbol = chain_data['native_symbol']
                    # Remove color codes for length calculation
                    display_str = f"{native_str} {symbol}"
                    # Calculate padding considering ANSI codes
                    ansi_length = len(Colors.FAIL) + len(Colors.ENDC) if chain_data['native'] == 0 else \
                                  len(Colors.WARNING) + len(Colors.ENDC) if chain_data['native'] < Decimal('0.05') else \
                                  len(Colors.OKGREEN) + len(Colors.ENDC)
                    padding = 20 + ansi_length
                    row += f" {display_str:<{padding}} |"
                else:
                    row += f" {'N/A':<20} |"

            print(row)

            # Second row: tokens (if any)
            has_tokens = False
            for chain_data in chains_data.values():
                if any(chain_data['tokens'].values()):
                    has_tokens = True
                    break

            if has_tokens:
                token_row = f"{'':<25} | {'':<42} |"
                for chain_name in chains_to_check:
                    if chain_name in chains_data:
                        chain_data = chains_data[chain_name]
                        tokens_str = []
                        for token_symbol, token_balance in chain_data['tokens'].items():
                            if token_balance > 0 or show_empty:
                                bal_str = format_balance_compact(token_balance, token_symbol)
                                tokens_str.append(f"{bal_str} {token_symbol}")

                        if tokens_str:
                            display = ", ".join(tokens_str)
                            # Calculate padding with ANSI codes
                            ansi_count = display.count(Colors.FAIL) + display.count(Colors.WARNING) + display.count(Colors.OKGREEN)
                            padding = 20 + (ansi_count * (len(Colors.FAIL) + len(Colors.ENDC)))
                            token_row += f" {display:<{padding}} |"
                        else:
                            token_row += f" {'-':<20} |"
                    else:
                        token_row += f" {'-':<20} |"

                print(token_row)

            print()  # Empty line between wallets

def main():
    # Build chain choices dynamically
    chain_choices = list(CHAINS.keys()) + ['all', 'testnets', 'mainnets']

    parser = argparse.ArgumentParser(
        description='Check balances for all Karmacadabra wallets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Check all chains (testnets + mainnets, default)
  python check_all_balances.py

  # Check only testnets
  python check_all_balances.py --chain testnets

  # Check only mainnets
  python check_all_balances.py --chain mainnets

  # Check specific chain
  python check_all_balances.py --chain fuji
  python check_all_balances.py --chain avalanche
        '''
    )
    parser.add_argument(
        '--chain',
        choices=chain_choices,
        default='all',
        help='Which chain(s) to check (default: all - testnets + mainnets)'
    )
    parser.add_argument(
        '--wallet-type',
        choices=['system', 'facilitators', 'deployers', 'user', 'all'],
        default='all',
        help='Which wallet type to check (default: all)'
    )
    parser.add_argument(
        '--show-empty',
        action='store_true',
        help='Show wallets with 0 balance'
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )

    args = parser.parse_args()

    # Disable colors if requested
    if args.no_color:
        for attr in dir(Colors):
            if not attr.startswith('_'):
                setattr(Colors, attr, '')

    print(f"{Colors.HEADER}{Colors.BOLD}")
    print("=" * 80)
    print("KARMACADABRA ECOSYSTEM - BALANCE MONITOR")
    print("=" * 80)
    print(f"{Colors.ENDC}")

    # Fetch all wallets from AWS
    print(f"{Colors.OKBLUE}[INFO] Fetching wallet addresses from AWS Secrets Manager...{Colors.ENDC}")
    all_wallets = get_all_wallets_from_aws()

    # Filter by wallet type
    if args.wallet_type != 'all':
        type_map = {
            'system': 'system_agents',
            'facilitators': 'facilitators',
            'deployers': 'deployers',
            'user': 'user_agents'
        }
        filtered_wallets = {type_map[args.wallet_type]: all_wallets[type_map[args.wallet_type]]}
        all_wallets = filtered_wallets

    # Count total wallets
    total_wallets = sum(len(category) for category in all_wallets.values())
    print(f"{Colors.OKBLUE}[INFO] Found {total_wallets} wallets{Colors.ENDC}")

    # Determine which chains to check
    if args.chain == 'all':
        # Check all chains (testnets + mainnets)
        chains_to_check = list(CHAINS.keys())
    elif args.chain == 'testnets':
        # Only testnets
        chains_to_check = [name for name, config in CHAINS.items() if config.get('is_testnet', False)]
    elif args.chain == 'mainnets':
        # Only mainnets
        chains_to_check = [name for name, config in CHAINS.items() if not config.get('is_testnet', False)]
    else:
        # Specific chain
        chains_to_check = [args.chain]

    print(f"{Colors.OKBLUE}[INFO] Checking {len(chains_to_check)} chain(s): {', '.join(chains_to_check)}{Colors.ENDC}\n")

    # Get all balances in matrix format
    balance_matrix = get_all_balances_matrix(all_wallets, chains_to_check, args.show_empty)

    # Print matrix
    print_balance_matrix(balance_matrix, chains_to_check, args.show_empty)

    # Summary
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}SUMMARY{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")
    print(f"  Chains checked:    {', '.join(chains_to_check)}")
    print(f"  Total wallets:     {total_wallets}")
    print(f"  Wallet categories: {len([c for c in all_wallets.values() if c])}")
    print()
    print(f"{Colors.OKGREEN}[DONE] Balance check complete{Colors.ENDC}\n")

if __name__ == "__main__":
    main()
