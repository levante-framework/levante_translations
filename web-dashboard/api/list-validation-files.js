import fs from 'fs';
import path from 'path';
import { Storage } from '@google-cloud/storage';

const DATA_BUCKET = process.env.DASHBOARD_DATA_BUCKET || 'levante-dashboard-dev';
const VALIDATION_PREFIX = process.env.VALIDATION_DATA_PREFIX || 'data/';

let storageClient = null;
function getStorage() {
	if (storageClient) return storageClient;
	try {
		const raw = process.env.GCP_SERVICE_ACCOUNT_JSON || process.env.GOOGLE_APPLICATION_CREDENTIALS_JSON;
		if (raw) {
			const creds = JSON.parse(raw);
			storageClient = new Storage({ credentials: creds, projectId: creds.project_id });
		} else {
			storageClient = new Storage();
		}
	} catch (error) {
		console.warn('list-validation-files: failed to init storage client', error.message);
		storageClient = null;
	}
	return storageClient;
}

function getPrefix() {
	return VALIDATION_PREFIX.endsWith('/') ? VALIDATION_PREFIX : `${VALIDATION_PREFIX}/`;
}

function sanitizeName(name) {
	return (name || '').toString().trim().replace(/\//g, '');
}

async function listFromGcs() {
	try {
		const storage = getStorage();
		if (!storage) return [];
		const bucket = storage.bucket(DATA_BUCKET);
		const prefix = getPrefix();
		const [files] = await bucket.getFiles({ prefix, autoPaginate: true });
		return files
			.filter(f => f.name && f.name.toLowerCase().endsWith('.json'))
			.map(f => f.name.slice(prefix.length))
			.filter(name => !!sanitizeName(name));
	} catch (error) {
		console.warn('list-validation-files: GCS listing failed', error.message);
		return [];
	}
}

function listFromLocal() {
	try {
		const dataDir = path.resolve(__dirname, '..', 'data');
		return fs.readdirSync(dataDir, { withFileTypes: true })
			.filter(d => d.isFile() && d.name.toLowerCase().endsWith('.json'))
			.map(d => d.name);
	} catch (error) {
		return [];
	}
}

export default async function handler(req, res) {
	res.setHeader('Access-Control-Allow-Origin', '*');
	res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
	res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
	if (req.method === 'OPTIONS') return res.status(200).end();
	if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });

	try {
		let files = await listFromGcs();
		if (!files || files.length === 0) {
			files = listFromLocal();
		}
		files = (files || []).map(sanitizeName).filter(Boolean).sort().reverse();

		return res.status(200).json({ success: true, files });
	} catch (error) {
		console.error('list-validation-files error:', error);
		return res.status(500).json({ success: false, error: 'Internal error', message: error.message });
	}
}
