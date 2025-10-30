#!/bin/bash
#
# Deploy ONLY ReputationRegistry with rateValidator() function
# Quick deployment without touching other contracts
#

set -e

cd "$(dirname "$0")/.."

echo "======================================================================="
echo "🚀 DEPLOYING REPUTATION REGISTRY (with rateValidator)"
echo "======================================================================="
echo ""

# Check dependencies
if ! command -v forge &> /dev/null; then
    echo "❌ Foundry not installed! Install from: https://getfoundry.sh/"
    exit 1
fi

if ! command -v cast &> /dev/null; then
    echo "❌ Cast not installed! Install Foundry from: https://getfoundry.sh/"
    exit 1
fi

# Load environment
if [ -f ".env" ]; then
    echo "📂 Loading .env..."
    export $(grep -v '^#' .env | xargs)
else
    echo "❌ .env file not found!"
    exit 1
fi

# Check required vars
if [ -z "$PRIVATE_KEY" ] && [ -z "$EVM_PRIVATE_KEY" ]; then
    echo "❌ PRIVATE_KEY or EVM_PRIVATE_KEY not set in .env"
    exit 1
fi

DEPLOYER_KEY="${EVM_PRIVATE_KEY:-$PRIVATE_KEY}"

if [ -z "$RPC_URL_FUJI" ]; then
    echo "❌ RPC_URL_FUJI not set in .env"
    exit 1
fi

if [ -z "$IDENTITY_REGISTRY" ]; then
    echo "❌ IDENTITY_REGISTRY not set in .env"
    exit 1
fi

echo "Configuration:"
echo "  RPC: $RPC_URL_FUJI"
echo "  Identity Registry: $IDENTITY_REGISTRY"
echo ""

# Build contracts
echo "🔨 Building contracts..."
cd erc-8004/contracts

forge build --silent

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi

echo "✅ Build successful"
echo ""

# Deploy ReputationRegistry
echo "🚀 Deploying ReputationRegistry..."

DEPLOY_OUTPUT=$(forge create \
    --rpc-url "$RPC_URL_FUJI" \
    --private-key "$DEPLOYER_KEY" \
    --constructor-args "$IDENTITY_REGISTRY" \
    src/ReputationRegistry.sol:ReputationRegistry \
    2>&1)

if [ $? -ne 0 ]; then
    echo "❌ Deployment failed!"
    echo "$DEPLOY_OUTPUT"
    exit 1
fi

# Extract deployed address
NEW_REPUTATION=$(echo "$DEPLOY_OUTPUT" | grep "Deployed to:" | awk '{print $3}')

if [ -z "$NEW_REPUTATION" ]; then
    echo "❌ Could not extract deployed address!"
    echo "$DEPLOY_OUTPUT"
    exit 1
fi

echo "✅ ReputationRegistry deployed!"
echo ""
echo "=" * 70
echo "📍 NEW ADDRESS: $NEW_REPUTATION"
echo "=" * 70
echo ""

# Verify contract has rateValidator
echo "🔍 Verifying rateValidator() exists in bytecode..."

CODE=$(cast code "$NEW_REPUTATION" --rpc-url "$RPC_URL_FUJI")
SELECTOR=$(cast sig "rateValidator(uint256,uint8)")

if echo "$CODE" | grep -q "${SELECTOR:2:8}"; then
    echo "✅ rateValidator() found in contract!"
else
    echo "⚠️  rateValidator() not found - this might be an issue"
fi

echo ""
echo "=" * 70
echo "📝 NEXT STEPS"
echo "=" * 70
echo ""
echo "1. Update .env file:"
echo "   REPUTATION_REGISTRY=$NEW_REPUTATION"
echo ""
echo "2. Restart agents:"
echo "   docker-compose restart"
echo ""
echo "3. Test validator ratings:"
echo "   python3 scripts/test_complete_flow.py"
echo ""
echo "4. View on Snowtrace:"
echo "   https://testnet.snowtrace.io/address/$NEW_REPUTATION"
echo ""
echo "🎉 Deployment complete!"
echo ""
