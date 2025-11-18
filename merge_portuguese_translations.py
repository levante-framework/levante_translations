#!/usr/bin/env python3
"""
Merge Portuguese translations from Crowdin export into item_bank_translations.csv

Usage:
    python3 merge_portuguese_translations.py <path_to_downloaded_excel_file.xlsx>

This script:
1. Reads the downloaded Excel file from Crowdin (with pt-PT translations)
2. Merges the pt-PT column into translation_text/item_bank_translations.csv
3. Matches rows by item_id
"""

import sys
import pandas as pd
from pathlib import Path

def merge_translations(excel_path: str):
    """Merge Portuguese translations from Excel file into CSV."""
    
    excel_path = Path(excel_path)
    if not excel_path.exists():
        print(f"❌ Error: File not found: {excel_path}")
        return False
    
    csv_path = Path('translation_text/item_bank_translations.csv')
    if not csv_path.exists():
        print(f"❌ Error: CSV file not found: {csv_path}")
        return False
    
    print(f"📖 Reading Excel file: {excel_path}")
    try:
        df_excel = pd.read_excel(excel_path)
    except Exception as e:
        print(f"❌ Error reading Excel file: {e}")
        return False
    
    print(f"   Columns: {list(df_excel.columns)}")
    print(f"   Rows: {len(df_excel)}")
    
    if 'pt-PT' not in df_excel.columns:
        print(f"❌ Error: Excel file does not have 'pt-PT' column")
        print(f"   Available columns: {list(df_excel.columns)}")
        return False
    
    if 'item_id' not in df_excel.columns:
        print(f"❌ Error: Excel file does not have 'item_id' column")
        print(f"   Available columns: {list(df_excel.columns)}")
        return False
    
    # Count non-empty translations
    non_empty = df_excel['pt-PT'].notna() & (df_excel['pt-PT'] != '') & (df_excel['pt-PT'].astype(str).str.strip() != '')
    print(f"✅ Found {non_empty.sum()} non-empty Portuguese translations in Excel file")
    
    if non_empty.sum() == 0:
        print("⚠️  Warning: No translations found in Excel file")
        return False
    
    print(f"\n📖 Reading CSV file: {csv_path}")
    df_csv = pd.read_csv(csv_path)
    print(f"   Rows: {len(df_csv)}")
    
    # Merge translations
    print(f"\n🔀 Merging translations...")
    df_merged = df_csv.merge(
        df_excel[['item_id', 'pt-PT']],
        on='item_id',
        how='left',
        suffixes=('', '_new')
    )
    
    # Use new pt-PT column, keep old if new is empty
    if 'pt-PT_new' in df_merged.columns:
        # Fill empty values from old column if it exists
        old_pt = df_merged.get('pt-PT', '')
        new_pt = df_merged['pt-PT_new']
        df_merged['pt-PT'] = new_pt.fillna(old_pt)
        df_merged = df_merged.drop(columns=['pt-PT_new'], errors='ignore')
    elif 'pt-PT' not in df_merged.columns:
        # If pt-PT didn't exist, use the new one
        df_merged['pt-PT'] = df_merged.get('pt-PT_new', '')
        df_merged = df_merged.drop(columns=['pt-PT_new'], errors='ignore')
    
    # Save updated CSV
    df_merged.to_csv(csv_path, index=False)
    
    # Count final translations
    final_non_empty = df_merged['pt-PT'].notna() & (df_merged['pt-PT'] != '') & (df_merged['pt-PT'].astype(str).str.strip() != '')
    print(f"✅ Successfully merged {final_non_empty.sum()} Portuguese translations into CSV!")
    
    print(f"\n📊 Sample translations:")
    sample = df_merged[final_non_empty][['item_id', 'en', 'pt-PT']].head(5)
    for idx, row in sample.iterrows():
        print(f"   {row['item_id']}:")
        print(f"     EN: {str(row['en'])[:60]}...")
        print(f"     PT: {str(row['pt-PT'])[:60]}...")
        print()
    
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 merge_portuguese_translations.py <path_to_excel_file.xlsx>")
        print("\nExample:")
        print("  python3 merge_portuguese_translations.py ~/Downloads/levantetranslations-pt-PT.xlsx")
        sys.exit(1)
    
    excel_file = sys.argv[1]
    success = merge_translations(excel_file)
    
    if success:
        print("\n✅ Done! You can now run:")
        print("   python3 generate_speech.py Portuguese")
    else:
        print("\n❌ Failed to merge translations")
        sys.exit(1)

