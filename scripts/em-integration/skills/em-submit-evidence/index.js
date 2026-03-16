#!/usr/bin/env node
/**
 * em-submit-evidence - OpenClaw Skill
 * 
 * Allows KarmaCadabra agents to submit evidence for Execution Market tasks
 * Supports multiple evidence types: photo, document, text_response, etc.
 */

import axios from 'axios';
import FormData from 'form-data';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Execution Market configuration
const EM_API_BASE = process.env.EM_API_BASE || 'https://api.execution.market/api/v1';
const EM_EVIDENCE_BUCKET = process.env.EM_EVIDENCE_BUCKET || 'em-production-evidence';

/**
 * OpenClaw skill main function
 * Called by OpenClaw when agent uses this skill
 */
export default async function submitEvidence({
    taskId,
    evidenceType = 'text_response',
    evidenceContent,
    evidenceFile,
    notes = '',
    agentWallet = null
}) {
    try {
        console.log(`[em-submit-evidence] Submitting evidence for task ${taskId}`);
        
        // Validate required parameters
        if (!taskId) {
            throw new Error('taskId is required');
        }
        
        if (!evidenceContent && !evidenceFile) {
            throw new Error('Either evidenceContent or evidenceFile is required');
        }
        
        // Prepare evidence submission
        let evidenceUrl = null;
        let submissionData = {
            evidence_type: evidenceType,
            notes: notes
        };
        
        // Handle different evidence types
        if (evidenceFile) {
            // Upload file evidence (photo, document, etc.)
            evidenceUrl = await uploadEvidenceFile(evidenceFile, taskId, evidenceType);
            submissionData.evidence_url = evidenceUrl;
        } else if (evidenceContent) {
            // Handle text evidence
            if (evidenceType === 'text_response') {
                submissionData.evidence_text = evidenceContent;
            } else {
                // For other types, create a temporary file
                evidenceUrl = await uploadTextAsFile(evidenceContent, taskId, evidenceType);
                submissionData.evidence_url = evidenceUrl;
            }
        }
        
        // Submit to Execution Market
        const response = await submitToExecutionMarket(taskId, submissionData, agentWallet);
        
        console.log(`[em-submit-evidence] Successfully submitted evidence`);
        console.log(`- Task ID: ${taskId}`);
        console.log(`- Evidence Type: ${evidenceType}`);
        console.log(`- Evidence URL: ${evidenceUrl || 'N/A'}`);
        console.log(`- Submission ID: ${response.submission_id}`);
        
        return {
            success: true,
            taskId,
            submissionId: response.submission_id,
            evidenceType,
            evidenceUrl,
            message: 'Evidence submitted successfully',
            status: response.status || 'submitted'
        };
        
    } catch (error) {
        console.error(`[em-submit-evidence] Error: ${error.message}`);
        
        return {
            success: false,
            error: error.message,
            taskId: taskId || 'unknown'
        };
    }
}

/**
 * Upload evidence file to S3/evidence storage
 */
async function uploadEvidenceFile(filePath, taskId, evidenceType) {
    // For now, create a placeholder URL
    // In production, this would upload to S3 and return real URL
    const filename = `task-${taskId}-evidence-${Date.now()}.${getFileExtension(evidenceType)}`;
    const placeholderUrl = `https://${EM_EVIDENCE_BUCKET}.s3.amazonaws.com/${filename}`;
    
    console.log(`[upload] Would upload ${filePath} to ${placeholderUrl}`);
    console.log(`[upload] File size: ${(await fs.stat(filePath)).size} bytes`);
    
    // TODO: Implement actual S3 upload
    // const uploadResult = await uploadToS3(filePath, filename);
    // return uploadResult.url;
    
    return placeholderUrl;
}

/**
 * Upload text content as file
 */
async function uploadTextAsFile(content, taskId, evidenceType) {
    const filename = `task-${taskId}-${evidenceType}-${Date.now()}.txt`;
    const placeholderUrl = `https://${EM_EVIDENCE_BUCKET}.s3.amazonaws.com/${filename}`;
    
    console.log(`[upload] Would create text file: ${filename}`);
    console.log(`[upload] Content length: ${content.length} characters`);
    
    return placeholderUrl;
}

/**
 * Submit evidence to Execution Market API
 */
async function submitToExecutionMarket(taskId, submissionData, agentWallet) {
    const submitUrl = `${EM_API_BASE}/tasks/${taskId}/submit`;
    
    // Prepare headers
    const headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'KarmaCadabra-Agent/1.0'
    };
    
    // Add authentication if agent wallet provided
    if (agentWallet) {
        // TODO: Implement ERC-8128 wallet authentication
        // For now, use API key if available
        if (process.env.EM_API_KEY) {
            headers['X-API-Key'] = process.env.EM_API_KEY;
        } else {
            headers['X-Agent-Wallet'] = agentWallet;
        }
    }
    
    console.log(`[api] POST ${submitUrl}`);
    console.log(`[api] Data:`, submissionData);
    
    try {
        const response = await axios.post(submitUrl, submissionData, { headers });
        
        if (response.status === 200 || response.status === 201) {
            return response.data;
        } else {
            throw new Error(`API returned status ${response.status}: ${response.statusText}`);
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
 * Get file extension for evidence type
 */
function getFileExtension(evidenceType) {
    const extensions = {
        photo: 'jpg',
        document: 'pdf',
        video: 'mp4',
        text_response: 'txt',
        screenshot: 'png',
        receipt: 'jpg'
    };
    
    return extensions[evidenceType] || 'txt';
}

/**
 * CLI interface for testing
 */
if (import.meta.url === `file://${process.argv[1]}`) {
    const args = process.argv.slice(2);
    
    if (args.length === 0) {
        console.log(`
Usage: node index.js <taskId> [options]

Examples:
  node index.js task123 --type text_response --content "Completed successfully"
  node index.js task456 --type photo --file ./evidence.jpg --notes "Photo evidence"
  node index.js task789 --type document --file ./report.pdf
        `);
        process.exit(1);
    }
    
    const taskId = args[0];
    const options = {};
    
    for (let i = 1; i < args.length; i += 2) {
        const key = args[i]?.replace('--', '');
        const value = args[i + 1];
        if (key && value) {
            options[key] = value;
        }
    }
    
    const result = await submitEvidence({
        taskId,
        evidenceType: options.type || 'text_response',
        evidenceContent: options.content,
        evidenceFile: options.file,
        notes: options.notes || '',
        agentWallet: options.wallet
    });
    
    console.log('\nResult:', JSON.stringify(result, null, 2));
}