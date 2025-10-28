// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Test.sol";
import "../src/ReputationRegistry.sol";
import "../src/IdentityRegistry.sol";

/**
 * @title ReputationRegistryTest
 * @dev Unit tests for bidirectional trust pattern in ReputationRegistry
 * @notice Tests both rateClient() and rateValidator() functions
 */
contract ReputationRegistryTest is Test {
    // Contracts
    IdentityRegistry public identityRegistry;
    ReputationRegistry public reputationRegistry;

    // Test addresses
    address public serverAgent = address(0x1);
    address public clientAgent = address(0x2);
    address public validatorAgent = address(0x3);
    address public unregisteredAgent = address(0x4);

    // Agent IDs (assigned during registration)
    uint256 public serverAgentId;
    uint256 public clientAgentId;
    uint256 public validatorAgentId;

    // Registration fee
    uint256 public constant REGISTRATION_FEE = 0.005 ether;

    // Events to test
    event ClientRated(uint256 indexed clientId, uint256 indexed serverId, uint8 rating);
    event ValidatorRated(uint256 indexed validatorId, uint256 indexed serverId, uint8 rating);

    function setUp() public {
        // Deploy contracts
        identityRegistry = new IdentityRegistry();
        reputationRegistry = new ReputationRegistry(address(identityRegistry));

        // Fund test accounts with registration fees
        vm.deal(serverAgent, 1 ether);
        vm.deal(clientAgent, 1 ether);
        vm.deal(validatorAgent, 1 ether);

        // Register server agent
        vm.prank(serverAgent);
        serverAgentId = identityRegistry.newAgent{value: REGISTRATION_FEE}(
            "server.karmacadabra.ultravioletadao.xyz",
            serverAgent
        );

        // Register client agent
        vm.prank(clientAgent);
        clientAgentId = identityRegistry.newAgent{value: REGISTRATION_FEE}(
            "client.karmacadabra.ultravioletadao.xyz",
            clientAgent
        );

        // Register validator agent
        vm.prank(validatorAgent);
        validatorAgentId = identityRegistry.newAgent{value: REGISTRATION_FEE}(
            "validator.karmacadabra.ultravioletadao.xyz",
            validatorAgent
        );
    }

    // ============ rateClient() Tests ============

    function testRateClient_Success() public {
        uint8 rating = 85;

        // Expect ClientRated event
        vm.expectEmit(true, true, false, true);
        emit ClientRated(clientAgentId, serverAgentId, rating);

        // Server rates client
        vm.prank(serverAgent);
        reputationRegistry.rateClient(clientAgentId, rating);

        // Verify rating was stored
        (bool hasRating, uint8 storedRating) = reputationRegistry.getClientRating(clientAgentId, serverAgentId);
        assertTrue(hasRating, "Rating should exist");
        assertEq(storedRating, rating, "Rating should match");
    }

    function testRateClient_RatingZero() public {
        uint8 rating = 0;

        vm.prank(serverAgent);
        reputationRegistry.rateClient(clientAgentId, rating);

        (bool hasRating, uint8 storedRating) = reputationRegistry.getClientRating(clientAgentId, serverAgentId);
        assertTrue(hasRating);
        assertEq(storedRating, 0);
    }

    function testRateClient_Rating100() public {
        uint8 rating = 100;

        vm.prank(serverAgent);
        reputationRegistry.rateClient(clientAgentId, rating);

        (bool hasRating, uint8 storedRating) = reputationRegistry.getClientRating(clientAgentId, serverAgentId);
        assertTrue(hasRating);
        assertEq(storedRating, 100);
    }

    function testRateClient_RevertIf_RatingTooHigh() public {
        uint8 rating = 101;

        vm.expectRevert(IReputationRegistry.UnauthorizedFeedback.selector);
        vm.prank(serverAgent);
        reputationRegistry.rateClient(clientAgentId, rating);
    }

    function testRateClient_RevertIf_ClientNotFound() public {
        uint256 fakeClientId = 999;

        vm.expectRevert(IReputationRegistry.AgentNotFound.selector);
        vm.prank(serverAgent);
        reputationRegistry.rateClient(fakeClientId, 50);
    }

    function testRateClient_RevertIf_CallerNotRegistered() public {
        vm.expectRevert(IReputationRegistry.AgentNotFound.selector);
        vm.prank(unregisteredAgent);
        reputationRegistry.rateClient(clientAgentId, 50);
    }

    function testRateClient_CanUpdateRating() public {
        // First rating
        vm.prank(serverAgent);
        reputationRegistry.rateClient(clientAgentId, 70);

        // Update rating
        vm.prank(serverAgent);
        reputationRegistry.rateClient(clientAgentId, 90);

        (bool hasRating, uint8 storedRating) = reputationRegistry.getClientRating(clientAgentId, serverAgentId);
        assertTrue(hasRating);
        assertEq(storedRating, 90, "Rating should be updated");
    }

    // ============ rateValidator() Tests ============

    function testRateValidator_Success() public {
        uint8 rating = 95;

        // Expect ValidatorRated event
        vm.expectEmit(true, true, false, true);
        emit ValidatorRated(validatorAgentId, serverAgentId, rating);

        // Server rates validator
        vm.prank(serverAgent);
        reputationRegistry.rateValidator(validatorAgentId, rating);

        // Verify rating was stored
        (bool hasRating, uint8 storedRating) = reputationRegistry.getValidatorRating(validatorAgentId, serverAgentId);
        assertTrue(hasRating, "Rating should exist");
        assertEq(storedRating, rating, "Rating should match");
    }

    function testRateValidator_RatingZero() public {
        uint8 rating = 0;

        vm.prank(serverAgent);
        reputationRegistry.rateValidator(validatorAgentId, rating);

        (bool hasRating, uint8 storedRating) = reputationRegistry.getValidatorRating(validatorAgentId, serverAgentId);
        assertTrue(hasRating);
        assertEq(storedRating, 0);
    }

    function testRateValidator_Rating100() public {
        uint8 rating = 100;

        vm.prank(serverAgent);
        reputationRegistry.rateValidator(validatorAgentId, rating);

        (bool hasRating, uint8 storedRating) = reputationRegistry.getValidatorRating(validatorAgentId, serverAgentId);
        assertTrue(hasRating);
        assertEq(storedRating, 100);
    }

    function testRateValidator_RevertIf_RatingTooHigh() public {
        uint8 rating = 101;

        vm.expectRevert(IReputationRegistry.UnauthorizedFeedback.selector);
        vm.prank(serverAgent);
        reputationRegistry.rateValidator(validatorAgentId, rating);
    }

    function testRateValidator_RevertIf_ValidatorNotFound() public {
        uint256 fakeValidatorId = 999;

        vm.expectRevert(IReputationRegistry.AgentNotFound.selector);
        vm.prank(serverAgent);
        reputationRegistry.rateValidator(fakeValidatorId, 50);
    }

    function testRateValidator_RevertIf_CallerNotRegistered() public {
        vm.expectRevert(IReputationRegistry.AgentNotFound.selector);
        vm.prank(unregisteredAgent);
        reputationRegistry.rateValidator(validatorAgentId, 50);
    }

    function testRateValidator_CanUpdateRating() public {
        // First rating
        vm.prank(serverAgent);
        reputationRegistry.rateValidator(validatorAgentId, 75);

        // Update rating
        vm.prank(serverAgent);
        reputationRegistry.rateValidator(validatorAgentId, 95);

        (bool hasRating, uint8 storedRating) = reputationRegistry.getValidatorRating(validatorAgentId, serverAgentId);
        assertTrue(hasRating);
        assertEq(storedRating, 95, "Rating should be updated");
    }

    // ============ Bidirectional Pattern Tests ============

    function testBidirectional_ServerRatesBothClientAndValidator() public {
        uint8 clientRating = 80;
        uint8 validatorRating = 90;

        // Server rates client
        vm.prank(serverAgent);
        reputationRegistry.rateClient(clientAgentId, clientRating);

        // Server rates validator
        vm.prank(serverAgent);
        reputationRegistry.rateValidator(validatorAgentId, validatorRating);

        // Verify both ratings exist independently
        (bool hasClientRating, uint8 storedClientRating) = reputationRegistry.getClientRating(clientAgentId, serverAgentId);
        (bool hasValidatorRating, uint8 storedValidatorRating) = reputationRegistry.getValidatorRating(validatorAgentId, serverAgentId);

        assertTrue(hasClientRating, "Client rating should exist");
        assertTrue(hasValidatorRating, "Validator rating should exist");
        assertEq(storedClientRating, clientRating, "Client rating should match");
        assertEq(storedValidatorRating, validatorRating, "Validator rating should match");
    }

    function testBidirectional_MultipleServersRateSameClient() public {
        // Register second server
        address server2 = address(0x5);
        vm.deal(server2, 1 ether);
        vm.prank(server2);
        uint256 server2Id = identityRegistry.newAgent{value: REGISTRATION_FEE}(
            "server2.karmacadabra.ultravioletadao.xyz",
            server2
        );

        // Server 1 rates client
        vm.prank(serverAgent);
        reputationRegistry.rateClient(clientAgentId, 80);

        // Server 2 rates same client
        vm.prank(server2);
        reputationRegistry.rateClient(clientAgentId, 90);

        // Verify both ratings are independent
        (bool hasRating1, uint8 rating1) = reputationRegistry.getClientRating(clientAgentId, serverAgentId);
        (bool hasRating2, uint8 rating2) = reputationRegistry.getClientRating(clientAgentId, server2Id);

        assertTrue(hasRating1);
        assertTrue(hasRating2);
        assertEq(rating1, 80);
        assertEq(rating2, 90);
    }

    function testBidirectional_MultipleServersRateSameValidator() public {
        // Register second server
        address server2 = address(0x6);
        vm.deal(server2, 1 ether);
        vm.prank(server2);
        uint256 server2Id = identityRegistry.newAgent{value: REGISTRATION_FEE}(
            "server3.karmacadabra.ultravioletadao.xyz",
            server2
        );

        // Server 1 rates validator
        vm.prank(serverAgent);
        reputationRegistry.rateValidator(validatorAgentId, 85);

        // Server 2 rates same validator
        vm.prank(server2);
        reputationRegistry.rateValidator(validatorAgentId, 95);

        // Verify both ratings are independent
        (bool hasRating1, uint8 rating1) = reputationRegistry.getValidatorRating(validatorAgentId, serverAgentId);
        (bool hasRating2, uint8 rating2) = reputationRegistry.getValidatorRating(validatorAgentId, server2Id);

        assertTrue(hasRating1);
        assertTrue(hasRating2);
        assertEq(rating1, 85);
        assertEq(rating2, 95);
    }

    // ============ Getter Tests ============

    function testGetClientRating_NoRating() public {
        (bool hasRating, uint8 rating) = reputationRegistry.getClientRating(clientAgentId, serverAgentId);
        assertFalse(hasRating, "Should have no rating");
        assertEq(rating, 0, "Rating should be 0");
    }

    function testGetValidatorRating_NoRating() public {
        (bool hasRating, uint8 rating) = reputationRegistry.getValidatorRating(validatorAgentId, serverAgentId);
        assertFalse(hasRating, "Should have no rating");
        assertEq(rating, 0, "Rating should be 0");
    }
}
