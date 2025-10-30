#!/bin/bash
#
# Redeploy ReputationRegistry with rateValidator() function
#
# This script redeploys the updated ReputationRegistry contract that includes
# the rateValidator() function missing from the current deployment.
#

set -e

echo "======================================================================="
echo "🔄 REDEPLOYING REPUTATION REGISTRY"
echo "======================================================================="
echo ""
echo "⚠️  WARNING: This will deploy a NEW ReputationRegistry contract"
echo "   The old contract at 0x932d32194C7A47c0fe246C1d61caF244A4804C6a"
echo "   will remain on-chain but we'll use the new address."
echo ""
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

# Navigate to contracts directory
cd "$(dirname "$0")/../erc-8004/contracts" || exit 1

echo ""
echo "📂 Working directory: $(pwd)"
echo ""

# Check if forge is available
if ! command -v forge &> /dev/null; then
    echo "❌ Foundry not installed!"
    echo "   Install from: https://getfoundry.sh/"
    exit 1
fi

echo "🔨 Building contracts with Foundry..."
forge build

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi

echo "✅ Build successful"
echo ""

# Check for deployment script
DEPLOY_SCRIPT="../deploy-fuji.sh"

if [ ! -f "$DEPLOY_SCRIPT" ]; then
    echo "❌ Deployment script not found: $DEPLOY_SCRIPT"
    exit 1
fi

echo "🚀 Deploying to Avalanche Fuji..."
echo "   This will deploy:"
echo "   1. Identity Registry (if needed)"
echo "   2. Reputation Registry (NEW with rateValidator)"
echo "   3. Validation Registry (if needed)"
echo ""

# Run deployment
bash "$DEPLOY_SCRIPT"

if [ $? -ne 0 ]; then
    echo "❌ Deployment failed!"
    exit 1
fi

echo ""
echo "======================================================================="
echo "✅ DEPLOYMENT COMPLETE"
echo "======================================================================="
echo ""
echo "Next steps:"
echo "  1. Check erc-8004/.env.deployed for new addresses"
echo "  2. Update .env with new REPUTATION_REGISTRY address"
echo "  3. Restart agents: docker-compose restart"
echo "  4. Test validator ratings work!"
echo ""
