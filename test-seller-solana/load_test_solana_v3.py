#!/usr/bin/env python3
"""
Load Test v3 for Solana Test Seller
Hybrid approach: Buyer as fee payer + Real blockhash
"""
import base64
from solana.rpc.api import Client
from load_test_solana_v2 import *

class SolanaLoadTestV3(SolanaLoadTest):
    """
    V3: Buyer as fee payer (like original) but with real blockhash (not Hash.default())

    Facilitator code analysis shows:
    - replace_recent_blockhash: false (facilitator won't replace it)
    - Buyer must be fee payer for gasless flow
    - Transaction must be signable by facilitator
    """

    def create_transfer_transaction(self) -> str:
        """
        Create SPL Token transfer with buyer as payer and real blockhash
        """
        # Get buyer's USDC token account (ATA)
        buyer_ata = get_associated_token_address(self.buyer.pubkey(), USDC_MINT)

        # Get seller's USDC token account (ATA)
        seller_ata = get_associated_token_address(self.seller, USDC_MINT)

        # Create instructions
        instructions = []

        # 1. Set compute unit limit
        compute_limit_ix = set_compute_unit_limit(200_000)
        instructions.append(compute_limit_ix)

        # 2. Set compute unit price
        compute_price_ix = set_compute_unit_price(1_000_000)
        instructions.append(compute_price_ix)

        # 3. Transfer USDC
        transfer_ix = transfer_checked(
            TransferCheckedParams(
                program_id=TOKEN_PROGRAM_ID,
                source=buyer_ata,
                mint=USDC_MINT,
                dest=seller_ata,
                owner=self.buyer.pubkey(),
                amount=PRICE_USDC,
                decimals=USDC_DECIMALS,
            )
        )
        instructions.append(transfer_ix)

        # Get REAL recent blockhash from Solana RPC
        client = Client("https://api.mainnet-beta.solana.com")
        recent_blockhash = client.get_latest_blockhash().value.blockhash

        print(f"[DEBUG] V3 transaction structure:")
        print(f"  - Using buyer as payer: {self.buyer.pubkey()}")
        print(f"  - Recent blockhash: {recent_blockhash}")

        # Create message with BUYER as payer (gasless = facilitator pays fees, but buyer is message payer)
        message = MessageV0.try_compile(
            payer=self.buyer.pubkey(),
            instructions=instructions,
            address_lookup_table_accounts=[],
            recent_blockhash=recent_blockhash,
        )

        # Sign with buyer's keypair only
        tx = VersionedTransaction(message, [self.buyer])

        # Serialize to bytes then base64
        tx_bytes = bytes(tx)
        tx_base64 = base64.b64encode(tx_bytes).decode('utf-8')

        print(f"  - Transaction bytes length: {len(tx_bytes)}")
        print(f"  - Buyer signature present: True")

        return tx_base64


if __name__ == "__main__":
    import sys

    SELLER = "Ez4frLQzDbV1AT9BNJkQFEjyTFRTsEwJ5YFaSGG8nRGB"

    print("==" * 30)
    print("LOAD TEST V3: Buyer as Payer + Real Blockhash")
    print("==" * 30)

    buyer = load_buyer_keypair_from_aws()
    tester = SolanaLoadTestV3(seller_pubkey=SELLER, buyer_keypair=buyer)

    # Run single test
    success = tester.make_paid_request(1, verbose=True)

    if success:
        print("\nSUCCESS: V3 approach works!")
        sys.exit(0)
    else:
        print("\nFAILED: V3 approach failed")
        sys.exit(1)
