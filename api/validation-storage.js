/**
 * Validation Storage API Endpoint
 * Handles saving and loading validation results to/from a shared JSON file
 * This allows validation results to be shared between users
 */

// Note: Vercel serverless functions run on read-only filesystem
// We'll use a simple in-memory storage with reset on cold starts
// This provides session-based sharing but not persistent storage

let inMemoryValidationData = {
    validation_results: {},
    metadata: {
        created: new Date().toISOString(),
        version: '1.0',
        item_count: 0,
        validation_count: 0,
        description: 'In-memory validation results for Levante Translation Dashboard'
    }
};

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
        console.log(`📖 Loading validation results from memory: ${Object.keys(inMemoryValidationData.validation_results || {}).length} items`);
        
        return res.status(200).json({
            success: true,
            data: inMemoryValidationData,
            timestamp: new Date().toISOString()
        });
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

        // Update in-memory storage
        inMemoryValidationData = {
            validation_results,
            metadata: {
                ...metadata,
                saved: new Date().toISOString(),
                version: '1.0',
                item_count: Object.keys(validation_results).length,
                validation_count: totalValidations
            }
        };
        
        console.log(`💾 Saved validation results to memory: ${inMemoryValidationData.metadata.item_count} items, ${inMemoryValidationData.metadata.validation_count} validations`);

        return res.status(200).json({
            success: true,
            message: 'Validation results saved successfully (in-memory)',
            metadata: inMemoryValidationData.metadata,
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

        // Update specific validation entry in memory
        if (!inMemoryValidationData.validation_results[item_id]) {
            inMemoryValidationData.validation_results[item_id] = {};
        }

        inMemoryValidationData.validation_results[item_id][language] = {
            ...validation_data,
            updated: new Date().toISOString()
        };

        // Update metadata
        inMemoryValidationData.metadata.last_updated = new Date().toISOString();
        inMemoryValidationData.metadata.item_count = Object.keys(inMemoryValidationData.validation_results).length;

        let totalValidations = 0;
        Object.keys(inMemoryValidationData.validation_results).forEach(itemId => {
            totalValidations += Object.keys(inMemoryValidationData.validation_results[itemId] || {}).length;
        });
        inMemoryValidationData.metadata.validation_count = totalValidations;

        console.log(`🔄 Updated validation for ${item_id} (${language}) in memory`);

        return res.status(200).json({
            success: true,
            message: 'Validation entry updated successfully (in-memory)',
            item_id,
            language,
            metadata: inMemoryValidationData.metadata,
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        throw new Error(`Failed to update validation results: ${error.message}`);
    }
}