// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/UVD_V2.sol";

/**
 * @title UVD V2 Deployment Script
 * @notice Deploys UVD V2 token to Avalanche Fuji Testnet
 * @dev Uses same deployment parameters as UVT V1:
 *      - Initial Supply: 24,157,817 UVD
 *      - Owner: 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8
 *      - Decimals: 6
 *
 * Usage:
 *   forge script script/Deploy.s.sol:DeployUVD_V2 \
 *     --rpc-url $RPC_URL_AVALANCHE_FUJI \
 *     --broadcast \
 *     --verify \
 *     -vvvv
 */
contract DeployUVD_V2 is Script {
    /// @notice Owner wallet (same as UVT V1)
    address constant OWNER_WALLET = 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8;

    /// @notice Initial supply: 24,157,817 UVD
    uint256 constant INITIAL_SUPPLY = 24_157_817;

    function run() external {
        // Get deployer private key from environment
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

        // Start broadcasting transactions
        vm.startBroadcast(deployerPrivateKey);

        // Deploy UVD V2 token
        UVD_V2 token = new UVD_V2();

        // Log deployment info
        console.log("========================================");
        console.log("UVD V2 Token Deployment");
        console.log("========================================");
        console.log("Network: Avalanche Fuji Testnet");
        console.log("Chain ID: 43113");
        console.log("");
        console.log("Contract Address:", address(token));
        console.log("Token Name:", token.name());
        console.log("Token Symbol:", token.symbol());
        console.log("Decimals:", token.decimals());
        console.log("Initial Supply:", INITIAL_SUPPLY, "UVD");
        console.log("Total Supply (with decimals):", token.totalSupply());
        console.log("Owner:", OWNER_WALLET);
        console.log("Owner Balance:", token.balanceOf(OWNER_WALLET) / 10**6, "UVD");
        console.log("========================================");

        // Stop broadcasting
        vm.stopBroadcast();

        // Save deployment address to file
        string memory deploymentJson = string(
            abi.encodePacked(
                '{\n',
                '  "network": "avalanche-fuji",\n',
                '  "chainId": 43113,\n',
                '  "tokenAddress": "', vm.toString(address(token)), '",\n',
                '  "tokenName": "Gasless Ultravioleta DAO Extended Token",\n',
                '  "tokenSymbol": "UVD",\n',
                '  "decimals": 6,\n',
                '  "initialSupply": ', vm.toString(INITIAL_SUPPLY), ',\n',
                '  "owner": "', vm.toString(OWNER_WALLET), '",\n',
                '  "deployedAt": ', vm.toString(block.timestamp), '\n',
                '}'
            )
        );

        // vm.writeFile("deployment.json", deploymentJson);
        console.log("");
        console.log("Deployment info (manual save required):");
        console.log(deploymentJson);
    }
}
