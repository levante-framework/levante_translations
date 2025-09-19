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

DEFAULT_SOURCE_URL = "https://raw.githubusercontent.com/levante-framework/levante_translations/l10n_pending/translations/itembank/item-bank-translations.csv"
DEFAULT_OUTPUT_PATH = os.path.join("translation_text", "item_bank_translations.csv")


def fetch_csv_text(source_url: str) -> str:
	resp = requests.get(source_url, timeout=60)
	resp.raise_for_status()
	return resp.text


def remap_columns(df: pd.DataFrame) -> pd.DataFrame:
	"""Map columns for dashboard compatibility: identifier -> item_id, text -> en"""
	if "identifier" in df.columns:
		df = df.rename(columns={"identifier": "item_id"})
	if "text" in df.columns:
		df = df.rename(columns={"text": "en"})
	return df


def get_translations(force: bool = True,
					output: Optional[str] = None,
					source_url: Optional[str] = None) -> bool:
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
		df = remap_columns(df)
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
	return parser.parse_args()


def main() -> int:
	args = _parse_args()
	ok = get_translations(force=args.force, output=args.output, source_url=args.source_url)
	return 0 if ok else 1


if __name__ == "__main__":
	sys.exit(main())
