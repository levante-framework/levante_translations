## Itembank XLIFF Regen Report (SQLite)

This workflow uses the authoritative Crowdin XLIFF exports in `itembank_by_task/` to decide
which items need audio regeneration. It stores a local SQLite snapshot for versioned diffs and
emits a report for confirmation before any regen step.

### What it does
- Downloads `itembank_by_task/*.xliff` from Crowdin (or reuses a local cache).
- Parses `trans-unit` entries into a normalized table.
- Compares the new snapshot to the previous SQLite state.
- Produces a report with reasons:
  - `NEW_ITEM`
  - `TEXT_CHANGED`
  - `MISSING_TRANSLATION`
  - `MISSING_AUDIO`

### Requirements
- `CROWDIN_API_TOKEN` set in your environment or `~/.crowdin_api_token`.
- `CROWDIN_PROJECT_ID` or `CROWDIN_LEVANTE_PID` for the Levante translations project.

### Run the report
```bash
python utilities/itembank_by_task_regen_report.py \
  --project-id "$CROWDIN_PROJECT_ID" \
  --langs all
```

Defaults (can be overridden):
- Download cache: `tmp/itembank_by_task_xliff/`
- SQLite: `tmp/itembank_by_task_regen.sqlite`
- Reports: `tmp/itembank_by_task_reports/`
- Crowdin prefix: `itembank_by_task/`
- Audio base dir: `audio_files/`

If your Crowdin folder is nested under `main/`, override the prefix:
```bash
python utilities/itembank_by_task_regen_report.py \
  --project-id "$CROWDIN_PROJECT_ID" \
  --langs all \
  --crowdin-prefix "main/itembank_by_task"
```

### Optional: sync the SQLite baseline to GCS
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

### Skip download (use cached XLIFF)
```bash
python utilities/itembank_by_task_regen_report.py --langs es-CO de --skip-download
```

### Skip audio check
```bash
python utilities/itembank_by_task_regen_report.py --langs all --skip-audio-check
```

### Review the report
The report is saved as both CSV and JSON:
```
tmp/itembank_by_task_reports/regen_report_YYYYMMDD_HHMMSS.csv
tmp/itembank_by_task_reports/regen_report_YYYYMMDD_HHMMSS.json
tmp/itembank_by_task_reports/regen_report_YYYYMMDD_HHMMSS.md
```

Use it as a confirmation step before running audio generation.

### Notes
- The SQLite snapshot enables precise diffs across runs.
- `item_id` is taken from XLIFF `trans-unit` `resname` or `id`.
- Task name is inferred from the XLIFF filename in `itembank_by_task/`.
