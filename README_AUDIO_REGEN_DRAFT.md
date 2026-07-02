## Draft itembank audio regeneration

Generates ElevenLabs audio for new or changed itembank strings. Intended to run **after** itembank translation JSON exists in the draft bucket (produced by **Build itembank translations** in the `translation-utilities` repo). Cross-repo chaining is planned but not wired up yet.

**Workflow:** `.github/workflows/audio-regen-draft.yml`  
**Script:** `generate_itembank_audio.py`  
**Dependencies:** `requirements_itembank_audio.txt`

### Buckets

| Role | Default bucket | Path |
|------|----------------|------|
| Translation JSON (read) | `levante-assets-draft` | `translations/itembank/<task>/<locale>/item-bank-translations.json` |
| Approved audio (read) | `levante-assets-dev` | `audio/<locale>/<item_id>.mp3` |
| Pending audio (read) | `levante-assets-draft` | `audio/<locale>/<item_id>.mp3` |
| Generated audio (write) | `levante-assets-draft` only | `audio/<locale>/<item_id>.mp3` |

The approved (dev) bucket is never written. New clips go to draft for the [Partner Audio Approval Tool](README_PARTNER_AUDIO_APPROVAL.md).

### Decision logic (per item)

1. **Placeholder** (`NO APPROVED TRANSLATION`) → skip (always; no flag overrides).
2. **`force_regenerate`** → regenerate to draft.
3. **Config mismatch** (voice / model / service / locale in ID3 vs current config) → **fail fast** unless `config_change` is true. The flag is permission only; mismatches are verified from existing audio tags.
4. **Current clip in dev or draft** (text + config match) → skip.
5. **Otherwise** (text changed, or no clip) → generate to draft.

### GitHub Actions

**Actions → Regenerate Draft Audio → Run workflow**

| Input | Description |
|-------|-------------|
| `languages` | Dashboard locale codes (`es-AR`, `nl-NL`, …), comma/space-separated, or `all` (from `languageoptions.json` on dev). |
| `tasks` | `all` (every itembank task below) or one or more task folder names. |
| `dry_run` | Plan only; no synthesis or upload. |
| `config_change` | Allow regeneration when config changed but text is unchanged. |
| `force_regenerate` | Regenerate all non-placeholder strings. |

**Secrets:** `GOOGLE_APPLICATION_CREDENTIALS_DEV_JSON`, `ELEVEN_API_KEY` (or `ELEVENLABS_API_KEY`), `SLACK_WEBHOOK_URL` (optional).

**Artifacts:** `audio_regen_summary.json`, `report_links.json` (also uploaded under `reports/audio-regen/<run_id>/` on the draft bucket).

### Local run

```bash
pip install -r requirements_itembank_audio.txt

# .env in repo root (recommended):
# GOOGLE_APPLICATION_CREDENTIALS=secrets/devkey.json
# ELEVENLABS_API_KEY=...

python3 generate_itembank_audio.py \
  --languages nl-NL \
  --tasks general trog vocab \
  --dry-run
```

Boolean flags are presence-only: `--config-change`, not `--config-change true`.

### Locales and tasks

- **Locales** must appear in `languageoptions.json` on the dev bucket.
- **Translation JSON** uses the dashboard locale (e.g. `nl-NL`).
- **Audio paths** use the canonical locale (e.g. `audio/nl-NL/`). Dutch variants (`nl`, `nl-BE`, …) resolve to `nl-NL`.
- **Voice config** is loaded from `gs://levante-assets-dev/language_config.json` ([web dashboard](README_ADD_LANGUAGE.md)). Each language needs `service`, `voice`, and **`voice_id`**.

**Valid `--tasks` values** (folder names under `translations/itembank/`):

| Task folder |
|-------------|
| `child-survey` |
| `general` |
| `hearts-and-flowers` |
| `hostile-attribution` |
| `egma-math` |
| `matrix-reasoning` |
| `memory-game` |
| `mental-rotation` |
| `same-different-selection` |
| `theory-of-mind` |
| `trog` |
| `vocab` |

Use `all` to run every task in this list. Unknown names fail with an error listing valid values. Missing JSON for a task/locale is reported in the summary (`missing_translation_blob`) but does not stop other tasks.

### Pipeline (manual for now)

1. **Build itembank translations** (`translation-utilities` repo) → JSON to draft.  
2. **Regenerate Draft Audio** (this repo) → MP3s to draft.  
3. **Partner approval** → promotes approved audio to dev.
