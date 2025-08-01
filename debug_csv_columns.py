#!/usr/bin/env python3
"""
Debug script to check what columns are available in the CSV and find Spanish translations.
"""

import pandas as pd
import utilities.config as conf

print("=== Debugging CSV Columns and Spanish Translations ===")
print(f"Source URL: {conf.item_bank_translations}")
print(f"Expected Spanish code from config: {conf.LANGUAGE_CODES['Spanish']}")

try:
    # Load the CSV
    df = pd.read_csv(conf.item_bank_translations)
    print(f"\nSUCCESS: Loaded CSV with {len(df)} rows")
    
    print(f"\nAvailable columns ({len(df.columns)}):")
    for i, col in enumerate(df.columns):
        print(f"  {i+1:2d}. '{col}'")
    
    # Look for Spanish-related columns
    spanish_cols = [col for col in df.columns if 'es' in col.lower()]
    print(f"\nSpanish-related columns: {spanish_cols}")
    
    # Check for common Spanish column names
    possible_spanish_cols = ['es', 'es-co', 'es-CO', 'Spanish', 'spanish']
    found_spanish_cols = [col for col in possible_spanish_cols if col in df.columns]
    print(f"Found Spanish columns from common names: {found_spanish_cols}")
    
    # Check if any Spanish translations exist
    for col in spanish_cols + found_spanish_cols:
        if col in df.columns:
            non_null_count = df[col].notna().sum()
            print(f"\nColumn '{col}':")
            print(f"  Non-null entries: {non_null_count}")
            if non_null_count > 0:
                print("  Sample entries:")
                samples = df[df[col].notna()][col].head(3).tolist()
                for i, sample in enumerate(samples, 1):
                    print(f"    {i}. {sample[:100]}...")
    
    # Check first few rows to see what data looks like
    print(f"\nFirst 3 rows of data:")
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    print(df.head(3))
    
except Exception as e:
    print(f"ERROR: {str(e)}")