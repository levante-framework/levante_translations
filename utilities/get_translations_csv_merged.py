#!/usr/bin/env python3
"""
utilities/get_translations_csv_merged.py

Fetch, normalize, and prepare item bank translations CSV.
- Fetches from GitHub l10n_pending by default
- Renames: identifier->item_id, labels/label->task
- Normalizes language headers to canonical BCP-47
- Drops 'context' by default (configurable)
- Writes to translation_text/item_bank_translations.csv by default

Provides:
- get_translations(force=True, output=None, source_url=None, keep_context=False) -> bool
- CLI entrypoint (python utilities/get_translations_csv_merged.py)
"""

import argparse
import io
import os
import re
import sys
from typing import List, Optional

import pandas as pd
import requests

DEFAULT_SOURCE_URL = "https://raw.githubusercontent.com/levante-framework/levante_translations/l10n_pending/item-bank-translations.csv"
DEFAULT_OUTPUT_PATH = os.path.join("translation_text", "item_bank_translations.csv")


def fetch_csv_text(source_url: str) -> str:
	resp = requests.get(source_url, timeout=60)
	resp.raise_for_status()
	return resp.text


def canonicalize_header(col: str) -> str:
	if col in {"item_id", "identifier", "labels", "label", "task", "en", "de", "nl", "context"}:
		return col
	known = {
		"es-co": "es-CO", "fr-ca": "fr-CA", "de-ch": "de-CH",
		"ES-CO": "es-CO", "FR-CA": "fr-CA", "DE-CH": "de-CH",
	}
	if col.lower() in known:
		return known[col.lower()]
	m = re.match(r"^([A-Za-z]{2,3})[ _-]([A-Za-z]{2})$", col)
	if m:
		lang = m.group(1).lower()
		region = m.group(2).upper()
		return f"{lang}-{region}"
	return col


def remap_columns(df: pd.DataFrame, drop_context: bool = True) -> pd.DataFrame:
	if "identifier" in df.columns:
		df = df.rename(columns={"identifier": "item_id"})
	if "labels" in df.columns:
		df = df.rename(columns={"labels": "task"})
	elif "label" in df.columns:
		df = df.rename(columns={"label": "task"})
	if drop_context and "context" in df.columns:
		df = df.drop(columns=["context"])
	new_cols = [canonicalize_header(c) for c in df.columns]
	df.columns = new_cols
	return df


def reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
	priority = ["item_id", "task", "en"]
	existing_priority = [c for c in priority if c in df.columns]
	rest = [c for c in df.columns if c not in existing_priority]
	return df[existing_priority + rest]


def get_translations(force: bool = True,
					output: Optional[str] = None,
					source_url: Optional[str] = None,
					keep_context: bool = False) -> bool:
	"""Fetch and write normalized translations CSV. Returns True on success."""
	out_path = output or DEFAULT_OUTPUT_PATH
	src_url = source_url or DEFAULT_SOURCE_URL
	os.makedirs(os.path.dirname(out_path), exist_ok=True)
	if os.path.exists(out_path) and not force:
		print(f"❌ Output exists: {out_path}. Set force=True to overwrite.")
		return False
	try:
		print(f"📥 Fetching CSV from: {src_url}")
		csv_text = fetch_csv_text(src_url)
		try:
			df = pd.read_csv(io.StringIO(csv_text))
		except Exception:
			df = pd.read_csv(io.StringIO(csv_text), engine="python")
		df = remap_columns(df, drop_context=not keep_context)
		df = reorder_columns(df)
		df.to_csv(out_path, index=False, encoding="utf-8")
		print(f"✅ Wrote {len(df):,} rows → {os.path.abspath(out_path)}")
		return True
	except Exception as e:
		print(f"❌ Failed to fetch/write translations: {e}")
		return False


def _parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Fetch, normalize, and prepare item bank translations CSV")
	parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL, help="Source URL (default: l10n_pending on GitHub)")
	parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH, help="Output path for normalized CSV")
	parser.add_argument("--force", action="store_true", help="Overwrite output if exists")
	parser.add_argument("--keep-context", action="store_true", help="Do not drop the 'context' column")
	return parser.parse_args()


def main() -> int:
	args = _parse_args()
	ok = get_translations(force=args.force, output=args.output, source_url=args.source_url, keep_context=args.keep_context)
	return 0 if ok else 1


if __name__ == "__main__":
	sys.exit(main())
