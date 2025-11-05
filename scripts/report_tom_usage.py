#!/usr/bin/env python3

"""Generate a color-coded CSV highlighting Theory of Mind translation usage."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set

from find_unused_itembank_keys import (  # type: ignore
    run_search,
    resolve_default_paths,
)


DEFAULT_OUTPUT = Path("reports/tom_usage_report.csv")
USED_COLOR = "#34D399"  # emerald-400
UNUSED_COLOR = "#F97316"  # orange-400


def load_tom_rows(csv_path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            item_id = (row.get("item_id") or "").strip()
            if item_id.lower().startswith("tom"):
                row["item_id"] = item_id
                rows.append(row)
    return rows


def collect_usage(keys: Sequence[str], repo_paths: Dict[str, Path]) -> Dict[str, Set[str]]:
    usage: Dict[str, Set[str]] = {}
    for label, path in repo_paths.items():
        usage[label] = run_search(keys, path)
    return usage


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    defaults = resolve_default_paths(Path(__file__).resolve())

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=defaults.csv,
        help="Path to item_bank_translations.csv (default: %(default)s)",
    )
    parser.add_argument(
        "--core-tasks",
        type=Path,
        default=defaults.core_tasks,
        help="Path to the core-tasks repository (default: %(default)s)",
    )
    parser.add_argument(
        "--levante-dashboard",
        type=Path,
        default=defaults.levante_dashboard,
        help="Path to the levante-dashboard repository (default: %(default)s)",
    )
    parser.add_argument(
        "--core-task-assets",
        type=Path,
        default=defaults.core_task_assets,
        help="Path to the core-task-assets repository (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination CSV file (default: %(default)s)",
    )
    return parser.parse_args(argv if argv is not None else [])


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)

    tom_rows = load_tom_rows(args.csv)
    if not tom_rows:
        print("No Theory of Mind rows found in the CSV.")
        return 0

    repo_paths: Dict[str, Path] = {
        "core-tasks": args.core_tasks,
        "levante-dashboard": args.levante_dashboard,
    }
    if args.core_task_assets:
        repo_paths["core-task-assets"] = args.core_task_assets

    keys = [row["item_id"] for row in tom_rows]
    usage = collect_usage(keys, repo_paths)
    used_union: Set[str] = set().union(*usage.values()) if usage else set()

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "item_id",
        "status",
        "color",
        "used_in",
        "labels",
        "en",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for row in sorted(tom_rows, key=lambda r: r["item_id"].lower()):
            item_id = row["item_id"]
            used_in = [label for label, found in usage.items() if item_id in found]
            is_used = item_id in used_union
            writer.writerow(
                {
                    "item_id": item_id,
                    "status": "used" if is_used else "unused",
                    "color": USED_COLOR if is_used else UNUSED_COLOR,
                    "used_in": "|".join(sorted(used_in)),
                    "labels": row.get("labels", ""),
                    "en": row.get("en", ""),
                }
            )

    print(f"Report written to {output_path}")
    print(
        "Legend: used → green (", USED_COLOR, ") | unused → orange (", UNUSED_COLOR, ")",
        sep="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

