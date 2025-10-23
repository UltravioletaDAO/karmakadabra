// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/TransactionLogger.sol";

/**
 * @title TransactionLogger Deployment Script
 * @notice Deploys TransactionLogger to Avalanche Fuji Testnet
 */
contract DeployTransactionLogger is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

        vm.startBroadcast(deployerPrivateKey);

        TransactionLogger logger = new TransactionLogger();

        console.log("========================================");
        console.log("TransactionLogger Deployment");
        console.log("========================================");
        console.log("Network: Avalanche Fuji Testnet");
        console.log("Chain ID: 43113");
        console.log("");
        console.log("Contract Address:", address(logger));
        console.log("Total Transactions:", logger.totalTransactions());
        console.log("========================================");

        vm.stopBroadcast();

        console.log("");
        console.log("Save this address to your .env:");
        console.log("TRANSACTION_LOGGER_ADDRESS=", vm.toString(address(logger)));
    }
}
