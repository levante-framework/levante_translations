# AGENTS.md

Guidance for AI agents working in the `levante_translations` repository. This is the
portable, tool-neutral entry point. Cursor-specific rules live in `.cursor/rules/`.

## Core principles

See `.cursor/rules/core-principles.mdc` (KISS, YAGNI, minimal scope). Do only what the
task requires; propose broader changes before implementing them.

## What this repo does

Levante audio + translation tooling:

- **Audio generation** (`generate_speech.py`): produces per-language MP3s with ID3 tags
  for the Levante item bank, using ElevenLabs (primary) or PlayHT TTS.
- **Audio validation** (`validate_audio/`): ASR-based quality checks (Whisper/Google).
- **Translation quality metrics** (`translation_grading/`): composite scoring that fuses
  embeddings, back-translation, Gemini/VLM judgments, and oracle QA signals.
- **Dashboards**: desktop (`dashboard.py`) and the web dashboard in the sibling repo
  `../levante-web-dashboard` (deployed via Vercel).

## Environments

Two separate Python virtualenvs:

- **`.venv`** — main env for generation, deployment, utilities, dashboard.
  Set up with `npm run venv:setup` (or `python3 -m venv .venv`).
- **`.venv-validate-audio`** — heavy ML deps (PyTorch, sentence-transformers) for audio
  validation only. Set up with `npm run validate:audio:setup`.

Always activate the right env first: `source .venv/bin/activate`.

## Key commands

```bash
# Generate audio (draft bucket JSON is the default translation source)
python generate_speech.py "English (United States)" --translation-source draft
python generate_speech.py "Spanish (Argentina)" --translation-source draft

# Dry-run / audit only (no generation). Writes needed_item_bank_translations.csv
python generate_speech.py "Spanish (Colombia)" --validate-only --translation-source draft

# Limit to specific task labels
python generate_speech.py Spanish --tasks child-survey,matrix-reasoning

# Force regenerate everything (e.g. after a voice change)
python generate_speech.py English --force
```

Language names must match keys in `utilities/config.py` (e.g. `"Spanish (Argentina)"`,
not `es-AR`). Voices/locales/services are all defined there.

## Source-of-truth conventions

- **Translations**: draft bucket JSON is canonical for generation:
  `gs://levante-assets-draft/translations/itembank/<task>/<locale>/item-bank-translations.json`
  At runtime `generate_speech.py` builds a temp CSV from these JSONs.
  Refresh local CSV with `npm run refresh:translations-from-draft`.
- **Existing audio detection is LOCAL**: validation checks `audio_files/<lang_code>/<item_id>.mp3`
  on disk (via `utilities.audio_file_path` + `utilities.audio_validation.needs_regeneration`),
  not GCS. Sync down first if you need bucket state:
  `gsutil -m rsync -c -r gs://levante-assets-dev/audio/ audio_files/`
- **Approved audio**: once partner approvals move clips into `levante-assets-dev/audio`,
  treat the **dev bucket as source-of-truth** and rsync it back before any deploy.

## Regeneration logic (how `needs_regeneration` decides)

An item is flagged for (re)generation when any of these hold:
1. The MP3 does not exist locally.
2. ID3 `original_translation_text` (or `text`) differs from current translation
   (whitespace/`<br>`/`<p>` differences are ignored).
3. Voice, service, lang_code, or (when checked) `model_id` differ from config.

Default ElevenLabs model is `eleven_v3`.

## Deployment guardrails

- `levante-dashboard-*` buckets are **CSV-only** — never upload code/HTML/JS there.
- `deploy_translations.py` has a drift check that blocks dev audio deploys when local
  `audio_files/` differs from approved `levante-assets-dev/audio`. Only bypass with
  `--skip-dev-audio-drift-check` for intentional exceptions.
- Web dashboard is deployed from `../levante-web-dashboard` (`npm run deploy`), not here.

## Agent working rules

- Prefer the dedicated tools over shell for file read/edit/search.
- Don't commit unless explicitly asked.
- When generating audio in CI, use the `audio-regen-draft.yml` workflow (supports a
  `dry_run` input and `language=all` with locale-alias deduplication).
- Keep `.env` secrets out of commits (`GEMINI_API_KEY`, `ELEVEN_LABS_API_KEY`,
  `PLAY_DOT_HT_API_KEY`, etc.).

## Pointers

- `README.md` — full setup, deployment, and workflow reference.
- `.cursor/rules/context-mode.mdc` — context-mode tooling rules.
- `translation_grading/README.md` — composite quality metrics details.
- `validate_audio/README.md` — audio validation system.
- `README_ADD_LANGUAGE.md` — adding a new language.
