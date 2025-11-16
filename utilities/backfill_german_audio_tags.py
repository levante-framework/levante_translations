from __future__ import annotations

import argparse
import os
import pathlib
import sys
import tempfile
from typing import Iterable, List

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

VOICE_NAME = "Julia"
SOURCE_TAG_VALUE = "patch"
LICENSE_TEXT = audio_tags["copyright"]
DEFAULT_BUCKET = "levante-assets-dev"
DEFAULT_PREFIX = "audio/de"
TARGET_FILES: List[str] = [
    "child-survey-intro-no-responses.mp3",
    "general-intro1.mp3",
    "vocab-item-001.mp3",
    "vocab-item-002.mp3",
    "vocab-item-025.mp3",
    "vocab-item-040.mp3",
    "vocab-item-045.mp3",
    "vocab-item-059.mp3",
    "vocab-item-061.mp3",
    "vocab-item-066.mp3",
    "vocab-item-076.mp3",
    "vocab-item-088.mp3",
    "vocab-item-095.mp3",
    "vocab-item-099.mp3",
    "vocab-item-100.mp3",
    "vocab-item-127.mp3",
    "vocab-item-131.mp3",
    "vocab-item-135.mp3",
    "vocab-item-142.mp3",
    "vocab-item-145.mp3",
    "vocab-item-149.mp3",
    "vocab-item-152.mp3",
    "vocab-item-154.mp3",
    "vocab-item-155.mp3",
    "vocab-item-157.mp3",
]


def _merge_tags(existing: dict[str, str | None], title: str) -> dict[str, str | None]:
    """Merge defaults with existing tags and apply overrides."""
    merged = audio_tags.copy()
    merged.update(existing or {})

    if not merged.get("title"):
        merged["title"] = title
    if not merged.get("artist"):
        merged["artist"] = "Levante Project"
    if not merged.get("album"):
        merged["album"] = "German Audio"

    merged["voice"] = VOICE_NAME
    merged["source"] = SOURCE_TAG_VALUE
    merged["copyright"] = LICENSE_TEXT
    return merged


def update_local_audio(files: Iterable[str], base_dir: str) -> None:
    print(f"➡️  Updating local audio in {base_dir}")
    updated = 0
    skipped = 0

    for name in files:
        path = os.path.join(base_dir, name)
        if not os.path.exists(path):
            print(f"  ⚠️  Missing local file: {path}")
            skipped += 1
            continue

        tags = read_id3_tags(path)
        merged = _merge_tags(tags, title=os.path.splitext(name)[0])
        if write_id3_tags(path, merged):
            print(f"  ✅ Updated tags for {name}")
            updated += 1
        else:
            print(f"  ❌ Failed to update {name}")

    print(f"Local update complete. Updated {updated}, skipped {skipped}.")


def update_bucket_audio(files: Iterable[str], bucket_name: str, prefix: str) -> None:
    if not GCS_AVAILABLE:
        raise RuntimeError("google-cloud-storage is not installed. Install it to update GCS audio.")

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    print(f"➡️  Updating GCS bucket gs://{bucket_name}/{prefix}")

    for name in files:
        blob_path = f"{prefix.rstrip('/')}/{name}"
        blob = bucket.blob(blob_path)
        if not blob.exists():
            print(f"  ⚠️  Missing blob: {blob_path}")
            continue

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            blob.download_to_filename(temp_path)
            tags = read_id3_tags(temp_path)
            merged = _merge_tags(tags, title=os.path.splitext(name)[0])
            if write_id3_tags(temp_path, merged):
                blob.upload_from_filename(temp_path, content_type="audio/mpeg")
                print(f"  ✅ Updated tags for gs://{bucket_name}/{blob_path}")
            else:
                print(f"  ❌ Failed to write tags for {name}")
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill German audio ID3 metadata for voice Julia and standard license.")
    parser.add_argument(
        "--base-dir",
        default="audio_files/de",
        help="Local directory containing German audio files (default: audio_files/de)",
    )
    parser.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help=f"GCS bucket to update (default: {DEFAULT_BUCKET})",
    )
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PREFIX,
        help=f"Object prefix in the bucket (default: {DEFAULT_PREFIX})",
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    files: List[str] = TARGET_FILES

    if not args.bucket_only:
        update_local_audio(files, args.base_dir)

    if not args.local_only:
        update_bucket_audio(files, args.bucket, args.prefix)


if __name__ == "__main__":
    main()
