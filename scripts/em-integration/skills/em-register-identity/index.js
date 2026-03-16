#!/usr/bin/env node
/**
 * em-register-identity - OpenClaw Skill
 *
 * Allows KarmaCadabra agents to register as workers on Execution Market
 * and obtain an ERC-8004 on-chain identity (gasless via Facilitator).
 *
 * Two-step process:
 *   1. Register as a worker (executor) in the platform database
 *   2. Register on-chain ERC-8004 identity via the Facilitator (gasless)
 */

import axios from 'axios';

// Execution Market configuration
const EM_API_BASE = process.env.EM_API_BASE || 'https://api.execution.market/api/v1';

/**
 * OpenClaw skill main function
 * Called by OpenClaw when agent uses this skill
 */
export default async function registerIdentity({
    walletAddress,
    name = null,
    email = null,
    agentUri = null,
    network = 'base',
    metadata = null
}) {
    try {
        console.log(`[em-register-identity] Registering identity for ${walletAddress}`);

        // Validate required parameters
        if (!walletAddress) {
            throw new Error('walletAddress is required');
        }

        if (!/^0x[0-9a-fA-F]{40}$/.test(walletAddress)) {
            throw new Error('Invalid Ethereum wallet address format');
        }

        // Step 1: Register as a worker (executor) in the platform
        console.log('[step 1/2] Registering as worker on Execution Market...');
        const workerResult = await registerWorker(walletAddress, name);

        const executorId = workerResult.executor?.id || null;
        const isNew = workerResult.created || false;

        console.log(`[step 1/2] ${isNew ? 'Created new' : 'Found existing'} executor: ${executorId}`);

        // Step 2: Register ERC-8004 on-chain identity (gasless)
        console.log(`[step 2/2] Registering ERC-8004 identity on ${network}...`);
        let identityResult = null;
        let agentId = null;

        try {
            identityResult = await registerERC8004Identity(
                walletAddress,
                network,
                agentUri,
                metadata
            );
            agentId = identityResult.agent_id || null;

            if (identityResult.success) {
                console.log(`[step 2/2] ERC-8004 identity registered: Agent #${agentId}`);
                if (identityResult.transaction) {
                    console.log(`[step 2/2] TX: ${identityResult.transaction}`);
                }
            } else {
                console.warn(`[step 2/2] ERC-8004 registration issue: ${identityResult.error || 'unknown'}`);
            }
        } catch (error) {
            console.warn(`[step 2/2] ERC-8004 registration failed: ${error.message}`);
            // Don't fail the whole operation if on-chain registration fails
            // The worker is still registered in the platform
        }

        console.log('[em-register-identity] Registration complete');
        console.log(`- Wallet: ${walletAddress}`);
        console.log(`- Executor ID: ${executorId}`);
        console.log(`- Agent ID: ${agentId || 'N/A'}`);
        console.log(`- Network: ${network}`);

        return {
            success: true,
            walletAddress,
            executorId,
            agentId,
            network,
            isNewWorker: isNew,
            identityRegistration: identityResult,
            message: agentId
                ? `Registered as Agent #${agentId} on ${network}`
                : 'Worker registered (ERC-8004 identity pending)'
        };

    } catch (error) {
        console.error(`[em-register-identity] Error: ${error.message}`);

        return {
            success: false,
            error: error.message,
            walletAddress: walletAddress || 'unknown'
        };
    }
}

/**
 * Register as a worker (executor) on Execution Market
 */
async function registerWorker(walletAddress, name) {
    const registerUrl = `${EM_API_BASE}/executors/register`;

    const workerData = {
        wallet_address: walletAddress,
        display_name: name || `Agent ${walletAddress.slice(0, 8)}`
    };

    const headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'KarmaCadabra-Agent/1.0'
    };

    if (process.env.EM_API_KEY) {
        headers['X-API-Key'] = process.env.EM_API_KEY;
    }

    console.log(`[api] POST ${registerUrl}`);

    try {
        const response = await axios.post(registerUrl, workerData, { headers });

        if (response.status === 200 || response.status === 201) {
            return response.data;
        } else {
            throw new Error(`API returned status ${response.status}: ${response.statusText}`);
        }
    } catch (error) {
        if (error.response) {
            throw new Error(`Worker registration failed: ${error.response.status} ${error.response.data?.detail || error.response.statusText}`);
        } else {
            throw new Error(`Network error during worker registration: ${error.message}`);
        }
    }
}

/**
 * Register ERC-8004 on-chain identity via the Facilitator (gasless)
 */
async function registerERC8004Identity(walletAddress, network, agentUri, metadata) {
    const registerUrl = `${EM_API_BASE}/reputation/register`;

    const requestData = {
        network: network,
        agent_uri: agentUri || `https://execution.market/agents/${walletAddress}`,
        recipient: walletAddress
    };

    if (metadata && Array.isArray(metadata) && metadata.length > 0) {
        requestData.metadata = metadata;
    }

    const headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'KarmaCadabra-Agent/1.0'
    };

    if (process.env.EM_API_KEY) {
        headers['X-API-Key'] = process.env.EM_API_KEY;
    }

    console.log(`[api] POST ${registerUrl}`);
    console.log(`[api] Network: ${network}, Recipient: ${walletAddress}`);

    try {
        const response = await axios.post(registerUrl, requestData, { headers });

        if (response.status === 200 || response.status === 201) {
            return response.data;
        } else {
            throw new Error(`API returned status ${response.status}: ${response.statusText}`);
        }
    } catch (error) {
        if (error.response) {
            throw new Error(`ERC-8004 registration failed: ${error.response.status} ${error.response.data?.detail || error.response.data?.error || error.response.statusText}`);
        } else {
            throw new Error(`Network error during ERC-8004 registration: ${error.message}`);
        }
    }
}

/**
 * CLI interface for testing
 */
if (import.meta.url === `file://${process.argv[1]}`) {
    const args = process.argv.slice(2);

    if (args.length === 0) {
        console.log(`
Usage: node index.js <walletAddress> [options]

Examples:
  node index.js 0xC2D4a3bEfC12E8c4F1234567890abcdef12345678
  node index.js 0xC2D4...eFBa --name "Aurora Agent" --network base
  node index.js 0xC2D4...eFBa --name "Builder" --uri "ipfs://QmYourCID"

Options:
  --name <text>       Display name for the worker
  --email <text>      Email address (optional)
  --network <name>    ERC-8004 network (default: base)
  --uri <text>        Agent URI for ERC-8004 metadata (IPFS or HTTPS)
        `);
        process.exit(1);
    }

    const walletAddress = args[0];
    const options = {};

    for (let i = 1; i < args.length; i += 2) {
        const key = args[i]?.replace('--', '');
        const value = args[i + 1];
        if (key && value) {
            options[key] = value;
        }
    }

    const result = await registerIdentity({
        walletAddress,
        name: options.name,
        email: options.email,
        agentUri: options.uri,
        network: options.network || 'base',
        metadata: null
    });

    console.log('\nResult:', JSON.stringify(result, null, 2));
}
