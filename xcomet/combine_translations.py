#!/usr/bin/env python3
import argparse
import csv
import os
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


def find_language_dirs(output_dir: Path) -> List[str]:
    langs = []
    if not output_dir.exists():
        return langs
    for child in output_dir.iterdir():
        if child.is_dir() and (child / 'segment_scores.csv').exists():
            langs.append(child.name)
    return sorted(langs)


def load_lang_csv(output_dir: Path, lang: str) -> pd.DataFrame:
    path = output_dir / lang / 'segment_scores.csv'
    if not path.exists():
        raise FileNotFoundError(f'Missing {path}')
    df = pd.read_csv(path)
    # Expect columns: item_id, en, <lang>, score
    # Keep only item_id, en, <lang>
    keep_cols = ['item_id']
    if 'en' in df.columns:
        keep_cols.append('en')
    if lang in df.columns:
        keep_cols.append(lang)
    else:
        # accommodate cases where translation column header was not renamed
        if 'translation' in df.columns:
            df = df.rename(columns={'translation': lang})
            keep_cols.append(lang)
        else:
            df[lang] = ''
            keep_cols.append(lang)
    return df[keep_cols]


def main():
    p = argparse.ArgumentParser(description='Combine per-language xcomet segment_scores.csv into a single CSV with item_id, english, and language columns.')
    p.add_argument('--output_dir', type=Path, default=Path('xcomet/output'), help='Base output directory containing language subfolders (default: xcomet/output)')
    p.add_argument('--out_csv', type=Path, default=Path('xcomet/output/combined_translations.csv'), help='Path to write combined CSV')
    p.add_argument('--langs', help='Comma-separated list of language codes to include (default: autodetect from output_dir)')
    p.add_argument('--base_csv', type=Path, default=Path('translation_master.csv'), help='Optional root CSV to source English text when missing')
    args = p.parse_args()

    langs = args.langs.split(',') if args.langs else find_language_dirs(args.output_dir)
    if not langs:
        raise SystemExit('No languages found. Provide --langs or ensure xcomet/output/<lang>/segment_scores.csv exist.')

    # Load English from base CSV (optional)
    base_en: Dict[str, str] = {}
    if args.base_csv and args.base_csv.exists():
        base_df = pd.read_csv(args.base_csv)
        if 'item_id' in base_df.columns and 'en' in base_df.columns:
            base_en = dict(zip(base_df['item_id'].astype(str), base_df['en'].astype(str)))

    combined: Optional[pd.DataFrame] = None
    english_filled = False

    for lang in langs:
        df = load_lang_csv(args.output_dir, lang)
        df['item_id'] = df['item_id'].astype(str)
        # First language initializes combined
        if combined is None:
            combined = pd.DataFrame({'item_id': df['item_id']})
            # Prefer en from this df; fill from base if missing
            if 'en' in df.columns:
                combined['english'] = df['en'].astype(str)
                english_filled = True
            else:
                combined['english'] = ''
        # Add language column
        combined = combined.merge(df[['item_id', lang]], on='item_id', how='outer')
        # If english not yet filled and df has en, fill it now (first available)
        if not english_filled and 'en' in df.columns:
            # align by item_id
            fill_map = dict(zip(df['item_id'], df['en'].astype(str)))
            combined['english'] = combined.apply(lambda r: fill_map.get(r['item_id'], r['english']), axis=1)
            english_filled = True

    # Fill english from base CSV where empty
    if base_en:
        combined['english'] = combined.apply(
            lambda r: r['english'] if isinstance(r['english'], str) and len(r['english']) > 0 else base_en.get(r['item_id'], ''),
            axis=1
        )

    # Ensure stable column order: item_id, english, then languages in requested order
    ordered_cols = ['item_id', 'english'] + langs
    # Remove potential duplicates/missing columns
    ordered_cols = [c for c in ordered_cols if c in combined.columns]
    combined = combined[ordered_cols]

    # Sort by item_id for consistency
    combined = combined.sort_values(by='item_id')

    # Write CSV with UTF-8 and quoting minimal
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(args.out_csv, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f'Wrote combined CSV: {args.out_csv}')


if __name__ == '__main__':
    main()
