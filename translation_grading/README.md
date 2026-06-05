# Translation Grading Pipeline

This folder contains the frontier-model translation grading workflow for Levante.
It complements the existing back-translation and `xcomet/` tooling in this repo.

## What It Does

The pipeline scores current translations with multiple signals:

1. **Cross-lingual consistency**
   - Uses LaBSE or multilingual-e5 embeddings.
   - For multi-language runs, each translation is compared to the centroid of the other language versions for the same item.
   - For single-language runs, it falls back to source-vs-target similarity.

2. **COMET / xCOMET / COMET-Kiwi** *(optional)*
   - Uses `unbabel-comet` if installed.
   - Default QE model: `Unbabel/wmt22-cometkiwi-da`.

3. **Gemini LLM judge** *(optional)*
   - Uses `gemini-2.5-pro` by default.
   - Runs direct source+target assessment, not back-translation.
   - Can run only on metric-flagged rows to control cost.

4. **Review triage outputs**
   - CSV with per-row scores and review reasons.
   - JSON with full row metadata.
   - Markdown flag report.

## Setup

```bash
python3 -m venv .venv-translation-grading
source .venv-translation-grading/bin/activate
python -m pip install --upgrade pip
pip install -r translation_grading/requirements.txt
```

For Gemini judging:

```bash
export GEMINI_API_KEY=...
```

For direct Crowdin API input:

```bash
export CROWDIN_API_TOKEN=...
```

The Crowdin token can also live at `~/.crowdin_api_token`, matching existing tooling in this repo.

## Examples

### Local CSV

```bash
python translation_grading/pipeline.py \
  --input-mode csv \
  --input-csv translation_master.csv \
  --source-col en \
  --target-cols "de,es-CO,fr-CA,nl"
```

### Crowdin Approved Export

This is the preferred path when grading the current approved translator output.

```bash
python translation_grading/pipeline.py \
  --input-mode crowdin-api \
  --crowdin-project-id 756721 \
  --source-col en \
  --target-cols "de,es-CO,fr-CA,nl"
```

### Crowdin ZIP Download

```bash
python translation_grading/pipeline.py \
  --input-mode crowdin-zip \
  --crowdin-zip path/to/crowdin-export.zip \
  --source-col en \
  --target-cols "de,es-CO,fr-CA,nl"
```

### Dashboard Endpoint Compatibility

Useful when you want to score exactly the same approved-export endpoint used by the web dashboard:

```bash
python translation_grading/pipeline.py \
  --input-mode dashboard-endpoint \
  --dashboard-base-url https://levante-cockpit.vercel.app \
  --source-col en \
  --target-cols "de,es-CO,fr-CA,nl"
```

### Gemini on Flagged Rows

```bash
python translation_grading/pipeline.py \
  --input-mode crowdin-api \
  --target-cols "de,es-CO,fr-CA,nl" \
  --run-llm-judge \
  --llm-only-flagged \
  --llm-max-calls 200
```

### COMET-Kiwi + Gemini

```bash
python translation_grading/pipeline.py \
  --input-mode crowdin-api \
  --target-cols "de,es-CO,fr-CA,nl" \
  --run-comet \
  --run-llm-judge \
  --llm-only-flagged
```

## Outputs

Defaults:

- `translation_grading/output/translation-grading-report.csv`
- `translation_grading/output/translation-grading-summary.json`
- `translation_grading/output/translation-grading-flag-report.md`

Review reasons use compact machine-readable labels:

- `consistency<0.78`
- `comet<0.62`
- `llm<75.0`
- `llm_severity:critical`
- `llm_severity:major`

## Relationship to Existing Validation

- Back-translation remains useful as a human-inspectable signal.
- `xcomet/` remains the richer COMET/xCOMET workflow and Excel export path.
- This pipeline combines cross-lingual outlier detection, optional COMET QE, and Gemini direct assessment into a single review queue.
