#!/usr/bin/env python3
"""
Fund Agent Wallets on Base Sepolia
Sends 0.005 ETH from deployer wallet to each system agent wallet
"""

import json
import boto3
from web3 import Web3
from decimal import Decimal

# Configuration
BASE_SEPOLIA_RPC = "https://base-sepolia.g.alchemy.com/v2/demo"  # Alchemy public endpoint
CHAIN_ID = 84532
FUNDING_AMOUNT = Web3.to_wei(0.005, 'ether')  # 0.005 ETH per agent

# Agent wallets to fund
AGENT_WALLETS = {
    "validator": "0x1219eF9484BF7E40E6479141B32634623d37d507",
    "karma-hello": "0x2C3e071df446B25B821F59425152838ae4931E75",
    "abracadabra": "0x940DDDf6fB28E611b132FbBedbc4854CC7C22648",
    "skill-extractor": "0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9",
    "voice-extractor": "0x8e0Db88181668cdE24660D7Ee8dA18A77DDbbF96"
}

def get_deployer_key():
    """Get deployer private key from AWS Secrets Manager"""
    print("[*] Fetching deployer private key from AWS Secrets Manager...")

    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name='us-east-1'
    )

    try:
        response = client.get_secret_value(SecretId='karmacadabra')
        secret = json.loads(response['SecretString'])

        # Get ERC-20 deployer key
        erc20_key = secret.get('erc-20', {}).get('private_key')
        if not erc20_key:
            raise ValueError("ERC-20 deployer private key not found in AWS")

        print("[+] Deployer key retrieved successfully")
        return erc20_key
    except Exception as e:
        print(f"[-] Error fetching secret: {e}")
        raise

def fund_agents():
    """Fund all agent wallets with ETH"""

    # Connect to Base Sepolia
    print(f"[*] Connecting to Base Sepolia: {BASE_SEPOLIA_RPC}")
    w3 = Web3(Web3.HTTPProvider(BASE_SEPOLIA_RPC))

    if not w3.is_connected():
        raise Exception("Failed to connect to Base Sepolia RPC")

    print(f"[+] Connected to Base Sepolia (Chain ID: {w3.eth.chain_id})")

    # Get deployer account
    deployer_key = get_deployer_key()
    deployer_account = w3.eth.account.from_key(deployer_key)
    deployer_address = deployer_account.address

    print(f"\n[*] Deployer Address: {deployer_address}")

    # Check deployer balance
    deployer_balance = w3.eth.get_balance(deployer_address)
    deployer_balance_eth = w3.from_wei(deployer_balance, 'ether')
    print(f"   Balance: {deployer_balance_eth} ETH")

    # Calculate total needed (funding + gas estimate)
    total_funding = FUNDING_AMOUNT * len(AGENT_WALLETS)
    gas_estimate = w3.to_wei(0.001, 'ether')  # ~0.001 ETH for all txs
    total_needed = total_funding + gas_estimate

    print(f"\n[*] Funding Plan:")
    print(f"   Amount per agent: {w3.from_wei(FUNDING_AMOUNT, 'ether')} ETH")
    print(f"   Number of agents: {len(AGENT_WALLETS)}")
    print(f"   Total funding: {w3.from_wei(total_funding, 'ether')} ETH")
    print(f"   Estimated gas: {w3.from_wei(gas_estimate, 'ether')} ETH")
    print(f"   Total needed: {w3.from_wei(total_needed, 'ether')} ETH")

    if deployer_balance < total_needed:
        raise Exception(f"Insufficient balance. Need {w3.from_wei(total_needed, 'ether')} ETH, have {deployer_balance_eth} ETH")

    print(f"   Remaining after: {w3.from_wei(deployer_balance - total_needed, 'ether')} ETH")

    # Confirm
    print(f"\n[!] About to send {len(AGENT_WALLETS)} transactions...")
    input("Press Enter to continue or Ctrl+C to cancel...")

    # Get nonce
    nonce = w3.eth.get_transaction_count(deployer_address)

    # Fund each agent
    print("\n[*] Funding agents...")
    txs = []

    for agent_name, agent_address in AGENT_WALLETS.items():
        print(f"\n[*] Funding {agent_name}...")
        print(f"   To: {agent_address}")
        print(f"   Amount: {w3.from_wei(FUNDING_AMOUNT, 'ether')} ETH")

        # Check current balance
        current_balance = w3.eth.get_balance(agent_address)
        print(f"   Current balance: {w3.from_wei(current_balance, 'ether')} ETH")

        # Build transaction
        tx = {
            'nonce': nonce,
            'to': agent_address,
            'value': FUNDING_AMOUNT,
            'gas': 21000,  # Standard ETH transfer
            'gasPrice': w3.eth.gas_price,
            'chainId': CHAIN_ID
        }

        # Sign transaction
        signed_tx = w3.eth.account.sign_transaction(tx, deployer_key)

        # Send transaction
        try:
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"   [*] Transaction sent: {tx_hash.hex()}")

            # Wait for receipt
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] == 1:
                print(f"   [+] Transaction confirmed!")
                print(f"   Gas used: {receipt['gasUsed']}")

                # Verify new balance
                new_balance = w3.eth.get_balance(agent_address)
                print(f"   New balance: {w3.from_wei(new_balance, 'ether')} ETH")

                txs.append({
                    'agent': agent_name,
                    'address': agent_address,
                    'tx_hash': tx_hash.hex(),
                    'status': 'success',
                    'gas_used': receipt['gasUsed']
                })
            else:
                print(f"   [-] Transaction failed!")
                txs.append({
                    'agent': agent_name,
                    'address': agent_address,
                    'tx_hash': tx_hash.hex(),
                    'status': 'failed'
                })

            nonce += 1

        except Exception as e:
            print(f"   [-] Error sending transaction: {e}")
            txs.append({
                'agent': agent_name,
                'address': agent_address,
                'status': 'error',
                'error': str(e)
            })
            nonce += 1  # Increment anyway to avoid nonce issues

    # Summary
    print("\n" + "="*60)
    print("[*] FUNDING SUMMARY")
    print("="*60)

    successful = [tx for tx in txs if tx.get('status') == 'success']
    failed = [tx for tx in txs if tx.get('status') != 'success']

    print(f"\n[+] Successful: {len(successful)}/{len(AGENT_WALLETS)}")
    for tx in successful:
        print(f"   {tx['agent']}: {tx['tx_hash']}")

    if failed:
        print(f"\n[-] Failed: {len(failed)}/{len(AGENT_WALLETS)}")
        for tx in failed:
            print(f"   {tx['agent']}: {tx.get('error', 'Transaction failed')}")

    # Final deployer balance
    final_balance = w3.eth.get_balance(deployer_address)
    print(f"\n[*] Deployer final balance: {w3.from_wei(final_balance, 'ether')} ETH")

    # Save transaction log
    log_file = "funding_transactions.json"
    with open(log_file, 'w') as f:
        json.dump({
            'network': 'base-sepolia',
            'chain_id': CHAIN_ID,
            'deployer': deployer_address,
            'funding_amount': str(w3.from_wei(FUNDING_AMOUNT, 'ether')),
            'transactions': txs
        }, f, indent=2)

    print(f"\n[*] Transaction log saved to: {log_file}")

    return len(successful) == len(AGENT_WALLETS)

if __name__ == "__main__":
    print("="*60)
    print("Fund Agent Wallets - Base Sepolia")
    print("="*60)

    try:
        success = fund_agents()
        if success:
            print("\n[+] All agents funded successfully!")
            exit(0)
        else:
            print("\n[!] Some transactions failed. Check the summary above.")
            exit(1)
    except KeyboardInterrupt:
        print("\n\n[-] Funding cancelled by user")
        exit(1)
    except Exception as e:
        print(f"\n[-] Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
