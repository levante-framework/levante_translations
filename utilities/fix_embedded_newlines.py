#!/usr/bin/env python3
"""
Fix embedded newlines in CSV files that cause parsing issues.
Replaces literal newlines within quoted fields with <br> tags or spaces.
"""

import pandas as pd
import csv
import re

def fix_embedded_newlines(input_file, output_file):
    """Fix embedded newlines in CSV files."""
    
    print(f"Fixing embedded newlines in {input_file}...")
    
    # Read the CSV with proper handling of quoted fields
    try:
        df = pd.read_csv(input_file, quoting=csv.QUOTE_ALL, keep_default_na=False)
        print(f"Loaded {len(df)} rows with {len(df.columns)} columns")
        
        # Fix embedded newlines in all text columns
        for column in df.columns:
            if df[column].dtype == 'object':  # String columns
                # Replace embedded newlines with <br> tags for HTML display
                df[column] = df[column].str.replace('\n', '<br>', regex=False)
                # Also clean up any double spaces
                df[column] = df[column].str.replace('  ', ' ', regex=False)
        
        # Save the cleaned CSV
        df.to_csv(output_file, index=False, quoting=csv.QUOTE_MINIMAL)
        print(f"Fixed CSV saved to {output_file}")
        
        # Show items that were affected
        affected_items = df[df.apply(lambda row: any('<br>' in str(val) for val in row), axis=1)]
        if len(affected_items) > 0:
            print(f"\nFixed {len(affected_items)} items with embedded newlines:")
            for idx, row in affected_items.iterrows():
                print(f"  - {row.get('item_id', row.iloc[0])}")
        
        return True
        
    except Exception as e:
        print(f"Error processing CSV: {e}")
        return False

def validate_fix(file_path):
    """Validate that the fix worked correctly."""
    try:
        df = pd.read_csv(file_path)
        
        # Check for any remaining embedded newlines
        newline_issues = []
        for column in df.columns:
            if df[column].dtype == 'object':
                mask = df[column].str.contains('\n', na=False)
                if mask.any():
                    newline_issues.extend(df[mask]['item_id'].tolist() if 'item_id' in df.columns else df[mask].index.tolist())
        
        if newline_issues:
            print(f"⚠️  Still found newline issues in: {newline_issues}")
            return False
        else:
            print("✅ No embedded newlines found - fix successful!")
            return True
            
    except Exception as e:
        print(f"Error validating fix: {e}")
        return False

if __name__ == "__main__":
    input_file = "translation_master.csv"
    output_file = "translation_master_fixed.csv"
    
    if fix_embedded_newlines(input_file, output_file):
        if validate_fix(output_file):
            print(f"\n🎉 Successfully fixed embedded newlines!")
            print(f"Replace the original file with: mv {output_file} {input_file}")
        else:
            print("❌ Fix validation failed")
    else:
        print("❌ Failed to fix embedded newlines")