/**
 * Validation Storage API Endpoint
 * Handles saving and loading validation results to/from Google Cloud Storage
 * Falls back to in-memory storage if GCS is not available
 */

// In-memory fallback storage
let inMemoryValidationData = {
    validation_results: {},
    metadata: {
        created: new Date().toISOString(),
        version: '1.0',
        item_count: 0,
        validation_count: 0,
        description: 'Fallback in-memory validation results for Levante Translation Dashboard'
    }
};

// GCS configuration
const BUCKET_NAME = 'levante-translations-dev';
const FILE_PATH = 'validations/validation_results.json';

let gcsStorage = null;

// Initialize Google Cloud Storage
async function initializeGCS() {
    if (gcsStorage) return gcsStorage;

    try {
        const credentials = process.env.GOOGLE_APPLICATION_CREDENTIALS_JSON;
        if (!credentials) {
            console.log('🟡 No GCS credentials found, using in-memory storage');
            return null;
        }

        // Dynamic import of @google-cloud/storage
        const { Storage } = await import('@google-cloud/storage');
        
        const credentialsObj = JSON.parse(credentials);
        gcsStorage = new Storage({
            projectId: credentialsObj.project_id,
            credentials: credentialsObj
        });

        console.log('✅ Google Cloud Storage initialized successfully');
        return gcsStorage;
    } catch (error) {
        console.error('❌ Failed to initialize GCS:', error.message);
        return null;
    }
}

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

async function loadFromGCS() {
    const storage = await initializeGCS();
    if (!storage) return null;

    try {
        const bucket = storage.bucket(BUCKET_NAME);
        const file = bucket.file(FILE_PATH);
        
        const [exists] = await file.exists();
        if (!exists) {
            console.log('📁 No validation file found in GCS, creating new one');
            return null;
        }

        const [data] = await file.download();
        const validationData = JSON.parse(data.toString());
        console.log(`☁️ Loaded validation results from GCS: ${Object.keys(validationData.validation_results || {}).length} items`);
        return validationData;
    } catch (error) {
        console.error('Failed to load from GCS:', error.message);
        return null;
    }
}

async function saveToGCS(validationData) {
    const storage = await initializeGCS();
    if (!storage) return false;

    try {
        const bucket = storage.bucket(BUCKET_NAME);
        const file = bucket.file(FILE_PATH);
        
        await file.save(JSON.stringify(validationData, null, 2), {
            metadata: {
                contentType: 'application/json'
            }
        });

        console.log(`☁️ Saved validation results to GCS: ${validationData.metadata.item_count} items, ${validationData.metadata.validation_count} validations`);
        return true;
    } catch (error) {
        console.error('Failed to save to GCS:', error.message);
        return false;
    }
}

async function getValidationResults(req, res) {
    try {
        // Try to load from GCS first
        let validationData = await loadFromGCS();
        
        if (!validationData) {
            // Fall back to in-memory storage
            validationData = inMemoryValidationData;
            console.log(`📖 Loading validation results from memory: ${Object.keys(validationData.validation_results || {}).length} items`);
        }
        
        return res.status(200).json({
            success: true,
            data: validationData,
            source: validationData === inMemoryValidationData ? 'memory' : 'gcs',
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

        // Prepare validation data
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

        // Try to save to GCS first
        const gcsSuccess = await saveToGCS(validationData);
        
        // Always update in-memory as backup
        inMemoryValidationData = validationData;
        
        const source = gcsSuccess ? 'Google Cloud Storage' : 'session storage';
        console.log(`💾 Saved validation results to ${source}`);

        return res.status(200).json({
            success: true,
            message: `Validation results saved successfully (${source})`,
            source: gcsSuccess ? 'gcs' : 'memory',
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

        // Load current data (from GCS or memory)
        let currentData = await loadFromGCS();
        if (!currentData) {
            currentData = inMemoryValidationData;
        }

        // Update specific validation entry
        if (!currentData.validation_results[item_id]) {
            currentData.validation_results[item_id] = {};
        }

        currentData.validation_results[item_id][language] = {
            ...validation_data,
            updated: new Date().toISOString()
        };

        // Update metadata
        currentData.metadata.last_updated = new Date().toISOString();
        currentData.metadata.item_count = Object.keys(currentData.validation_results).length;

        let totalValidations = 0;
        Object.keys(currentData.validation_results).forEach(itemId => {
            totalValidations += Object.keys(currentData.validation_results[itemId] || {}).length;
        });
        currentData.metadata.validation_count = totalValidations;

        // Save updated data
        const gcsSuccess = await saveToGCS(currentData);
        
        // Always update in-memory as backup
        inMemoryValidationData = currentData;

        const source = gcsSuccess ? 'Google Cloud Storage' : 'session storage';
        console.log(`🔄 Updated validation for ${item_id} (${language}) in ${source}`);

        return res.status(200).json({
            success: true,
            message: `Validation entry updated successfully (${source})`,
            source: gcsSuccess ? 'gcs' : 'memory',
            item_id,
            language,
            metadata: currentData.metadata,
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        throw new Error(`Failed to update validation results: ${error.message}`);
    }
}