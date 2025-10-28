// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/GLUE.sol";

/**
 * @title GLUE Token Deployment Script
 * @notice Deploys GLUE token to Avalanche Fuji Testnet
 * @dev Deployment parameters:
 *      - Initial Supply: 24,157,817 GLUE
 *      - Owner: 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8
 *      - Decimals: 6
 *
 * Usage:
 *   forge script script/DeployGLUE.s.sol:DeployGLUE \
 *     --rpc-url $RPC_URL_AVALANCHE_FUJI \
 *     --broadcast \
 *     --verify \
 *     -vvvv
 */
contract DeployGLUE is Script {
    /// @notice Owner wallet
    address constant OWNER_WALLET = 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8;

    /// @notice Initial supply: 24,157,817 GLUE
    uint256 constant INITIAL_SUPPLY = 24_157_817;

    function run() external {
        // Get deployer private key from environment
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

        // Start broadcasting transactions
        vm.startBroadcast(deployerPrivateKey);

        // Deploy GLUE token
        GLUE token = new GLUE();

        // Log deployment info
        console.log("========================================");
        console.log("GLUE Token Deployment");
        console.log("========================================");
        console.log("Network: Avalanche Fuji Testnet");
        console.log("Chain ID: 43113");
        console.log("");
        console.log("Contract Address:", address(token));
        console.log("Token Name:", token.name());
        console.log("Token Symbol:", token.symbol());
        console.log("Decimals:", token.decimals());
        console.log("Initial Supply:", INITIAL_SUPPLY, "GLUE");
        console.log("Total Supply (with decimals):", token.totalSupply());
        console.log("Owner:", OWNER_WALLET);
        console.log("Owner Balance:", token.balanceOf(OWNER_WALLET) / 10**6, "GLUE");
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
                '  "tokenSymbol": "GLUE",\n',
                '  "decimals": 6,\n',
                '  "initialSupply": ', vm.toString(INITIAL_SUPPLY), ',\n',
                '  "owner": "', vm.toString(OWNER_WALLET), '",\n',
                '  "deployedAt": ', vm.toString(block.timestamp), '\n',
                '}'
            )
        );

        // vm.writeFile("deployment.json", deploymentJson);
        console.log("");
        console.log("Deployment info (save this to deployment.json):");
        console.log(deploymentJson);
    }
}
