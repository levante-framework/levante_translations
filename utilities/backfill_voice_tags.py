#!/usr/bin/env python3
"""Backfill voice and source tags for audio files missing metadata.

This script scans local audio directories (and optionally GCS buckets) for MP3
files without a voice tag, then applies standardized ID3 metadata (voice, album,
source=patch, etc.). It is intended to mirror the German backfill workflow but
supports multiple languages via configuration.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import tempfile
from dataclasses import dataclass
from typing import Dict, Iterable, List

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from utilities.utilities import audio_tags, read_id3_tags, write_id3_tags  # noqa: E402

try:
    from google.cloud import storage  # type: ignore

    GCS_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    storage = None  # type: ignore
    GCS_AVAILABLE = False

DEFAULT_BUCKET = "levante-assets-dev"
SOURCE_TAG_VALUE = "patch"
MISSING_VOICE_VALUES = {"", "not available", "n/a", "unknown", "none"}


@dataclass
class LanguageConfig:
    lang_code: str
    voice: str
    album: str
    base_dir: str
    prefix: str


LANGUAGE_CONFIG: Dict[str, LanguageConfig] = {
    "en": LanguageConfig(
        lang_code="en",
        voice="Clara - Children's Storyteller",
        album="English Audio",
        base_dir="audio_files/en",
        prefix="audio/en",
    ),
    "es-CO": LanguageConfig(
        lang_code="es-CO",
        voice="Valeria - Energetic & Engaging",
        album="es-CO Audio",
        base_dir="audio_files/es-CO",
        prefix="audio/es-CO",
    ),
}


def is_missing_voice(tags: Dict[str, str | None] | None) -> bool:
    voice = (tags or {}).get("voice") or ""
    return voice.strip().lower() in MISSING_VOICE_VALUES


def merge_tags(existing: Dict[str, str | None] | None, title: str, config: LanguageConfig) -> Dict[str, str | None]:
    merged = audio_tags.copy()
    merged.update(existing or {})

    if not merged.get("title"):
        merged["title"] = title
    if not merged.get("artist"):
        merged["artist"] = "Levante Project"
    merged["album"] = config.album
    merged["voice"] = config.voice
    merged["lang_code"] = config.lang_code
    merged["source"] = SOURCE_TAG_VALUE

    return merged


def discover_local_files(config: LanguageConfig, explicit_files: Iterable[str] | None = None) -> List[str]:
    base_path = pathlib.Path(config.base_dir)
    if explicit_files:
        return sorted(set(f.replace("\\", "/") for f in explicit_files))

    if not base_path.exists():
        print(f"⚠️  Base directory not found for {config.lang_code}: {base_path}")
        return []

    candidates: List[str] = []
    for mp3_path in base_path.rglob("*.mp3"):
        tags = read_id3_tags(str(mp3_path))
        if is_missing_voice(tags):
            rel_path = mp3_path.relative_to(base_path).as_posix()
            candidates.append(rel_path)
    return sorted(candidates)


def update_local_audio(files: Iterable[str], config: LanguageConfig, dry_run: bool = False) -> None:
    base_dir = pathlib.Path(config.base_dir)
    if not files:
        print(f"ℹ️  No local files to update for {config.lang_code}.")
        return

    print(f"➡️  Updating local audio for {config.lang_code} in {base_dir}")
    updated = 0
    skipped = 0

    for rel_path in files:
        file_path = base_dir / rel_path
        if not file_path.exists():
            print(f"  ⚠️  Missing local file: {file_path}")
            skipped += 1
            continue

        if dry_run:
            print(f"  🔎 DRY RUN: would update {rel_path}")
            updated += 1
            continue

        tags = read_id3_tags(str(file_path))
        merged = merge_tags(tags, title=file_path.stem, config=config)
        if write_id3_tags(str(file_path), merged):
            print(f"  ✅ Updated tags for {rel_path}")
            updated += 1
        else:
            print(f"  ❌ Failed to update {rel_path}")

    print(f"Local update complete for {config.lang_code}. Updated {updated}, skipped {skipped}.")


def update_bucket_audio(files: Iterable[str], config: LanguageConfig, bucket_name: str, dry_run: bool = False) -> None:
    if not files:
        print(f"ℹ️  No bucket files to update for {config.lang_code}.")
        return

    if not GCS_AVAILABLE:
        raise RuntimeError("google-cloud-storage is not installed. Install it to update GCS audio.")

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    prefix = config.prefix.rstrip("/")
    print(f"➡️  Updating GCS bucket gs://{bucket_name}/{prefix}")

    for rel_path in files:
        blob_path = f"{prefix}/{rel_path}".replace("//", "/")
        blob = bucket.blob(blob_path)
        if not blob.exists():
            print(f"  ⚠️  Missing blob: {blob_path}")
            continue

        if dry_run:
            print(f"  🔎 DRY RUN: would update gs://{bucket_name}/{blob_path}")
            continue

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            blob.download_to_filename(temp_path)
            tags = read_id3_tags(temp_path)
            merged = merge_tags(tags, title=pathlib.Path(rel_path).stem, config=config)
            if write_id3_tags(temp_path, merged):
                blob.upload_from_filename(temp_path, content_type="audio/mpeg")
                print(f"  ✅ Updated tags for gs://{bucket_name}/{blob_path}")
            else:
                print(f"  ❌ Failed to write tags for {rel_path}")
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill voice/source tags for audio files with missing metadata.")
    parser.add_argument(
        "--languages",
        "-l",
        nargs="+",
        default=["en", "es-CO"],
        help=f"Languages to process (default: en es-CO). Available: {', '.join(LANGUAGE_CONFIG)}",
    )
    parser.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help=f"GCS bucket to update (default: {DEFAULT_BUCKET})",
    )
    parser.add_argument(
        "--local-only",
        "--local",
        dest="local_only",
        action="store_true",
        help="Only update local files, skip GCS",
    )
    parser.add_argument(
        "--bucket-only",
        action="store_true",
        help="Only update GCS files, skip local",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show actions without modifying any files",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help="Explicit relative file paths (relative to the language base directory). Applies to all specified languages.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    languages = []
    for lang in args.languages:
        if lang not in LANGUAGE_CONFIG:
            print(f"⚠️  Unknown language '{lang}'. Skipping.")
        else:
            languages.append(lang)

    if not languages:
        print("No valid languages selected. Exiting.")
        return

    for lang in languages:
        config = LANGUAGE_CONFIG[lang]
        files = discover_local_files(config, explicit_files=args.files)
        print(f"\n===== {lang} =====")
        print(f"Found {len(files)} candidate files to update.")

        if not args.bucket_only:
            update_local_audio(files, config, dry_run=args.dry_run)

        if not args.local_only:
            update_bucket_audio(files, config, bucket_name=args.bucket, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
