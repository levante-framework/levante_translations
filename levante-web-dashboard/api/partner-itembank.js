import { Storage } from '@google-cloud/storage';

let storageClient = null;
function getStorage() {
    if (storageClient) return storageClient;
    const json = process.env.GOOGLE_APPLICATION_CREDENTIALS_JSON || process.env.GCP_SERVICE_ACCOUNT_JSON;
    if (json) {
        try {
            const credentials = JSON.parse(json);
            storageClient = new Storage({ credentials, projectId: credentials.project_id });
            return storageClient;
        } catch (e) {
            console.warn('GCS service-account JSON parse failed', e);
        }
    }
    try {
        // Vercel / GCP ADC or GOOGLE_APPLICATION_CREDENTIALS pointing at a key file (local)
        storageClient = new Storage();
        return storageClient;
    } catch (error) {
        console.warn('GCS init failed', error);
        return null;
    }
}

/**
 * Partner audio dashboard item list from GCS JSON (exported from itembank SQLite / XLIFF pipeline).
 * Upload: utilities/partner_itembank_export.py or itembank_by_task_regen_report.py (--gcs-sync).
 */
export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') return res.status(200).end();
    if (req.method !== 'GET') return res.status(405).json({ success: false, error: 'method_not_allowed' });

    const storage = getStorage();
    if (!storage) {
        return res.status(500).json({
            success: false,
            error: 'gcs_unavailable',
            message:
                'Could not initialize Google Cloud Storage. Set GOOGLE_APPLICATION_CREDENTIALS_JSON (or GCP_SERVICE_ACCOUNT_JSON) on Vercel, or use default credentials locally.',
        });
    }

    const bucketName =
        (req.query.bucket && String(req.query.bucket)) || process.env.ASSETS_DRAFT_BUCKET || 'levante-assets-draft';
    const objectPath =
        (req.query.object && String(req.query.object)) ||
        process.env.PARTNER_ITEMBANK_OBJECT ||
        'translations/partner-itembank-audio-dashboard.json';

    try {
        const bucket = storage.bucket(bucketName);
        const blob = bucket.file(objectPath);
        const [exists] = await blob.exists();
        if (!exists) {
            return res.status(404).json({
                success: false,
                error: 'not_found',
                message: `Partner itembank JSON not found: gs://${bucketName}/${objectPath}`,
            });
        }
        const [buf] = await blob.download();
        const doc = JSON.parse(buf.toString('utf8'));
        const items = Array.isArray(doc.items) ? doc.items : [];
        return res.status(200).json({
            success: true,
            bucket: bucketName,
            object: objectPath,
            source: doc.source || 'itembank_sqlite_xliff',
            generated_at: doc.generated_at || null,
            version: doc.version || 1,
            item_count: doc.item_count != null ? doc.item_count : items.length,
            items,
        });
    } catch (err) {
        console.error('partner-itembank error', err);
        return res.status(500).json({
            success: false,
            error: 'read_failed',
            message: err && err.message ? String(err.message) : 'Failed to read partner itembank JSON',
        });
    }
}
