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

// Fallback: read ID3 via public HTTP Range request without GCS SDK/auth
async function httpReadID3Tags(audioUrl) {
    try {
        const resp = await fetch(audioUrl, { headers: { Range: 'bytes=0-65535' } });
        if (!resp.ok) {
            return { ok: false, tags: null, status: resp.status };
        }
        const arrayBuf = await resp.arrayBuffer();
        const buf = Buffer.from(arrayBuf);
        const tags = NodeID3.read(buf);
        return { ok: true, tags: tags || null, status: resp.status };
    } catch (err) {
        console.warn('⚠️ HTTP ID3 fallback failed:', err.message);
        return { ok: false, tags: null, status: 0 };
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
        
        let metadata = null;
        let id3Tags = null;
        let fileExists = false;

        // Try GCS SDK first (if credentials available or default works)
        try {
            const storage = await initializeGCS();
            const bucket = storage.bucket(bucketName);
            const file = bucket.file(filePath);
            const [exists] = await file.exists();
            if (exists) {
                fileExists = true;
                [metadata] = await file.getMetadata();
                id3Tags = await downloadAndReadID3Tags(bucket, file);
            } else {
                console.warn(`⚠️ GCS reports missing file: ${filePath}`);
            }
        } catch (gcsErr) {
            console.warn('⚠️ GCS access failed, will try HTTP fallback:', gcsErr.message);
        }

        // If GCS path failed or tags not found, try HTTP fallback
        if (!id3Tags) {
            const httpResult = await httpReadID3Tags(audioUrl);
            if (httpResult.ok) {
                fileExists = true;
                id3Tags = httpResult.tags;
            }
        }

        // If neither GCS nor HTTP located the file, return error
        if (!fileExists) {
            return { error: 'File not accessible', details: `Unable to access: ${filePath}` };
        }

        if (!metadata) {
            // Minimal metadata from path when GCS metadata not available
            metadata = { name: filePath, size: undefined, contentType: 'audio/mpeg', timeCreated: undefined, updated: undefined };
        }
        
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
                        id3Tags?.date || metadata.timeCreated || null,
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

// List top-level language prefixes present in the audio bucket
async function listAudioLanguagesFromBucket(bucketName) {
    try {
        const storage = await initializeGCS();
        const bucket = storage.bucket(bucketName);
        // Use delimiter to list pseudo-directories (language codes)
        const [files, , apiResponse] = await bucket.getFiles({ delimiter: '/', prefix: '' });
        const prefixes = (apiResponse && apiResponse.prefixes) || [];
        const langs = prefixes.map(p => p.replace(/\/$/, '')).filter(Boolean);
        return langs;
    } catch (err) {
        console.warn('⚠️ Failed to list languages in bucket:', err.message);
        return [];
    }
}

export default async function handler(req, res) {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    res.setHeader('Cache-Control', 'no-cache');
    
    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }
    
    if (req.method !== 'GET' && req.method !== 'POST') {
        res.status(405).json({ error: 'Method not allowed' });
        return;
    }
    
    try {
        const { itemId, langCode, list } = req.method === 'GET' ? req.query : req.body;

        // If listing was requested, return languages found in the dev bucket
        if (list === '1' || list === 1 || list === true) {
            const bucketName = 'levante-audio-dev';
            const languages = await listAudioLanguagesFromBucket(bucketName);
            res.status(200).json({ bucket: bucketName, languages });
            return;
        }
        const rawStrict = (req.method === 'GET' ? req.query.strict : req.body?.strict);
        const strict = typeof rawStrict === 'string'
            ? ['1','true','yes','on'].includes(rawStrict.toLowerCase())
            : Boolean(rawStrict);
        
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
            // In strict mode, do not attempt language fallbacks
            if (!strict) {
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