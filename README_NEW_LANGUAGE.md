## Adding and Deploying New Languages and Dialects

This guide explains how to add and deploy:
- a new root language (e.g., `de` German)
- a new dialect of an existing root language (e.g., `de-CH` German (Switzerland))
- a new dialect when there is no root language present (e.g., only `fr-CA` without `fr`)

Our system uses a centralized language configuration stored in Google Cloud Storage and a single translations CSV. Audio generation and all apps consume the same configuration.

### Prerequisites
- GCP service account with access to buckets:
  - `levante-dashboard-<env>` (CSV only)
  - `levante-audio-<env>` (audio files + shared config)
- Local env for CLI use:
  - export `GCP_SERVICE_ACCOUNT_JSON='…service_account_json…'`
- Web dashboard deployed and accessible (loads/saves language config via `/api/language-config`).

### Source of Truth
- Centralized configuration JSON: `gs://levante-audio-dev/language_config.json` (and `…-prod`) 
- Translations CSV: `item-bank-translations.csv` (in repo and deployed to `levante-dashboard-<env>` as `item-bank-translations.csv`)

### Naming and Codes
- Use BCP 47/ISO codes:
  - Root languages: `en`, `es`, `de`, `nl`, …
  - Dialects: `es-CO`, `de-CH`, `fr-CA`, …
- Display names should be user-friendly: `German (Switzerland)`, `Spanish`, etc.

---

## 1) Add a New Root Language

Example: Add `Italian` with code `it`.

1) Ensure CSV has a column for the new language code
- Via translation platform or directly in `item-bank-translations.csv`, add a new column `it` (root code)
- Commit to `l10n_pending` branch if needed; our tools fetch from there

2) Update the centralized language configuration
- Open the Web Dashboard
- Click “Edit Language Config”
- Add a new entry:

```json
{
  "Italian": {
    "lang_code": "it",
    "service": "ElevenLabs",
    "voice": "<Choose a default voice name>"
  }
}
```

- Save (writes to `gs://levante-audio-<env>/language_config.json`)

3) Fetch the latest translations locally
```bash
npm run fetch:translations
```

4) Generate audio for the new language (initial full build)
```bash
python generate_speech.py Italian --force
```

5) Validate (optional but recommended)
```bash
npm run validate:core-tasks-quick
```

6) Deploy
- Dev:
```bash
npm run deploy:translations-dev
```
- Prod (after validation): trigger your manual prod deploy or:
```bash
npm run deploy:translations-prod
```

Notes:
- CSV uploads go to `levante-dashboard-<env>` as `item-bank-translations.csv`
- Audio files sync to `gs://levante-audio-<env>/audio_files/<lang_code>/…`

---

## 2) Add a New Dialect of an Existing Root Language

Example: Add `German (Austria)` with code `de-AT` when `de` exists.

1) Ensure CSV has the dialect column
- Add a new column `de-AT` to `item-bank-translations.csv`

2) Update centralized config (Web Dashboard → Edit Language Config)
```json
{
  "German (Austria)": {
    "lang_code": "de-AT",
    "service": "ElevenLabs",
    "voice": "<Choose default voice>"
  }
}
```

3) Fetch translations
```bash
npm run fetch:translations
```

4) Generate audio
```bash
python generate_speech.py "German (Austria)" --force
```

5) Validate and deploy (same as section 1)

Notes:
- Root `de` and dialect `de-AT` can coexist as independent columns.
- Use `--force` on first build to create all audio for that dialect.

---

## 3) Add a New Dialect When No Root Language Exists

Example: Add `French (Canada)` with code `fr-CA` when there is no `fr` column.

1) Ensure CSV has the dialect column only
- Add `fr-CA` to `item-bank-translations.csv`
- A root `fr` is not required

2) Update centralized config
```json
{
  "French (Canada)": {
    "lang_code": "fr-CA",
    "service": "ElevenLabs",
    "voice": "<Choose default voice>"
  }
}
```

3) Fetch, generate, validate, and deploy
```bash
npm run fetch:translations
python generate_speech.py "French (Canada)" --force
npm run deploy:translations-dev
# Manual prod after validation
```

Notes:
- The system does not require a root language to exist for a dialect.
- Ensure the display name is unique and maps to the correct `lang_code`.

---

## Useful Commands

- Detect any new languages in CSV:
```bash
npm run detect:languages
```

- Auto-add languages to config (best-effort helper):
```bash
npm run auto:add-languages
```

- Fetch translations from `l10n_pending`:
```bash
npm run fetch:translations
```

- Generate audio for a language:
```bash
python generate_speech.py "German (Switzerland)" --force
```

- Deploy both CSV and audio:
```bash
npm run deploy:translations-dev
npm run deploy:translations-prod
```

- CSV-only or Audio-only deploys:
```bash
npm run deploy:translations-csv-only-dev
npm run deploy:translations-audio-only-dev
```

- Validate core tasks (Cypress):
```bash
npm run validate:core-tasks-quick
```

---

## Buckets and File Separation

- `levante-dashboard-<env>`:
  - CSV only: `item-bank-translations.csv`
  - Never upload code or audio here
- `levante-audio-<env>`:
  - Audio files under `audio_files/<lang_code>/…`
  - Centralized `language_config.json`

---

## Troubleshooting

- “Column <code> not found in CSV”
  - Ensure the language/dialect column exists in `item-bank-translations.csv`
  - Re-run `npm run fetch:translations`

- “Anonymous caller” or `401` on deploy
  - Ensure the workflow or local env has valid `GCP_SERVICE_ACCOUNT_JSON`
  - Bucket IAM: service account must have `objectAdmin` on target buckets

- Web dashboard not showing new language
  - Hard refresh; dashboard fetches `language_config.json` at runtime
  - Confirm the config entry exists and was saved successfully

- Want to fully rebuild a language’s audio
```bash
python generate_speech.py <Language Name> --force
```
This clears the per-language cache in `translation_master.csv` and regenerates all items using the current voice.

---

## Template: language_config.json Entry

```json
{
  "<Display Name>": {
    "lang_code": "<bcp47_code>",
    "service": "ElevenLabs",
    "voice": "<Default voice name>"
  }
}
```

If you use PlayHT for a language, set `service` to `PlayHt` and provide a valid voice name.

---

## Rollout Checklist
- [ ] CSV column added for new `lang_code`
- [ ] `language_config.json` updated and saved via web dashboard
- [ ] Translations fetched locally
- [ ] Audio generated with `--force` (initial build)
- [ ] Validation passed (optional)
- [ ] Dev deploy completed
- [ ] Manual prod deploy completed after validation
