// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title TransactionLogger
 * @notice Logs transaction messages on-chain for agent economy transparency
 * @dev All agent transactions emit events that appear on Snowtrace forever
 *
 * Inspired by Karma-Hello's transaction logging system
 * Messages are UTF-8 strings that appear in blockchain explorers
 */
contract TransactionLogger {
    // =============================================================================
    // Events
    // =============================================================================

    /**
     * @notice Emitted when an agent logs a transaction
     * @param agent Address of the agent logging the transaction
     * @param txHash Transaction hash being logged
     * @param message Human-readable UTF-8 message
     * @param timestamp Block timestamp
     */
    event TransactionLogged(
        address indexed agent,
        bytes32 indexed txHash,
        string message,
        uint256 timestamp
    );

    /**
     * @notice Emitted for agent-to-agent payments
     * @param from Payer agent address
     * @param to Payee agent address
     * @param amount Amount transferred
     * @param service Service being paid for
     * @param message Full transaction message
     */
    event AgentPayment(
        address indexed from,
        address indexed to,
        uint256 amount,
        string service,
        string message
    );

    /**
     * @notice Emitted for validation events
     * @param validator Validator agent address
     * @param target Target being validated
     * @param score Validation score
     * @param message Validation message
     */
    event ValidationLogged(
        address indexed validator,
        address indexed target,
        uint256 score,
        string message
    );

    // =============================================================================
    // Storage
    // =============================================================================

    /// @notice Mapping of transaction hash to message
    mapping(bytes32 => string) public transactionMessages;

    /// @notice Mapping of agent to their transaction count
    mapping(address => uint256) public agentTransactionCount;

    /// @notice Total number of logged transactions
    uint256 public totalTransactions;

    // =============================================================================
    // Functions
    // =============================================================================

    /**
     * @notice Log a generic transaction with message
     * @param txHash Transaction hash to log
     * @param message UTF-8 message describing the transaction
     */
    function logTransaction(bytes32 txHash, string calldata message) external {
        require(bytes(message).length > 0, "Message cannot be empty");
        require(bytes(transactionMessages[txHash]).length == 0, "Transaction already logged");

        transactionMessages[txHash] = message;
        agentTransactionCount[msg.sender]++;
        totalTransactions++;

        emit TransactionLogged(msg.sender, txHash, message, block.timestamp);
    }

    /**
     * @notice Log an agent-to-agent payment
     * @param from Payer address
     * @param to Payee address
     * @param amount Amount paid (in smallest units)
     * @param service Service description
     * @param txHash Transaction hash
     */
    function logAgentPayment(
        address from,
        address to,
        uint256 amount,
        string calldata service,
        bytes32 txHash
    ) external {
        require(msg.sender == from || msg.sender == to, "Only involved parties can log");

        // Construct message similar to Karma-Hello format
        // "Payment via Karmacadabra by Ultravioleta DAO | {from_agent} → {to_agent} | {amount} GLUE for {service}"
        string memory message = string(
            abi.encodePacked(
                "Payment via Karmacadabra by Ultravioleta DAO | ",
                addressToString(from),
                " \xe2\x86\x92 ",  // → arrow in UTF-8
                addressToString(to),
                " | ",
                uintToString(amount / 1e6),
                " GLUE for ",
                service
            )
        );

        transactionMessages[txHash] = message;
        agentTransactionCount[msg.sender]++;
        totalTransactions++;

        emit AgentPayment(from, to, amount, service, message);
        emit TransactionLogged(msg.sender, txHash, message, block.timestamp);
    }

    /**
     * @notice Log a validation event
     * @param target Address being validated
     * @param score Validation score (0-100)
     * @param details Validation details
     * @param txHash Transaction hash
     */
    function logValidation(
        address target,
        uint256 score,
        string calldata details,
        bytes32 txHash
    ) external {
        require(score <= 100, "Score must be 0-100");

        string memory message = string(
            abi.encodePacked(
                "Validation via Karmacadabra by Ultravioleta DAO | Validator: ",
                addressToString(msg.sender),
                " | Target: ",
                addressToString(target),
                " | Score: ",
                uintToString(score),
                "/100 | ",
                details
            )
        );

        transactionMessages[txHash] = message;
        agentTransactionCount[msg.sender]++;
        totalTransactions++;

        emit ValidationLogged(msg.sender, target, score, message);
        emit TransactionLogged(msg.sender, txHash, message, block.timestamp);
    }

    // =============================================================================
    // View Functions
    // =============================================================================

    /**
     * @notice Get message for a transaction hash
     * @param txHash Transaction hash
     * @return message The logged message
     */
    function getMessage(bytes32 txHash) external view returns (string memory) {
        return transactionMessages[txHash];
    }

    /**
     * @notice Get transaction count for an agent
     * @param agent Agent address
     * @return count Number of transactions logged by agent
     */
    function getAgentTransactionCount(address agent) external view returns (uint256) {
        return agentTransactionCount[agent];
    }

    // =============================================================================
    // Helper Functions
    // =============================================================================

    /**
     * @notice Convert address to string
     * @param addr Address to convert
     * @return String representation of address
     */
    function addressToString(address addr) internal pure returns (string memory) {
        bytes memory alphabet = "0123456789abcdef";
        bytes memory str = new bytes(42);
        str[0] = '0';
        str[1] = 'x';

        for (uint256 i = 0; i < 20; i++) {
            str[2 + i * 2] = alphabet[uint8(uint160(addr) >> (8 * (19 - i)) & 0xf)];
            str[3 + i * 2] = alphabet[uint8(uint160(addr) >> (8 * (19 - i) - 4) & 0xf)];
        }

        return string(str);
    }

    /**
     * @notice Convert uint to string
     * @param value Value to convert
     * @return String representation of value
     */
    function uintToString(uint256 value) internal pure returns (string memory) {
        if (value == 0) {
            return "0";
        }

        uint256 temp = value;
        uint256 digits;

        while (temp != 0) {
            digits++;
            temp /= 10;
        }

        bytes memory buffer = new bytes(digits);

        while (value != 0) {
            digits -= 1;
            buffer[digits] = bytes1(uint8(48 + uint256(value % 10)));
            value /= 10;
        }

        return string(buffer);
    }
}
