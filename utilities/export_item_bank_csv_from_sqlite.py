#!/usr/bin/env python3
"""
Export item-bank-translations CSV from SQLite items_current.

This creates the legacy CSV shape consumed by dashboard/deploy tooling while
using the XLIFF/SQLite baseline as source-of-truth.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path
from typing import Dict, List


DEFAULT_COLUMNS: List[str] = [
    "item_id",
    "task",
    "en",
    "es-CO",
    "de",
    "fr-CA",
    "nl",
    "de-CH",
    "es-AR",
    "en-GH",
    "pt-PT",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export item-bank-translations.csv from itembank SQLite (items_current)."
    )
    parser.add_argument(
        "--db-path",
        default="tmp/itembank_by_task_regen.sqlite",
        help="Path to SQLite DB containing items_current.",
    )
    parser.add_argument(
        "--output",
        default="translation_text/item_bank_translations.csv",
        help="Output CSV path.",
    )
    return parser.parse_args()


def _normalize_text(value: str | None) -> str:
    return (value or "").strip()


def build_rows(db_path: Path) -> List[Dict[str, str]]:
    if not db_path.is_file():
        raise FileNotFoundError(f"DB not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            """
            SELECT item_id, task, lang, source_text, target_text
            FROM items_current
            """
        ).fetchall()
    finally:
        conn.close()

    by_item: Dict[str, Dict[str, str]] = {}
    for item_id, task, lang, source_text, target_text in rows:
        item_id = _normalize_text(item_id)
        lang = _normalize_text(lang)
        if not item_id or not lang:
            continue

        text = _normalize_text(target_text) or _normalize_text(source_text)
        item = by_item.setdefault(item_id, {"item_id": item_id, "task": _normalize_text(task)})

        # Keep the first non-empty task label if task is missing/blank in later rows.
        if not item.get("task") and _normalize_text(task):
            item["task"] = _normalize_text(task)

        if text:
            item[lang] = text

    out_rows: List[Dict[str, str]] = []
    for item_id in sorted(by_item):
        item = by_item[item_id]
        out_rows.append(
            {
                "item_id": item.get("item_id", ""),
                "task": item.get("task", ""),
                "en": item.get("en") or item.get("en-US") or item.get("en-GB") or "",
                "es-CO": item.get("es-CO", ""),
                "de": item.get("de") or item.get("de-DE") or "",
                "fr-CA": item.get("fr-CA", ""),
                "nl": item.get("nl", ""),
                "de-CH": item.get("de-CH", ""),
                "es-AR": item.get("es-AR", ""),
                "en-GH": item.get("en-GH", ""),
                "pt-PT": item.get("pt-PT", ""),
            }
        )
    return out_rows


def write_csv(rows: List[Dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=DEFAULT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    db_path = Path(args.db_path)
    output_path = Path(args.output)

    rows = build_rows(db_path)
    write_csv(rows, output_path)

    es_ar_count = sum(1 for row in rows if _normalize_text(row.get("es-AR")))
    print(f"✅ Wrote {len(rows)} rows to {output_path}")
    print(f"ℹ️  Non-empty es-AR rows: {es_ar_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
