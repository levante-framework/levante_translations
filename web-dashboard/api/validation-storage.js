/**
 * Validation Storage API Endpoint
 * Handles saving and loading validation results to/from a shared JSON file
 * This allows validation results to be shared between users
 */

import { promises as fs } from 'fs';
import path from 'path';

const VALIDATION_FILE = path.join(process.cwd(), 'validation_results.json');

export default async function handler(req, res) {
    // Set CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    // Handle preflight requests
    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    try {
        switch (req.method) {
            case 'GET':
                return await getValidationResults(req, res);
            case 'POST':
                return await saveValidationResults(req, res);
            case 'PUT':
                return await updateValidationResults(req, res);
            default:
                return res.status(405).json({ error: 'Method not allowed' });
        }
    } catch (error) {
        console.error('Validation storage error:', error);
        return res.status(500).json({ 
            error: 'Internal server error',
            message: error.message 
        });
    }
}

async function getValidationResults(req, res) {
    try {
        // Check if validation file exists
        try {
            const fileContent = await fs.readFile(VALIDATION_FILE, 'utf8');
            const validationData = JSON.parse(fileContent);
            
            console.log(`📖 Loaded validation results: ${Object.keys(validationData.validation_results || {}).length} items`);
            
            return res.status(200).json({
                success: true,
                data: validationData,
                timestamp: new Date().toISOString()
            });
        } catch (fileError) {
            // File doesn't exist or is invalid, return empty structure
            console.log('📝 No validation file found, returning empty structure');
            return res.status(200).json({
                success: true,
                data: {
                    validation_results: {},
                    metadata: {
                        created: new Date().toISOString(),
                        version: '1.0'
                    }
                },
                timestamp: new Date().toISOString()
            });
        }
    } catch (error) {
        throw new Error(`Failed to load validation results: ${error.message}`);
    }
}

async function saveValidationResults(req, res) {
    try {
        const { validation_results, metadata } = req.body;

        if (!validation_results) {
            return res.status(400).json({ 
                error: 'Missing validation_results in request body' 
            });
        }

        // Count validation entries
        let totalValidations = 0;
        Object.keys(validation_results).forEach(itemId => {
            totalValidations += Object.keys(validation_results[itemId] || {}).length;
        });

        const validationData = {
            validation_results,
            metadata: {
                ...metadata,
                saved: new Date().toISOString(),
                version: '1.0',
                item_count: Object.keys(validation_results).length,
                validation_count: totalValidations
            }
        };

        // Save to file
        await fs.writeFile(VALIDATION_FILE, JSON.stringify(validationData, null, 2), 'utf8');
        
        console.log(`💾 Saved validation results: ${validationData.metadata.item_count} items, ${validationData.metadata.validation_count} validations`);

        return res.status(200).json({
            success: true,
            message: 'Validation results saved successfully',
            metadata: validationData.metadata,
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        throw new Error(`Failed to save validation results: ${error.message}`);
    }
}

async function updateValidationResults(req, res) {
    try {
        const { item_id, language, validation_data } = req.body;

        if (!item_id || !language || !validation_data) {
            return res.status(400).json({ 
                error: 'Missing required fields: item_id, language, validation_data' 
            });
        }

        // Load existing data
        let existingData;
        try {
            const fileContent = await fs.readFile(VALIDATION_FILE, 'utf8');
            existingData = JSON.parse(fileContent);
        } catch (fileError) {
            // File doesn't exist, create new structure
            existingData = {
                validation_results: {},
                metadata: {
                    created: new Date().toISOString(),
                    version: '1.0'
                }
            };
        }

        // Update specific validation entry
        if (!existingData.validation_results[item_id]) {
            existingData.validation_results[item_id] = {};
        }

        existingData.validation_results[item_id][language] = {
            ...validation_data,
            updated: new Date().toISOString()
        };

        // Update metadata
        existingData.metadata.last_updated = new Date().toISOString();
        existingData.metadata.item_count = Object.keys(existingData.validation_results).length;

        let totalValidations = 0;
        Object.keys(existingData.validation_results).forEach(itemId => {
            totalValidations += Object.keys(existingData.validation_results[itemId] || {}).length;
        });
        existingData.metadata.validation_count = totalValidations;

        // Save updated data
        await fs.writeFile(VALIDATION_FILE, JSON.stringify(existingData, null, 2), 'utf8');

        console.log(`🔄 Updated validation for ${item_id} (${language})`);

        return res.status(200).json({
            success: true,
            message: 'Validation entry updated successfully',
            item_id,
            language,
            metadata: existingData.metadata,
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        throw new Error(`Failed to update validation results: ${error.message}`);
    }
}