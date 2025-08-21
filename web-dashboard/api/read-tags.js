import { Storage } from '@google-cloud/storage';
import NodeID3 from 'node-id3';

// Use the assets bucket and the audio/ folder for coverage and metadata reads
const ASSETS_BUCKET = process.env.ASSETS_DEV_BUCKET || 'levante-assets-dev';

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
        // URL format: https://storage.googleapis.com/levante-assets-dev/audio/es-AR/itemid.mp3
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
        const pathParts = filePath.split('/');
        const itemId = pathParts[pathParts.length - 1].replace('.mp3', '');
        // Expect audio/<lang>/<file>
        const languageCode = pathParts[0] === 'audio' ? pathParts[1] : pathParts[0];
        
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

// List language prefixes under audio/ in the assets bucket
async function listAudioLanguagesFromBucket(bucketName) {
    try {
        const storage = await initializeGCS();
        const bucket = storage.bucket(bucketName);
        // Only list languages under audio/ prefix (ignore root-level folders like corpus/, translations/)
        const [, , apiResp] = await bucket.getFiles({ delimiter: '/', prefix: 'audio/' });
        const prefixes = (apiResp && apiResp.prefixes) || [];
        const langs = prefixes
            .map(p => p.replace(/^audio\//, '').replace(/\/$/, ''))
            .filter(Boolean)
            .filter(code => code !== 'validations' && code !== '_gsdata_');
        return langs;
    } catch (err) {
        console.warn('⚠️ Failed to list languages in bucket:', err.message);
        return [];
    }
}

// List languages from the repository (audio_files/* on main)
async function listRepoLanguages() {
    try {
        const apiUrl = 'https://api.github.com/repos/levante-framework/levante_translations/contents/audio_files?ref=main';
        const resp = await fetch(apiUrl, { headers: { 'User-Agent': 'levante-audio-dashboard' } });
        if (!resp.ok) return [];
        const data = await resp.json();
        if (!Array.isArray(data)) return [];
        return data
            .filter(e => e && e.type === 'dir' && e.name)
            .map(e => e.name)
            .filter(Boolean);
    } catch (err) {
        console.warn('⚠️ Failed to list repo languages:', err.message);
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
        // Optional bucket override (default to assets-dev)
        const requestedBucket = (req.method === 'GET' ? req.query.bucket : req.body?.bucket) || '';
        const bucketOverride = typeof requestedBucket === 'string' && requestedBucket.trim().length > 0 ? requestedBucket.trim() : null;
        const source = ((req.method === 'GET' ? req.query.source : req.body?.source) || '').toString().trim().toLowerCase();

        // If listing was requested, return languages found in the dev assets bucket
        if (list === '1' || list === 1 || list === true) {
            if (source === 'repo') {
                const languages = await listRepoLanguages();
                res.status(200).json({ source: 'repo', languages });
                return;
            }
            const bucketName = bucketOverride || ASSETS_BUCKET;
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
        
        // Construct audio URL based on source
        let audioUrl = '';
        let targetBucket = bucketOverride || ASSETS_BUCKET;
        const encItemId = encodeURIComponent(itemId);
        if (source === 'repo') {
            audioUrl = `https://raw.githubusercontent.com/levante-framework/levante_translations/main/audio_files/${encodeURIComponent(langCode)}/${encItemId}.mp3`;
        } else {
            audioUrl = `https://storage.googleapis.com/${encodeURIComponent(targetBucket)}/audio/${encodeURIComponent(langCode)}/${encItemId}.mp3`;
        }
        
        console.log(`🔍 Reading metadata for: ${itemId} in ${langCode}`);
        
        let metadata = null;
        if (source === 'repo') {
            // For repo files, use HTTP range read and construct metadata manually
            const httpResult = await httpReadID3Tags(audioUrl);
            if (!httpResult.ok) {
                res.status(404).json({ error: 'File not accessible', details: `Unable to access: ${audioUrl}` });
                return;
            }
            const id3Tags = httpResult.tags;
            metadata = {
                fileName: `${langCode}/${itemId}.mp3`,
                size: undefined,
                contentType: 'audio/mpeg',
                created: undefined,
                updated: undefined,
                itemId,
                language: langCode,
                id3Tags: {
                    title: id3Tags?.title || itemId,
                    artist: id3Tags?.artist || 'Levante Project',
                    album: id3Tags?.album || langCode || 'Levante Audio',
                    genre: id3Tags?.genre || 'Speech Synthesis',
                    service: id3Tags?.userDefinedText?.find(t => t.description === 'service')?.value || id3Tags?.service || 'Not available',
                    voice: id3Tags?.userDefinedText?.find(t => t.description === 'voice')?.value || id3Tags?.voice || 'Not available',
                    lang_code: id3Tags?.userDefinedText?.find(t => t.description === 'lang_code')?.value || id3Tags?.lang_code || langCode,
                    text: id3Tags?.userDefinedText?.find(t => t.description === 'text')?.value || id3Tags?.text || 'Original text not available',
                    created: id3Tags?.userDefinedText?.find(t => t.description === 'created')?.value || id3Tags?.date || null,
                    copyright: id3Tags?.copyright || 'This file was created for the LEVANTE project and is released under a Creative Commons BY-NC-SA 4.0 license',
                    comment: id3Tags?.comment?.text || id3Tags?.comment || `Generated audio for item: ${itemId}`,
                    note: id3Tags ? `ID3 tags successfully read from embedded metadata. Found ${Object.keys(id3Tags).length} fields.` : 'Could not read embedded ID3 tags. Showing fallback values.',
                    debug_raw_tags: id3Tags ? Object.fromEntries(Object.entries(id3Tags).slice(0, 10)) : null
                }
            };
        } else {
            metadata = await readAudioMetadata(audioUrl);
            if (metadata && metadata.error) {
                // Backward-compat alternative path: top-level <lang>/<id>.mp3 (no audio/ prefix)
                const altUrl = `https://storage.googleapis.com/${encodeURIComponent(targetBucket)}/${encodeURIComponent(langCode)}/${encodeURIComponent(itemId)}.mp3`;
                const altMeta = await readAudioMetadata(altUrl);
                if (!altMeta.error) {
                    altMeta.note = 'Using legacy top-level path';
                    res.status(200).json(altMeta);
                    return;
                }
            }
        }
        
        if (metadata.error) {
            // In strict mode, do not attempt language fallbacks
            if (!strict) {
                // Try fallback for es-CO -> es
                if (langCode === 'es-CO') {
                    console.log('🔄 Trying es fallback for es-CO...');
                    const encId = encodeURIComponent(itemId);
                    const fallbackUrl = source === 'repo'
                        ? `https://raw.githubusercontent.com/levante-framework/levante_translations/main/audio_files/es/${encId}.mp3`
                        : `https://storage.googleapis.com/${encodeURIComponent(targetBucket)}/audio/es/${encId}.mp3`;
                    const fallbackMetadata = source === 'repo'
                        ? (await (async () => {
                            const r = await httpReadID3Tags(fallbackUrl);
                            if (!r.ok) return { error: 'File not accessible' };
                            const tags = r.tags;
                            return {
                                fileName: `es/${itemId}.mp3`,
                                size: undefined,
                                contentType: 'audio/mpeg',
                                created: undefined,
                                updated: undefined,
                                itemId,
                                language: 'es',
                                id3Tags: {
                                    title: tags?.title || itemId,
                                    artist: tags?.artist || 'Levante Project',
                                    album: tags?.album || 'es' || 'Levante Audio',
                                    genre: tags?.genre || 'Speech Synthesis',
                                    service: tags?.userDefinedText?.find(t => t.description === 'service')?.value || tags?.service || 'Not available',
                                    voice: tags?.userDefinedText?.find(t => t.description === 'voice')?.value || tags?.voice || 'Not available',
                                    lang_code: tags?.userDefinedText?.find(t => t.description === 'lang_code')?.value || tags?.lang_code || 'es',
                                    text: tags?.userDefinedText?.find(t => t.description === 'text')?.value || tags?.text || 'Original text not available',
                                    created: tags?.userDefinedText?.find(t => t.description === 'created')?.value || tags?.date || null,
                                    copyright: tags?.copyright || 'This file was created for the LEVANTE project and is released under a Creative Commons BY-NC-SA 4.0 license',
                                    comment: tags?.comment?.text || tags?.comment || `Generated audio for item: ${itemId}`,
                                    note: tags ? `ID3 tags successfully read from embedded metadata. Found ${Object.keys(tags).length} fields.` : 'Could not read embedded ID3 tags. Showing fallback values.',
                                    debug_raw_tags: tags ? Object.fromEntries(Object.entries(tags).slice(0, 10)) : null
                                }
                            };
                        })())
                        : await readAudioMetadata(fallbackUrl);
                    
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