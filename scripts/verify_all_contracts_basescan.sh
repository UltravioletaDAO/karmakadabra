#!/bin/bash

# Script to verify all Base Sepolia contracts on Basescan
# Requires: BASESCAN_API_KEY environment variable
# Usage: bash scripts/verify_all_contracts_basescan.sh

set -e

echo "=========================================="
echo "Base Sepolia Contract Verification"
echo "=========================================="
echo ""

# Check if API key is set
if [ -z "$BASESCAN_API_KEY" ]; then
    echo "[ERROR] BASESCAN_API_KEY not set"
    echo ""
    echo "Get API key from: https://basescan.org/myapikey"
    echo "Then run: export BASESCAN_API_KEY='your-api-key'"
    echo ""
    exit 1
fi

echo "[OK] BASESCAN_API_KEY is set"
echo ""

# Contract addresses
GLUE_TOKEN="0xfEe5CC33479E748f40F5F299Ff6494b23F88C425"
IDENTITY_REGISTRY="0x8a20f665c02a33562a0462a0908a64716Ed7463d"
REPUTATION_REGISTRY="0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F"
VALIDATION_REGISTRY="0x3C545DBeD1F587293fA929385442A459c2d316c4"

# Verify GLUE Token
echo "=========================================="
echo "[1/4] Verifying GLUE Token..."
echo "Address: $GLUE_TOKEN"
echo "=========================================="
echo ""

cd erc-20

forge verify-contract \
  $GLUE_TOKEN \
  src/GLUE.sol:GLUE \
  --chain base-sepolia \
  --watch || echo "[WARNING] GLUE verification failed or already verified"

echo ""
echo "[OK] GLUE Token verification complete"
echo ""

cd ..

# Verify Identity Registry
echo "=========================================="
echo "[2/4] Verifying Identity Registry..."
echo "Address: $IDENTITY_REGISTRY"
echo "=========================================="
echo ""

cd erc-8004/contracts

forge verify-contract \
  $IDENTITY_REGISTRY \
  src/IdentityRegistry.sol:IdentityRegistry \
  --chain base-sepolia \
  --watch || echo "[WARNING] IdentityRegistry verification failed or already verified"

echo ""
echo "[OK] Identity Registry verification complete"
echo ""

# Verify Reputation Registry
echo "=========================================="
echo "[3/4] Verifying Reputation Registry..."
echo "Address: $REPUTATION_REGISTRY"
echo "=========================================="
echo ""

forge verify-contract \
  $REPUTATION_REGISTRY \
  src/ReputationRegistry.sol:ReputationRegistry \
  --chain base-sepolia \
  --watch || echo "[WARNING] ReputationRegistry verification failed or already verified"

echo ""
echo "[OK] Reputation Registry verification complete"
echo ""

# Verify Validation Registry
echo "=========================================="
echo "[4/4] Verifying Validation Registry..."
echo "Address: $VALIDATION_REGISTRY"
echo "=========================================="
echo ""

forge verify-contract \
  $VALIDATION_REGISTRY \
  src/ValidationRegistry.sol:ValidationRegistry \
  --chain base-sepolia \
  --watch || echo "[WARNING] ValidationRegistry verification failed or already verified"

echo ""
echo "[OK] Validation Registry verification complete"
echo ""

cd ../..

# Summary
echo "=========================================="
echo "VERIFICATION COMPLETE"
echo "=========================================="
echo ""
echo "Check verified contracts at:"
echo "  GLUE Token:           https://sepolia.basescan.org/address/$GLUE_TOKEN"
echo "  Identity Registry:    https://sepolia.basescan.org/address/$IDENTITY_REGISTRY"
echo "  Reputation Registry:  https://sepolia.basescan.org/address/$REPUTATION_REGISTRY"
echo "  Validation Registry:  https://sepolia.basescan.org/address/$VALIDATION_REGISTRY"
echo ""
