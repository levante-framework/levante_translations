import { Storage } from '@google-cloud/storage';

// Initialize Google Cloud Storage client
let storageClient = null;

async function initializeGCS() {
    if (storageClient) return storageClient;
    
    try {
        const credentials = process.env.GOOGLE_APPLICATION_CREDENTIALS_JSON;
        if (credentials) {
            const credentialsObj = JSON.parse(credentials);
            storageClient = new Storage({
                credentials: credentialsObj,
                projectId: credentialsObj.project_id
            });
            console.log('✅ GCS client initialized successfully');
        } else {
            console.warn('⚠️ No GCS credentials found - using default auth');
            storageClient = new Storage();
        }
        return storageClient;
    } catch (error) {
        console.error('❌ Failed to initialize GCS client:', error);
        throw error;
    }
}

async function readAudioMetadata(audioUrl) {
    try {
        // Extract bucket and file path from URL
        // URL format: https://storage.googleapis.com/levante-audio-dev/es/itemid.mp3
        const urlParts = audioUrl.replace('https://storage.googleapis.com/', '').split('/');
        const bucketName = urlParts[0];
        const filePath = urlParts.slice(1).join('/');
        
        console.log(`📁 Reading metadata from: ${bucketName}/${filePath}`);
        
        const storage = await initializeGCS();
        const bucket = storage.bucket(bucketName);
        const file = bucket.file(filePath);
        
        // Check if file exists
        const [exists] = await file.exists();
        if (!exists) {
            return {
                error: 'File not found',
                details: `Audio file not found: ${filePath}`
            };
        }
        
        // Get file metadata from Google Cloud Storage
        const [metadata] = await file.getMetadata();
        
        // Try to download a small portion of the file to read ID3 tags
        // Note: This is a simplified approach. For full ID3 tag reading,
        // we'd need a proper audio metadata library
        
        const basicMetadata = {
            // GCS metadata
            fileName: metadata.name,
            size: metadata.size,
            contentType: metadata.contentType,
            created: metadata.timeCreated,
            updated: metadata.updated,
            
            // Audio file info (extracted from file name and path)
            itemId: filePath.split('/').pop().replace('.mp3', ''),
            language: filePath.split('/')[0],
            
            // Enhanced ID3 tags with Levante custom fields
            // Note: These are currently extracted from GCS metadata or estimated
            // Full ID3 tag reading would require server-side audio processing library
            id3Tags: {
                // Standard ID3 tags
                title: metadata.metadata?.title || filePath.split('/').pop().replace('.mp3', ''),
                artist: metadata.metadata?.artist || 'Levante Project',
                album: metadata.metadata?.album || filePath.split('/')[0] || 'Levante Audio',
                genre: metadata.metadata?.genre || 'Speech Synthesis',
                service: metadata.metadata?.service || 'Unknown',
                voice: metadata.metadata?.voice || 'Unknown',
                
                // Custom Levante fields
                lang_code: metadata.metadata?.lang_code || filePath.split('/')[0],
                text: metadata.metadata?.text || 'Original text not available in metadata',
                created: metadata.metadata?.created || metadata.timeCreated,
                copyright: metadata.metadata?.copyright || 'This file was created for the LEVANTE project and is released under a Creative Commons BY-NC-SA 4.0 license',
                comment: metadata.metadata?.comment || `Generated audio for item: ${filePath.split('/').pop().replace('.mp3', '')}`,
                
                note: 'ID3 tags shown are extracted from GCS metadata. Full embedded ID3 reading requires server-side audio processing.'
            }
        };
        
        return basicMetadata;
        
    } catch (error) {
        console.error('❌ Error reading audio metadata:', error);
        return {
            error: 'Metadata read failed',
            details: error.message
        };
    }
}

export default async function handler(req, res) {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    
    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }
    
    if (req.method !== 'GET' && req.method !== 'POST') {
        res.status(405).json({ error: 'Method not allowed' });
        return;
    }
    
    try {
        const { itemId, langCode } = req.method === 'GET' ? req.query : req.body;
        
        if (!itemId || !langCode) {
            res.status(400).json({ 
                error: 'Missing parameters', 
                details: 'itemId and langCode are required' 
            });
            return;
        }
        
        // Construct audio URL using the same pattern as playAudio function
        const audioUrl = `https://storage.googleapis.com/levante-audio-dev/${langCode}/${itemId}.mp3`;
        
        console.log(`🔍 Reading metadata for: ${itemId} in ${langCode}`);
        
        const metadata = await readAudioMetadata(audioUrl);
        
        if (metadata.error) {
            // Try fallback for es-CO -> es
            if (langCode === 'es-CO') {
                console.log('🔄 Trying es fallback for es-CO...');
                const fallbackUrl = `https://storage.googleapis.com/levante-audio-dev/es/${itemId}.mp3`;
                const fallbackMetadata = await readAudioMetadata(fallbackUrl);
                
                if (!fallbackMetadata.error) {
                    fallbackMetadata.note = 'Using es fallback for es-CO';
                    res.status(200).json(fallbackMetadata);
                    return;
                }
            }
            
            res.status(404).json(metadata);
            return;
        }
        
        res.status(200).json(metadata);
        
    } catch (error) {
        console.error('❌ API Error:', error);
        res.status(500).json({ 
            error: 'Internal server error', 
            details: error.message 
        });
    }
}