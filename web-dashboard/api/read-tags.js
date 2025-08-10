import { Storage } from '@google-cloud/storage';
import NodeID3 from 'node-id3';

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

async function downloadAndReadID3Tags(bucket, file) {
    try {
        console.log('📥 Downloading file to read ID3 tags...');
        
        // Download only the first 64KB of the file (ID3v2 tags are typically at the beginning)
        // This is much more efficient than downloading the entire audio file
        const [fileBuffer] = await file.download({
            start: 0,
            end: 65535 // First 64KB should contain ID3 tags
        });
        
        console.log(`📖 Reading ID3 tags from ${fileBuffer.length} bytes...`);
        
        // Read ID3 tags using node-id3
        const tags = NodeID3.read(fileBuffer);
        
        console.log('🏷️ ID3 tags found:', Object.keys(tags));
        return tags;
        
    } catch (error) {
        console.warn('⚠️ Could not read ID3 tags:', error.message);
        return null;
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
        
        // Download and read actual ID3 tags from the MP3 file
        const id3Tags = await downloadAndReadID3Tags(bucket, file);
        
        // Build comprehensive metadata combining GCS and ID3 tag data
        const itemId = filePath.split('/').pop().replace('.mp3', '');
        const languageCode = filePath.split('/')[0];
        
        const basicMetadata = {
            // GCS metadata
            fileName: metadata.name,
            size: metadata.size,
            contentType: metadata.contentType,
            created: metadata.timeCreated,
            updated: metadata.updated,
            
            // Audio file info (extracted from file name and path)
            itemId: itemId,
            language: languageCode,
            
            // Enhanced ID3 tags with actual embedded data
            id3Tags: {
                // Standard ID3 tags (from embedded ID3 or fallback)
                title: id3Tags?.title || itemId,
                artist: id3Tags?.artist || 'Levante Project',
                album: id3Tags?.album || languageCode || 'Levante Audio',
                genre: id3Tags?.genre || 'Speech Synthesis',
                
                // Custom Levante fields (check both TXXX custom frames and standard fields)
                service: id3Tags?.userDefinedText?.find(t => t.description === 'service')?.value || 
                        id3Tags?.service || 'Not available',
                voice: id3Tags?.userDefinedText?.find(t => t.description === 'voice')?.value || 
                      id3Tags?.voice || 'Not available',
                lang_code: id3Tags?.userDefinedText?.find(t => t.description === 'lang_code')?.value || 
                          id3Tags?.lang_code || languageCode,
                text: id3Tags?.userDefinedText?.find(t => t.description === 'text')?.value || 
                     id3Tags?.text || 'Original text not available',
                created: id3Tags?.userDefinedText?.find(t => t.description === 'created')?.value || 
                        id3Tags?.date || metadata.timeCreated,
                copyright: id3Tags?.copyright || 'This file was created for the LEVANTE project and is released under a Creative Commons BY-NC-SA 4.0 license',
                comment: id3Tags?.comment?.text || id3Tags?.comment || `Generated audio for item: ${itemId}`,
                
                // Metadata about the reading process
                note: id3Tags ? 
                    `ID3 tags successfully read from embedded metadata. Found ${Object.keys(id3Tags).length} fields.` :
                    'Could not read embedded ID3 tags. Showing fallback values.',
                
                // Raw ID3 data for debugging (first 10 fields)
                debug_raw_tags: id3Tags ? 
                    Object.fromEntries(Object.entries(id3Tags).slice(0, 10)) : 
                    null
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