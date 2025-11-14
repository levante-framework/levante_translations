import { Storage } from '@google-cloud/storage';
import fetch from 'node-fetch';

const USER_AGENT = 'levante-dashboard';

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

function getGithubConfig() {
    const repo = process.env.GITHUB_AUDIO_REPO || process.env.AUDIO_REPO || process.env.LEVANTE_AUDIO_REPO || process.env.GITHUB_REPO || '';
    const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN || process.env.LEVANTE_GITHUB_TOKEN || '';
    const branch = process.env.GITHUB_AUDIO_BRANCH || process.env.AUDIO_REPO_BRANCH || process.env.GITHUB_BRANCH || 'main';
    const committerName = process.env.GITHUB_COMMITTER_NAME || process.env.GIT_COMMITTER_NAME || 'Levante Dashboard';
    const committerEmail = process.env.GITHUB_COMMITTER_EMAIL || process.env.GIT_COMMITTER_EMAIL || 'dashboard@levante.local';
    return { repo, token, branch, committerName, committerEmail };
}

function sanitizePath(value) {
    if (!value) return '';
    return String(value)
        .replace(/\\/g, '/')
        .replace(/^\/+/, '')
        .split('/')
        .filter(segment => segment && segment !== '.' && segment !== '..')
        .join('/');
}

function ensureAudioRepoPath(path) {
    const sanitized = sanitizePath(path);
    if (!sanitized) return '';
    if (sanitized.startsWith('audio/')) return sanitized;
    return `audio/${sanitized}`;
}

function encodeGitRef(ref) {
    return encodeURIComponent(ref);
}

async function githubRequest(method, path, body, token) {
    const headers = { 'Accept': 'application/vnd.github+json', 'User-Agent': USER_AGENT };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const options = { method, headers };
    if (body !== undefined) {
        headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(body);
    }
    const response = await fetch(`https://api.github.com${path}`, options);
    const text = await response.text();
    if (!response.ok) {
        const err = new Error(`GitHub API ${method} ${path} failed: ${response.status} ${response.statusText} - ${text}`);
        err.status = response.status;
        throw err;
    }
    if (!text) return null;
    try {
        return JSON.parse(text);
    } catch (_) {
        return text;
    }
}

async function fetchGcsFile(storage, bucketName, filePath) {
    const bucket = storage.bucket(bucketName);
    const file = bucket.file(filePath);
    const [exists] = await file.exists();
    if (!exists) {
        throw new Error(`GCS object not found: gs://${bucketName}/${filePath}`);
    }
    const [data] = await file.download();
    return data;
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') return res.status(200).end();
    if (req.method !== 'POST') return res.status(405).json({ success: false, error: 'method_not_allowed' });

    try {
        const storage = getStorage();
        if (!storage) {
            return res.status(500).json({ success: false, error: 'gcs_unavailable', message: 'Could not initialize Google Cloud Storage client.' });
        }

        const githubConfig = getGithubConfig();
        if (!githubConfig.repo || !githubConfig.token) {
            return res.status(500).json({
                success: false,
                error: 'github_config_missing',
                message: 'GitHub repository or token is not configured. Set GITHUB_AUDIO_REPO and GITHUB_TOKEN in the environment.'
            });
        }

        const body = req.body || {};
        const files = Array.isArray(body.files) ? body.files : [];
        if (!files.length) {
            return res.status(400).json({ success: false, error: 'no_files', message: 'No files provided for deployment.' });
        }

        const bucketOverride = body.bucket || '';
        const prepared = [];
        for (const entry of files) {
            const bucketName = sanitizePath(entry.bucket || bucketOverride || 'levante-assets-draft');
            const gcsPath = sanitizePath(entry.path);
            if (!gcsPath) {
                throw new Error('Invalid file path provided.');
            }
            const repoPath = ensureAudioRepoPath(gcsPath);
            if (!repoPath.startsWith('audio/')) {
                throw new Error(`Refusing to deploy outside audio directory: ${repoPath}`);
            }
            const buffer = await fetchGcsFile(storage, bucketName, gcsPath);
            prepared.push({
                bucket: bucketName,
                gcsPath,
                repoPath,
                buffer,
                size: buffer.length,
                language: entry.language || '',
                itemId: entry.itemId || '',
                version: entry.version || ''
            });
        }

        if (!prepared.length) {
            return res.status(400).json({ success: false, error: 'nothing_prepared', message: 'No files could be read from draft storage.' });
        }

        const { repo, token, branch, committerName, committerEmail } = githubConfig;
        const branchRef = await githubRequest('GET', `/repos/${repo}/git/ref/heads/${encodeGitRef(branch)}`, undefined, token);
        const headCommitSha = branchRef && branchRef.object && branchRef.object.sha;
        if (!headCommitSha) {
            throw new Error(`Unable to resolve HEAD commit for ${repo}#${branch}`);
        }
        const headCommit = await githubRequest('GET', `/repos/${repo}/git/commits/${headCommitSha}`, undefined, token);
        const baseTreeSha = headCommit && headCommit.tree && headCommit.tree.sha;
        if (!baseTreeSha) {
            throw new Error('Could not determine base tree for commit.');
        }

        const treeEntries = [];
        for (const file of prepared) {
            const blob = await githubRequest('POST', `/repos/${repo}/git/blobs`, {
                content: file.buffer.toString('base64'),
                encoding: 'base64'
            }, token);
            treeEntries.push({
                path: file.repoPath,
                mode: '100644',
                type: 'blob',
                sha: blob.sha
            });
        }

        const tree = await githubRequest('POST', `/repos/${repo}/git/trees`, {
            base_tree: baseTreeSha,
            tree: treeEntries
        }, token);

        const defaultMessage = prepared.length === 1
            ? `Deploy audio ${prepared[0].repoPath}`
            : `Deploy ${prepared.length} audio files from dashboard`;
        const commitMessage = (body.commitMessage && String(body.commitMessage).trim()) || defaultMessage;
        const commitPayload = {
            message: commitMessage,
            tree: tree && tree.sha,
            parents: [headCommitSha]
        };
        if (committerName && committerEmail) {
            commitPayload.author = { name: committerName, email: committerEmail };
            commitPayload.committer = { name: committerName, email: committerEmail };
        }

        const commit = await githubRequest('POST', `/repos/${repo}/git/commits`, commitPayload, token);
        await githubRequest('PATCH', `/repos/${repo}/git/refs/heads/${encodeGitRef(branch)}`, {
            sha: commit.sha
        }, token);

        const responsePayload = {
            success: true,
            repository: repo,
            branch,
            commitSha: commit.sha,
            commitUrl: `https://github.com/${repo}/commit/${commit.sha}`,
            files: prepared.map(file => ({
                repoPath: file.repoPath,
                bucket: file.bucket,
                gcsPath: file.gcsPath,
                size: file.size,
                language: file.language,
                itemId: file.itemId,
                version: file.version
            }))
        };

        return res.status(200).json(responsePayload);
    } catch (error) {
        console.error('Error deploying draft audio to GitHub:', error);
        const status = error.status && Number.isInteger(error.status) ? error.status : 500;
        return res.status(status).json({
            success: false,
            error: 'deployment_failed',
            message: error.message || 'Unknown deployment failure'
        });
    }
}
