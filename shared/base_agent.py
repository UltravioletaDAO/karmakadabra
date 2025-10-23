#!/usr/bin/env python3
"""
ERC8004BaseAgent - Base class for all Karmacadabra agents

Provides core functionality for agent lifecycle:
- Registration in Identity Registry
- Reputation management (bidirectional ratings)
- Web3 integration with Avalanche Fuji
- AWS Secrets Manager integration
- Contract interaction utilities

All agents (Validator, Karma-Hello, Abracadabra, etc.) inherit from this class.
"""

import os
from typing import Optional, Dict, Tuple
from decimal import Decimal
from web3 import Web3
from web3.contract import Contract
from eth_account import Account
from eth_account.signers.local import LocalAccount
import logging

from .secrets_manager import get_private_key


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ERC8004BaseAgent:
    """
    Base class for all ERC-8004 compliant agents in Karmacadabra

    Features:
    - Automatic wallet management (AWS Secrets Manager or local .env)
    - Identity Registry registration
    - Reputation management (rate servers/clients, query ratings)
    - Gas estimation and transaction handling
    - Event monitoring

    Example:
        >>> agent = ERC8004BaseAgent(
        ...     agent_name="validator-agent",
        ...     agent_domain="validator.ultravioletadao.xyz",
        ...     rpc_url="https://avalanche-fuji-c-chain-rpc.publicnode.com"
        ... )
        >>> agent.register_agent()
        >>> print(f"Agent ID: {agent.agent_id}")
    """

    def __init__(
        self,
        agent_name: str,
        agent_domain: str,
        rpc_url: str = None,
        chain_id: int = 43113,
        identity_registry_address: str = None,
        reputation_registry_address: str = None,
        validation_registry_address: str = None,
        private_key: str = None
    ):
        """
        Initialize ERC8004BaseAgent

        Args:
            agent_name: Name for AWS Secrets Manager lookup (e.g., "validator-agent")
            agent_domain: Agent's domain (e.g., "validator.ultravioletadao.xyz")
            rpc_url: Avalanche Fuji RPC endpoint
            chain_id: Chain ID (default: 43113 for Fuji)
            identity_registry_address: Identity Registry contract address
            reputation_registry_address: Reputation Registry contract address
            validation_registry_address: Validation Registry contract address
            private_key: Optional override (for testing). Uses AWS Secrets Manager if None.
        """
        self.agent_name = agent_name
        self.agent_domain = agent_domain
        self.chain_id = chain_id

        # Load configuration from environment or use provided values
        self.rpc_url = rpc_url or os.getenv("RPC_URL_FUJI", "https://avalanche-fuji-c-chain-rpc.publicnode.com")
        self.identity_registry_address = identity_registry_address or os.getenv("IDENTITY_REGISTRY")
        self.reputation_registry_address = reputation_registry_address or os.getenv("REPUTATION_REGISTRY")
        self.validation_registry_address = validation_registry_address or os.getenv("VALIDATION_REGISTRY")

        # Validate required addresses
        if not self.identity_registry_address:
            raise ValueError("IDENTITY_REGISTRY address not provided or found in environment")
        if not self.reputation_registry_address:
            raise ValueError("REPUTATION_REGISTRY address not provided or found in environment")

        # Initialize Web3
        logger.info(f"[{self.agent_name}] Connecting to Fuji: {self.rpc_url}")
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))

        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to Fuji RPC: {self.rpc_url}")

        logger.info(f"[{self.agent_name}] Connected to Fuji (Chain ID: {self.w3.eth.chain_id})")

        # Load wallet from AWS Secrets Manager or private_key override
        if private_key:
            logger.warning(f"[{self.agent_name}] Using provided private key (testing mode)")
            self.private_key = private_key
        else:
            logger.info(f"[{self.agent_name}] Loading private key from AWS Secrets Manager")
            self.private_key = get_private_key(self.agent_name)

        # Create account from private key
        self.account: LocalAccount = Account.from_key(self.private_key)
        self.address = self.account.address

        logger.info(f"[{self.agent_name}] Wallet address: {self.address}")

        # Check balance
        balance_wei = self.w3.eth.get_balance(self.address)
        balance_avax = self.w3.from_wei(balance_wei, 'ether')
        logger.info(f"[{self.agent_name}] Balance: {balance_avax:.4f} AVAX")

        # Initialize contracts
        self.identity_registry: Contract = self._load_identity_registry()
        self.reputation_registry: Contract = self._load_reputation_registry()

        # Agent ID (will be set after registration or lookup)
        self.agent_id: Optional[int] = None

        logger.info(f"[{self.agent_name}] ERC8004BaseAgent initialized")

    def _load_identity_registry(self) -> Contract:
        """Load Identity Registry contract"""
        abi = [
            {
                "type": "function",
                "name": "newAgent",
                "inputs": [
                    {"name": "agentDomain", "type": "string"},
                    {"name": "agentAddress", "type": "address"}
                ],
                "outputs": [{"name": "agentId", "type": "uint256"}],
                "stateMutability": "payable"
            },
            {
                "type": "function",
                "name": "getAgent",
                "inputs": [{"name": "agentId", "type": "uint256"}],
                "outputs": [{
                    "name": "agentInfo",
                    "type": "tuple",
                    "components": [
                        {"name": "agentId", "type": "uint256"},
                        {"name": "agentDomain", "type": "string"},
                        {"name": "agentAddress", "type": "address"}
                    ]
                }],
                "stateMutability": "view"
            },
            {
                "type": "function",
                "name": "agentExists",
                "inputs": [{"name": "agentId", "type": "uint256"}],
                "outputs": [{"name": "exists", "type": "bool"}],
                "stateMutability": "view"
            },
            {
                "type": "function",
                "name": "getAgentCount",
                "inputs": [],
                "outputs": [{"name": "count", "type": "uint256"}],
                "stateMutability": "view"
            },
            {
                "type": "function",
                "name": "REGISTRATION_FEE",
                "inputs": [],
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view"
            }
        ]

        return self.w3.eth.contract(
            address=Web3.to_checksum_address(self.identity_registry_address),
            abi=abi
        )

    def _load_reputation_registry(self) -> Contract:
        """Load Reputation Registry contract"""
        abi = [
            {
                "type": "function",
                "name": "rateServer",
                "inputs": [
                    {"name": "agentServerId", "type": "uint256"},
                    {"name": "rating", "type": "uint8"}
                ],
                "outputs": [],
                "stateMutability": "nonpayable"
            },
            {
                "type": "function",
                "name": "rateClient",
                "inputs": [
                    {"name": "agentClientId", "type": "uint256"},
                    {"name": "rating", "type": "uint8"},
                    {"name": "feedbackAuthId", "type": "bytes32"}
                ],
                "outputs": [],
                "stateMutability": "nonpayable"
            },
            {
                "type": "function",
                "name": "getServerRating",
                "inputs": [
                    {"name": "agentClientId", "type": "uint256"},
                    {"name": "agentServerId", "type": "uint256"}
                ],
                "outputs": [
                    {"name": "hasRating", "type": "bool"},
                    {"name": "rating", "type": "uint8"}
                ],
                "stateMutability": "view"
            },
            {
                "type": "function",
                "name": "getClientRating",
                "inputs": [
                    {"name": "agentClientId", "type": "uint256"},
                    {"name": "agentServerId", "type": "uint256"}
                ],
                "outputs": [
                    {"name": "hasRating", "type": "bool"},
                    {"name": "rating", "type": "uint8"}
                ],
                "stateMutability": "view"
            },
            {
                "type": "function",
                "name": "acceptFeedback",
                "inputs": [
                    {"name": "agentClientId", "type": "uint256"},
                    {"name": "agentServerId", "type": "uint256"}
                ],
                "outputs": [],
                "stateMutability": "nonpayable"
            },
            {
                "type": "function",
                "name": "getFeedbackAuthId",
                "inputs": [
                    {"name": "agentClientId", "type": "uint256"},
                    {"name": "agentServerId", "type": "uint256"}
                ],
                "outputs": [{"name": "feedbackAuthId", "type": "bytes32"}],
                "stateMutability": "view"
            }
        ]

        return self.w3.eth.contract(
            address=Web3.to_checksum_address(self.reputation_registry_address),
            abi=abi
        )

    # =========================================================================
    # IDENTITY REGISTRY METHODS
    # =========================================================================

    def register_agent(self) -> int:
        """
        Register agent in Identity Registry

        Returns:
            agent_id: The assigned agent ID

        Raises:
            Exception: If registration fails
        """
        logger.info(f"[{self.agent_name}] Registering agent...")
        logger.info(f"   Domain: {self.agent_domain}")
        logger.info(f"   Address: {self.address}")

        # Get registration fee
        registration_fee = self.identity_registry.functions.REGISTRATION_FEE().call()
        logger.info(f"   Registration fee: {self.w3.from_wei(registration_fee, 'ether')} AVAX")

        # Build transaction
        tx = self.identity_registry.functions.newAgent(
            self.agent_domain,
            self.address
        ).build_transaction({
            'from': self.address,
            'value': registration_fee,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'gas': 500000,
            'gasPrice': self.w3.eth.gas_price,
            'chainId': self.chain_id
        })

        # Sign and send transaction
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        logger.info(f"   TX Hash: {tx_hash.hex()}")
        logger.info(f"   Waiting for confirmation...")

        # Wait for receipt
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt['status'] != 1:
            raise Exception(f"Registration failed! TX: {tx_hash.hex()}")

        # Extract agent_id from logs
        # The newAgent function returns the agent_id
        # For now, we'll get the agent count - 1 as the ID
        agent_count = self.identity_registry.functions.getAgentCount().call()
        self.agent_id = agent_count - 1

        logger.info(f"[{self.agent_name}] ✅ Registration successful!")
        logger.info(f"   Agent ID: {self.agent_id}")
        logger.info(f"   TX: https://testnet.snowtrace.io/tx/{tx_hash.hex()}")

        return self.agent_id

    def get_agent_info(self, agent_id: int) -> Dict:
        """
        Get agent information from Identity Registry

        Args:
            agent_id: The agent ID to query

        Returns:
            dict: Agent information (agentId, agentDomain, agentAddress)
        """
        if not self.identity_registry.functions.agentExists(agent_id).call():
            raise ValueError(f"Agent ID {agent_id} does not exist")

        agent_info = self.identity_registry.functions.getAgent(agent_id).call()

        return {
            'agent_id': agent_info[0],
            'agent_domain': agent_info[1],
            'agent_address': agent_info[2]
        }

    def agent_exists(self, agent_id: int) -> bool:
        """Check if an agent ID exists in the registry"""
        return self.identity_registry.functions.agentExists(agent_id).call()

    def get_agent_count(self) -> int:
        """Get total number of registered agents"""
        return self.identity_registry.functions.getAgentCount().call()

    # =========================================================================
    # REPUTATION REGISTRY METHODS
    # =========================================================================

    def rate_server(self, server_agent_id: int, rating: int) -> str:
        """
        Rate a server agent (as a client)

        Args:
            server_agent_id: The server agent's ID
            rating: Rating (0-100)

        Returns:
            tx_hash: Transaction hash
        """
        if not self.agent_id:
            raise ValueError("Agent not registered. Call register_agent() first.")

        if not (0 <= rating <= 100):
            raise ValueError("Rating must be between 0 and 100")

        logger.info(f"[{self.agent_name}] Rating server {server_agent_id}: {rating}/100")

        # Build transaction
        tx = self.reputation_registry.functions.rateServer(
            server_agent_id,
            rating
        ).build_transaction({
            'from': self.address,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'gas': 200000,
            'gasPrice': self.w3.eth.gas_price,
            'chainId': self.chain_id
        })

        # Sign and send
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        logger.info(f"   TX Hash: {tx_hash.hex()}")

        # Wait for confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt['status'] != 1:
            raise Exception(f"Rating failed! TX: {tx_hash.hex()}")

        logger.info(f"[{self.agent_name}] ✅ Server rated successfully")

        return tx_hash.hex()

    def rate_client(self, client_agent_id: int, rating: int, feedback_auth_id: bytes) -> str:
        """
        Rate a client agent (as a server)

        Args:
            client_agent_id: The client agent's ID
            rating: Rating (0-100)
            feedback_auth_id: Feedback authorization ID (from acceptFeedback)

        Returns:
            tx_hash: Transaction hash
        """
        if not self.agent_id:
            raise ValueError("Agent not registered. Call register_agent() first.")

        if not (0 <= rating <= 100):
            raise ValueError("Rating must be between 0 and 100")

        logger.info(f"[{self.agent_name}] Rating client {client_agent_id}: {rating}/100")

        # Build transaction
        tx = self.reputation_registry.functions.rateClient(
            client_agent_id,
            rating,
            feedback_auth_id
        ).build_transaction({
            'from': self.address,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'gas': 200000,
            'gasPrice': self.w3.eth.gas_price,
            'chainId': self.chain_id
        })

        # Sign and send
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        logger.info(f"   TX Hash: {tx_hash.hex()}")

        # Wait for confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt['status'] != 1:
            raise Exception(f"Rating failed! TX: {tx_hash.hex()}")

        logger.info(f"[{self.agent_name}] ✅ Client rated successfully")

        return tx_hash.hex()

    def get_server_rating(self, client_id: int, server_id: int) -> Tuple[bool, int]:
        """
        Get server rating given by a client

        Args:
            client_id: Client agent ID
            server_id: Server agent ID

        Returns:
            (has_rating, rating): Tuple of whether rating exists and the rating value
        """
        return self.reputation_registry.functions.getServerRating(client_id, server_id).call()

    def get_client_rating(self, client_id: int, server_id: int) -> Tuple[bool, int]:
        """
        Get client rating given by a server

        Args:
            client_id: Client agent ID
            server_id: Server agent ID

        Returns:
            (has_rating, rating): Tuple of whether rating exists and the rating value
        """
        return self.reputation_registry.functions.getClientRating(client_id, server_id).call()

    def accept_feedback(self, server_agent_id: int) -> str:
        """
        Accept feedback from a server (as a client)
        Generates a feedback authorization ID that the server can use to rate the client

        Args:
            server_agent_id: The server agent's ID

        Returns:
            tx_hash: Transaction hash
        """
        if not self.agent_id:
            raise ValueError("Agent not registered. Call register_agent() first.")

        logger.info(f"[{self.agent_name}] Accepting feedback from server {server_agent_id}")

        # Build transaction
        tx = self.reputation_registry.functions.acceptFeedback(
            self.agent_id,
            server_agent_id
        ).build_transaction({
            'from': self.address,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'gas': 150000,
            'gasPrice': self.w3.eth.gas_price,
            'chainId': self.chain_id
        })

        # Sign and send
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        logger.info(f"   TX Hash: {tx_hash.hex()}")

        # Wait for confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt['status'] != 1:
            raise Exception(f"Accept feedback failed! TX: {tx_hash.hex()}")

        logger.info(f"[{self.agent_name}] ✅ Feedback accepted")

        return tx_hash.hex()

    def get_feedback_auth_id(self, client_id: int, server_id: int) -> bytes:
        """
        Get feedback authorization ID

        Args:
            client_id: Client agent ID
            server_id: Server agent ID

        Returns:
            feedback_auth_id: The authorization ID
        """
        return self.reputation_registry.functions.getFeedbackAuthId(client_id, server_id).call()

    def submit_validation_response(
        self,
        seller_address: str,
        buyer_address: str,
        score: int,
        metadata: str = ""
    ) -> str:
        """
        Submit validation response to ValidationRegistry on-chain

        This method is called by validator agents to submit validation scores.
        The validator PAYS GAS for this transaction.

        Args:
            seller_address: Address of the seller being validated
            buyer_address: Address of the buyer requesting validation
            score: Validation score (0-100)
            metadata: Optional metadata (validation ID, notes, etc.)

        Returns:
            tx_hash: Transaction hash
        """
        if not self.agent_id:
            raise ValueError("Agent not registered. Call register_agent() first.")

        logger.info(f"[{self.agent_name}] Submitting validation: score={score} for {seller_address}")

        # Build transaction for validationResponse
        tx = self.validation_registry.functions.validationResponse(
            seller_address,
            buyer_address,
            score,
            metadata
        ).build_transaction({
            'from': self.address,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'gas': 200000,
            'gasPrice': self.w3.eth.gas_price
        })

        # Sign transaction
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)

        # Send transaction (validator pays gas!)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)

        # Wait for confirmation
        self.w3.eth.wait_for_transaction_receipt(tx_hash)

        logger.info(f"[{self.agent_name}] ✅ Validation submitted: {tx_hash.hex()}")

        return tx_hash.hex()

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_balance(self) -> Decimal:
        """Get wallet balance in AVAX"""
        balance_wei = self.w3.eth.get_balance(self.address)
        return Decimal(str(self.w3.from_wei(balance_wei, 'ether')))

    def __repr__(self) -> str:
        return (
            f"<ERC8004BaseAgent "
            f"name='{self.agent_name}' "
            f"id={self.agent_id} "
            f"address='{self.address}' "
            f"domain='{self.agent_domain}'>"
        )
