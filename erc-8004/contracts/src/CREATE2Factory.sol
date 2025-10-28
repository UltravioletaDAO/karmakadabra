// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title CREATE2Factory
 * @dev Factory contract for deploying contracts with deterministic addresses using CREATE2
 * @notice This allows the same contract to have the same address across different chains
 * @author ERC-8004 Canonical Registry Initiative
 */
contract CREATE2Factory {

    event ContractDeployed(
        address indexed deployedAddress,
        bytes32 indexed salt,
        address indexed deployer
    );

    /**
     * @dev Deploy a contract using CREATE2
     * @param bytecode The creation bytecode of the contract to deploy
     * @param salt A salt to ensure address uniqueness and determinism
     * @return deployedAddress The address of the deployed contract
     *
     * @notice The deployed address can be pre-calculated using:
     * address = keccak256(0xff ++ deployerAddress ++ salt ++ keccak256(bytecode))[12:]
     */
    function deploy(bytes memory bytecode, bytes32 salt)
        public
        payable
        returns (address deployedAddress)
    {
        assembly {
            deployedAddress := create2(
                callvalue(),           // wei sent with current call
                add(bytecode, 0x20),   // bytecode location (skip length prefix)
                mload(bytecode),       // bytecode length
                salt                   // salt for deterministic address
            )
        }

        require(deployedAddress != address(0), "CREATE2: Failed to deploy");

        emit ContractDeployed(deployedAddress, salt, msg.sender);
    }

    /**
     * @dev Compute the address of a contract deployed via CREATE2
     * @param bytecode The creation bytecode of the contract
     * @param salt The salt used for deployment
     * @return predictedAddress The address where the contract will be deployed
     */
    function computeAddress(bytes memory bytecode, bytes32 salt)
        public
        view
        returns (address predictedAddress)
    {
        bytes32 bytecodeHash = keccak256(bytecode);
        bytes32 data = keccak256(
            abi.encodePacked(
                bytes1(0xff),
                address(this),
                salt,
                bytecodeHash
            )
        );
        predictedAddress = address(uint160(uint256(data)));
    }

    /**
     * @dev Check if a contract has been deployed at a specific address
     * @param contractAddress The address to check
     * @return deployed True if code exists at the address, false otherwise
     */
    function isDeployed(address contractAddress)
        public
        view
        returns (bool deployed)
    {
        uint32 size;
        assembly {
            size := extcodesize(contractAddress)
        }
        deployed = (size > 0);
    }
}
