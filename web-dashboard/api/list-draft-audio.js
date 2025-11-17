import { Storage } from '@google-cloud/storage';

let storageClient = null;
function getStorage() {
    if (storageClient) return storageClient;
    try {
        const json = process.env.GOOGLE_APPLICATION_CREDENTIALS_JSON || process.env.GCP_SERVICE_ACCOUNT_JSON;
        if (!json) throw new Error('Missing GOOGLE_APPLICATION_CREDENTIALS_JSON');
        const credentials = JSON.parse(json);
        storageClient = new Storage({ credentials, projectId: credentials.project_id });
        return storageClient;
    } catch (error) {
        console.warn('GCS init failed', error);
        return null;
    }
}

function stripExtension(fileName = '') {
    return fileName.replace(/\.[^/.]+$/u, '');
}

function removeVersionSuffix(base = '') {
    return base.replace(/([_-]v?\d{3,})$/iu, '');
}

function buildApprovalKey(language = '', baseId = '') {
    if (!language || !baseId) return '';
    return `${language}/${baseId}`.toLowerCase();
}

function parseTimestamp(value) {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') return res.status(200).end();
    if (req.method !== 'GET') return res.status(405).json({ success: false, error: 'method_not_allowed' });

    try {
        const storage = getStorage();
        if (!storage) {
            return res.status(500).json({ success: false, error: 'gcs_unavailable', message: 'Could not initialize Google Cloud Storage client.' });
        }

        const bucketName = (req.query.bucket && String(req.query.bucket)) || process.env.ASSETS_DRAFT_BUCKET || 'levante-assets-draft';
        const prefix = (req.query.prefix && String(req.query.prefix)) || 'audio/';
        const limitRaw = req.query.limit ? Number(req.query.limit) : 500;
        const maxResults = Number.isFinite(limitRaw) ? Math.min(Math.max(limitRaw, 1), 1000) : 500;

        const bucket = storage.bucket(bucketName);
        const [files] = await bucket.getFiles({ prefix, maxResults });

        const [deployFiles] = await bucket.getFiles({ prefix: 'deploy/', maxResults: 2000 });
        const deployInfo = new Map();
        deployFiles.forEach((file) => {
            const name = file.name || '';
            const segments = name.split('/');
            if (segments.length < 3) return;
            const language = segments[1] || '';
            const fileBase = removeVersionSuffix(stripExtension(segments[segments.length - 1] || ''));
            const key = buildApprovalKey(language, fileBase);
            if (!key) return;

            const metadata = file.metadata || {};
            const updatedRaw = metadata.updated || metadata.timeCreated || null;
            const updatedDate = parseTimestamp(updatedRaw);
            const current = deployInfo.get(key);

            if (!current || (updatedDate && (!current.updatedDate || updatedDate > current.updatedDate))) {
                deployInfo.set(key, {
                    path: name,
                    bucket: bucketName,
                    updated: updatedRaw,
                    updatedDate,
                    generation: metadata.generation || null,
                    size: Number(metadata.size || 0)
                });
            }
        });

        const items = files
            .filter(file => file.name && file.name.toLowerCase().endsWith('.mp3'))
            .map(file => {
                const metadata = file.metadata || {};
                const name = file.name;
                const parts = name ? name.split('/') : [];
                const language = parts.length >= 2 ? parts[1] : '';
                const filename = parts.length ? parts[parts.length - 1] : name;
                const itemIdRaw = filename ? filename.replace(/\.mp3$/i, '') : '';
                const versionMatch = itemIdRaw.match(/_v(\d{3})$/);
                const version = versionMatch ? parseInt(versionMatch[1], 10) : null;
                const baseItemId = versionMatch ? itemIdRaw.replace(/_v\d{3}$/, '') : itemIdRaw;
                const approvalKey = buildApprovalKey(language, baseItemId);

                const draftUpdated = metadata.updated || metadata.timeCreated || null;
                const draftUpdatedDate = parseTimestamp(draftUpdated);
                const deployEntry = approvalKey ? deployInfo.get(approvalKey) : null;

                let approvedBySite = false;
                let approvalStatus = 'not_approved';

                if (deployEntry) {
                    const deployUpdatedDate = deployEntry.updatedDate;
                    if (!draftUpdatedDate || !deployUpdatedDate) {
                        approvedBySite = true;
                        approvalStatus = 'approved';
                    } else if (deployUpdatedDate >= draftUpdatedDate) {
                        approvedBySite = true;
                        approvalStatus = 'approved';
                    } else {
                        approvedBySite = false;
                        approvalStatus = 'stale';
                    }
                }

                return {
                    name,
                    language,
                    itemId: baseItemId,
                    version,
                    path: name,
                    size: Number(metadata.size || 0),
                    updated: metadata.updated || metadata.timeCreated || null,
                    generation: metadata.generation || null,
                    contentType: metadata.contentType || null,
                    approvedBySite,
                    siteApproval: {
                        status: approvalStatus,
                        deployPath: deployEntry ? deployEntry.path : null,
                        deployUpdated: deployEntry ? deployEntry.updated : null,
                        deployGeneration: deployEntry ? deployEntry.generation : null,
                        draftUpdated
                    }
                };
            });

        return res.status(200).json({
            success: true,
            bucket: bucketName,
            prefix,
            count: items.length,
            items
        });
    } catch (error) {
        console.error('Error listing draft audio files', error);
        return res.status(500).json({ success: false, error: 'internal_error', message: error.message });
    }
}
