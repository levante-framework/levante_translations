#!/usr/bin/env python3
"""Identify item bank translation keys that are unused in core repositories.

This script scans `translation_text/item_bank_translations.csv` for `item_id`
values and reports the ones that are not referenced anywhere in the
`core-tasks` or `levante-dashboard` repositories.

The defaults assume the following directory layout:

```
levante/
├── core-tasks/
├── levante-dashboard/
└── levante_translations/
    └── scripts/find_unused_itembank_keys.py
```

Usage:

```
python scripts/find_unused_itembank_keys.py \
    --csv translation_text/item_bank_translations.csv \
    --core-tasks ../core-tasks \
    --levante-dashboard ../levante-dashboard
```

The default values already match the layout above, so running without
arguments from within `levante_translations/` is usually sufficient.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, Set


def load_item_ids(csv_path: Path) -> Set[str]:
    """Return the set of item IDs from the item bank CSV."""

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    keys: Set[str] = set()
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if "item_id" not in reader.fieldnames:
            raise ValueError(
                "Expected an 'item_id' column in the CSV; "
                f"found columns: {reader.fieldnames}"
            )
        for row in reader:
            key = (row.get("item_id") or "").strip()
            if key:
                keys.add(key)
    return keys


def camelize(value: str) -> str:
    """Replicate the camelize helper used in core-tasks."""

    regex = re.compile(r"^([A-Z])|[\s_-](\w)")

    def repl(match: re.Match[str]) -> str:
        first, second = match.group(1), match.group(2)
        if second:
            return second.upper()
        return first.lower() if first else ''

    return regex.sub(repl, value)


def generate_aliases(key: str) -> Set[str]:
    aliases = {key}
    camel = camelize(key)
    if camel:
        aliases.add(camel)
    return aliases


def run_search(patterns: Iterable[str], repo_path: Path) -> Set[str]:
    """Return the subset of patterns that appear in the repository."""

    repo_path = repo_path.resolve()
    if not repo_path.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

    patterns = list(patterns)
    if not patterns:
        return set()

    expanded_patterns: Dict[str, Set[str]] = {}
    search_terms: Set[str] = set()
    for pattern in patterns:
        aliases = generate_aliases(pattern)
        expanded_patterns[pattern] = aliases
        search_terms.update(aliases)

    search_tool = None
    if shutil.which("rg"):
        search_tool = "rg"
        cmd = [
            "rg",
            "-F",  # treat patterns as fixed strings
            "-o",  # print only the matching part
            "-n",  # include line numbers (useful for debugging)
            "-f",
            "__PATTERN_FILE__",
            str(repo_path),
        ]
        success_codes = {0, 1}
    elif shutil.which("grep"):
        search_tool = "grep"
        cmd = [
            "grep",
            "-R",
            "-n",
            "-F",
            "-o",
            "-f",
            "__PATTERN_FILE__",
            str(repo_path),
        ]
        success_codes = {0, 1}
    else:
        raise RuntimeError("Neither 'rg' nor 'grep' is available in PATH")

    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
        for pattern in sorted(search_terms):
            tmp.write(f"{pattern}\n")
        tmp_path = Path(tmp.name)

    try:
        cmd = [part if part != "__PATTERN_FILE__" else str(tmp_path) for part in cmd]
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass

    if result.returncode not in success_codes:
        tool_name = search_tool or "search"
        raise RuntimeError(
            f"{tool_name} failed with exit code {result.returncode}: "
            f"{result.stderr.strip()}"
        )

    found_aliases: Set[str] = set()
    for line in result.stdout.splitlines():
        # ripgrep -o output format: path:line:match
        match = line.rsplit(":", 1)[-1]
        if match in search_terms:
            found_aliases.add(match)

    matched_originals: Set[str] = set()
    for original, aliases in expanded_patterns.items():
        if aliases & found_aliases:
            matched_originals.add(original)

    return matched_originals


def resolve_default_paths(script_path: Path) -> argparse.Namespace:
    repo_root = script_path.parent.parent.resolve()
    parent_root = repo_root.parent
    return argparse.Namespace(
        csv=repo_root / "translation_text" / "item_bank_translations.csv",
        core_tasks=parent_root / "core-tasks",
        levante_dashboard=parent_root / "levante-dashboard",
        core_task_assets=parent_root / "core-task-assets",
    )


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
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
        "--limit",
        type=int,
        default=0,
        help="Limit the number of unused keys shown (0 means show all).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-essential log messages.",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)

    try:
        keys = load_item_ids(args.csv)
    except Exception as exc:  # pragma: no cover - CLI validation
        print(f"Error loading CSV: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Loaded {len(keys)} item IDs from {args.csv}")

    results = {}

    repo_targets = {
        "core-tasks": args.core_tasks,
        "levante-dashboard": args.levante_dashboard,
    }

    if args.core_task_assets:
        repo_targets["core-task-assets"] = args.core_task_assets

    for label, path in repo_targets.items():
        try:
            found = run_search(keys, path)
        except FileNotFoundError as exc:  # pragma: no cover - CLI validation
            print(f"Warning: {exc}", file=sys.stderr)
            continue
        except RuntimeError as exc:  # pragma: no cover - CLI validation
            print(f"Error running ripgrep in {path}: {exc}", file=sys.stderr)
            return 1

        if not args.quiet:
            print(f"Found {len(found)} matches in {label} ({path})")

        results[label] = found

    aggregates = list(results.values())
    used_keys = set().union(*aggregates) if aggregates else set()
    found_core = results.get("core-tasks", set())
    found_dashboard = results.get("levante-dashboard", set())
    found_core_assets = results.get("core-task-assets", set())
    unused_keys = sorted(keys - used_keys)

    if not args.quiet:
        summary_parts = [
            f"Total unused keys: {len(unused_keys)}",
            f"core-tasks missing: {len(keys - found_core)}",
            f"levante-dashboard missing: {len(keys - found_dashboard)}",
        ]
        if "core-task-assets" in results:
            summary_parts.append(f"core-task-assets missing: {len(keys - found_core_assets)}")
        print("; ".join(summary_parts))

    if args.limit and len(unused_keys) > args.limit:
        display_keys = unused_keys[: args.limit]
    else:
        display_keys = unused_keys

    for key in display_keys:
        print(key)

    if args.limit and len(unused_keys) > args.limit:
        print(
            f"... (showing first {args.limit} of {len(unused_keys)} unused keys)",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main(sys.argv[1:]))


