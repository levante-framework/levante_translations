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
It is now the default input mode in `pipeline.py`.

```bash
python translation_grading/pipeline.py \
  --crowdin-project-id 756721 \
  --source-col en \
  --target-cols "de,es-CO,fr-CA,nl"
```

Crowdin approved-export cache behavior:

- First run fetches approved export from Crowdin API and writes:
  - `translation_grading/output/.crowdin-approved-cache.zip`
- Later runs reuse that cache for speed **only while fresh**.
- Default freshness window: 120 minutes (`--crowdin-cache-max-age-minutes 120`).
- Force refresh when needed:

```bash
python translation_grading/pipeline.py --refresh-crowdin-cache
```

Always refresh from Crowdin (no cache reuse):

```bash
python translation_grading/pipeline.py --crowdin-cache-max-age-minutes 0
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

By default, `pipeline.py` now uses **task-aware Gemini prompts** (same template
selection logic as `gemini_quality_evaluator.py`).

- `--llm-prompt-mode task-aware` (default)
- `--llm-prompt-mode generic` (legacy single prompt style)
- `--llm-default-label <label>` to force a fallback task label when input data
  lacks `labels`/`task`.

### COMET-Kiwi + Gemini

```bash
python translation_grading/pipeline.py \
  --input-mode crowdin-api \
  --target-cols "de,es-CO,fr-CA,nl" \
  --run-comet \
  --run-llm-judge \
  --llm-only-flagged
```

### Task-Specific Gemini Quality Evaluation

Use `gemini_quality_evaluator.py` when grading `complete_translations.csv`
with task-specific prompts selected from the `labels` and `identifier`
columns.

```bash
python translation_grading/gemini_quality_evaluator.py \
  --input-csv complete_translations.csv \
  --output-csv translation_quality_results.csv
```

The evaluator checks `es-CO`, `de`, `fr-CA`, and `nl` by default, uses
`gemini-2.0-flash` with fallback to `gemini-1.5-pro`, batches
`OBJECT_NAMING` items up to 20 per request, and writes a `human_review` flag
for scores `<= 3` or any critical error.

To include Crowdin screenshots as Gemini image inputs for visual-context-heavy
tasks, opt in with:

```bash
python translation_grading/gemini_quality_evaluator.py \
  --input-csv complete_translations.csv \
  --output-csv translation_quality_results.csv \
  --use-crowdin-screenshots
```

Screenshot mode joins Crowdin source string identifiers to tagged screenshots,
caches matched images under `translation_grading/output/crowdin_screenshots`,
and attaches at most one screenshot per item by default. It only applies to
`vocab`, `theory-of-mind`, `hostile-attribution`, `matrix-reasoning`,
`mental-rotation`, and `same-different-selection`; strings without screenshots
fall back to text-only evaluation.

### Vocab VLM Benchmark Storage

`vocab_vlm_language_benchmark.py` always stores runs locally in SQLite under
`translation_grading/output/vocab_vlm_language_runs.sqlite`. To also shadow
write run metadata and per-trial records to the named Firestore database
`levante-tools-data` in `hs-levante-admin-dev`, opt in with:

```bash
python translation_grading/vocab_vlm_language_benchmark.py \
  --run --analyze \
  --languages nl \
  --firestore-shadow
```

This uses Application Default Credentials and targets the collection
`vocabVlmLanguageRuns` by default. Existing SQLite runs can be backfilled without
rerunning Cypress:

```bash
python translation_grading/vocab_vlm_language_benchmark.py \
  --backfill-firestore \
  --firestore-shadow
```

Human review escalation priority is theory-of-mind first, then vocab, then
trog, then all other tasks, matching the pilot invariance and translation-risk
patterns described in the task-design paper.

## Current End-to-End Workflow (NL, all tasks including surveys)

This is the current practical workflow used for Dutch (`nl`) review triage.
It runs on Crowdin-approved exports, then narrows to a human-review queue.

### Stage 0: Input scope

- Source: Crowdin approved export (`project_id=756721`)
- Scope: all task content plus caregiver/teacher survey files
- Excludes legacy/UI-only strings (e.g., `surveyjs`, `Z_LEGACY_DO_NOT_TRANSLATE`)

### Stage 1: Embedding gate

- Build complete multilingual rows (`en`, `es-CO`, `de`, `fr-CA`, `nl`)
- Compute LaBSE centroid distance per language row
- Candidate rules:
  - `high`: `nl_delta > 0.15`
  - `medium_high_risk`: high-risk task (`theory-of-mind`, `vocab`, `trog`, `hostile-attribution`) and `nl_delta > 0.08`
  - `medium`: all other tasks and `nl_delta > 0.08`

Only candidate rows continue to Gemini/backtranslation.

### Stage 2: Task-aware Gemini + screenshot-aware backtranslation

- Attach Crowdin screenshots for eligible labels (`vocab`, `theory-of-mind`, etc.)
- Run task-aware grading prompt (`evaluate_single`)
- Run screenshot-aware backtranslation prompt (`evaluate_backtranslation`)

The survey prompt is now audience-aware:
- caregiver survey: parent/other caregiver respondent context
- teacher survey: teacher/classroom respondent context

### Stage 3: Human-review escalation rules

Rows are escalated if any of the following triggers fire:

- Gemini severity `critical`
- Backtranslation severity `critical`
- Gemini score `<= 3`
- Backtranslation score `<= 3`
- `nl_delta > 0.15` and Gemini score `<= 4`
- `nl_delta > 0.08` and backtranslation score `<= 3`
- High-risk task + low model score
- Survey + low model score

### Outputs used in current runs

For the baseline all-task run:

- `translation_grading/output/nl_all_tasks_auto_review_results.csv`
- `translation_grading/output/nl_all_tasks_auto_review_results.json`
- `translation_grading/output/nl_all_tasks_human_review_summary.md`
- `translation_grading/output/nl_all_tasks_human_review_summary_embedded.html`

For the survey prompt update rerun:

- `translation_grading/output/nl_all_tasks_auto_review_results_prompt_update.csv`
- `translation_grading/output/nl_all_tasks_auto_review_results_prompt_update.json`
- `translation_grading/output/nl_all_tasks_human_review_summary_prompt_update.md`
- `translation_grading/output/nl_all_tasks_human_review_summary_embedded_prompt_update.html`
- `translation_grading/output/nl_all_tasks_human_review_full_printout_prompt_update.md`
- `translation_grading/output/nl_all_tasks_human_review_full_printout_prompt_update_embedded.html`

### Important note

There is not yet a single committed CLI entrypoint that executes this full
three-stage NL workflow in one command. The process is reproducible with the
documented stages above and existing modules in `pipeline.py` and
`gemini_quality_evaluator.py`.

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

## Persistent Embedding Baseline (New)

Use `embedding_baseline.py` when you want persistent outlier checks for newly
arriving translations against a stored multilingual baseline.

### 1) Build baseline embeddings

```bash
python translation_grading/embedding_baseline.py build \
  --input-csv translation_master.csv \
  --source-col en \
  --target-cols "de,es-CO,fr-CA,nl" \
  --baseline-out translation_grading/output/embedding_baseline.npz
```

This stores per-row embeddings + metadata in `embedding_baseline.npz`.

### 2) Detect outliers in a new CSV

```bash
python translation_grading/embedding_baseline.py detect \
  --baseline translation_grading/output/embedding_baseline.npz \
  --input-csv translation_master.csv \
  --source-col en \
  --target-cols "es-CO" \
  --output-csv translation_grading/output/embedding_outlier_report.csv \
  --summary-json translation_grading/output/embedding_outlier_summary.json
```

Outlier scores include:

- `same_item_centroid_sim`: candidate vs all historical translations for that item
- `same_item_lang_max_sim`: candidate vs historical same item+language entries
- `lang_centroid_sim`: candidate vs overall language centroid baseline

Rows are flagged when any score falls below its threshold (`--item-centroid-threshold`,
`--item-lang-threshold`, `--lang-centroid-threshold`).
`--lang-centroid-threshold` defaults to `0` (disabled) until calibrated.

## Pipeline Integration (New)

`pipeline.py` can now build and/or use the same persistent baseline directly.

Build baseline from the current run:

```bash
python translation_grading/pipeline.py \
  --input-mode csv \
  --input-csv translation_master.csv \
  --source-col en \
  --target-cols "de,nl,es-CO,fr-CA,de-CH,es-AR,en-GH,en-GB,pt-PT,pt-BR" \
  --embedding-baseline translation_grading/output/stories_all_langs_baseline.npz \
  --build-embedding-baseline
```

Detect outliers against an existing baseline:

```bash
python translation_grading/pipeline.py \
  --input-mode csv \
  --input-csv translation_master.csv \
  --source-col en \
  --target-cols "de,nl,es-CO,fr-CA,de-CH,es-AR,en-GH,en-GB,pt-PT,pt-BR" \
  --embedding-baseline translation_grading/output/stories_all_langs_baseline.npz \
  --detect-embedding-outliers
```

## Relationship to Existing Validation

- Back-translation remains useful as a human-inspectable signal.
- `xcomet/` remains the richer COMET/xCOMET workflow and Excel export path.
- This pipeline combines cross-lingual outlier detection, optional COMET QE, and Gemini direct assessment into a single review queue.
