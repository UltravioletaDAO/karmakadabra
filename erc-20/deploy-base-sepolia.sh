#!/bin/bash
# =============================================================================
# GLUE Token Deployment Script - Base Sepolia
# Karmacadabra - Ultravioleta DAO
# =============================================================================
#
# Deploys GLUE token to Base Sepolia Testnet
#
# Deployment Parameters:
# - Initial Supply: 24,157,817 GLUE
# - Owner: 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8
# - Decimals: 6
# - Network: Base Sepolia (Chain ID: 84532)
#
# Usage:
#   ./deploy-base-sepolia.sh
#
# =============================================================================

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NETWORK="base-sepolia"
CHAIN_ID=84532
OWNER_WALLET="0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8"
INITIAL_SUPPLY=24157817
RPC_URL="https://base-sepolia.g.alchemy.com/v2/demo"
EXPLORER_URL="https://sepolia.basescan.org"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}GLUE Token Deployment - Base Sepolia${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Network:${NC} Base Sepolia Testnet"
echo -e "${YELLOW}Chain ID:${NC} $CHAIN_ID"
echo -e "${YELLOW}Owner Wallet:${NC} $OWNER_WALLET"
echo -e "${YELLOW}Initial Supply:${NC} $INITIAL_SUPPLY GLUE"
echo ""

# Check if forge is installed
if ! command -v forge &> /dev/null; then
    echo -e "${RED}Error: Foundry (forge) not found${NC}"
    echo -e "${YELLOW}Install Foundry: https://getfoundry.sh${NC}"
    exit 1
fi

# Get private key from AWS Secrets Manager
echo -e "${BLUE}Fetching deployer private key from AWS Secrets Manager...${NC}"
PRIVATE_KEY=$(aws secretsmanager get-secret-value \
    --secret-id karmacadabra \
    --region us-east-1 \
    --query 'SecretString' \
    --output text | python -c "import sys, json; print(json.load(sys.stdin)['erc-20']['private_key'])")

if [ -z "$PRIVATE_KEY" ]; then
    echo -e "${RED}Error: Failed to fetch private key from AWS${NC}"
    exit 1
fi

echo -e "${GREEN}Private key retrieved successfully${NC}"
export PRIVATE_KEY

# Check deployer balance
DEPLOYER_BALANCE=$(cast balance $OWNER_WALLET --rpc-url $RPC_URL)
DEPLOYER_BALANCE_ETH=$(cast --to-unit $DEPLOYER_BALANCE ether)

echo -e "${YELLOW}Deployer balance:${NC} $DEPLOYER_BALANCE_ETH ETH"

if [ "$(echo "$DEPLOYER_BALANCE_ETH < 0.01" | bc)" -eq 1 ]; then
    echo -e "${RED}Warning: Low balance. Deployment may fail.${NC}"
    echo -e "${YELLOW}Recommended: At least 0.01 ETH${NC}"
fi

# Install dependencies if needed
if [ ! -d "lib/openzeppelin-contracts" ]; then
    echo -e "${BLUE}Installing OpenZeppelin contracts...${NC}"
    forge install OpenZeppelin/openzeppelin-contracts --no-commit
fi

if [ ! -d "lib/forge-std" ]; then
    echo -e "${BLUE}Installing Forge Standard Library...${NC}"
    forge install foundry-rs/forge-std --no-commit
fi

# Build contracts
echo -e "${BLUE}Building contracts...${NC}"
forge build

if [ $? -ne 0 ]; then
    echo -e "${RED}Build failed${NC}"
    exit 1
fi

echo -e "${GREEN}Build successful${NC}"
echo ""

# Deploy contract
echo -e "${BLUE}Deploying GLUE token to Base Sepolia...${NC}"
echo ""

forge script script/DeployGLUE.s.sol:DeployGLUE \
    --rpc-url $RPC_URL \
    --broadcast \
    --verify \
    --etherscan-api-key $BASESCAN_API_KEY \
    --verifier-url https://api-sepolia.basescan.org/api \
    -vvvv

DEPLOY_STATUS=$?

echo ""

if [ $DEPLOY_STATUS -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Deployment Successful!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""

    # Extract deployed address from broadcast artifacts
    BROADCAST_FILE="broadcast/DeployGLUE.s.sol/$CHAIN_ID/run-latest.json"

    if [ -f "$BROADCAST_FILE" ]; then
        echo -e "${BLUE}Extracting deployment info...${NC}"

        # Get token address
        TOKEN_ADDRESS=$(cat $BROADCAST_FILE | jq -r '.transactions[] | select(.contractName == "GLUE") | .contractAddress' | head -n 1)

        if [ ! -z "$TOKEN_ADDRESS" ]; then
            echo -e "${YELLOW}Token Address:${NC} $TOKEN_ADDRESS"
            echo ""

            # Save to .env.base-sepolia
            cat > .env.base-sepolia <<EOF
# Base Sepolia Deployment
NETWORK=base-sepolia
CHAIN_ID=$CHAIN_ID
GLUE_TOKEN_ADDRESS=$TOKEN_ADDRESS
OWNER_ADDRESS=$OWNER_WALLET
RPC_URL=$RPC_URL
EXPLORER_URL=$EXPLORER_URL
EOF

            echo -e "${GREEN}Deployment info saved to .env.base-sepolia${NC}"
            echo ""

            # Verify on explorer
            echo -e "${YELLOW}Verify on Base Sepolia Explorer:${NC}"
            echo -e "  $EXPLORER_URL/address/$TOKEN_ADDRESS"
            echo ""

            # Next steps
            echo -e "${YELLOW}Next steps:${NC}"
            echo "  1. Verify contract was deployed: cast code $TOKEN_ADDRESS --rpc-url $RPC_URL"
            echo "  2. Check total supply: cast call $TOKEN_ADDRESS \"totalSupply()\" --rpc-url $RPC_URL"
            echo "  3. Check owner balance: cast call $TOKEN_ADDRESS \"balanceOf(address)\" $OWNER_WALLET --rpc-url $RPC_URL"
            echo "  4. Continue with ERC-8004 registry deployment"
            echo ""
        else
            echo -e "${YELLOW}Warning: Could not extract token address from broadcast artifacts${NC}"
        fi
    else
        echo -e "${YELLOW}Warning: Broadcast file not found at $BROADCAST_FILE${NC}"
    fi
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}Deployment Failed${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo -e "${YELLOW}Try again without --verify if Basescan verification fails:${NC}"
    echo "  forge script script/DeployGLUE.s.sol:DeployGLUE \\"
    echo "    --rpc-url $RPC_URL \\"
    echo "    --broadcast \\"
    echo "    -vvvv"
    exit 1
fi

echo -e "${GREEN}Done!${NC}"
