#!/usr/bin/env python3
"""
From downloaded itembank_by_task XLIFF files, list task names where every
trans-unit that has non-empty target text is marked approved/final in XLIFF.

Typical use before a targeted generate_speech run:

  python utilities/itembank_by_task_regen_report.py --langs es-AR --skip-download
  python utilities/list_fully_approved_itembank_tasks.py --lang es-AR

Then pass the comma-separated task list to generate_speech.py --tasks.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utilities.itembank_by_task_regen_report import parse_xliff_file


def _task_stats(
    xliff_path: Path,
    lang: str,
) -> Tuple[str, int, int, int]:
    """
    Returns (task_name, count_with_target, approved_with_target, total_units).
    total_units includes rows from parse (units skipped when no item_id are excluded).
    """
    name = xliff_path.stem
    suffix = f"-{lang}"
    if not name.endswith(suffix):
        return (name, 0, 0, 0)

    rows = parse_xliff_file(xliff_path, approved_only=False)
    task = name[: -len(suffix)]

    with_target: List[dict] = []
    for row in rows:
        t = (row.get("target_text") or "").strip()
        if t:
            with_target.append(row)

    approved_n = sum(1 for row in with_target if row.get("approved") == "1")
    return (task, len(with_target), approved_n, len(rows))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List itembank_by_task tasks where all non-empty targets are XLIFF-approved."
    )
    parser.add_argument(
        "--xliff-dir",
        default="tmp/itembank_by_task_xliff",
        help="Directory containing *.xliff from itembank_by_task_regen_report",
    )
    parser.add_argument(
        "--lang",
        required=True,
        help='Crowdin language slug as used in filenames (e.g. "es-AR")',
    )
    parser.add_argument(
        "--format",
        choices=["lines", "comma", "json"],
        default="lines",
        help="Output format (default: lines)",
    )
    args = parser.parse_args()

    d = Path(args.xliff_dir)
    if not d.is_dir():
        print(f"❌ Not a directory: {d}", file=sys.stderr)
        return 1

    suffix = f"-{args.lang}"
    files = sorted(d.glob(f"*{suffix}.xliff"))
    if not files:
        print(f"❌ No files matching *{suffix}.xliff under {d}", file=sys.stderr)
        return 1

    fully: List[str] = []
    partial: List[str] = []
    empty: List[str] = []

    for path in files:
        task, n_target, n_appr, _ = _task_stats(path, args.lang)
        if n_target == 0:
            empty.append(task)
            continue
        if n_appr == n_target:
            fully.append(task)
        else:
            partial.append(f"{task} ({n_appr}/{n_target} targets approved)")

    fully.sort()
    partial.sort()
    empty.sort()

    if args.format == "comma":
        print(",".join(fully))
    elif args.format == "json":
        import json

        print(
            json.dumps(
                {"fully_approved_tasks": fully, "partial": partial, "no_translated_targets": empty},
                indent=2,
            )
        )
    else:
        print("# Tasks with all translated targets approved in XLIFF:")
        for t in fully:
            print(t)
        if partial:
            print("\n# Partially approved (excluded from comma list):")
            for p in partial:
                print(p)
        if empty:
            print("\n# No non-empty targets in XLIFF:")
            for t in empty:
                print(t)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
