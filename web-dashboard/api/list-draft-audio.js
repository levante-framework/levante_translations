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

			return {
				name,
				language,
				itemId: baseItemId,
				version,
				path: name,
				size: Number(metadata.size || 0),
				updated: metadata.updated || metadata.timeCreated || null,
				generation: metadata.generation || null,
				contentType: metadata.contentType || null
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
