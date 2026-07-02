#!/usr/bin/env python3
"""
Generate item-bank audio from draft-bucket JSON with bucket-first existence checks.

Source text (per task + locale):
  gs://<draft-bucket>/translations/itembank/<task>/<lang>/item-bank-translations.json

Existence check (read-only):
  gs://<approved-bucket>/audio/<locale>/<item_id>.mp3  (approved / authoritative)
  gs://<draft-bucket>/audio/<locale>/<item_id>.mp3     (pending approval)
  Locale is the canonical dashboard code (e.g. nl-NL); Dutch variants (nl, nl-BE, …) resolve to nl-NL.

Output (write target — draft bucket only):
  gs://<draft-bucket>/audio/<locale>/<item_id>.mp3

Decision logic per item (in strict priority order):
  1. Placeholder text ("NO APPROVED TRANSLATION") -> skip. Always. No flag overrides.
  2. --force-regenerate -> generate to draft.
  3. Config check (voice/model/service/lang changed in any existing clip)?
     -> BLOCKED unless --config-change; with flag -> continue to step 4.
  4. Text current in approved bucket? -> skip. Text current in draft? -> skip.
  5. Otherwise (text changed, or no clip) -> generate to draft.

Output goes to the draft bucket only.

Environment:
  ELEVENLABS_API_KEY or ELEVEN_API_KEY  — ElevenLabs TTS
  GOOGLE_APPLICATION_CREDENTIALS_JSON  — GCS service account (JSON string)
  GCP_SERVICE_ACCOUNT_JSON             — alias for the above
  GOOGLE_APPLICATION_CREDENTIALS       — path to service account key file (e.g. secrets/devkey.json)
  GOOGLE_APPLICATION_CREDENTIALS_DEV   — alias for local dev key file path
  GOOGLE_CLOUD_PROJECT                 — optional; used with gcloud ADC fallback
  ASSETS_DRAFT_BUCKET                  — draft bucket name (default: levante-assets-draft)
  ASSETS_DEV_BUCKET                    — approved bucket name (default: levante-assets-dev)
  ITEMBANK_PREFIX                      — translation prefix (default: translations/itembank/)
  ITEMBANK_OBJECT_NAME                 — JSON filename (default: item-bank-translations.json)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utilities.elevenlabs_model import DEFAULT_ELEVENLABS_MODEL_ID
import utilities.config as conf

try:
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, COMM, TXXX, TCOP
    from mutagen.mp3 import MP3
    _MUTAGEN = True
    _TCOP = True
except ImportError:
    _MUTAGEN = False
    _TCOP = False

DEFAULT_DRAFT_BUCKET = "levante-assets-draft"
DEFAULT_APPROVED_BUCKET = "levante-assets-dev"
DEFAULT_PREFIX = "translations/itembank/"
DEFAULT_OBJECT_NAME = "item-bank-translations.json"
LANGUAGEOPTIONS_PATH = "translations/dashboard-consolidated-flat/languageoptions.json"
# Dashboard locale keys in languageoptions.json → voice-config lang_code when no exact match.
DASHBOARD_LOCALE_TO_VOICE_LANG: Dict[str, str] = {
    "de-DE": "de",
    "nl-NL": "nl",
}
# Any locale whose prefix matches but is not already canonical → audio bucket folder.
AUDIO_LOCALE_CANONICAL_BY_PREFIX: Dict[str, str] = {
    "nl": "nl-NL",
}
# Canonical folder names under translations/itembank/ (shared with build-itembank-translations).
ITEMBANK_TASK_FOLDERS: Tuple[str, ...] = (
    "child-survey",
    "general",
    "hearts-and-flowers",
    "hostile-attribution",
    "egma-math",
    "matrix-reasoning",
    "memory-game",
    "mental-rotation",
    "same-different-selection",
    "theory-of-mind",
    "trog",
    "vocab",
)
OUTPUT_FORMAT = "mp3_44100_128"

_PLACEHOLDER_TRANSLATIONS = {"NO APPROVED TRANSLATION"}

_STANDARD_ID3_FIELDS = {"title", "artist", "album", "date", "genre", "comment", "copyright"}

_AUDIO_TAGS_TEMPLATE: Dict[str, Any] = {
    "title": None,
    "artist": "Levante Project",
    "album": None,
    "genre": "Speech Synthesis",
    "comment": None,
    "copyright": (
        "This file was created for the LEVANTE project and is released under a "
        "Creative Commons BY-NC-SA 4.0 license"
    ),
    "text": None,
    "created": None,
    "lang_code": None,
    "service": None,
    "voice": None,
    "voice_id": None,
    "model_id": None,
    "original_translation_text": None,
}


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class VoiceConfigEntry:
    """ElevenLabs voice settings from language_config (keyed by config lang_code)."""
    config_lang_code: str
    display_name: str
    service: str
    voice: str
    voice_id: str


@dataclass
class LanguageProfile:
    locale_key: str          # dashboard / translation locale (e.g. nl-NL)
    audio_lang_code: str     # canonical audio bucket folder (e.g. nl-NL, never nl)
    display_name: str
    service: str
    voice: str
    voice_id: str


@dataclass
class ItemAction:
    task: str
    lang_code: str
    item_id: str
    text: str
    action: str   # placeholder | skip | generate | blocked
    tier: Optional[str]   # dev | draft | None
    reason: str


@dataclass
class LangStats:
    skipped_dev: int = 0
    skipped_draft: int = 0
    generated: int = 0
    blocked: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    placeholders: int = 0
    missing_translation_blob: int = 0


@dataclass
class RunStats:
    skipped_dev: int = 0
    skipped_draft: int = 0
    generated: int = 0
    blocked: int = 0
    placeholders: int = 0
    errors: int = 0
    missing_translation_blob: int = 0
    per_lang: Dict[str, LangStats] = field(default_factory=dict)

    def lang(self, code: str) -> LangStats:
        if code not in self.per_lang:
            self.per_lang[code] = LangStats()
        return self.per_lang[code]



# ── ID3 ───────────────────────────────────────────────────────────────────────

def _read_id3_tags(file_path: str) -> Dict[str, str]:
    if not _MUTAGEN or not os.path.isfile(file_path):
        return {}
    try:
        audio_file = MP3(file_path, ID3=ID3)
        if audio_file.tags is None:
            return {}
        tags: Dict[str, str] = {}
        for frame_key, tag_key in (
            ("TIT2", "title"),
            ("TPE1", "artist"),
            ("TALB", "album"),
            ("TDRC", "date"),
            ("TCON", "genre"),
        ):
            if frame_key in audio_file.tags:
                tags[tag_key] = str(audio_file.tags[frame_key][0])
        for frame in audio_file.tags.getall("COMM"):
            if frame.text:
                tags["comment"] = str(frame.text[0])
        for frame in audio_file.tags.getall("TXXX"):
            if frame.desc and frame.text:
                tags[str(frame.desc)] = str(frame.text[0])
        return tags
    except Exception:
        return {}


def _write_id3_tags(file_path: str, tags: Dict[str, Any]) -> bool:
    if not _MUTAGEN:
        print("Warning: mutagen not installed; skipping ID3 tags")
        return False
    try:
        audio_file = MP3(file_path, ID3=ID3)
        if audio_file.tags is None:
            audio_file.add_tags()
        if tags.get("title"):
            audio_file.tags.add(TIT2(encoding=3, text=tags["title"]))
        if tags.get("artist"):
            audio_file.tags.add(TPE1(encoding=3, text=tags["artist"]))
        if tags.get("album"):
            audio_file.tags.add(TALB(encoding=3, text=tags["album"]))
        if tags.get("date"):
            audio_file.tags.add(TDRC(encoding=3, text=tags["date"]))
        if tags.get("genre"):
            audio_file.tags.add(TCON(encoding=3, text=tags["genre"]))
        if tags.get("comment"):
            audio_file.tags.add(COMM(encoding=3, lang="eng", desc="", text=tags["comment"]))
        if tags.get("copyright"):
            if _TCOP:
                audio_file.tags.add(TCOP(encoding=3, text=tags["copyright"]))
            else:
                audio_file.tags.add(TXXX(encoding=3, desc="COPYRIGHT", text=tags["copyright"]))
        for field_name, field_value in tags.items():
            if field_name not in _STANDARD_ID3_FIELDS and field_value:
                audio_file.tags.add(
                    TXXX(encoding=3, desc=field_name, text=str(field_value))
                )
        audio_file.save()
        return True
    except Exception as exc:
        print(f"Warning: could not write ID3 tags to {file_path}: {exc}")
        return False


# ── Text normalization + diff classification ──────────────────────────────────

def _normalize_text(value: str) -> str:
    """
    Collapse whitespace and treat <br>/<p> markup as spaces.
    Matches the normalization in utilities/audio_validation.needs_regeneration.
    """
    text = value or ""
    text = re.sub(r"<\s*/?\s*(br|p)\s*/?\s*>", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _classify_diff(
    audio_path: str,
    current_text: str,
    profile: LanguageProfile,
    model_id: str,
) -> Tuple[str, str]:
    """
    Compare existing MP3 ID3 tags against current text + config.

    Returns (reason, detail) where reason is one of:
      'match'         - everything is current; no regeneration needed
      'no_tags'       - file present but ID3 unreadable; treat as needing generation
      'text'          - translation text has changed
      'config_change' - text matches but voice/service/lang/model differs
    """
    tags = _read_id3_tags(audio_path)
    if not tags:
        return "no_tags", "existing audio has no readable ID3 tags"

    # Check config first — a voice/model/service/lang change blocks the run
    # regardless of whether the text also changed.
    stored_voice = tags.get("voice", "").strip()
    if stored_voice != profile.voice:
        return "config_change", f"voice: '{stored_voice}' -> '{profile.voice}'"

    stored_service = tags.get("service", "").strip()
    if stored_service != profile.service:
        return "config_change", f"service: '{stored_service}' -> '{profile.service}'"

    stored_lang = tags.get("lang_code", "").strip()
    if stored_lang != profile.audio_lang_code:
        return "config_change", (
            f"lang_code: '{stored_lang}' -> '{profile.audio_lang_code}'"
        )

    stored_model = tags.get("model_id", "").strip()
    if stored_model != str(model_id).strip():
        return "config_change", f"model: '{stored_model}' -> '{model_id}'"

    # Config matches; now check translation text.
    stored_raw = tags.get("original_translation_text") or ""
    stored = _normalize_text(stored_raw)
    current = _normalize_text(current_text)

    if stored != current:
        return "text", f"text changed: '{stored[:50]}' -> '{current[:50]}'"

    return "match", "up to date"


# ── GCS helpers ───────────────────────────────────────────────────────────────

def _init_gcs_client():
    try:
        from google.cloud import storage  # type: ignore
        from google.oauth2 import service_account  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-storage is required. Install with: pip install google-cloud-storage"
        ) from exc

    creds_json = (
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        or os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    )
    if creds_json:
        info = json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(info)
        return storage.Client(credentials=credentials, project=info.get("project_id"))

    creds_path = (
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS_DEV")
    )
    if creds_path:
        path = Path(creds_path.strip()).expanduser()
        if not path.is_absolute():
            path = REPO_ROOT / path
        if not path.is_file():
            raise RuntimeError(
                f"Service account key not found: {path}\n"
                "Set GOOGLE_APPLICATION_CREDENTIALS in .env to the key file path "
                "(e.g. secrets/devkey.json)."
            )
        credentials = service_account.Credentials.from_service_account_file(str(path))
        with open(path, encoding="utf-8") as f:
            info = json.load(f)
        return storage.Client(credentials=credentials, project=info.get("project_id"))

    # Fall back to Application Default Credentials (gcloud auth application-default login)
    project = (
        os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCP_PROJECT")
        or os.getenv("GCLOUD_PROJECT")
    )
    try:
        if project:
            return storage.Client(project=project)
        return storage.Client()
    except Exception as exc:
        raise RuntimeError(
            "No GCS credentials found. Set one of:\n"
            "  GOOGLE_APPLICATION_CREDENTIALS=secrets/your-key.json\n"
            "  GOOGLE_APPLICATION_CREDENTIALS_JSON='{\"type\":\"service_account\",...}'\n"
            "  GCP_SERVICE_ACCOUNT_JSON (same as JSON string above)\n"
            "Or use gcloud ADC: gcloud auth application-default login\n"
            "  (set GOOGLE_CLOUD_PROJECT if you see quota-project warnings)\n"
            f"\nADC error: {exc}"
        ) from exc


def _download_audio_to_temp(
    bucket,
    item_id: str,
    lang_code: str,
    dest_dir: Path,
) -> Optional[Path]:
    """
    Download audio/<lang_code>/<item_id>.mp3 from bucket into dest_dir.
    Returns the local Path on success, None if the blob does not exist.
    """
    gcs_path = f"audio/{lang_code}/{item_id}.mp3"
    blob = bucket.blob(gcs_path)
    if not blob.exists():
        return None
    dest = dest_dir / f"{item_id}.mp3"
    dest.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(dest))
    return dest


def _upload_audio(
    bucket,
    local_path: Path,
    *,
    item_id: str,
    task: str,
    text: str,
    profile: LanguageProfile,
    model_id: str,
) -> None:
    """Upload a generated MP3 to draft bucket with GCS object metadata."""
    gcs_path = f"audio/{profile.audio_lang_code}/{item_id}.mp3"
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(str(local_path), content_type="audio/mpeg")
    blob.metadata = {
        "service": profile.service,
        "voice": profile.voice,
        "voice_id": profile.voice_id,
        "model_id": model_id,
        "lang_code": profile.audio_lang_code,
        "item_id": item_id,
        "task": task,
        "text": text[:500],
    }
    blob.patch()
    print(f"  ✅ uploaded gs://{bucket.name}/{gcs_path}")


# ── Language options / locale validation ──────────────────────────────────────

def _fetch_languageoptions(approved_bucket) -> Dict[str, Any]:
    """
    Fetch languageoptions.json from the approved bucket, with HTTPS public fallback.
    Raises RuntimeError if neither succeeds.
    """
    blob = approved_bucket.blob(LANGUAGEOPTIONS_PATH)
    try:
        content = blob.download_as_text(encoding="utf-8")
        return json.loads(content)
    except Exception as gcs_err:
        print(
            f"Warning: GCS fetch of languageoptions.json failed ({gcs_err}); "
            "trying public HTTPS URL."
        )

    public_url = (
        f"https://storage.googleapis.com/{approved_bucket.name}/{LANGUAGEOPTIONS_PATH}"
    )
    try:
        with urllib.request.urlopen(public_url, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as https_err:
        raise RuntimeError(
            f"Could not fetch languageoptions.json via GCS or public URL: {https_err}"
        )


def resolve_all_locales(approved_bucket) -> List[str]:
    """
    Return all locale codes listed in languageoptions.json, including testing:true entries.
    Truly in-development languages are absent from the file entirely.
    """
    options = _fetch_languageoptions(approved_bucket)
    locales = sorted(options.keys())
    print(f"languageoptions.json: {len(locales)} locale(s): {', '.join(locales)}")
    return locales


def validate_requested_locales(requested: List[str], approved_bucket) -> None:
    """
    Hard-fail if any explicitly-requested locale is absent from languageoptions.json.
    This prevents generating audio for languages not yet released on the dashboard.
    """
    options = _fetch_languageoptions(approved_bucket)
    missing = [loc for loc in requested if loc not in options]
    if missing:
        raise SystemExit(
            f"❌ Locale(s) not found in languageoptions.json: {', '.join(missing)}\n"
            "   Release the language on the dashboard first (add it to languageoptions.json), "
            "then re-run."
        )


# ── Language profiles ─────────────────────────────────────────────────────────

def resolve_audio_locale(locale: str) -> str:
    """
    Canonical locale for audio bucket paths and ID3 lang_code tags.
    Dutch variants (nl, nl-BE, …) all resolve to nl-NL.
    """
    loc = str(locale or "").strip().replace("_", "-")
    if not loc:
        return loc
    for prefix, canonical in AUDIO_LOCALE_CANONICAL_BY_PREFIX.items():
        if loc.lower().startswith(prefix) and loc.lower() != canonical.lower():
            return canonical
    return loc


def _lookup_voice_config(
    requested: str, by_code: Dict[str, VoiceConfigEntry]
) -> Tuple[Optional[VoiceConfigEntry], Optional[str]]:
    """
    Resolve voice config for a dashboard locale key.
    Returns (entry, fallback_code_tried) — fallback_code is set when a mapped
    short code was used (e.g. nl-NL → nl).
    """
    entry = by_code.get(requested)
    if entry:
        return entry, None
    fallback = DASHBOARD_LOCALE_TO_VOICE_LANG.get(requested)
    if fallback:
        entry = by_code.get(fallback)
        if entry:
            return entry, fallback
    return None, fallback


def _build_lang_profiles(requested: List[str]) -> Dict[str, LanguageProfile]:
    """
    Map dashboard locale keys to ElevenLabs voice config from conf.get_languages().
    JSON paths use locale_key (e.g. nl-NL); audio paths use audio_lang_code (also
    nl-NL — short codes like nl are never used for bucket folders).
    Hard-fails (no warn-and-skip) if any locale is missing or misconfigured.
    """
    languages = conf.get_languages() or {}
    by_code: Dict[str, VoiceConfigEntry] = {}

    for display_name, cfg in languages.items():
        code = str(cfg.get("lang_code") or "").strip()
        if not code:
            continue
        entry = VoiceConfigEntry(
            config_lang_code=code,
            display_name=display_name,
            service=str(cfg.get("service") or "").strip(),
            voice=str(cfg.get("voice") or "").strip(),
            voice_id=str(cfg.get("voice_id") or "").strip(),
        )
        existing = by_code.get(code)
        if existing is None:
            by_code[code] = entry
            continue
        # Same lang_code under multiple display names (e.g. "German" + "German (Germany)").
        # Prefer the entry that has voice_id; remote dashboard names usually win over
        # legacy local fallback aliases.
        if entry.voice_id and not existing.voice_id:
            by_code[code] = entry
        elif entry.voice_id or not existing.voice_id:
            if "(" in display_name and "(" not in existing.display_name:
                by_code[code] = entry

    profiles: Dict[str, LanguageProfile] = {}
    config_errors: List[str] = []

    for code in requested:
        voice_cfg, fallback = _lookup_voice_config(code, by_code)
        if not voice_cfg:
            hint = ""
            if fallback:
                hint = f" (also tried voice config lang_code {fallback!r})"
            config_errors.append(
                f"  {code}: no entry in conf.get_languages(){hint} — add it to "
                "utilities/config.py or language_config.json in the dev bucket"
            )
            continue
        if voice_cfg.service != "ElevenLabs":
            config_errors.append(
                f"  {code} ({voice_cfg.display_name}): service='{voice_cfg.service}'; "
                "only ElevenLabs is supported by this script"
            )
            continue
        if not voice_cfg.voice_id:
            resolved = f"{code} → {voice_cfg.config_lang_code}" if fallback else code
            config_errors.append(
                f"  {resolved} ({voice_cfg.display_name}): missing voice_id in language config"
            )
            continue
        audio_lang_code = resolve_audio_locale(code)
        profiles[code] = LanguageProfile(
            locale_key=code,
            audio_lang_code=audio_lang_code,
            display_name=voice_cfg.display_name,
            service=voice_cfg.service,
            voice=voice_cfg.voice,
            voice_id=voice_cfg.voice_id,
        )

    if config_errors:
        raise SystemExit(
            "❌ Language config errors — fix before generating:\n"
            + "\n".join(config_errors)
        )
    return profiles


# ── Translation fetching ──────────────────────────────────────────────────────

def fetch_translations(
    bucket,
    prefix: str,
    task: str,
    lang_code: str,
    object_name: str,
) -> Optional[Dict[str, str]]:
    """
    GET the exact translation JSON for one (task, locale) pair.
    Returns None if the blob does not exist.
    Filters out empty/null values and placeholder strings.
    """
    gcs_path = f"{prefix}{task}/{lang_code}/{object_name}"
    blob = bucket.blob(gcs_path)
    if not blob.exists():
        return None

    raw = blob.download_as_bytes().decode("utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Tolerate trailing commas (common in hand-edited JSON)
        sanitized = re.sub(r",(\s*[}\]])", r"\1", raw)
        payload = json.loads(sanitized)

    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at gs://{bucket.name}/{gcs_path}")

    return {
        str(k).strip(): str(v).strip()
        for k, v in payload.items()
        if str(k).strip() and v is not None and str(v).strip()
    }


def resolve_task_lists(
    lang_codes: List[str],
    tasks_arg: List[str],
) -> Dict[str, List[str]]:
    """
    Resolve --tasks to per-locale task folder lists.
    ``all`` expands to every entry in ITEMBANK_TASK_FOLDERS (not GCS discovery).
    """
    if len(tasks_arg) == 1 and tasks_arg[0].lower() == "all":
        selected = list(ITEMBANK_TASK_FOLDERS)
        print(f"Tasks (--tasks all): {len(selected)} — {', '.join(selected)}")
        return {lang: list(selected) for lang in lang_codes}

    names = [t.strip() for t in tasks_arg if t.strip()]
    if not names:
        raise SystemExit("❌ --tasks: each value must be non-empty.")
    if any(n.lower() == "all" for n in names):
        raise SystemExit("❌ Use '--tasks all' alone, not mixed with other task names.")

    bad = [n for n in names if n not in ITEMBANK_TASK_FOLDERS]
    if bad:
        raise SystemExit(
            f"❌ Unknown task(s): {bad!r}. Use 'all' or one or more of: "
            f"{list(ITEMBANK_TASK_FOLDERS)}"
        )
    return {lang: list(names) for lang in lang_codes}


# ── ElevenLabs synthesis ──────────────────────────────────────────────────────

def _elevenlabs_api_key() -> str:
    key = (
        os.getenv("ELEVENLABS_API_KEY") or os.getenv("ELEVEN_API_KEY") or ""
    ).strip()
    if not key:
        raise RuntimeError(
            "Missing ElevenLabs API key. Set ELEVENLABS_API_KEY (or ELEVEN_API_KEY) "
            "in .env or CI secrets."
        )
    return key


def _synthesize_mp3(text: str, voice_id: str, model_id: str) -> bytes:
    from elevenlabs.client import ElevenLabs  # type: ignore

    client = ElevenLabs(api_key=_elevenlabs_api_key())
    chunks = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        output_format=OUTPUT_FORMAT,
    )
    if hasattr(chunks, "content"):
        return chunks.content
    if isinstance(chunks, (bytes, bytearray)):
        return bytes(chunks)
    return b"".join(chunks)


def _write_tags(
    mp3_path: Path,
    *,
    item_id: str,
    task: str,
    text: str,
    profile: LanguageProfile,
    model_id: str,
) -> None:
    tags = _AUDIO_TAGS_TEMPLATE.copy()
    now = datetime.now(timezone.utc).isoformat()
    tags.update(
        {
            "title": item_id,
            "artist": f"Levante Framework - {profile.service}",
            "album": task,
            "date": str(datetime.now(timezone.utc).year),
            "created": now,
            "lang_code": profile.audio_lang_code,
            "service": profile.service,
            "voice": profile.voice,
            "voice_id": profile.voice_id,
            "model_id": model_id,
            "task": task,
            "text": text,
            "original_translation_text": text,
            "comment": (
                f"Levante Project - {profile.service} - {profile.voice} - {profile.audio_lang_code}"
            ),
        }
    )
    _write_id3_tags(str(mp3_path), tags)


# ── Core decision logic ───────────────────────────────────────────────────────

def decide_action(
    *,
    item_id: str,
    text: str,
    task: str,
    profile: LanguageProfile,
    model_id: str,
    approved_bucket,
    draft_bucket,
    force_regenerate: bool,
    config_change: bool,
    check_dir: Path,
) -> ItemAction:
    """
    Decide what to do with one item. Downloads clips to check_dir as needed for ID3 comparison.
    The approved bucket and draft bucket are both read-only in this function.
    """
    def _make(action: str, tier: Optional[str], reason: str) -> ItemAction:
        return ItemAction(
            task=task, lang_code=profile.locale_key, item_id=item_id,
            text=text, action=action, tier=tier, reason=reason,
        )

    # Step 0: placeholder — absolute skip; no flag overrides this
    if str(text).strip().upper() in _PLACEHOLDER_TRANSLATIONS:
        return _make("placeholder", None, "NO APPROVED TRANSLATION — skip always")

    # Step 1: force regenerate (non-placeholder items only)
    if force_regenerate:
        return _make("generate", None, "--force-regenerate")

    # Pass A: config-change check — fail fast or regenerate before any text work.
    # _classify_diff checks config before text, so config_change is returned even
    # when text has also changed. The --config-change flag is permission; we always
    # verify the actual diff rather than taking the user's word for it.
    diffs: Dict[str, Tuple[str, str]] = {}

    for tier_name, bucket in (("dev", approved_bucket), ("draft", draft_bucket)):
        dest_dir = check_dir / tier_name / profile.audio_lang_code
        downloaded = _download_audio_to_temp(
            bucket, item_id, profile.audio_lang_code, dest_dir
        )
        if downloaded is None:
            continue
        reason, detail = _classify_diff(str(downloaded), text, profile, model_id)
        diffs[tier_name] = (reason, detail)
        if reason == "config_change":
            # Config mismatch verified. If the flag is not set, block immediately.
            # If it is set, generate immediately — no point checking text currency
            # since the voice/model/service changed and everything needs regeneration.
            if not config_change:
                return _make("blocked", tier_name, f"config-change required: {detail}")
            return _make("generate", tier_name, f"config-change verified and allowed: {detail}")

    # Pass B: no config mismatch. Is there a fully current clip (text + config match)?
    for tier_name in ("dev", "draft"):
        if tier_name not in diffs:
            continue
        reason, detail = diffs[tier_name]
        if reason == "match":
            return _make("skip", tier_name, detail)

    # Nothing current; text changed or no clip exists in either bucket
    return _make("generate", None, "new or text changed")


# ── Planning pass (no synthesis) ──────────────────────────────────────────────

def plan_all_actions(
    *,
    client,
    draft_bucket_name: str,
    approved_bucket_name: str,
    prefix: str,
    object_name: str,
    profiles: Dict[str, LanguageProfile],
    task_map: Dict[str, List[str]],
    model_id: str,
    force_regenerate: bool,
    config_change: bool,
    check_dir: Path,
    stats: RunStats,
) -> List[ItemAction]:
    """
    First pass: decide action for every (locale, task, item). No synthesis or upload.
    Downloads clips from both buckets as needed to read ID3 tags.
    """
    approved_bucket = client.bucket(approved_bucket_name)
    draft_bucket = client.bucket(draft_bucket_name)

    actions: List[ItemAction] = []

    for lang_code, tasks in task_map.items():
        profile = profiles[lang_code]
        if not tasks:
            print(f"\n⚠️  No tasks to plan for {lang_code}")
            continue

        for task in tasks:
            print(f"\n{'─' * 60}")
            print(f"Planning: task={task} | locale={lang_code} | voice={profile.voice}")

            translations = fetch_translations(
                draft_bucket, prefix, task, lang_code, object_name
            )
            if translations is None:
                print(
                    f"  ⚠️  No translation JSON: "
                    f"gs://{draft_bucket_name}/{prefix}{task}/{lang_code}/{object_name}"
                )
                stats.missing_translation_blob += 1
                stats.lang(lang_code).missing_translation_blob += 1
                continue

            print(f"  {len(translations)} string(s) in JSON")

            for item_id, text in sorted(translations.items()):
                action = decide_action(
                    item_id=item_id,
                    text=text,
                    task=task,
                    profile=profile,
                    model_id=model_id,
                    approved_bucket=approved_bucket,
                    draft_bucket=draft_bucket,
                    force_regenerate=force_regenerate,
                    config_change=config_change,
                    check_dir=check_dir,
                )
                actions.append(action)

                indicator = {
                    "placeholder": "⏭️ ",
                    "skip": "✅",
                    "generate": "🔄",
                    "blocked": "🚫",
                }[action.action]
                tier_tag = f" [{action.tier}]" if action.tier else ""
                print(f"  {indicator} {item_id}{tier_tag}: {action.reason}")

    return actions


# ── Tally planned actions into RunStats ───────────────────────────────────────

def _tally_actions(actions: List[ItemAction], stats: RunStats) -> None:
    """Update stats counters from the planning pass (generates/errors tallied in execute)."""
    for a in actions:
        ls = stats.lang(a.lang_code)
        if a.action == "placeholder":
            stats.placeholders += 1
            ls.placeholders += 1
        elif a.action == "skip":
            if a.tier == "dev":
                stats.skipped_dev += 1
                ls.skipped_dev += 1
            else:
                stats.skipped_draft += 1
                ls.skipped_draft += 1
        elif a.action == "blocked":
            stats.blocked += 1
            ls.blocked.append(a.item_id)
        # generate + errors are tallied during execute_actions


# ── Execution pass (synthesis + upload) ───────────────────────────────────────

def execute_actions(
    *,
    actions: List[ItemAction],
    profiles: Dict[str, LanguageProfile],
    draft_bucket,
    model_id: str,
    out_dir: Path,
    stats: RunStats,
    dry_run: bool,
) -> None:
    """
    Second pass: synthesize and upload items with action='generate'.
    No writes to the approved bucket.
    """
    to_generate = [a for a in actions if a.action == "generate"]
    if not to_generate:
        print("\nNothing to generate.")
        return

    print(f"\n{'=' * 60}")
    print(f"Generating {len(to_generate)} clip(s) (dry_run={dry_run})...")

    for action in to_generate:
        profile = profiles[action.lang_code]
        print(f"\n  🎵 [{action.lang_code}] {action.item_id}: {action.reason}")

        if dry_run:
            print("    --dry-run: skipping synthesis and upload")
            stats.generated += 1
            stats.lang(action.lang_code).generated += 1
            continue

        try:
            audio_bytes = _synthesize_mp3(action.text, profile.voice_id, model_id)
            out_path = out_dir / profile.audio_lang_code / f"{action.item_id}.mp3"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(audio_bytes)
            _write_tags(
                out_path,
                item_id=action.item_id,
                task=action.task,
                text=action.text,
                profile=profile,
                model_id=model_id,
            )
            _upload_audio(
                draft_bucket,
                out_path,
                item_id=action.item_id,
                task=action.task,
                text=action.text,
                profile=profile,
                model_id=model_id,
            )
            stats.generated += 1
            stats.lang(action.lang_code).generated += 1
        except Exception as exc:
            print(f"  ❌ {action.item_id}: {exc}")
            stats.errors += 1
            stats.lang(action.lang_code).errors.append(action.item_id)


# ── Reporting ─────────────────────────────────────────────────────────────────

def write_summary(
    stats: RunStats, actions: List[ItemAction], dry_run: bool
) -> Path:
    """Write audio_regen_summary.json for workflow artifact upload and Slack."""
    per_lang: Dict[str, Any] = {}
    for code, ls in stats.per_lang.items():
        generated_items = [
            a.item_id for a in actions if a.lang_code == code and a.action == "generate"
        ]
        per_lang[code] = {
            "skipped_dev": ls.skipped_dev,
            "skipped_draft": ls.skipped_draft,
            "generated": ls.generated,
            "blocked_count": len(ls.blocked),
            "blocked_items": ls.blocked[:50],
            "error_count": len(ls.errors),
            "error_items": ls.errors[:20],
            "placeholders": ls.placeholders,
            "missing_translation_blob": ls.missing_translation_blob,
            "generated_items_preview": generated_items[:25],
        }

    summary = {
        "dry_run": dry_run,
        "skipped_dev": stats.skipped_dev,
        "skipped_draft": stats.skipped_draft,
        "generated": stats.generated,
        "blocked": stats.blocked,
        "placeholders": stats.placeholders,
        "errors": stats.errors,
        "missing_translation_blob": stats.missing_translation_blob,
        "languages": per_lang,
    }
    out = Path("audio_regen_summary.json")
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def print_summary(stats: RunStats) -> None:
    print(f"\n{'=' * 60}")
    print("Run summary")
    print(f"  Skipped — approved (dev):   {stats.skipped_dev}")
    print(f"  Skipped — pending (draft):  {stats.skipped_draft}")
    print(f"  Generated to draft:         {stats.generated}")
    print(f"  Blocked (config mismatch):  {stats.blocked}")
    print(f"  Placeholders (always skip): {stats.placeholders}")
    print(f"  Errors:                     {stats.errors}")
    print(f"  Missing translation JSON:   {stats.missing_translation_blob}")


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate item-bank audio from draft-bucket JSON (bucket-first, no CSV).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_itembank_audio.py --languages es-AR --tasks general trog
  python generate_itembank_audio.py --languages all --tasks all
  python generate_itembank_audio.py --languages de-DE es-CO --tasks child-survey --dry-run
  python generate_itembank_audio.py --languages es-AR --tasks all --config-change
  python generate_itembank_audio.py --languages all --tasks all --force-regenerate

  # Comma-separated values also work (useful from CI inputs):
  python generate_itembank_audio.py --languages es-AR,de-DE --tasks general,trog
        """.strip(),
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        required=True,
        metavar="LOCALE",
        help=(
            'BCP-47 locale codes (e.g. es-AR de-DE) or "all" to use '
            "languageoptions.json from the approved bucket."
        ),
    )
    parser.add_argument(
        "--tasks",
        nargs="+",
        required=True,
        metavar="TASK",
        help=(
            'Task folder names under translations/itembank/ (e.g. general trog child-survey), '
            f'"all" for every configured task ({len(ITEMBANK_TASK_FOLDERS)} folders). '
            f"Valid: {', '.join(ITEMBANK_TASK_FOLDERS)}."
        ),
    )
    parser.add_argument(
        "--config-change",
        action="store_true",
        help=(
            "Permit regeneration when voice/model/service/lang config differs from existing audio. "
            "Without this flag, config mismatches cause a hard fail before any generation."
        ),
    )
    parser.add_argument(
        "--force-regenerate",
        action="store_true",
        help=(
            "Regenerate every non-placeholder string unconditionally, "
            "ignoring existing clips in both buckets."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan and report decisions only; do not synthesize or upload anything.",
    )
    parser.add_argument(
        "--bucket",
        default=(
            os.getenv("ASSETS_DRAFT_BUCKET")
            or os.getenv("TRANSLATIONS_DRAFT_BUCKET")
            or DEFAULT_DRAFT_BUCKET
        ),
        help=(
            f"Draft GCS bucket — source of translation JSON and target for generated audio "
            f"(default: {DEFAULT_DRAFT_BUCKET})."
        ),
    )
    parser.add_argument(
        "--approved-bucket",
        default=os.getenv("ASSETS_DEV_BUCKET") or DEFAULT_APPROVED_BUCKET,
        help=(
            f"Approved GCS bucket — read-only existence check for approved clips "
            f"(default: {DEFAULT_APPROVED_BUCKET})."
        ),
    )
    parser.add_argument(
        "--prefix",
        default=os.getenv("ITEMBANK_PREFIX", DEFAULT_PREFIX),
        help=f"Itembank prefix in the draft bucket (default: {DEFAULT_PREFIX}).",
    )
    parser.add_argument(
        "--object-name",
        default=os.getenv("ITEMBANK_OBJECT_NAME", DEFAULT_OBJECT_NAME),
        help=f"Translation JSON filename per task/locale (default: {DEFAULT_OBJECT_NAME}).",
    )
    parser.add_argument(
        "--model-id",
        default=None,
        help=(
            f"Override ElevenLabs model_id "
            f"(default: {DEFAULT_ELEVENLABS_MODEL_ID} from utilities/elevenlabs_model.py). "
            "Changing this from the default is a config-change and requires --config-change "
            "when existing audio used a different model."
        ),
    )
    return parser.parse_args()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    # Load .env for local runs
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except Exception:
        pass

    args = parse_args()
    prefix = args.prefix if args.prefix.endswith("/") else f"{args.prefix}/"
    model_id = args.model_id or DEFAULT_ELEVENLABS_MODEL_ID

    # Normalise comma-separated or space-separated inputs from CI
    languages_raw = [
        loc.strip()
        for item in args.languages
        for loc in item.split(",")
        if loc.strip()
    ]
    tasks_raw = [
        t.strip()
        for item in args.tasks
        for t in item.split(",")
        if t.strip()
    ]

    print(f"{'=' * 60}")
    print(f"Levante Draft Audio Regeneration")
    print(f"  Model:            {model_id}")
    print(f"  Draft bucket:     {args.bucket}")
    print(f"  Approved bucket:  {args.approved_bucket} (read-only)")
    print(f"  Languages input:  {languages_raw}")
    print(f"  Tasks input:      {tasks_raw}")
    print(f"  --config-change:  {args.config_change}")
    print(f"  --force-regen:    {args.force_regenerate}")
    print(f"  --dry-run:        {args.dry_run}")

    # ── Init GCS ──────────────────────────────────────────────────────────────
    try:
        client = _init_gcs_client()
    except Exception as exc:
        print(f"\n❌ GCS client error: {exc}")
        return 1

    approved_bucket_handle = client.bucket(args.approved_bucket)
    draft_bucket_handle = client.bucket(args.bucket)

    # ── Resolve locales ───────────────────────────────────────────────────────
    if len(languages_raw) == 1 and languages_raw[0].lower() == "all":
        try:
            requested_locales = resolve_all_locales(approved_bucket_handle)
        except Exception as exc:
            print(f"\n❌ {exc}")
            return 1
    else:
        requested_locales = languages_raw
        try:
            validate_requested_locales(requested_locales, approved_bucket_handle)
        except SystemExit as exc:
            print(exc)
            return 1

    print(f"\nLocales to process: {', '.join(requested_locales)}")

    # ── Validate voice config — hard fail pre-generation ──────────────────────
    try:
        profiles = _build_lang_profiles(requested_locales)
    except SystemExit as exc:
        print(exc)
        return 1

    # ── Verify ElevenLabs key exists (fail fast before network work) ──────────
    if not args.dry_run:
        try:
            _elevenlabs_api_key()
        except RuntimeError as exc:
            print(f"\n❌ {exc}")
            return 1

    # ── Resolve tasks ─────────────────────────────────────────────────────────
    lang_codes = list(profiles.keys())
    task_map = resolve_task_lists(lang_codes, tasks_raw)

    stats = RunStats()

    with tempfile.TemporaryDirectory(prefix="itembank_audio_") as tmp:
        work_dir = Path(tmp)
        check_dir = work_dir / "check"
        out_dir = work_dir / "out"
        check_dir.mkdir()
        out_dir.mkdir()

        # ── Planning pass: decide action for every item ───────────────────────
        print(f"\n{'=' * 60}")
        print("Planning pass (no synthesis)")
        if args.force_regenerate:
            print("  --force-regenerate active: all non-placeholder items will regenerate")
        if args.dry_run:
            print("  --dry-run active: no synthesis or upload will occur")

        actions = plan_all_actions(
            client=client,
            draft_bucket_name=args.bucket,
            approved_bucket_name=args.approved_bucket,
            prefix=prefix,
            object_name=args.object_name,
            profiles=profiles,
            task_map=task_map,
            model_id=model_id,
            force_regenerate=args.force_regenerate,
            config_change=args.config_change,
            check_dir=check_dir,
            stats=stats,
        )

        _tally_actions(actions, stats)

        # ── Fail fast: blocked config mismatches ──────────────────────────────
        blocked = [a for a in actions if a.action == "blocked"]
        if blocked and not args.config_change:
            print(f"\n{'=' * 60}")
            print(
                f"🚫 BLOCKED: {len(blocked)} item(s) have config mismatches.\n"
                "   Existing audio text matches the current JSON, but voice/model/service/lang\n"
                "   has changed. Re-run with --config-change to permit regeneration.\n"
                "   Affected items:"
            )
            for a in blocked[:20]:
                print(f"     [{a.lang_code}] {a.item_id} [{a.tier}]: {a.reason}")
            if len(blocked) > 20:
                print(f"     ... and {len(blocked) - 20} more (see audio_regen_summary.json)")
            write_summary(stats, actions, args.dry_run)
            return 2   # exit code 2 = blocked (distinct from generic failure = 1)

        # ── Execution pass: synthesize and upload ─────────────────────────────
        execute_actions(
            actions=actions,
            profiles=profiles,
            draft_bucket=draft_bucket_handle,
            model_id=model_id,
            out_dir=out_dir,
            stats=stats,
            dry_run=args.dry_run,
        )

    summary_path = write_summary(stats, actions, args.dry_run)
    print_summary(stats)
    print(f"\nSummary written to: {summary_path}")

    return 1 if stats.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
