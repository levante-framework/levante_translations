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
		console.warn('get-validation-file: failed to init storage client', error.message);
		storageClient = null;
	}
	return storageClient;
}

function getPrefix() {
	return VALIDATION_PREFIX.endsWith('/') ? VALIDATION_PREFIX : `${VALIDATION_PREFIX}/`;
}

function sanitizeName(name = '') {
	const cleaned = name.toString();
	if (cleaned.includes('..') || cleaned.includes('/') || cleaned.includes('\\')) {
		return '';
	}
	return cleaned.trim();
}

async function fetchFromGcs(name) {
	try {
		const storage = getStorage();
		if (!storage) return null;
		const bucket = storage.bucket(DATA_BUCKET);
		const prefix = getPrefix();
		const file = bucket.file(`${prefix}${name}`);
		const [exists] = await file.exists();
		if (!exists) return null;
		const [contents] = await file.download();
		return contents;
	} catch (error) {
		console.warn('get-validation-file: GCS download failed', error.message);
		return null;
	}
}

function fetchFromLocal(name) {
	const dataDir = path.resolve(__dirname, '..', 'data');
	const filePath = path.join(dataDir, name);
	if (!fs.existsSync(filePath)) return null;
	return fs.readFileSync(filePath);
}

export default async function handler(req, res) {
	res.setHeader('Access-Control-Allow-Origin', '*');
	res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
	res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
	if (req.method === 'OPTIONS') return res.status(200).end();
	if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });

	try {
		const name = sanitizeName(req.query.name || '');
		if (!name || !name.endsWith('.json')) {
			return res.status(400).json({ success: false, error: 'invalid_name' });
		}
		let buffer = await fetchFromGcs(name);
		if (!buffer) {
			buffer = fetchFromLocal(name);
		}
		if (!buffer) {
			return res.status(404).json({ success: false, error: 'not_found' });
		}
		res.setHeader('Content-Type', 'application/json');
		return res.status(200).send(buffer);
	} catch (error) {
		console.error('get-validation-file error:', error);
		return res.status(500).json({ success: false, error: 'Internal error', message: error.message });
	}
}
