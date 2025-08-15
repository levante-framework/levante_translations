#!/usr/bin/env python3
"""
get_translations_csv_merged.py

Merge the advantages of:
- utilities/fetch_latest_translations.py (robust remote fetch, header normalization)
- get_translations_csv.py (identifier/labels remapping, drop context)

Features:
- Fetches item-bank translations from GitHub l10n_pending by default
- Falls back to a configured/local path or a provided --source-url
- Renames columns: identifier->item_id, labels/label->task
- Normalizes language headers to canonical BCP-47 (e.g., es_ar -> es-AR)
- Optionally drops the 'context' column
- Writes to translation_text/item_bank_translations.csv by default

Usage examples:
  python get_translations_csv_merged.py
  python get_translations_csv_merged.py --output translation_text/item_bank_translations.csv --force
  python get_translations_csv_merged.py --source-url https://example.com/item-bank-translations.csv
"""

import argparse
import io
import os
import re
import sys
from typing import List

import pandas as pd
import requests

DEFAULT_SOURCE_URL = "https://raw.githubusercontent.com/levante-framework/levante_translations/l10n_pending/item-bank-translations.csv"
DEFAULT_OUTPUT_PATH = os.path.join("translation_text", "item_bank_translations.csv")


def fetch_csv_text(source_url: str) -> str:
	resp = requests.get(source_url, timeout=60)
	resp.raise_for_status()
	return resp.text


def canonicalize_header(col: str) -> str:
	# Keep known non-language columns as-is
	if col in {"item_id", "identifier", "labels", "label", "task", "en", "de", "nl", "context"}:
		return col
	# Normalize common known language tags
	known = {
		"es-co": "es-CO", "fr-ca": "fr-CA", "de-ch": "de-CH",
		"ES-CO": "es-CO", "FR-CA": "fr-CA", "DE-CH": "de-CH",
	}
	if col.lower() in known:
		return known[col.lower()]
	# General BCP-47: lang[_-]REGION
	m = re.match(r"^([A-Za-z]{2,3})[ _-]([A-Za-z]{2})$", col)
	if m:
		lang = m.group(1).lower()
		region = m.group(2).upper()
		return f"{lang}-{region}"
	return col


def remap_columns(df: pd.DataFrame, drop_context: bool = True) -> pd.DataFrame:
	cols = list(df.columns)
	# Step 1: rename identifier -> item_id once
	if "identifier" in df.columns:
		df = df.rename(columns={"identifier": "item_id"})
	# Step 2: labels/label -> task
	if "labels" in df.columns:
		df = df.rename(columns={"labels": "task"})
	elif "label" in df.columns:
		df = df.rename(columns={"label": "task"})
	# Step 3: drop context if requested and present
	if drop_context and "context" in df.columns:
		df = df.drop(columns=["context"])  # safe if exists
	# Step 4: canonicalize headers
	new_cols = [canonicalize_header(c) for c in df.columns]
	df.columns = new_cols
	return df


def reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
	# Put item_id, task, en first, then other columns in stable order
	priority = ["item_id", "task", "en"]
	existing_priority = [c for c in priority if c in df.columns]
	rest = [c for c in df.columns if c not in existing_priority]
	return df[existing_priority + rest]


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Fetch, normalize, and prepare item bank translations CSV")
	parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL, help="Source URL to fetch CSV (default: l10n_pending on GitHub)")
	parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH, help="Output path for normalized CSV")
	parser.add_argument("--force", action="store_true", help="Overwrite output if exists")
	parser.add_argument("--keep-context", action="store_true", help="Do not drop the 'context' column")
	return parser.parse_args()


def main() -> int:
	args = parse_args()

	# Ensure dir exists
	os.makedirs(os.path.dirname(args.output), exist_ok=True)
	if os.path.exists(args.output) and not args.force:
		print(f"❌ Output exists: {args.output}. Use --force to overwrite.")
		return 1

	# Fetch
	print(f"📥 Fetching CSV from: {args.source_url}")
	try:
		csv_text = fetch_csv_text(args.source_url)
	except Exception as e:
		print(f"❌ Failed to download CSV: {e}")
		return 1

	# Load via pandas
	try:
		df = pd.read_csv(io.StringIO(csv_text))
	except Exception:
		# Fallback: try python engine
		df = pd.read_csv(io.StringIO(csv_text), engine="python")

	# Remap and normalize
	df = remap_columns(df, drop_context=not args.keep_context)
	df = reorder_columns(df)

	# Save
	df.to_csv(args.output, index=False, encoding="utf-8")
	print(f"✅ Wrote {len(df):,} rows → {os.path.abspath(args.output)}")

	# Show language columns summary
	language_cols: List[str] = [c for c in df.columns if c not in {"item_id", "task", "en"}]
	print(f"🌐 Language columns: {', '.join(language_cols[:10])}{' ...' if len(language_cols)>10 else ''}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
