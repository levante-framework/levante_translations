## Itembank XLIFF Regen Report (SQLite)

This workflow uses the authoritative Crowdin XLIFF exports in `itembank_by_task/` to decide
which items need audio regeneration. It stores a local SQLite snapshot for versioned diffs and
emits a report for confirmation before any regen step.

### What changed
- Translation tracking moved from CSV-first diffing to a versioned SQLite baseline.
- The baseline now supports current state, append-only history, and staged imports:
  - `items_current`
  - `item_versions`
  - `items_staged`
- Regeneration checks now include:
  - `TEXT_CHANGED`
  - `VOICE_CHANGED`
  - `SERVICE_CHANGED`
  - `NEW_ITEM`
  - `MISSING_AUDIO`
- Voice/service expectations now resolve with this fallback chain:
  1. Dashboard API (`/api/language-config`)
  2. Public bucket `language_config.json`
  3. Local `utilities.config`
- Audio writing now persists `task` in ID3 metadata.
- `generate_speech.py` can now read translations from SQLite (`--translation-source sqlite`, default).
- Language alias symlinks were added for compatibility:
  - `audio_files/en-US -> en`
  - `audio_files/de-DE -> de`

### Symlink note (current state)
- Symlinks are currently intentional for Mac/Linux workflows.
- They allow the 4-letter language code paths to work while legacy 2-letter directories still exist.
- Long-term target is to keep only the 4-letter directories (`en-US`, `de-DE`, etc.) and remove aliases.
- When syncing/deploying with tooling, make sure symlinks are preserved (or pre-resolved) in your environment.

### What the workflow does
- Downloads `itembank_by_task/*.xliff` from Crowdin (or reuses a local cache).
- Parses `trans-unit` entries into normalized rows keyed by `item_id`, `lang`, and `task`.
- Upserts current state into SQLite and appends item versions.
- Optionally imports approved-only rows into `items_staged`.
- Compares staged rows against current baseline to propose regeneration candidates.
- Emits human-readable and machine-readable reports before generation.

### Requirements
- `CROWDIN_API_TOKEN` set in your environment or `~/.crowdin_api_token`.
- `CROWDIN_PROJECT_ID` or `CROWDIN_LEVANTE_PID` for the Levante translations project.

### Default paths
- Download cache: `tmp/itembank_by_task_xliff/`
- SQLite DB: `tmp/itembank_by_task_regen.sqlite`
- Reports: `tmp/itembank_by_task_reports/`
- Crowdin prefix: `itembank_by_task/`
- Audio base dir: `audio_files/`

### 1) Build/update baseline report (current state)
```bash
python utilities/itembank_by_task_regen_report.py \
  --project-id "$CROWDIN_PROJECT_ID" \
  --langs all
```

If your Crowdin folder is nested under `main/`, override the prefix:
```bash
python utilities/itembank_by_task_regen_report.py \
  --project-id "$CROWDIN_PROJECT_ID" \
  --langs all \
  --crowdin-prefix "main/itembank_by_task"
```

### Optional: sync SQLite baseline to GCS
GCS is not a database; use sync to download before the run and upload after.
```bash
python utilities/itembank_by_task_regen_report.py \
  --project-id "$CROWDIN_PROJECT_ID" \
  --langs all \
  --skip-download \
  --gcs-sync \
  --gcs-bucket "levante-assets-draft" \
  --gcs-path "baselines/itembank_by_task_regen.sqlite"
```

### Optional: reset to clean versioned schema
```bash
python utilities/itembank_by_task_regen_report.py \
  --reset-db
```

### Optional: seed baseline from existing audio metadata
This is useful when bootstrapping baseline state from existing MP3 ID3 tags.
```bash
python utilities/itembank_by_task_regen_report.py \
  --seed-audio-lang en-US \
  --seed-audio-dir audio_files/en-US \
  --task-map-csv translation_text/item_bank_translations.csv \
  --audio-seed-only
```

### Optional: import staged approved translations
```bash
python utilities/itembank_by_task_regen_report.py \
  --project-id "$CROWDIN_PROJECT_ID" \
  --langs en-US es-CO de \
  --import-staged \
  --approved-only
```

### Optional: skip download (use cached XLIFF)
```bash
python utilities/itembank_by_task_regen_report.py --langs es-CO de --skip-download
```

### Optional: skip audio existence check
```bash
python utilities/itembank_by_task_regen_report.py --langs all --skip-audio-check
```

### 2) Generate post-staging regeneration report
This compares `items_staged` against `items_current`.
```bash
python utilities/staged_regen_report.py \
  --db-path tmp/itembank_by_task_regen.sqlite \
  --voice-config-source dashboard_api
```

Report outputs:
```
tmp/itembank_by_task_reports/staged_regen_report_YYYYMMDD_HHMMSS.csv
tmp/itembank_by_task_reports/staged_regen_report_YYYYMMDD_HHMMSS.json
tmp/itembank_by_task_reports/staged_regen_report_YYYYMMDD_HHMMSS.md
tmp/itembank_by_task_reports/staged_regen_report_YYYYMMDD_HHMMSS.pdf
```

### 3) Generate audio from SQLite baseline
`generate_speech.py` now supports SQLite as translation source (default).
```bash
python generate_speech.py Spanish \
  --translation-source sqlite \
  --sqlite-db tmp/itembank_by_task_regen.sqlite
```

Force all items:
```bash
python generate_speech.py Spanish \
  --translation-source sqlite \
  --sqlite-db tmp/itembank_by_task_regen.sqlite \
  --force
```

### Notes
- The SQLite baseline enables stable diffs across runs and keeps version history in `item_versions`.
- `item_id` is taken from XLIFF `trans-unit` `resname` or `id`.
- Task name is inferred from the XLIFF filename in `itembank_by_task/`.
- Crowdin `de` is normalized to `de-DE` for parity with audio path conventions.
