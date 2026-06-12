#!/usr/bin/env python3
"""Export the complete Crowdin approved translations into a wide CSV.

The Crowdin approved export is delivered one *(language, string)* per row with a
language-prefixed path id (e.g. ``nl/main/.../ToM-scene-10-q1``). This script
collapses those rows into one wide row per logical item keyed by the *bare*
identifier (the last path component, e.g. ``ToM-scene-10-q1``) which is the key
space shared by the item bank, COMET segment scores, and the composite metric.

Output columns: ``identifier, item_id, labels, en, <target langs...>``. This is
the input contract for ``gemini_quality_evaluator.py`` (needs identifier/labels/
en/target cols) and the translations backbone for ``composite_metrics.py``.

By default only items that exist in the item bank are emitted (these are the
child-assessment strings that carry task labels); pass ``--all-strings`` to also
export app/UI strings.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as pl  # noqa: E402  (reuse the Crowdin loader/merger)


DEFAULT_TARGET_LANGS = ["de", "nl", "es-CO", "fr-CA", "es-AR", "en-GB", "pt-PT", "pt-BR"]

# Normalize item-bank task labels to the vocabulary understood by
# gemini_quality_evaluator.select_template so task-aware prompts kick in.
# NB: child-survey is intentionally NOT mapped to "survey" - child surveys are
# answered by the child (child-directed "you"), and the adult-respondent SURVEY
# framing produces false "subject shift" criticals on correct translations.
LABEL_ALIASES = {
    "egma-math": "math",
    "memory": "memory-game",
}


def bare_identifier(item_id: str) -> str:
    parts = str(item_id or "").replace("::", "/").split("/")
    return parts[-1].strip()


def load_item_bank_labels(path: Path) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    if not path.exists():
        return labels
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            item_id = str(row.get("item_id", "") or "").strip()
            if item_id:
                labels[item_id] = str(row.get("task", "") or row.get("labels", "") or "").strip()
    return labels


def load_crowdin_rows(args: argparse.Namespace) -> List[dict]:
    cache = Path(args.crowdin_cache_zip)
    if cache.exists() and cache.stat().st_size > 0 and not args.refresh:
        return pl.merge_crowdin_zip(cache.read_bytes())
    ns = argparse.Namespace(
        input_mode="crowdin-api", input_csv="", crowdin_zip="",
        crowdin_project_id=args.crowdin_project_id,
        crowdin_cache_zip=str(cache),
        refresh_crowdin_cache=True, crowdin_cache_max_age_minutes=0,
    )
    return pl.load_source_rows(ns)


def collapse_wide(rows: List[dict], target_langs: List[str],
                  item_labels: Dict[str, str], all_strings: bool) -> Dict[str, dict]:
    wide: Dict[str, dict] = {}
    for row in rows:
        ident = bare_identifier(row.get("item_id", ""))
        if not ident:
            continue
        if not all_strings and ident not in item_labels:
            continue
        entry = wide.setdefault(ident, {"identifier": ident, "item_id": ident,
                                        "labels": item_labels.get(ident, ""), "en": ""})
        en = str(row.get("en", "") or "").strip()
        if en and not entry["en"]:
            entry["en"] = en
        for lang in target_langs:
            val = str(row.get(lang, "") or "").strip()
            if val and not entry.get(lang):
                entry[lang] = val
    return wide


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-csv", default="translation_grading/output/complete_translations.csv")
    p.add_argument("--item-bank", default="translation_text/item_bank_translations.csv")
    p.add_argument("--target-langs", default=",".join(DEFAULT_TARGET_LANGS))
    p.add_argument("--crowdin-cache-zip", default="translation_grading/output/.crowdin-approved-cache.zip")
    p.add_argument("--crowdin-project-id", default=pl.DEFAULT_CROWDIN_PROJECT_ID)
    p.add_argument("--refresh", action="store_true", help="Force a fresh Crowdin build instead of using the cache.")
    p.add_argument("--all-strings", action="store_true", help="Include app/UI strings (default: item-bank items only).")
    args = p.parse_args()

    target_langs = [t.strip() for t in args.target_langs.split(",") if t.strip()]
    item_labels = load_item_bank_labels(Path(args.item_bank))
    rows = load_crowdin_rows(args)
    wide = collapse_wide(rows, target_langs, item_labels, args.all_strings)

    for entry in wide.values():
        entry["labels"] = LABEL_ALIASES.get(entry["labels"], entry["labels"])

    out_path = Path(args.output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["identifier", "item_id", "labels", "en", *target_langs]
    pairs = 0
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for ident in sorted(wide):
            entry = wide[ident]
            writer.writerow(entry)
            pairs += sum(1 for lang in target_langs if entry.get(lang))

    blank_en = sum(1 for e in wide.values() if not e["en"])
    print(f"[export] wrote {len(wide)} items / {pairs} translation pairs -> {out_path}")
    print(f"[export] items with blank en: {blank_en}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
