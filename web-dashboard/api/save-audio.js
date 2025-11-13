import { Storage } from '@google-cloud/storage';
import NodeID3 from 'node-id3';

let storageClient = null;
function getStorage() {
	if (storageClient) return storageClient;
	try {
		const json = process.env.GOOGLE_APPLICATION_CREDENTIALS_JSON || process.env.GCP_SERVICE_ACCOUNT_JSON;
		if (!json) throw new Error('Missing GOOGLE_APPLICATION_CREDENTIALS_JSON');
		const credentials = JSON.parse(json);
		storageClient = new Storage({ credentials, projectId: credentials.project_id });
		return storageClient;
	} catch (e) {
		console.warn('GCS init failed', e);
		return null;
	}
}

export default async function handler(req, res) {
	res.setHeader('Access-Control-Allow-Origin', '*');
	res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
	res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
	if (req.method === 'OPTIONS') return res.status(200).end();
	if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

	try {
		const { audioBase64, langCode, itemId, bucket, tags } = req.body || {};
		if (!audioBase64 || typeof audioBase64 !== 'string') {
			return res.status(400).json({ success: false, error: 'bad_request', message: 'audioBase64 missing or invalid' });
		}
		if (!langCode || !itemId) {
			return res.status(400).json({ success: false, error: 'bad_request', message: 'langCode and itemId are required' });
		}

		const b64 = audioBase64.replace(/^data:audio\/\w+;base64,/, '');
		let audioBuffer;
		try { audioBuffer = Buffer.from(b64, 'base64'); }
		catch(e) { return res.status(400).json({ success:false, error:'bad_audio', message:'Could not decode audio base64' }); }

		const userDefinedText = [];
		const pushCustomTag = (description, value) => {
			if (value === undefined || value === null) return;
			const trimmed = `${value}`.trim();
			if (!trimmed) return;
			userDefinedText.push({ description, value: trimmed });
		};

		const serviceValue = tags?.service || 'ElevenLabs';
		const commentValue = tags?.comment || `Generated audio for ${itemId}`;

		pushCustomTag('service', serviceValue);
		pushCustomTag('voice', tags?.voice);
		pushCustomTag('lang_code', tags?.lang_code || langCode);
		pushCustomTag('text', tags?.text);
		pushCustomTag('created', tags?.created || new Date().toISOString());

		const id3 = {
			title: tags?.title || itemId,
			artist: tags?.artist || 'Levante Project',
			album: tags?.album || langCode,
			genre: tags?.genre || 'Speech Synthesis'
		};
		if (commentValue) {
			id3.comment = { language: 'eng', text: commentValue };
		}
		if (tags?.copyright) {
			id3.copyright = tags.copyright;
		}
		if (userDefinedText.length) {
			id3.userDefinedText = userDefinedText;
		}

		try { audioBuffer = NodeID3.write(id3, audioBuffer); }
		catch (e) { console.warn('ID3 write failed', e.message); }

		const storage = getStorage();
		if (!storage) {
			return res.status(500).json({ success: false, error: 'gcs_unavailable', message: 'Could not initialize GCS. Check GOOGLE_APPLICATION_CREDENTIALS_JSON.' });
		}
		const bucketName = bucket || process.env.ASSETS_DEV_BUCKET || 'levante-assets-dev';
		try {
			const gcsBucket = storage.bucket(bucketName);
			const file = gcsBucket.file(`audio/${langCode}/${itemId}.mp3`);
			await file.save(audioBuffer, { contentType: 'audio/mpeg', resumable: false, public: false });
			return res.status(200).json({ success: true, bucket: bucketName, path: `audio/${langCode}/${itemId}.mp3` });
		} catch (e) {
			return res.status(500).json({ success:false, error:'upload_failed', message:e.message, bucket: bucketName, path:`audio/${langCode}/${itemId}.mp3` });
		}
	} catch (error) {
		return res.status(500).json({ success: false, error: 'internal_error', message: error.message });
	}
}
