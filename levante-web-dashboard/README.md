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
