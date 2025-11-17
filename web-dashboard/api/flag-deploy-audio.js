import fs from 'fs';
import path from 'path';

const QUEUE_DIR = path.join(process.cwd(), '.pitwall');
const QUEUE_FILE = path.join(QUEUE_DIR, 'deploy_queue.json');

function ensureQueueFile() {
  if (!fs.existsSync(QUEUE_DIR)) {
    fs.mkdirSync(QUEUE_DIR, { recursive: true });
  }
  if (!fs.existsSync(QUEUE_FILE)) {
    fs.writeFileSync(QUEUE_FILE, JSON.stringify({ entries: {} }, null, 2), 'utf8');
  }
}

function readQueue() {
  try {
    ensureQueueFile();
    const raw = fs.readFileSync(QUEUE_FILE, 'utf8');
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && parsed.entries && typeof parsed.entries === 'object') {
      return parsed.entries;
    }
  } catch (error) {
    console.warn('flag-deploy-audio: failed to read queue', error);
  }
  return {};
}

function writeQueue(entries) {
  ensureQueueFile();
  const payload = {
    updatedAt: new Date().toISOString(),
    entries
  };
  fs.writeFileSync(QUEUE_FILE, JSON.stringify(payload, null, 2), 'utf8');
}

function sanitizePath(value) {
  return (value || '')
    .replace(/\\/g, '/')
    .split('/')
    .filter((segment) => segment && segment !== '.' && segment !== '..')
    .join('/');
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  try {
    if (req.method === 'GET') {
      const entries = readQueue();
      res.status(200).json({ entries });
      return;
    }

    if (req.method !== 'POST') {
      res.status(405).json({ error: 'method_not_allowed' });
      return;
    }

    const { files, action } = req.body || {};
    if (!Array.isArray(files) || files.length === 0) {
      res.status(400).json({ error: 'no_files', message: 'No files provided for flagging.' });
      return;
    }

    const queue = readQueue();
    let flagged = 0;
    let cleared = 0;

    files.forEach((entry) => {
      const bucket = sanitizePath((entry && entry.bucket) || '');
      const objectPath = sanitizePath(entry && entry.path);
      if (!bucket || !objectPath) {
        return;
      }

      if (action === 'clear') {
        if (queue[objectPath]) {
          delete queue[objectPath];
          cleared += 1;
        }
        return;
      }

      queue[objectPath] = {
        bucket,
        path: objectPath,
        flaggedAt: new Date().toISOString()
      };
      flagged += 1;
    });

    writeQueue(queue);

    res.status(200).json({ flagged, cleared, entries: queue });
  } catch (error) {
    console.error('flag-deploy-audio error', error);
    res.status(500).json({ error: 'internal_error', message: error.message || 'Unexpected error' });
  }
}
