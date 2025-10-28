// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "./interfaces/IReputationRegistry.sol";
import "./interfaces/IIdentityRegistry.sol";

/**
 * @title ReputationRegistry
 * @dev Implementation of the Reputation Registry for ERC-XXXX Trustless Agents v0.3
 * @notice Lightweight entry point for task feedback between agents
 * @author ChaosChain Labs
 */
contract ReputationRegistry is IReputationRegistry {
    // ============ State Variables ============
    
    /// @dev Reference to the IdentityRegistry for agent validation
    IIdentityRegistry public immutable identityRegistry;
    
    /// @dev Mapping from feedback auth ID to whether it exists
    mapping(bytes32 => bool) private _feedbackAuthorizations;
    
    /// @dev Mapping from client-server pair to feedback auth ID
    mapping(uint256 => mapping(uint256 => bytes32)) private _clientServerToAuthId;

    /// @dev Mapping from (clientId, serverId) to client rating (0-100)
    mapping(uint256 => mapping(uint256 => uint8)) private _clientRatings;

    /// @dev Mapping from (clientId, serverId) to whether rating exists
    mapping(uint256 => mapping(uint256 => bool)) private _hasClientRating;

    /// @dev Mapping from (validatorId, serverId) to validator rating (0-100)
    mapping(uint256 => mapping(uint256 => uint8)) private _validatorRatings;

    /// @dev Mapping from (validatorId, serverId) to whether rating exists
    mapping(uint256 => mapping(uint256 => bool)) private _hasValidatorRating;

    // ============ Events ============

    /// @dev Emitted when a server rates a client
    event ClientRated(uint256 indexed clientId, uint256 indexed serverId, uint8 rating);

    /// @dev Emitted when a server rates a validator
    event ValidatorRated(uint256 indexed validatorId, uint256 indexed serverId, uint8 rating);

    // ============ Constructor ============
    
    /**
     * @dev Constructor sets the identity registry reference
     * @param _identityRegistry Address of the IdentityRegistry contract
     */
    constructor(address _identityRegistry) {
        identityRegistry = IIdentityRegistry(_identityRegistry);
    }

    // ============ Write Functions ============
    
    /**
     * @inheritdoc IReputationRegistry
     */
    function acceptFeedback(uint256 agentClientId, uint256 agentServerId) external {
        // Validate that both agents exist
        if (!identityRegistry.agentExists(agentClientId)) {
            revert AgentNotFound();
        }
        if (!identityRegistry.agentExists(agentServerId)) {
            revert AgentNotFound();
        }
        
        // Get server agent info to check authorization
        IIdentityRegistry.AgentInfo memory serverAgent = identityRegistry.getAgent(agentServerId);
        
        // Only the server agent can authorize feedback
        if (msg.sender != serverAgent.agentAddress) {
            revert UnauthorizedFeedback();
        }
        
        // Check if feedback is already authorized
        bytes32 existingAuthId = _clientServerToAuthId[agentClientId][agentServerId];
        if (existingAuthId != bytes32(0)) {
            revert FeedbackAlreadyAuthorized();
        }
        
        // Generate unique feedback authorization ID
        bytes32 feedbackAuthId = _generateFeedbackAuthId(agentClientId, agentServerId);
        
        // Store the authorization
        _feedbackAuthorizations[feedbackAuthId] = true;
        _clientServerToAuthId[agentClientId][agentServerId] = feedbackAuthId;
        
        emit AuthFeedback(agentClientId, agentServerId, feedbackAuthId);
    }

    /**
     * @dev Allows a server agent to rate a client's quality
     * @param agentClientId The client agent ID
     * @param rating The rating score (0-100)
     */
    function rateClient(uint256 agentClientId, uint8 rating) external {
        // Validate rating range (0-100)
        if (rating > 100) {
            revert UnauthorizedFeedback();
        }

        // Validate that client exists
        if (!identityRegistry.agentExists(agentClientId)) {
            revert AgentNotFound();
        }

        // Get the server agent ID from the caller
        IIdentityRegistry.AgentInfo memory serverAgent = identityRegistry.resolveByAddress(msg.sender);
        uint256 agentServerId = serverAgent.agentId;

        // Validate that caller is a registered agent
        if (agentServerId == 0) {
            revert AgentNotFound();
        }

        // Store the rating
        _clientRatings[agentClientId][agentServerId] = rating;
        _hasClientRating[agentClientId][agentServerId] = true;

        emit ClientRated(agentClientId, agentServerId, rating);
    }

    /**
     * @dev Allows a server agent to rate a validator's quality
     * @param agentValidatorId The validator agent ID
     * @param rating The rating score (0-100)
     */
    function rateValidator(uint256 agentValidatorId, uint8 rating) external {
        // Validate rating range (0-100)
        if (rating > 100) {
            revert UnauthorizedFeedback();
        }

        // Validate that validator exists
        if (!identityRegistry.agentExists(agentValidatorId)) {
            revert AgentNotFound();
        }

        // Get the server agent ID from the caller
        IIdentityRegistry.AgentInfo memory serverAgent = identityRegistry.resolveByAddress(msg.sender);
        uint256 agentServerId = serverAgent.agentId;

        // Validate that caller is a registered agent
        if (agentServerId == 0) {
            revert AgentNotFound();
        }

        // Store the rating
        _validatorRatings[agentValidatorId][agentServerId] = rating;
        _hasValidatorRating[agentValidatorId][agentServerId] = true;

        emit ValidatorRated(agentValidatorId, agentServerId, rating);
    }

    // ============ Read Functions ============
    
    /**
     * @inheritdoc IReputationRegistry
     */
    function isFeedbackAuthorized(
        uint256 agentClientId,
        uint256 agentServerId
    ) external view returns (bool isAuthorized, bytes32 feedbackAuthId) {
        feedbackAuthId = _clientServerToAuthId[agentClientId][agentServerId];
        isAuthorized = feedbackAuthId != bytes32(0) && _feedbackAuthorizations[feedbackAuthId];
    }
    
    /**
     * @inheritdoc IReputationRegistry
     */
    function getFeedbackAuthId(
        uint256 agentClientId,
        uint256 agentServerId
    ) external view returns (bytes32 feedbackAuthId) {
        feedbackAuthId = _clientServerToAuthId[agentClientId][agentServerId];
    }

    /**
     * @dev Gets the rating a server gave to a client
     * @param agentClientId The client agent ID
     * @param agentServerId The server agent ID
     * @return hasRating Whether a rating exists
     * @return rating The rating score (0-100)
     */
    function getClientRating(uint256 agentClientId, uint256 agentServerId) external view returns (bool hasRating, uint8 rating) {
        hasRating = _hasClientRating[agentClientId][agentServerId];
        if (hasRating) {
            rating = _clientRatings[agentClientId][agentServerId];
        }
    }

    /**
     * @dev Gets the rating a server gave to a validator
     * @param agentValidatorId The validator agent ID
     * @param agentServerId The server agent ID
     * @return hasRating Whether a rating exists
     * @return rating The rating score (0-100)
     */
    function getValidatorRating(uint256 agentValidatorId, uint256 agentServerId) external view returns (bool hasRating, uint8 rating) {
        hasRating = _hasValidatorRating[agentValidatorId][agentServerId];
        if (hasRating) {
            rating = _validatorRatings[agentValidatorId][agentServerId];
        }
    }

    // ============ Internal Functions ============

    /**
     * @dev Generates a unique feedback authorization ID
     * @param agentClientId The client agent ID
     * @param agentServerId The server agent ID
     * @return feedbackAuthId The unique authorization ID
     */
    function _generateFeedbackAuthId(
        uint256 agentClientId,
        uint256 agentServerId
    ) private view returns (bytes32 feedbackAuthId) {
        // Include block timestamp and transaction hash for uniqueness
        feedbackAuthId = keccak256(
            abi.encodePacked(
                agentClientId,
                agentServerId,
                block.timestamp,
                block.difficulty, // Use block.difficulty for additional entropy
                tx.origin
            )
        );
    }
}