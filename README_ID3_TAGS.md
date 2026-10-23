# ID3 tags on Levante audio

Every generated MP3 carries its own provenance. The file is the source of
truth for “what text, voice, model, and locale produced this clip,” so copies
across GCS buckets, laptops, and partner downloads stay inspectable without a
sidecar database.

This doc covers:

1. The tag schema
2. How `levante_translations` writes and reads tags
3. How `levante-web-dashboard` reads, displays, and extends them
4. How ROAR (or any similar item-bank TTS pipeline) can do the same

## Why embed tags in the MP3

Filenames (`audio/<lang_code>/<item_id>.mp3`) only identify the item. They do
not say which translation, voice, or model was used. Tags travel with the
bytes, so:

- Regeneration can compare the **file** to current translations/config.
- The dashboard Info modal can show what was actually synthesized.
- Partner approval can stamp `approved_by` / `approved_at` onto the same file.
- GCS copies and local `audio_files/` checkouts remain self-describing.

GCS object metadata is a **convenience mirror** (cheap to list; truncated
text). It is not a substitute for ID3. Regeneration always reads the MP3.

## Schema

Libraries: **mutagen** (Python, ID3v2.4, UTF-8 `encoding=3`) and **node-id3**
(Node, typically ID3v2.3). Custom fields are ID3v2 **TXXX** frames whose
`description` is the field name.

### Standard frames

| Python / JS key | ID3 frame | Typical value |
|---|---|---|
| `title` | TIT2 | `item_id` |
| `artist` | TPE1 | `Levante Framework - ElevenLabs` (Python) or `Levante Project` (dashboard regen) |
| `album` | TALB | Task label (`labels` / task slug) |
| `date` | TDRC | Year |
| `genre` | TCON | `Speech Synthesis` |
| `comment` | COMM | Human-readable `Levante Project - {service} - {voice} - {lang_code}` |
| `copyright` | TCOP (fallback TXXX `COPYRIGHT`) | CC BY-NC-SA 4.0 notice |

### Custom TXXX fields

Written by generation (`utilities.save_audio` and
`generate_itembank_audio.py`):

| TXXX description | Purpose |
|---|---|
| `original_translation_text` | **Regeneration anchor.** Source translation from JSON/CSV, not pronunciation-tweaked text. |
| `text` | Spoken/source text at generation time. Older files may only have this. |
| `lang_code` | Audio locale (`es-AR`, `de`, …). |
| `service` | `ElevenLabs` or `PlayHT`. |
| `voice` | Display name from language config. |
| `voice_id` | TTS provider voice id. |
| `voiceId` | Same as `voice_id` (legacy alias; Python `save_audio` writes both). |
| `model_id` | TTS model (`eleven_v3` by default). |
| `task` | Task slug from `labels`. |
| `created` | Timestamp when the MP3 was tagged. |

Written later by the **web dashboard** (not by batch generation):

| TXXX description | Purpose |
|---|---|
| `audio_enhanced_text` | Pronunciation / SSML-style rewrite actually sent to TTS, if different from the translation. |
| `used_audio_enhanced_text` | Whether enhanced text was used. |
| `source` | Origin of a dashboard re-save. |
| `version` | Dashboard version suffix (`v001`, …) when saving `_vNNN.mp3`. |
| `approved_by` | Partner / approver identity. |
| `approved_at` | Approval timestamp. |

Keep `original_translation_text` and `audio_enhanced_text` distinct. Freshness
checks compare the **source translation**, not the spoken rewrite.

## This repo (`levante_translations`)

### Write path

Both TTS backends call the same saver after synthesis:

- ElevenLabs: `ELabs/elevenlabs_tts.py` → `utilities.utilities.save_audio`
- PlayHT: `PlayHt/playHt_tts.py` → same `save_audio`

`save_audio` writes the MP3, then `write_id3_tags()`. Anything not in
`STANDARD_ID3_FIELDS` (`title`, `artist`, `album`, `date`, `genre`, `comment`,
`copyright`) becomes a TXXX frame.

The itembank generator (`generate_itembank_audio.py`) has a parallel
`_write_id3_tags` with the same field set (including `task`).

On GCS upload, a subset is copied onto the object:

`service`, `voice`, `voice_id`, `voiceId`, `model_id`, `lang_code`, `item_id`,
`task`, and `text` truncated to 500 characters.

### Read path and regeneration

`utilities/audio_validation.py`:

- `read_audio_metadata()` — standard frames + every TXXX `desc` → dict key
- `needs_regeneration()` flags a file when:
  1. The MP3 is missing locally
  2. `original_translation_text` (else `text`) differs from current translation
     after collapsing whitespace and ignoring `<br>` / `<p>`
  3. `voice`, `service`, or `lang_code` differ from config
  4. `model_id` differs, **only when** a model id is passed in

Existing-audio checks are **local** (`audio_files/`), not GCS. Sync first if
you need bucket state. Files with no readable ID3 are skipped unless
`--force-id`.

`generate_itembank_audio.py` uses the same comparison, and treats a
voice/model/service/locale mismatch as a fail-fast `config_change` unless
explicitly allowed.

ASR validation (`validate_audio/id3_utils.py`) looks up expected text from
TXXX (`text`, `original_translation_text`, …), then COMM / USLT / TIT2.

### Maintenance and tests

- `utilities/backfill_voice_tags.py`, `fix_audio_text_tags.py`,
  `backfill_german_audio_tags.py` — repair tags on existing MP3s
- `extract_vocab_id3_data.py` — harvest vocab from tags
- `tests/test_id3_metadata.py`, `tests/test_complete_audio_workflow.py`

Inspect a file:

```bash
python -c "from utilities.utilities import read_id3_tags; import json,sys; print(json.dumps(read_id3_tags(sys.argv[1]), indent=2, ensure_ascii=False))" path/to/item.mp3
```

## Web dashboard (`levante-web-dashboard`)

The dashboard does **not** generate the item bank in bulk. It reads tags for
QA, writes them when a user re-saves audio, and stamps approval.

| Piece | Role |
|---|---|
| `api/read-tags.js` | Download MP3 (head **and** tail — v2.3 vs v2.4 tag location), `NodeID3.read`, return standard + TXXX fields. Falls back to GCS object metadata if ID3 is unreadable. |
| `api/audio-metadata.js` | Voice / `voice_id` / `model_id` from TXXX (COMM as voice fallback). |
| `api/save-audio.js` | Re-encode with `NodeID3.write`: generation fields plus `audio_enhanced_text`, `used_audio_enhanced_text`, `source`, `version`. |
| `api/apply-approval-tags.js` | `NodeID3.update` of `approved_by` / `approved_at` only; other TXXX frames are preserved. |
| `api/move-audio-to-dev.js` | Promotion to approved audio; records whether approval tags were written. |
| `public/ts/audio.ts` | Info modal: file info, standard tags, `service`, `voice`, `lang_code`, `text`. |
| `scripts/backfill-dev-approval-id3-tags.js` and `scripts/retrofit-es-ar-id3-*.js` | One-off backfills. |

`CUSTOM_ID3_ENHANCEMENT.md` in that repo is a changelog for the Info button,
not the schema. Use this file as the source of truth.

## For ROAR colleagues

ROAR item-bank audio has the same problem Levante had: clips move between
buckets and machines, and a filename is not enough to know whether the file
matches the current item text or voice.

### Suggested minimal schema to copy

Write these on every generate (TXXX unless noted):

| Field | Why |
|---|---|
| `original_translation_text` (or `source_text`) | Compare to current item text. Never overwrite this with a pronunciation rewrite. |
| `text` | What was sent to TTS (may equal source, or an enhanced form). |
| `lang_code` | Locale of this file. |
| `voice` + `voice_id` | Config drift / voice change detection. |
| `model_id` | Model upgrades should regenerate. |
| `task` or `item_id` | TIT2 can hold `item_id`; keep task explicit if paths are flat. |
| `created` | Debug “when was this baked.” |

Optional later, without changing the regen anchor: `approved_by`,
`approved_at`, enhanced-text fields.

### Implementation sketch

1. **Write after TTS, before upload.** Python:

   ```python
   from mutagen.id3 import ID3, TIT2, TXXX
   from mutagen.mp3 import MP3

   audio = MP3(path, ID3=ID3)
   if audio.tags is None:
       audio.add_tags()
   audio.tags.add(TIT2(encoding=3, text=item_id))
   audio.tags.add(TXXX(encoding=3, desc="original_translation_text", text=source_text))
   audio.tags.add(TXXX(encoding=3, desc="voice_id", text=voice_id))
   audio.tags.add(TXXX(encoding=3, desc="model_id", text=model_id))
   audio.save()
   ```

   Node equivalent: `node-id3` `userDefinedText: [{ description, value }, ...]`.

2. **Regenerate when** the file is missing, source text (normalized) differs,
   or voice/model/locale differ from config. Ignore layout-only markup if your
   items use `<br>`/`<p>`.

3. **Mirror a short subset** to GCS custom metadata for listing; still read
   ID3 for decisions. Truncate long text in object metadata.

4. **Preserve unknown TXXX on update.** Approval stamps must use update/merge
   (`NodeID3.update` or read-modify-write), not a blank `write` that drops
   `original_translation_text`.

5. **Read both ends of the file** if you mix mutagen (often v2.4 at the
   start) and node-id3 (v2.3). Levante’s `read-tags.js` reads the first and
   last 64 KiB for this reason.

6. **Do not key regen off the spoken rewrite.** If you add phoneme/SSML
   hints, store them in a second field so a hint tweak does not look like a
   translation change (or vice versa).

Reuse in levante_translations repo if you want a reference implementation:
`utilities/utilities.py` (`write_id3_tags` / `read_id3_tags` / `save_audio`)
and `utilities/audio_validation.py` (`needs_regeneration`).
