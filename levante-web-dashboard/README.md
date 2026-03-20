# Levante Web Dashboard

Web-based tools for audio generation, validation, and partner approval. Deployed on **Vercel**.

## Layout

- `public/` – HTML (e.g. `partner-audio-dashboard.html`, `audio-approval.html`), JS/CSS, `public/data/` for validation JSON exports.
- `api/` – Vercel serverless routes (`partner-itembank.js`, proxies, etc.).
- `scripts/`, `package.json`, `vercel.json`, `.vercel/project.json` – deploy and tooling.

## When checked out inside `levante_translations`

From this directory:

```bash
npm install
npm run deploy          # production (see scripts/deploy-and-alias.js)
npm run deploy-dev      # preview
npm start               # local static serve
```

To refresh the partner catalog JSON (reads parent SQLite, optional GCS upload):

```bash
npm run export:partner-itembank
npm run export:partner-itembank:upload
```

Standalone clone: run the Python export from the `levante_translations` repo; paths in those scripts assume the parent folder layout.

## Vercel / partner catalog API

`public/partner-audio-dashboard.html` loads **`GET /api/partner-itembank`**, which reads  
`gs://<bucket>/<object>` (defaults: `levante-assets-draft`, `translations/partner-itembank-audio-dashboard.json`).

Set in the Vercel project (or use defaults):

| Variable | Purpose |
|----------|---------|
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` or `GCP_SERVICE_ACCOUNT_JSON` | Service account JSON (recommended on Vercel) |
| `ASSETS_DRAFT_BUCKET` | Override draft bucket name |
| `PARTNER_ITEMBANK_OBJECT` | Override object path inside the bucket |

After exporting from the monorepo, run **`npm run export:partner-itembank:upload`** (or regen report with `--gcs-sync`) so the JSON exists in GCS.

**Deploy:** run `npm run deploy` from this directory (not the monorepo root). The repo root `vercel.json` only lists legacy host aliases; the active config is **`./vercel.json`** here.

## npm scripts

| Script | Purpose |
|--------|---------|
| `npm run export:partner-itembank` | Build `../tmp/partner_itembank_audio_dashboard.json` (needs parent repo + SQLite) |
| `npm run export:partner-itembank:upload` | Same + upload to draft GCS |
| `npm run deploy` | Production deploy + aliases (`levante-pitwall`, `levante-partner-tools`, etc.) |
| `npm run test` | Legacy Node checks (may report failures without a browser/DOM; `tsc --noEmit` is the strict TS check) |
