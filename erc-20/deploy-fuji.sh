#!/bin/bash
# =============================================================================
# UVD V2 Token Deployment Script
# Karmacadabra - Ultravioleta DAO
# =============================================================================
#
# Deploys UVD V2 token to Avalanche Fuji Testnet
#
# Deployment Parameters (matching UVT V1):
# - Initial Supply: 24,157,817 UVD
# - Owner: 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8
# - Decimals: 6
# - Network: Avalanche Fuji (Chain ID: 43113)
#
# Usage:
#   ./deploy-fuji.sh
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
NETWORK="fuji"
CHAIN_ID=43113
OWNER_WALLET="0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8"
INITIAL_SUPPLY=24157817

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}UVD V2 Token Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Network:${NC} Avalanche Fuji Testnet"
echo -e "${YELLOW}Chain ID:${NC} $CHAIN_ID"
echo -e "${YELLOW}Owner Wallet:${NC} $OWNER_WALLET"
echo -e "${YELLOW}Initial Supply:${NC} $INITIAL_SUPPLY UVD"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo -e "${YELLOW}Please copy .env.example to .env and configure:${NC}"
    echo "  PRIVATE_KEY=0x..."
    echo "  RPC_URL_AVALANCHE_FUJI=https://..."
    exit 1
fi

# Load environment variables
source .env

# Check required environment variables
if [ -z "$PRIVATE_KEY" ]; then
    echo -e "${RED}Error: PRIVATE_KEY not set in .env${NC}"
    exit 1
fi

if [ -z "$RPC_URL_AVALANCHE_FUJI" ]; then
    echo -e "${RED}Error: RPC_URL_AVALANCHE_FUJI not set in .env${NC}"
    echo -e "${YELLOW}Using fallback RPC...${NC}"
    export RPC_URL_AVALANCHE_FUJI="https://avalanche-fuji-c-chain-rpc.publicnode.com"
fi

# Check if forge is installed
if ! command -v forge &> /dev/null; then
    echo -e "${RED}Error: Foundry (forge) not found${NC}"
    echo -e "${YELLOW}Install Foundry: https://getfoundry.sh${NC}"
    exit 1
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

echo -e "${GREEN} Build successful${NC}"
echo ""

# Deploy contract
echo -e "${BLUE}Deploying UVD V2 to Avalanche Fuji...${NC}"
echo ""

forge script script/Deploy.s.sol:DeployUVD_V2 \
    --rpc-url $RPC_URL_AVALANCHE_FUJI \
    --broadcast \
    --verify \
    -vvvv

if [ $? -ne 0 ]; then
    echo -e "${RED}Deployment failed${NC}"
    echo -e "${YELLOW}Try again without --verify if Snowtrace verification fails${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} Deployment Successful!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if deployment.json was created
if [ -f "deployment.json" ]; then
    echo -e "${BLUE}Deployment info saved to: deployment.json${NC}"
    echo ""
    cat deployment.json | jq '.'
    echo ""

    # Extract token address
    TOKEN_ADDRESS=$(cat deployment.json | jq -r '.tokenAddress')

    echo -e "${YELLOW}Next steps:${NC}"
    echo "  1. Update x402-rs/.env with:"
    echo "     UVD_TOKEN_ADDRESS=$TOKEN_ADDRESS"
    echo ""
    echo "  2. Verify on Snowtrace:"
    echo "     https://testnet.snowtrace.io/address/$TOKEN_ADDRESS"
    echo ""
    echo "  3. Continue with x402 facilitator deployment:"
    echo "     cd ../x402-rs"
    echo "     ./deploy-facilitator.sh init"
    echo ""
else
    echo -e "${YELLOW}Warning: deployment.json not found${NC}"
    echo -e "${YELLOW}Check broadcast/ folder for deployment artifacts${NC}"
fi

echo -e "${GREEN}Done!${NC}"
