import { Storage } from '@google-cloud/storage';

const DEFAULT_OWNER = process.env.TRANSLATIONS_REPO_OWNER || 'levante-framework';
const DEFAULT_REPO = process.env.TRANSLATIONS_REPO_NAME || 'levante_translations';
const DEFAULT_BRANCH = process.env.TRANSLATIONS_HISTORY_BRANCH || 'l10n_pending';
const DEFAULT_PATH = process.env.TRANSLATIONS_HISTORY_PATH || 'translations,translation_text';
const DEV_BUCKET = process.env.ASSETS_DEV_BUCKET || 'levante-assets-dev';
const PROD_BUCKET = process.env.ASSETS_PROD_BUCKET || 'levante-assets-prod';
const TRANSLATION_OBJECT_PATH = process.env.TRANSLATION_OBJECT_PATH || 'translations/item-bank-translations.csv';
const SURVEY_OBJECT_PATH = process.env.SURVEY_OBJECT_PATH || 'surveys/latest-surveys-export.zip';
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || process.env.GITHUB_PAT || null;
const GITHUB_USER_AGENT = 'levante-dashboard-asset-history';
const OPENAI_API_KEY = process.env.OPENAI_API_KEY || null;
const OPENAI_MODEL = process.env.OPENAI_MODEL || 'gpt-4o-mini';

const LOCALE_LABELS = {
    'de': 'German',
    'de-de': 'German (Germany)',
    'de-ch': 'German (Switzerland)',
    'en': 'English',
    'en-us': 'English (US)',
    'en-gb': 'English (UK)',
    'es': 'Spanish',
    'es-co': 'Spanish (Colombia)',
    'es-ar': 'Spanish (Argentina)',
    'fr': 'French',
    'fr-ca': 'French (Canada)',
    'nl': 'Dutch',
};

let storageClient = null;
const csvHeaderCache = new Map();

function parseCsvLine(line) {
    const row = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
        const char = line[i];
        if (char === '"') {
            if (inQuotes && line[i + 1] === '"') {
                current += '"';
                i++;
            } else {
                inQuotes = !inQuotes;
            }
            continue;
        }
        if (char === ',' && !inQuotes) {
            row.push(current);
            current = '';
            continue;
        }
        current += char;
    }
    row.push(current);
    return row;
}

function stripHtml(value) {
    if (!value) return '';
    return value.replace(/<[^>]*>/g, '').replace(/\r/g, '').trim();
}

function truncateValue(value, length = 80) {
    const text = stripHtml(value);
    if (text.length <= length) return text;
    return text.slice(0, length - 1).trimEnd() + '…';
}

async function fetchCsvHeader(file) {
    if (!file?.raw_url) return null;
    if (csvHeaderCache.has(file.raw_url)) {
        return csvHeaderCache.get(file.raw_url);
    }
    try {
        let response = await fetch(file.raw_url, {
            headers: { Range: 'bytes=0-4095' },
        });
        if (response.status === 416 || response.status === 200) {
            // OK
        } else if (response.status === 206) {
            // partial content - ok
        } else if (!response.ok) {
            response = await fetch(file.raw_url);
        }
        const text = await response.text();
        const headerLine = text.split(/\r?\n/)[0] || '';
        const header = parseCsvLine(headerLine).map((cell) => cell.trim());
        csvHeaderCache.set(file.raw_url, header);
        return header;
    } catch (error) {
        console.warn('asset-history: failed to fetch CSV header', error.message);
        return null;
    }
}

function collectRowChangesFromPatch(patchText) {
    if (!patchText) return [];
    const changes = new Map();
    const lines = patchText.split(/\r?\n/);
    for (const line of lines) {
        if (!line) continue;
        if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('@@')) continue;
        if (!(line.startsWith('+') || line.startsWith('-'))) continue;
        const marker = line[0];
        const row = parseCsvLine(line.slice(1));
        if (!row.length) continue;
        const idCandidate = (row[0] || '').trim();
        const secondCandidate = (row[1] || '').trim();
        const key = idCandidate || secondCandidate || `row-${changes.size}`;
        if (!changes.has(key)) {
            changes.set(key, { key, before: null, after: null });
        }
        const entry = changes.get(key);
        if (marker === '+') {
            entry.after = row;
        } else if (marker === '-') {
            entry.before = row;
        }
    }
    return Array.from(changes.values());
}

function buildTranslationSummaryForChanges(changes, header) {
    if (!changes.length || !header) return [];
    const lowerHeader = header.map((h) => (h || '').toLowerCase());
    let itemIdIndex = lowerHeader.indexOf('item_id');
    if (itemIdIndex === -1) itemIdIndex = 0;
    let labelIndex = lowerHeader.indexOf('labels');
    if (labelIndex === -1 || labelIndex === itemIdIndex) labelIndex = itemIdIndex + 1;
    const languageColumns = header
        .map((name, index) => ({ name, index }))
        .filter((col) => col.index > labelIndex && col.name);

    const summaries = [];
    changes.forEach((change) => {
        const before = change.before;
        const after = change.after;
        const itemId = (after && after[itemIdIndex]) || (before && before[itemIdIndex]) || change.key || 'item';
        const label = (after && after[labelIndex]) || (before && before[labelIndex]) || '';
        const variations = [];
        languageColumns.forEach((col) => {
            const code = col.name.trim().toLowerCase();
            const labelName = LOCALE_LABELS[code] || LOCALE_LABELS[code.split('-')[0]] || code.toUpperCase();
            const beforeVal = before ? before[col.index] : '';
            const afterVal = after ? after[col.index] : '';
            if (before && after) {
                if (beforeVal !== afterVal) {
                    variations.push({
                        type: 'update',
                        label: labelName,
                        before: beforeVal,
                        after: afterVal,
                    });
                }
            } else if (!before && after && afterVal) {
                variations.push({
                    type: 'addition',
                    label: labelName,
                    after: afterVal,
                });
            } else if (before && !after && beforeVal) {
                variations.push({
                    type: 'removal',
                    label: labelName,
                    before: beforeVal,
                });
            }
        });

        if (!variations.length) return;
        const labelSnippet = label ? ` (${truncateValue(label, 40)})` : '';
        const baseId = `${itemId}${labelSnippet}`;

        const updates = variations.filter((v) => v.type === 'update');
        const additions = variations.filter((v) => v.type === 'addition');
        const removals = variations.filter((v) => v.type === 'removal');

        if (updates.length) {
            const entries = updates.slice(0, 2).map((v) => {
                return `${v.label}: "${truncateValue(v.after)}"` + (v.before ? ` (was "${truncateValue(v.before)}")` : '');
            });
            const more = updates.length > 2 ? ', …' : '';
            summaries.push(`Updated ${baseId} — ${entries.join('; ')}${more}`);
        }
        if (additions.length) {
            const entries = additions.slice(0, 2).map((v) => `${v.label}: "${truncateValue(v.after)}"`);
            const more = additions.length > 2 ? ', …' : '';
            summaries.push(`Added ${baseId} — ${entries.join('; ')}${more}`);
        }
        if (removals.length) {
            const entries = removals.slice(0, 2).map((v) => `${v.label}`);
            const more = removals.length > 2 ? ', …' : '';
            summaries.push(`Removed ${baseId} — ${entries.join(', ')}${more}`);
        }
    });
    return summaries;
}

async function summarizeTranslationCommit(detail) {
    const summaries = [];
    if (!detail?.files) return null;
    for (const file of detail.files) {
        if (!file?.filename) continue;
        if (/\.xliff$/i.test(file.filename)) {
            const lines = (file.patch || '').split(/\r?\n/);
            const targetSegments = [];
            const sourceSegments = [];
            let capturing = null; // 'target' | 'source'
            let currentLang = null;
            let buffer = [];
            const commitLocaleMatch = file.filename.match(/([a-z]{2}-[A-Za-z]{2})/i);
            const defaultLocale = commitLocaleMatch ? commitLocaleMatch[1].toLowerCase() : null;

            const flush = () => {
                if (!capturing) return;
                const text = buffer.join(' ').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
                if (text) {
                    if (capturing === 'target') {
                        const localeLabel = currentLang
                            ? (LOCALE_LABELS[currentLang] || LOCALE_LABELS[currentLang.split('-')[0]] || currentLang.toUpperCase())
                            : (defaultLocale ? (LOCALE_LABELS[defaultLocale] || LOCALE_LABELS[defaultLocale.split('-')[0]] || defaultLocale.toUpperCase()) : 'Translations');
                        targetSegments.push(`${localeLabel}: “${truncateValue(text, 140)}”`);
                    } else if (capturing === 'source') {
                        sourceSegments.push(`Source: “${truncateValue(text, 140)}”`);
                    }
                }
                capturing = null;
                currentLang = null;
                buffer = [];
            };

            for (const rawLine of lines) {
                if (rawLine.startsWith('+++') || rawLine.startsWith('---')) continue;
                const isAdd = rawLine.startsWith('+');
                const isDel = rawLine.startsWith('-');
                if (!isAdd && !isDel) {
                    if (capturing && /<\/target>/i.test(rawLine) || /<\/source>/i.test(rawLine)) {
                        flush();
                    }
                    continue;
                }

                const line = rawLine.slice(1);

                const targetMatch = line.match(/<target[^>]*xml:lang\s*=\s*"?([a-zA-Z-]+)"?[^>]*>/i);
                if (targetMatch && isAdd) {
                    flush();
                    capturing = 'target';
                    currentLang = targetMatch[1].toLowerCase();
                } else if (/^\s*<target/i.test(line) && isAdd) {
                    flush();
                    capturing = 'target';
                    currentLang = defaultLocale;
                }

                const sourceMatch = line.match(/<source[^>]*>/i);
                if (sourceMatch && isAdd) {
                    flush();
                    capturing = 'source';
                    currentLang = null;
                }

                if (capturing === 'target' || capturing === 'source') {
                    const closingTarget = /<\/target>/i.test(line);
                    const closingSource = /<\/source>/i.test(line);
                    const content = line.replace(/<[^>]+>/g, '').trim();
                    if (content) buffer.push(content);
                    if ((capturing === 'target' && closingTarget) || (capturing === 'source' && closingSource)) {
                        flush();
                    }
                }
            }

            flush();

            if (targetSegments.length) {
                summaries.push(targetSegments.slice(0, 3).join(' • ') + (targetSegments.length > 3 ? ' • …' : ''));
            } else if (sourceSegments.length) {
                summaries.push(sourceSegments.slice(0, 3).join(' • ') + (sourceSegments.length > 3 ? ' • …' : ''));
            }
            continue;
        }
        if (!/item-bank-translations/.test(file.filename)) continue;
        const header = await fetchCsvHeader(file);
        if (!header) continue;
        const changes = collectRowChangesFromPatch(file.patch);
        if (!changes.length) continue;
        const fileSummaries = buildTranslationSummaryForChanges(changes, header);
        summaries.push(...fileSummaries);
    }
    if (!summaries.length) return null;
    const unique = Array.from(new Set(summaries));
    const limited = unique.slice(0, 3);
    const more = unique.length > limited.length ? ' • …' : '';
    return `${limited.join(' • ')}${more}`;
}

function normalizeDate(value, fallback = null) {
    if (!value) return fallback;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return fallback;
    return date;
}

async function getStorage() {
    if (storageClient) return storageClient;
    const credentials = process.env.GOOGLE_APPLICATION_CREDENTIALS_JSON;
    if (credentials) {
        try {
            const parsed = JSON.parse(credentials);
            storageClient = new Storage({
                credentials: parsed,
                projectId: parsed.project_id,
            });
        } catch (err) {
            console.warn('Failed to parse GOOGLE_APPLICATION_CREDENTIALS_JSON, falling back to default auth:', err.message);
            storageClient = new Storage();
        }
    } else {
        storageClient = new Storage();
    }
    return storageClient;
}

function buildGithubHeaders() {
    const headers = {
        Accept: 'application/vnd.github+json',
        'User-Agent': GITHUB_USER_AGENT,
    };
    if (GITHUB_TOKEN) {
        headers.Authorization = `Bearer ${GITHUB_TOKEN}`;
    }
    return headers;
}

async function fetchCommits({ owner, repo, branch, path, start, end, limit, signal }) {
    const baseUrl = new URL(`https://api.github.com/repos/${owner}/${repo}/commits`);
    baseUrl.searchParams.set('sha', branch);
    if (path) baseUrl.searchParams.set('path', path);
    if (limit) baseUrl.searchParams.set('per_page', Math.min(Math.max(Number(limit) || 1, 1), 100));
    if (start) baseUrl.searchParams.set('since', new Date(start).toISOString());
    if (end) baseUrl.searchParams.set('until', new Date(end).toISOString());

    const response = await fetch(baseUrl, { headers: buildGithubHeaders(), signal });
    if (response.status === 304) {
        return { commits: [], rateLimited: false, etag: response.headers.get('etag') || null };
    }
    if (!response.ok) {
        const errorBody = await response.text().catch(() => '');
        const error = new Error(`GitHub API error: ${response.status} ${response.statusText}`);
        error.status = response.status;
        error.body = errorBody;
        throw error;
    }

    const data = await response.json();
    const commits = Array.isArray(data) ? data : [];
    return {
        commits: commits.map((entry) => {
            const message = entry.commit?.message || '';
            const authorLogin = entry.author?.login || '';
            const authorName = entry.commit?.author?.name || entry.author?.login || 'Unknown';
            const isCrowdinExport = detectCrowdinExport({ message, authorLogin, authorName });

            const exportDisplayName = 'Crowdin';
            const exportLogin = 'crowdin-export';

            return {
                sha: entry.sha,
                url: entry.html_url,
                author: {
                    name: isCrowdinExport ? exportDisplayName : authorName,
                    email: isCrowdinExport ? null : entry.commit?.author?.email || null,
                    login: isCrowdinExport ? exportLogin : authorLogin || null,
                    avatar_url: isCrowdinExport ? null : entry.author?.avatar_url || null,
                },
                committer: {
                    name: isCrowdinExport
                        ? exportDisplayName
                        : entry.commit?.committer?.name || entry.committer?.login || null,
                    email: isCrowdinExport ? null : entry.commit?.committer?.email || null,
                    login: isCrowdinExport ? exportLogin : entry.committer?.login || null,
                },
                message,
                date: entry.commit?.author?.date || entry.commit?.committer?.date || null,
            };
        }),
        rateLimited: response.status === 403 && response.headers.get('x-ratelimit-remaining') === '0',
        etag: response.headers.get('etag') || null,
    };
}

function detectCrowdinExport({ message, authorLogin, authorName }) {
    const normalizedMessage = (message || '').toLowerCase();
    if (!normalizedMessage) return false;

    const looksLikeExport = normalizedMessage.startsWith('new translations') ||
        normalizedMessage.includes('(bundle:');
    if (!looksLikeExport) return false;

    const login = (authorLogin || '').toLowerCase();
    const name = (authorName || '').toLowerCase();
    const knownLogins = new Set(['digital-pro', 'levante-automation']);
    const knownNames = new Set(['david cardinal', 'levante automation']);

    if (knownLogins.has(login) || knownNames.has(name)) {
        return true;
    }

    return false;
}

function shortenCommitHeadline(rawHeadline, primaryFilename) {
    const firstLine = (rawHeadline || '').split('\n')[0] || '';
    if (!firstLine) return '';

    let result = firstLine;
    if (primaryFilename) {
        const baseName = primaryFilename.split('/').pop() || primaryFilename;
        if (baseName) {
            const escaped = primaryFilename.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            result = result.replace(new RegExp(escaped, 'g'), baseName);
        }
    }

    result = result.replace(/(New translations\s+)([^\s)]+)(.*)/i, (match, prefix, path, suffix) => {
        const baseName = path.split('/').pop();
        return baseName ? `${prefix}${baseName}${suffix}` : match;
    });

    result = result.replace(/([A-Za-z0-9_.-]+\/)+([A-Za-z0-9_.-]+)/g, (_full, _dirs, file) => file);

    result = result.replace(/^new\s+translations\s+/i, '').trim();

    return result.trim();
}

function inferLanguagesFromFiles(files = [], header) {
    const languages = new Map();
    const headerLower = Array.isArray(header) ? header.map((h) => (h || '').toLowerCase()) : [];
    const idIndex = headerLower.indexOf('item_id');
    files.forEach((file) => {
        const filename = file?.filename || '';
        const match = filename.match(/(?:translations|xliff|surveys)[/\\].*?(?:-|\.)((?:[a-z]{2})(?:-[A-Za-z]{2})?)/i)
            || filename.match(/\b([a-z]{2}-[A-Za-z]{2})\b/);
        let code = match ? match[1].toLowerCase() : null;
        if (!match) return;
        if (!languages.has(code)) {
            const label = LOCALE_LABELS[code] || LOCALE_LABELS[code.split('-')[0]] || code.toUpperCase();
            languages.set(code, {
                code,
                label,
                files: new Set(),
                additions: 0,
                deletions: 0,
            });
        }
        const entry = languages.get(code);
        entry.files.add(filename.split('/').pop() || filename);
        entry.additions += file?.additions || 0;
        entry.deletions += file?.deletions || 0;
    });
    return Array.from(languages.values()).map((entry) => ({
        ...entry,
        files: Array.from(entry.files),
    }));
}

function buildDiffSnippets(files = [], maxChars = 6000) {
    const snippets = [];
    let remaining = maxChars;

    for (const file of files) {
        if (!file?.patch || remaining <= 0) continue;
        const baseName = file.filename ? file.filename.split('/').pop() : 'file';
        const lines = file.patch.split('\n');
        const addedLines = lines.filter((line) => line.startsWith('+') && !line.startsWith('+++')).slice(0, 80);
        let snippet = addedLines.join('\n');
        if (!snippet) {
            snippet = lines.filter((line) => !line.startsWith('@@')).slice(0, 40).join('\n');
        }
        if (!snippet) continue;

        if (snippet.length > remaining) {
            snippet = snippet.slice(0, remaining);
        }

        snippets.push(`File: ${baseName}\n${snippet}`);
        remaining -= snippet.length;
        if (remaining <= 0) break;
    }

    return snippets.join('\n\n');
}

function buildFallbackSummary(detail, primaryFilename) {
    if (!detail) return null;
    const stats = detail.stats || {};
    const files = Array.isArray(detail.files) ? detail.files : [];
    const fileCount = files.length;
    const additions = Number(stats.additions || 0);
    const deletions = Number(stats.deletions || 0);
    const languages = inferLanguagesFromFiles(files);

    if (languages.length) {
        const langDescriptions = languages
            .map((lang) => {
                const added = lang.additions || 0;
                const removed = lang.deletions || 0;
                if (removed === 0) {
                    return `added ${added} ${lang.label} translation${added === 1 ? '' : 's'}`;
                }
                return `${lang.label} (+${added}/-${removed})`;
            })
            .slice(0, 3);
        const more = languages.length > 3 ? ', …' : '';
        return langDescriptions.join(', ') + more;
    }

    if (fileCount) {
        return `${fileCount} file${fileCount === 1 ? '' : 's'} changed (+${additions} / -${deletions})`;
    }

    if (additions || deletions) {
        return `Adjusted translations (+${additions} / -${deletions})`;
    }

    return null;
}

async function fetchCommitDetail({ owner, repo, sha, signal }) {
    const url = new URL(`https://api.github.com/repos/${owner}/${repo}/commits/${sha}`);
    const response = await fetch(url, { headers: buildGithubHeaders(), signal });
    if (!response.ok) {
        const text = await response.text().catch(() => '');
        const error = new Error(`GitHub commit detail error: ${response.status} ${response.statusText}`);
        error.status = response.status;
        error.body = text;
        throw error;
    }
    return response.json();
}

async function enrichCommitsWithDetails(commits, { owner, repo, signal }) {
    const enriched = [];
    for (const commit of commits) {
        let headline = shortenCommitHeadline(commit.message || '', null);
        let summary = null;
        try {
            const detail = await fetchCommitDetail({ owner, repo, sha: commit.sha, signal });
            const primaryFilename = detail?.files?.[0]?.filename || null;
            headline = shortenCommitHeadline(commit.message || headline, primaryFilename || null) || headline;
            const translationSummary = await summarizeTranslationCommit(detail);
            if (translationSummary) {
                summary = translationSummary;
            } else {
                summary = (await generateAISummary(detail, headline))
                    || buildFallbackSummary(detail, primaryFilename || null);
            }
        } catch (error) {
            console.warn(`asset-history: commit detail fetch failed for ${commit.sha}:`, error.message);
        }

        enriched.push({
            ...commit,
            headline: headline || commit.message || '',
            summary: summary || null,
        });
    }
    return enriched;
}

async function generateAISummary(detail, headline) {
    if (!OPENAI_API_KEY) return null;
    try {
        const stats = detail?.stats || {};
        const files = Array.isArray(detail?.files) ? detail.files : [];
        const languages = inferLanguagesFromFiles(files);
        const languageLines = languages.map((lang) => {
            const fileList = lang.files.slice(0, 4).join(', ');
            const more = lang.files.length > 4 ? ', …' : '';
            return `• ${lang.label} (${lang.code.toUpperCase()}): +${lang.additions}/-${lang.deletions} across ${lang.files.length} file(s) [${fileList}${more}]`;
        }).join('\n');
        const fileDescriptions = files.slice(0, 6).map((file) => {
            const base = file?.filename ? file.filename.split('/').pop() : 'unknown file';
            const additions = file?.additions ?? 0;
            const deletions = file?.deletions ?? 0;
            return `- ${base}: +${additions} / -${deletions}`;
        }).join('\n');
        const diffSnippets = buildDiffSnippets(files);

        const prompt = [
            'You summarize translation updates for a project dashboard.',
            `Commit headline: ${headline || detail?.commit?.message?.split('\n')[0] || 'N/A'}`,
            'Provide a concise, human-friendly summary in 25 words or fewer.',
            'Highlight which languages or dialects changed and the nature of the update (e.g., “Added three new German vocab translations”).',
            'Describe the intent (e.g., “Updated German vocab translations for juggling item”).',
            'Avoid mentioning bundle numbers or file paths.',
            'Focus on translation content changes, new locales, or notable counts.',
            'If diff snippets include text in quotes, mention notable phrases or items that were added.',
            'Language hints:',
            languageLines || '- No explicit locale hints.',
            'File changes:',
            fileDescriptions || '- No file details available.',
            'Diff snippets:',
            diffSnippets || '- No diff snippets available.',
            `Totals: +${stats.additions || 0} / -${stats.deletions || 0}`,
        ].join('\n');

        const response = await fetch('https://api.openai.com/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${OPENAI_API_KEY}`,
            },
            body: JSON.stringify({
                model: OPENAI_MODEL,
                messages: [
                    { role: 'system', content: 'You produce concise summaries of translation commits for release notes.' },
                    { role: 'user', content: prompt },
                ],
                temperature: 0.2,
                max_tokens: 80,
            }),
            signal,
        });

        if (!response.ok) {
            const text = await response.text().catch(() => '');
            console.warn('asset-history: OpenAI summary failed', response.status, text.slice(0, 120));
            return null;
        }

        const data = await response.json();
        const summary = data?.choices?.[0]?.message?.content?.trim();
        if (!summary) return null;
        return summary.replace(/\s+/g, ' ').trim();
    } catch (error) {
        console.warn('asset-history: OpenAI summary error', error.message);
        return null;
    }
}

async function getBucketMetadata(bucketName, objectPath) {
    if (!bucketName || !objectPath) return { bucket: bucketName, path: objectPath, status: 'unavailable' };
    try {
        const storage = await getStorage();
        const bucket = storage.bucket(bucketName);
        const file = bucket.file(objectPath);
        const [exists] = await file.exists();
        if (!exists) {
            return {
                bucket: bucketName,
                path: objectPath,
                status: 'missing',
            };
        }

        const [metadata] = await file.getMetadata();
        return {
            bucket: bucketName,
            path: objectPath,
            status: 'ok',
            updated: metadata.updated || metadata.timeCreated || null,
            size: metadata.size ? Number(metadata.size) : null,
            md5Hash: metadata.md5Hash || null,
            generation: metadata.generation || null,
            metageneration: metadata.metageneration || null,
        };
    } catch (err) {
        console.warn(`Failed to load metadata for ${bucketName}/${objectPath}:`, err.message);
        return {
            bucket: bucketName,
            path: objectPath,
            status: 'error',
            error: err.message,
        };
    }
}

function correlateEnvironment(commits, environment) {
    const updatedDate = normalizeDate(environment?.updated);
    if (!updatedDate) {
        return {
            status: environment?.status || 'unknown',
            pendingCommits: null,
            latestCommitDate: commits.length ? commits[0].date : null,
        };
    }

    const pending = commits.filter((commit) => {
        const commitDate = normalizeDate(commit.date);
        if (!commitDate) return false;
        return commitDate > updatedDate;
    });

    return {
        status: pending.length === 0 ? 'in-sync' : 'behind',
        pendingCommits: pending.length,
        latestCommitDate: commits.length ? commits[0].date : null,
        updatedDate: updatedDate.toISOString(),
        lastCommitAfterUpdate: pending.length ? pending[0].date : null,
    };
}

function normalizePaths(pathParam) {
    if (Array.isArray(pathParam)) {
        return pathParam
            .flatMap((p) => (typeof p === 'string' ? p.split(',') : []))
            .map((p) => p.trim())
            .filter(Boolean);
    }
    if (typeof pathParam === 'string') {
        return pathParam
            .split(',')
            .map((p) => p.trim())
            .filter(Boolean);
    }
    return [];
}

function sortAndDedupeCommits(commits) {
    const seen = new Map();
    commits.forEach((commit) => {
        if (!commit || !commit.sha) return;
        if (!seen.has(commit.sha)) {
            seen.set(commit.sha, commit);
        }
    });
    return Array.from(seen.values()).sort((a, b) => {
        const aTime = new Date(a.date || 0).getTime();
        const bTime = new Date(b.date || 0).getTime();
        return bTime - aTime;
    });
}

async function collectCommitsAcrossPaths({ owner, repo, branch, paths, start, end, limit, signal }) {
    const pathList = paths && paths.length ? paths : [];

    if (!pathList.length) {
        return await fetchCommits({ owner, repo, branch, path: undefined, start, end, limit, signal });
    }

    const aggregate = [];
    let rateLimited = false;

    for (const path of pathList) {
        try {
            const result = await fetchCommits({ owner, repo, branch, path, start, end, limit, signal });
            aggregate.push(...(result.commits || []));
            rateLimited = rateLimited || Boolean(result.rateLimited);
        } catch (error) {
            // Propagate rate limit errors, but for other failures continue to next path
            if (error && error.status === 403) {
                throw error;
            }
            console.warn(`asset-history: failed to fetch commits for path "${path}":`, error.message);
        }
    }

    const deduped = sortAndDedupeCommits(aggregate);
    const limited = typeof limit === 'number' ? deduped.slice(0, limit) : deduped;
    const enriched = await enrichCommitsWithDetails(limited, { owner, repo, signal });

    return {
        commits: enriched,
        rateLimited,
    };
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    if (req.method !== 'GET') {
        res.status(405).json({ error: 'Method not allowed' });
        return;
    }

    try {
        const {
            branch = DEFAULT_BRANCH,
            start,
            end,
            limit = 50,
            owner = DEFAULT_OWNER,
            repo = DEFAULT_REPO,
        } = req.query;

        const rawPath = req.query.path ?? DEFAULT_PATH;
        const pathList = normalizePaths(rawPath);
        const effectivePaths = pathList.length ? pathList : normalizePaths(DEFAULT_PATH);

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 1000 * 25);

        let commitsResponse;
        try {
            commitsResponse = await collectCommitsAcrossPaths({
                owner,
                repo,
                branch,
                paths: effectivePaths,
                start,
                end,
                limit: Number(limit) || 50,
                signal: controller.signal,
            });
        } finally {
            clearTimeout(timeout);
        }

        const commits = commitsResponse.commits || [];

        const [devMeta, prodMeta, devSurveyMeta, prodSurveyMeta] = await Promise.all([
            getBucketMetadata(DEV_BUCKET, TRANSLATION_OBJECT_PATH),
            getBucketMetadata(PROD_BUCKET, TRANSLATION_OBJECT_PATH),
            getBucketMetadata(DEV_BUCKET, SURVEY_OBJECT_PATH),
            getBucketMetadata(PROD_BUCKET, SURVEY_OBJECT_PATH),
        ]);

        const environments = {
            dev: {
                itemBank: { ...devMeta, correlation: correlateEnvironment(commits, devMeta) },
                surveys: { ...devSurveyMeta, correlation: correlateEnvironment(commits, devSurveyMeta) },
            },
            prod: {
                itemBank: { ...prodMeta, correlation: correlateEnvironment(commits, prodMeta) },
                surveys: { ...prodSurveyMeta, correlation: correlateEnvironment(commits, prodSurveyMeta) },
            },
        };

        res.status(200).json({
            repository: `${owner}/${repo}`,
            branch,
            paths: effectivePaths,
            range: {
                start: start ? new Date(start).toISOString() : null,
                end: end ? new Date(end).toISOString() : null,
            },
            commits,
            environments,
            meta: {
                total: commits.length,
                limit: Number(limit) || 50,
                rateLimited: commitsResponse.rateLimited,
                fetchedAt: new Date().toISOString(),
                tokenPresent: Boolean(process.env.GITHUB_TOKEN || process.env.GITHUB_PAT),
            },
        });
    } catch (error) {
        console.error('asset-history API error:', error);
        const status = error?.status && Number.isInteger(error.status) ? error.status : 500;
        res.status(status).json({
            error: 'Failed to load asset history',
            details: error.message,
            body: error.body || null,
        });
    }
}

