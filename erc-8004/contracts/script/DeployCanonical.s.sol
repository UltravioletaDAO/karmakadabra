// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {Script} from "forge-std/Script.sol";
import {console} from "forge-std/console.sol";
import "../src/IdentityRegistry.sol";
import "../src/ReputationRegistry.sol";
import "../src/ValidationRegistry.sol";
import "../src/CREATE2Factory.sol";

/**
 * @title DeployCanonical
 * @dev Deployment script for ERC-8004 Canonical Registries using CREATE2
 * @notice This deploys registries with deterministic addresses that can be replicated across chains
 * @author ERC-8004 Canonical Registry Initiative
 */
contract DeployCanonical is Script {

    // Canonical salt for ERC-8004 registries
    // Using a meaningful salt that represents "ERC8004" in hex
    bytes32 public constant IDENTITY_SALT = keccak256("ERC8004.IdentityRegistry.v1");
    bytes32 public constant REPUTATION_SALT = keccak256("ERC8004.ReputationRegistry.v1");
    bytes32 public constant VALIDATION_SALT = keccak256("ERC8004.ValidationRegistry.v1");

    // Factory address - will be deployed first or use existing
    CREATE2Factory public factory;

    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        vm.startBroadcast(deployerPrivateKey);

        console.log("=================================================");
        console.log("ERC-8004 CANONICAL REGISTRY DEPLOYMENT");
        console.log("=================================================");
        console.log("Network:", block.chainid);
        console.log("Deployer:", deployer);
        console.log("Balance:", deployer.balance / 1e18, "ETH");
        console.log("");

        // Step 1: Deploy or use existing CREATE2Factory
        console.log("Step 1: Deploying CREATE2Factory...");
        factory = new CREATE2Factory();
        console.log("CREATE2Factory deployed at:", address(factory));
        console.log("");

        // Step 2: Pre-calculate addresses
        console.log("Step 2: Pre-calculating deterministic addresses...");
        console.log("");

        bytes memory identityBytecode = type(IdentityRegistry).creationCode;
        address predictedIdentity = factory.computeAddress(identityBytecode, IDENTITY_SALT);
        console.log("IdentityRegistry will be at:", predictedIdentity);

        bytes memory reputationBytecode = abi.encodePacked(
            type(ReputationRegistry).creationCode,
            abi.encode(predictedIdentity)  // Constructor arg
        );
        address predictedReputation = factory.computeAddress(reputationBytecode, REPUTATION_SALT);
        console.log("ReputationRegistry will be at:", predictedReputation);

        bytes memory validationBytecode = abi.encodePacked(
            type(ValidationRegistry).creationCode,
            abi.encode(predictedIdentity)  // Constructor arg
        );
        address predictedValidation = factory.computeAddress(validationBytecode, VALIDATION_SALT);
        console.log("ValidationRegistry will be at:", predictedValidation);
        console.log("");

        // Step 3: Deploy IdentityRegistry
        console.log("Step 3: Deploying IdentityRegistry with CREATE2...");
        address identityRegistry = factory.deploy(identityBytecode, IDENTITY_SALT);
        require(identityRegistry == predictedIdentity, "Identity address mismatch");
        console.log("IdentityRegistry deployed at:", identityRegistry);
        console.log("Address matches prediction:", identityRegistry == predictedIdentity ? "YES" : "NO");
        console.log("");

        // Step 4: Deploy ReputationRegistry
        console.log("Step 4: Deploying ReputationRegistry with CREATE2...");
        address reputationRegistry = factory.deploy(reputationBytecode, REPUTATION_SALT);
        require(reputationRegistry == predictedReputation, "Reputation address mismatch");
        console.log("ReputationRegistry deployed at:", reputationRegistry);
        console.log("Address matches prediction:", reputationRegistry == predictedReputation ? "YES" : "NO");
        console.log("");

        // Step 5: Deploy ValidationRegistry
        console.log("Step 5: Deploying ValidationRegistry with CREATE2...");
        address validationRegistry = factory.deploy(validationBytecode, VALIDATION_SALT);
        require(validationRegistry == predictedValidation, "Validation address mismatch");
        console.log("ValidationRegistry deployed at:", validationRegistry);
        console.log("Address matches prediction:", validationRegistry == predictedValidation ? "YES" : "NO");
        console.log("");

        vm.stopBroadcast();

        // Final Summary
        console.log("=================================================");
        console.log("DEPLOYMENT SUMMARY - ERC-8004 CANONICAL REGISTRIES");
        console.log("=================================================");
        console.log("");
        console.log("Network: Chain ID", block.chainid);
        console.log("Deployer:", deployer);
        console.log("");
        console.log("CREATE2Factory:        ", address(factory));
        console.log("IdentityRegistry:      ", identityRegistry);
        console.log("ReputationRegistry:    ", reputationRegistry);
        console.log("ValidationRegistry:    ", validationRegistry);
        console.log("");
        console.log("Salts Used:");
        console.log("Identity:   ", uint256(IDENTITY_SALT));
        console.log("Reputation: ", uint256(REPUTATION_SALT));
        console.log("Validation: ", uint256(VALIDATION_SALT));
        console.log("");
        console.log("=================================================");
        console.log("NEXT STEPS:");
        console.log("=================================================");
        console.log("1. Verify contracts on block explorer");
        console.log("2. Update canonical-addresses.json");
        console.log("3. Submit proposal to ERC-8004 community");
        console.log("4. Deploy on other chains using same salts");
        console.log("=================================================");
        console.log("");

        // Write addresses to JSON file for easy reference
        _writeAddressesFile(
            block.chainid,
            address(factory),
            identityRegistry,
            reputationRegistry,
            validationRegistry
        );
    }

    function _writeAddressesFile(
        uint256 chainId,
        address factoryAddr,
        address identityAddr,
        address reputationAddr,
        address validationAddr
    ) internal {
        string memory json = string(abi.encodePacked(
            '{\n',
            '  "network": "',
            _getNetworkName(chainId),
            '",\n',
            '  "chainId": ',
            vm.toString(chainId),
            ',\n',
            '  "deploymentType": "canonical",\n',
            '  "deploymentDate": "',
            vm.toString(block.timestamp),
            '",\n',
            '  "contracts": {\n',
            '    "CREATE2Factory": "',
            vm.toString(factoryAddr),
            '",\n',
            '    "IdentityRegistry": "',
            vm.toString(identityAddr),
            '",\n',
            '    "ReputationRegistry": "',
            vm.toString(reputationAddr),
            '",\n',
            '    "ValidationRegistry": "',
            vm.toString(validationAddr),
            '"\n',
            '  },\n',
            '  "salts": {\n',
            '    "identity": "',
            vm.toString(IDENTITY_SALT),
            '",\n',
            '    "reputation": "',
            vm.toString(REPUTATION_SALT),
            '",\n',
            '    "validation": "',
            vm.toString(VALIDATION_SALT),
            '"\n',
            '  },\n',
            '  "verified": false,\n',
            '  "proposalStatus": "pending"\n',
            '}'
        ));

        vm.writeFile("./canonical-addresses.json", json);
        console.log("Addresses written to: canonical-addresses.json");
    }

    function _getNetworkName(uint256 chainId) internal pure returns (string memory) {
        if (chainId == 43113) return "Avalanche Fuji Testnet";
        if (chainId == 43114) return "Avalanche C-Chain";
        if (chainId == 1) return "Ethereum Mainnet";
        if (chainId == 11155111) return "Sepolia Testnet";
        if (chainId == 31337) return "Anvil Local";
        return "Unknown Network";
    }
}
