#!/usr/bin/env node
/**
 * em-rate-counterparty - OpenClaw Skill
 * 
 * Allows KarmaCadabra agents to rate counterparties in EM transactions
 * Builds bidirectional reputation via ERC-8004 on-chain registry
 */

import axios from 'axios';
import { ethers } from 'ethers';

// Execution Market configuration
const EM_API_BASE = process.env.EM_API_BASE || 'https://api.execution.market/api/v1';

// ERC-8004 contract addresses (Base mainnet)
const ERC8004_CONTRACTS = {
    base: {
        identity: '0x8004A169FB4a3325136EB29fA0ceB6D2e539a432',
        reputation: '0x8004BAa17C55a88189AE136b182e5fdA19dE9b63'
    }
};

// Base network config
const BASE_CONFIG = {
    chainId: 8453,
    name: 'Base Mainnet', 
    rpcUrl: 'https://mainnet.base.org'
};

/**
 * OpenClaw skill main function
 */
export default async function rateCounterparty({
    taskId,
    counterpartyAddress,
    rating,
    feedbackText = '',
    agentWallet = null,
    agentPrivateKey = null,
    network = 'base'
}) {
    try {
        console.log(`[em-rate-counterparty] Rating counterparty for task ${taskId}`);
        
        // Validate required parameters
        if (!taskId) {
            throw new Error('taskId is required');
        }
        
        if (!counterpartyAddress) {
            throw new Error('counterpartyAddress is required');
        }
        
        if (!rating || rating < 1 || rating > 5) {
            throw new Error('rating must be between 1 and 5');
        }
        
        if (!ethers.isAddress(counterpartyAddress)) {
            throw new Error('Invalid counterparty address');
        }
        
        // Submit via EM API first (simpler path)
        const apiResult = await submitViaAPI(taskId, counterpartyAddress, rating, feedbackText, agentWallet);
        
        // If agent private key provided, also submit on-chain
        let onChainResult = null;
        if (agentPrivateKey) {
            try {
                onChainResult = await submitOnChain(
                    counterpartyAddress, 
                    rating, 
                    feedbackText, 
                    taskId,
                    agentPrivateKey, 
                    network
                );
            } catch (error) {
                console.warn(`[em-rate-counterparty] On-chain submission failed: ${error.message}`);
                // Don't fail the whole operation if on-chain fails
            }
        }
        
        console.log(`[em-rate-counterparty] Successfully rated counterparty`);
        console.log(`- Task: ${taskId}`);
        console.log(`- Counterparty: ${counterpartyAddress}`);
        console.log(`- Rating: ${rating}/5 stars`);
        console.log(`- API submission: ${apiResult.success ? 'Success' : 'Failed'}`);
        console.log(`- On-chain: ${onChainResult ? 'Success' : 'Skipped'}`);
        
        return {
            success: true,
            taskId,
            counterpartyAddress,
            rating,
            feedbackText,
            apiSubmission: apiResult,
            onChainSubmission: onChainResult,
            message: 'Rating submitted successfully'
        };
        
    } catch (error) {
        console.error(`[em-rate-counterparty] Error: ${error.message}`);
        
        return {
            success: false,
            error: error.message,
            taskId: taskId || 'unknown'
        };
    }
}

/**
 * Submit rating via EM API
 */
async function submitViaAPI(taskId, counterpartyAddress, rating, feedbackText, agentWallet) {
    const feedbackUrl = `${EM_API_BASE}/feedback`;
    
    const feedbackData = {
        task_id: taskId,
        target_address: counterpartyAddress,
        rating: rating,
        feedback_text: feedbackText || ''
    };
    
    const headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'KarmaCadabra-Agent/1.0'
    };
    
    // Add authentication
    if (process.env.EM_API_KEY) {
        headers['X-API-Key'] = process.env.EM_API_KEY;
    } else if (agentWallet) {
        headers['X-Agent-Wallet'] = agentWallet;
    }
    
    console.log(`[api] POST ${feedbackUrl}`);
    console.log(`[api] Rating ${rating}/5 for ${counterpartyAddress}`);
    
    try {
        const response = await axios.post(feedbackUrl, feedbackData, { headers });
        
        if (response.status === 200 || response.status === 201) {
            return {
                success: true,
                feedbackId: response.data.feedback_id || response.data.id,
                status: response.data.status || 'submitted'
            };
        } else {
            throw new Error(`API returned status ${response.status}`);
        }
    } catch (error) {
        if (error.response) {
            throw new Error(`API error: ${error.response.status} ${error.response.data?.message || error.response.statusText}`);
        } else {
            throw new Error(`Network error: ${error.message}`);
        }
    }
}

/**
 * Submit rating directly on-chain via ERC-8004
 */
async function submitOnChain(counterpartyAddress, rating, feedbackText, taskId, privateKey, network) {
    if (network !== 'base') {
        throw new Error('On-chain submission currently only supports Base network');
    }
    
    // Setup provider and wallet
    const provider = new ethers.JsonRpcProvider(BASE_CONFIG.rpcUrl);
    const wallet = new ethers.Wallet(privateKey, provider);
    
    console.log(`[onchain] Submitting rating from ${wallet.address} to ${counterpartyAddress}`);
    
    // ERC-8004 Reputation contract ABI (minimal)
    const REPUTATION_ABI = [
        "function submitRating(address target, uint8 rating, string calldata feedback) external",
        "function getRating(address rater, address target) external view returns (uint8 rating, string memory feedback, uint256 timestamp)"
    ];
    
    const reputationContract = new ethers.Contract(
        ERC8004_CONTRACTS.base.reputation, 
        REPUTATION_ABI, 
        wallet
    );
    
    // Prepare feedback text with task context
    const contextualFeedback = feedbackText 
        ? `Task ${taskId}: ${feedbackText}`
        : `Task ${taskId} completed`;
    
    try {
        // Estimate gas
        const gasEstimate = await reputationContract.submitRating.estimateGas(
            counterpartyAddress,
            rating,
            contextualFeedback
        );
        
        const gasLimit = gasEstimate * BigInt(120) / BigInt(100); // 20% buffer
        
        // Submit rating transaction
        const tx = await reputationContract.submitRating(
            counterpartyAddress,
            rating,
            contextualFeedback,
            { gasLimit }
        );
        
        console.log(`[onchain] Transaction sent: ${tx.hash}`);
        
        // Wait for confirmation
        const receipt = await tx.wait();
        console.log(`[onchain] Confirmed in block ${receipt.blockNumber}`);
        
        return {
            success: true,
            txHash: tx.hash,
            blockNumber: receipt.blockNumber,
            gasUsed: receipt.gasUsed.toString(),
            network: 'base'
        };
        
    } catch (error) {
        throw new Error(`On-chain transaction failed: ${error.message}`);
    }
}

/**
 * CLI interface for testing
 */
if (import.meta.url === `file://${process.argv[1]}`) {
    const args = process.argv.slice(2);
    
    if (args.length < 3) {
        console.log(`
Usage: node index.js <taskId> <counterpartyAddress> <rating> [options]

Examples:
  node index.js task123 0x123...abc 5 --feedback "Excellent work, fast delivery"
  node index.js task456 0x456...def 3 --feedback "Good but took longer than expected"
  node index.js task789 0x789...ghi 1 --feedback "Did not meet requirements"
        
Options:
  --feedback <text>     Optional feedback text
  --wallet <address>    Agent wallet address for API auth
  --key <private_key>   Private key for on-chain submission
  --network <name>      Network (default: base)
        `);
        process.exit(1);
    }
    
    const taskId = args[0];
    const counterpartyAddress = args[1];
    const rating = parseInt(args[2]);
    
    const options = {};
    for (let i = 3; i < args.length; i += 2) {
        const key = args[i]?.replace('--', '');
        const value = args[i + 1];
        if (key && value) {
            options[key] = value;
        }
    }
    
    const result = await rateCounterparty({
        taskId,
        counterpartyAddress,
        rating,
        feedbackText: options.feedback || '',
        agentWallet: options.wallet,
        agentPrivateKey: options.key,
        network: options.network || 'base'
    });
    
    console.log('\nResult:', JSON.stringify(result, null, 2));
}