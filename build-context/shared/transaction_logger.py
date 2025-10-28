#!/usr/bin/env python3
"""
Transaction Logger Helper
Logs all agent transactions on-chain with descriptive UTF-8 messages

Inspired by Karma-Hello's transaction logging system
All messages appear in Snowtrace forever for full transparency
"""

import os
from typing import Optional
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
TRANSACTION_LOGGER_ADDRESS = "0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654"
RPC_URL = "https://avalanche-fuji-c-chain-rpc.publicnode.com"
CHAIN_ID = 43113

# TransactionLogger ABI (minimal - only what we need)
TRANSACTION_LOGGER_ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "txHash", "type": "bytes32"},
            {"internalType": "string", "name": "message", "type": "string"}
        ],
        "name": "logTransaction",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "from", "type": "address"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
            {"internalType": "string", "name": "service", "type": "string"},
            {"internalType": "bytes32", "name": "txHash", "type": "bytes32"}
        ],
        "name": "logAgentPayment",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "target", "type": "address"},
            {"internalType": "uint256", "name": "score", "type": "uint256"},
            {"internalType": "string", "name": "details", "type": "string"},
            {"internalType": "bytes32", "name": "txHash", "type": "bytes32"}
        ],
        "name": "logValidation",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "txHash", "type": "bytes32"}
        ],
        "name": "getMessage",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "agent", "type": "address"},
            {"indexed": True, "internalType": "bytes32", "name": "txHash", "type": "bytes32"},
            {"indexed": False, "internalType": "string", "name": "message", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "TransactionLogged",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"},
            {"indexed": False, "internalType": "string", "name": "service", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "message", "type": "string"}
        ],
        "name": "AgentPayment",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "validator", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "target", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "score", "type": "uint256"},
            {"indexed": False, "internalType": "string", "name": "message", "type": "string"}
        ],
        "name": "ValidationLogged",
        "type": "event"
    }
]


class TransactionLogger:
    """Helper class for logging agent transactions on-chain"""

    def __init__(self, agent_private_key: str, agent_name: str):
        """
        Initialize transaction logger for an agent

        Args:
            agent_private_key: Agent's private key (0x...)
            agent_name: Human-readable agent name (e.g., "karma-hello-agent")
        """
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        self.agent_name = agent_name
        self.account = Account.from_key(agent_private_key)
        self.logger_contract = self.w3.eth.contract(
            address=TRANSACTION_LOGGER_ADDRESS,
            abi=TRANSACTION_LOGGER_ABI
        )

    def log_payment(
        self,
        payment_tx_hash: str,
        from_agent: str,
        to_agent: str,
        amount_glue: float,
        service: str,
        from_address: Optional[str] = None,
        to_address: Optional[str] = None
    ) -> dict:
        """
        Log an agent-to-agent payment

        Similar to Karma-Hello format:
        "Payment via Karmacadabra by Ultravioleta DAO | {from} → {to} | {amount} GLUE for {service}"

        Args:
            payment_tx_hash: Hash of the GLUE payment transaction
            from_agent: Payer agent name (e.g., "client-agent")
            to_agent: Payee agent name (e.g., "karma-hello-agent")
            amount_glue: Amount in GLUE (e.g., 0.01)
            service: Service description (e.g., "Chat Logs")
            from_address: Optional payer address (will use agent's address if not provided)
            to_address: Optional payee address

        Returns:
            dict with transaction hash and status

        Example:
            >>> logger.log_payment(
            ...     payment_tx_hash="0x123...",
            ...     from_agent="client-agent",
            ...     to_agent="karma-hello-agent",
            ...     amount_glue=0.01,
            ...     service="Chat Logs for 2025-10-21"
            ... )
        """
        # Use agent's address if not provided
        if not from_address:
            from_address = self.account.address
        if not to_address:
            to_address = self.account.address

        # Convert amount to smallest units (6 decimals)
        amount_units = int(amount_glue * 10**6)

        # Convert tx hash to bytes32
        if isinstance(payment_tx_hash, str):
            payment_tx_hash = payment_tx_hash.replace('0x', '')
            tx_hash_bytes = bytes.fromhex(payment_tx_hash)
        else:
            tx_hash_bytes = payment_tx_hash

        # Build transaction
        nonce = self.w3.eth.get_transaction_count(self.account.address)

        tx = self.logger_contract.functions.logAgentPayment(
            self.w3.to_checksum_address(from_address),
            self.w3.to_checksum_address(to_address),
            amount_units,
            service,
            tx_hash_bytes
        ).build_transaction({
            'from': self.account.address,
            'nonce': nonce,
            'gas': 200000,
            'gasPrice': self.w3.eth.gas_price,
            'chainId': CHAIN_ID
        })

        # Sign and send
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
        log_tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"[LOGGER] Logged payment: {from_agent} → {to_agent} | {amount_glue} GLUE for {service}")
        print(f"[LOGGER] Payment TX: https://testnet.snowtrace.io/tx/{payment_tx_hash}")
        print(f"[LOGGER] Log TX: https://testnet.snowtrace.io/tx/{log_tx_hash.hex()}")

        return {
            'payment_tx': payment_tx_hash,
            'log_tx': log_tx_hash.hex(),
            'status': 'logged'
        }

    def log_validation(
        self,
        validation_tx_hash: str,
        target_address: str,
        score: int,
        details: str
    ) -> dict:
        """
        Log a validation event

        Args:
            validation_tx_hash: Hash of the validation transaction
            target_address: Address being validated
            score: Validation score (0-100)
            details: Validation details

        Returns:
            dict with transaction hash and status

        Example:
            >>> logger.log_validation(
            ...     validation_tx_hash="0x456...",
            ...     target_address="0x123...",
            ...     score=95,
            ...     details="High quality chat logs, well formatted"
            ... )
        """
        # Convert tx hash to bytes32
        if isinstance(validation_tx_hash, str):
            validation_tx_hash = validation_tx_hash.replace('0x', '')
            tx_hash_bytes = bytes.fromhex(validation_tx_hash)
        else:
            tx_hash_bytes = validation_tx_hash

        # Build transaction
        nonce = self.w3.eth.get_transaction_count(self.account.address)

        tx = self.logger_contract.functions.logValidation(
            self.w3.to_checksum_address(target_address),
            score,
            details,
            tx_hash_bytes
        ).build_transaction({
            'from': self.account.address,
            'nonce': nonce,
            'gas': 200000,
            'gasPrice': self.w3.eth.gas_price,
            'chainId': CHAIN_ID
        })

        # Sign and send
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
        log_tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"[LOGGER] Logged validation: Score {score}/100 for {target_address}")
        print(f"[LOGGER] Validation TX: https://testnet.snowtrace.io/tx/{validation_tx_hash}")
        print(f"[LOGGER] Log TX: https://testnet.snowtrace.io/tx/{log_tx_hash.hex()}")

        return {
            'validation_tx': validation_tx_hash,
            'log_tx': log_tx_hash.hex(),
            'status': 'logged'
        }

    def get_message(self, tx_hash: str) -> str:
        """
        Get the logged message for a transaction

        Args:
            tx_hash: Transaction hash (0x...)

        Returns:
            The logged message string
        """
        # Convert tx hash to bytes32
        tx_hash = tx_hash.replace('0x', '')
        tx_hash_bytes = bytes.fromhex(tx_hash)

        message = self.logger_contract.functions.getMessage(tx_hash_bytes).call()
        return message


# Convenience functions for common use cases

def create_payment_message(from_agent: str, to_agent: str, amount: float, service: str) -> str:
    """
    Create a payment message in Karma-Hello style

    Format: "Payment via Karmacadabra by Ultravioleta DAO | {from} → {to} | {amount} GLUE for {service}"
    """
    return f"Payment via Karmacadabra by Ultravioleta DAO | {from_agent} → {to_agent} | {amount:.6f} GLUE for {service}"


def create_validation_message(validator: str, target: str, score: int, details: str) -> str:
    """
    Create a validation message

    Format: "Validation via Karmacadabra by Ultravioleta DAO | Validator: {validator} | Target: {target} | Score: {score}/100 | {details}"
    """
    return f"Validation via Karmacadabra by Ultravioleta DAO | Validator: {validator} | Target: {target} | Score: {score}/100 | {details}"


# Example usage
if __name__ == "__main__":
    # This is just an example - in real usage, agents will call this after each transaction
    print("Transaction Logger Helper")
    print("=" * 60)
    print(f"Logger Contract: {TRANSACTION_LOGGER_ADDRESS}")
    print(f"Network: Avalanche Fuji (Chain ID: {CHAIN_ID})")
    print(f"Snowtrace: https://testnet.snowtrace.io/address/{TRANSACTION_LOGGER_ADDRESS}")
    print()
    print("Usage in agents:")
    print("  from shared.transaction_logger import TransactionLogger")
    print("  logger = TransactionLogger(agent_private_key, 'my-agent')")
    print("  logger.log_payment(tx_hash, 'buyer', 'seller', 0.01, 'Service Name')")
