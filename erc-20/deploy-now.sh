#!/bin/bash
cd "$(dirname "$0")"

export PRIVATE_KEY=$(aws secretsmanager get-secret-value --secret-id karmacadabra --region us-east-1 --query 'SecretString' --output text | python -c "import sys, json; print(json.load(sys.stdin)['erc-20']['private_key'])")

forge script script/DeployGLUE.s.sol:DeployGLUE \
  --rpc-url https://base-sepolia.g.alchemy.com/v2/demo \
  --broadcast \
  -vvv
