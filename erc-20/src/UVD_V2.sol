// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title UVD V2 Token (Ultravioleta DAO Token)
 * @author Ultravioleta DAO
 * @notice ERC-20 token with EIP-3009 (transferWithAuthorization) support for gasless payments
 * @dev This token enables AI agents to make micropayments without holding AVAX for gas fees
 *
 * Network: Avalanche Fuji Testnet (Chain ID: 43113)
 * Decimals: 6 (to match USDC and reduce gas costs)
 * Initial Supply: 24,157,817 UVD (same as UVT V1)
 * Owner: 0x52110a2Cc8B6bBf846101265edAAe34E753f3389 (same as UVT V1)
 *
 * Features:
 * - EIP-2612 Permit (gasless approvals)
 * - EIP-3009 transferWithAuthorization (gasless transfers via x402)
 * - EIP-712 typed structured data hashing
 *
 * ASCII Art:
 *     _   ___   ______    _   ______
 *    | | | \ \ / /  _ \  | | / /___ \
 *    | | | |\ V /| | | | | |/ /  __) |
 *    | |_| | | | | |_| | |   \  / __/
 *     \___/  |_| |____/  |_|\_\|_____|
 *
 * Part of Karmacadabra - Trustless Agent Economy
 */
contract UVD_V2 is ERC20, ERC20Permit, Ownable {
    // =============================================================================
    // Constants
    // =============================================================================

    /// @notice Token decimals (6 decimals to match USDC)
    uint8 private constant DECIMALS = 6;

    /// @notice Initial supply: 24,157,817 UVD (matching UVT V1)
    uint256 private constant INITIAL_SUPPLY = 24_157_817 * 10**DECIMALS;

    /// @notice Owner wallet address (matching UVT V1)
    address private constant OWNER_WALLET = 0x52110a2Cc8B6bBf846101265edAAe34E753f3389;

    // =============================================================================
    // EIP-3009: transferWithAuthorization
    // =============================================================================

    /// @notice EIP-3009 typehash for transferWithAuthorization
    bytes32 public constant TRANSFER_WITH_AUTHORIZATION_TYPEHASH = keccak256(
        "TransferWithAuthorization(address from,address to,uint256 value,uint256 validAfter,uint256 validBefore,bytes32 nonce)"
    );

    /// @notice Mapping of nonces used for EIP-3009 transfers
    mapping(address => mapping(bytes32 => bool)) public authorizationState;

    // =============================================================================
    // Events
    // =============================================================================

    /// @notice Emitted when transferWithAuthorization is executed
    event AuthorizationUsed(address indexed authorizer, bytes32 indexed nonce);

    /// @notice Emitted when an authorization is canceled
    event AuthorizationCanceled(address indexed authorizer, bytes32 indexed nonce);

    // =============================================================================
    // Constructor
    // =============================================================================

    /**
     * @notice Deploys UVD V2 token with initial supply minted to owner wallet
     * @dev Uses EIP-2612 Permit for gasless approvals
     */
    constructor()
        ERC20("Ultravioleta DAO Token", "UVD")
        ERC20Permit("Ultravioleta DAO Token")
        Ownable(OWNER_WALLET)
    {
        // Mint initial supply to owner wallet (same as UVT V1)
        _mint(OWNER_WALLET, INITIAL_SUPPLY);
    }

    // =============================================================================
    // ERC-20 Override: Decimals
    // =============================================================================

    /**
     * @notice Returns the number of decimals (6 to match USDC)
     * @return uint8 Number of decimals
     */
    function decimals() public pure override returns (uint8) {
        return DECIMALS;
    }

    // =============================================================================
    // EIP-3009: transferWithAuthorization Implementation
    // =============================================================================

    /**
     * @notice Execute a transfer with a signed authorization
     * @dev This is the core function for gasless transfers via x402 facilitator
     * @param from Payer's address (Authorizer)
     * @param to Payee's address
     * @param value Amount to transfer
     * @param validAfter Timestamp after which the authorization is valid
     * @param validBefore Timestamp before which the authorization is valid
     * @param nonce Unique nonce (prevents replay attacks)
     * @param v ECDSA signature parameter
     * @param r ECDSA signature parameter
     * @param s ECDSA signature parameter
     */
    function transferWithAuthorization(
        address from,
        address to,
        uint256 value,
        uint256 validAfter,
        uint256 validBefore,
        bytes32 nonce,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external {
        // Validate time window
        require(block.timestamp > validAfter, "Authorization not yet valid");
        require(block.timestamp < validBefore, "Authorization expired");

        // Validate nonce (prevent replay attacks)
        require(!authorizationState[from][nonce], "Authorization already used");

        // Build EIP-712 struct hash
        bytes32 structHash = keccak256(
            abi.encode(
                TRANSFER_WITH_AUTHORIZATION_TYPEHASH,
                from,
                to,
                value,
                validAfter,
                validBefore,
                nonce
            )
        );

        // Build EIP-712 digest
        bytes32 digest = _hashTypedDataV4(structHash);

        // Recover signer from signature
        address signer = ecrecover(digest, v, r, s);
        require(signer == from, "Invalid signature");
        require(signer != address(0), "Invalid signer");

        // Mark nonce as used
        authorizationState[from][nonce] = true;

        // Execute transfer
        _transfer(from, to, value);

        // Emit event
        emit AuthorizationUsed(from, nonce);
    }

    /**
     * @notice Cancel an authorization
     * @dev Allows the authorizer to prevent a signed authorization from being used
     * @param authorizer Authorizer's address
     * @param nonce Nonce of the authorization to cancel
     * @param v ECDSA signature parameter
     * @param r ECDSA signature parameter
     * @param s ECDSA signature parameter
     */
    function cancelAuthorization(
        address authorizer,
        bytes32 nonce,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external {
        // Validate nonce not already used/canceled
        require(!authorizationState[authorizer][nonce], "Authorization already used");

        // Build cancel typehash
        bytes32 CANCEL_AUTHORIZATION_TYPEHASH = keccak256(
            "CancelAuthorization(address authorizer,bytes32 nonce)"
        );

        // Build EIP-712 struct hash
        bytes32 structHash = keccak256(
            abi.encode(CANCEL_AUTHORIZATION_TYPEHASH, authorizer, nonce)
        );

        // Build EIP-712 digest
        bytes32 digest = _hashTypedDataV4(structHash);

        // Recover signer
        address signer = ecrecover(digest, v, r, s);
        require(signer == authorizer, "Invalid signature");

        // Mark nonce as used (canceled)
        authorizationState[authorizer][nonce] = true;

        // Emit event
        emit AuthorizationCanceled(authorizer, nonce);
    }

    // =============================================================================
    // View Functions
    // =============================================================================

    /**
     * @notice Check if an authorization has been used
     * @param authorizer Authorizer's address
     * @param nonce Nonce to check
     * @return bool True if authorization has been used
     */
    function authorizationUsed(address authorizer, bytes32 nonce) external view returns (bool) {
        return authorizationState[authorizer][nonce];
    }
}
