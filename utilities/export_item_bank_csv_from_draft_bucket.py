#!/usr/bin/env python3
"""
Build item_bank_translations.csv from draft-bucket per-task JSON files.

Expected object layout:
  gs://<bucket>/translations/itembank/<task>/<locale>/item-bank-translations.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from google.cloud import storage


DEFAULT_BUCKET = "levante-assets-draft"
DEFAULT_PREFIX = "translations/itembank/"
DEFAULT_OBJECT_NAME = "item-bank-translations.json"
DEFAULT_OUTPUT = "translation_text/item_bank_translations.csv"

CORE_COLUMNS = ["item_id", "task"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export item_bank_translations.csv from draft bucket JSON files."
    )
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--object-name", default=DEFAULT_OBJECT_NAME)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--locales",
        nargs="*",
        default=None,
        help="Optional locale allowlist (e.g., es-AR en-US de-DE).",
    )
    return parser.parse_args()


def _parse_blob_path(path: str, object_name: str) -> Tuple[str, str] | None:
    pattern = re.compile(
        rf"^translations/itembank/(?P<task>[^/]+)/(?P<locale>[^/]+)/{re.escape(object_name)}$"
    )
    match = pattern.match(path)
    if not match:
        return None
    return match.group("task"), match.group("locale")


def iter_translation_blobs(
    *, bucket: str, prefix: str, object_name: str
) -> Iterable[Tuple[str, str, storage.Blob]]:
    client = storage.Client()
    bucket_ref = client.bucket(bucket)
    for blob in client.list_blobs(bucket_ref, prefix=prefix):
        parsed = _parse_blob_path(blob.name, object_name)
        if not parsed:
            continue
        task, locale = parsed
        yield task, locale, blob


def build_rows(
    *, bucket: str, prefix: str, object_name: str, locale_filter: set[str] | None
) -> Tuple[List[Dict[str, str]], List[str]]:
    rows_by_item: Dict[str, Dict[str, str]] = {}
    discovered_locales: set[str] = set()

    blob_count = 0
    for task, locale, blob in iter_translation_blobs(
        bucket=bucket, prefix=prefix, object_name=object_name
    ):
        if locale_filter and locale not in locale_filter:
            continue
        blob_count += 1
        # Keep locale columns exactly as represented by draft folder structure.
        locale_key = locale
        discovered_locales.add(locale_key)

        payload_raw = blob.download_as_bytes().decode("utf-8")
        payload = json.loads(payload_raw)
        if not isinstance(payload, dict):
            continue

        for item_id, text in payload.items():
            item_id = str(item_id).strip()
            if not item_id:
                continue
            text_value = "" if text is None else str(text).strip()
            row = rows_by_item.setdefault(item_id, {"item_id": item_id, "task": task})
            if not row.get("task"):
                row["task"] = task
            if text_value:
                row[locale_key] = text_value

    print(f"✅ Parsed {blob_count} translation JSON blobs from gs://{bucket}/{prefix}")

    # Keep locales in a stable, human-friendly order matching current operational languages,
    # then append any additional locales discovered in alphabetical order.
    preferred_locale_order = ["en-US", "es-AR", "es-CO", "de-DE"]
    ordered_preferred = [lang for lang in preferred_locale_order if lang in discovered_locales]
    remaining = sorted(lang for lang in discovered_locales if lang not in set(ordered_preferred))
    columns = CORE_COLUMNS + ordered_preferred + remaining

    out_rows: List[Dict[str, str]] = []
    for item_id in sorted(rows_by_item):
        row = rows_by_item[item_id]
        out_rows.append({k: row.get(k, "") for k in columns})

    return out_rows, columns


def write_csv(output_path: Path, rows: List[Dict[str, str]], columns: List[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    locale_filter = set(args.locales) if args.locales else None

    rows, columns = build_rows(
        bucket=args.bucket,
        prefix=args.prefix,
        object_name=args.object_name,
        locale_filter=locale_filter,
    )
    output_path = Path(args.output)
    write_csv(output_path, rows, columns)

    es_ar_count = sum(1 for row in rows if (row.get("es-AR") or "").strip())
    print(f"✅ Wrote {len(rows)} rows to {output_path}")
    print(f"ℹ️  Non-empty es-AR rows: {es_ar_count}")
    if len(columns) > len(CORE_COLUMNS):
        extras = columns[len(CORE_COLUMNS) :]
        print(f"ℹ️  Extra locale columns included: {', '.join(extras)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
