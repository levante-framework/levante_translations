#!/usr/bin/env python3
"""
Fetch Latest Translations Script

Downloads the most current item-bank-translations.csv from the l10n_pending branch
and automatically maps the 'identifier' column to 'item_id' for compatibility with
existing scripts. This ensures we're always working with the latest translation data
in the format our scripts expect.

Usage:
    python utilities/fetch_latest_translations.py [--force] [--output PATH]
"""

import os
import sys
import requests
import argparse
from pathlib import Path

# Configuration
GITHUB_RAW_URL = "https://raw.githubusercontent.com/levante-framework/levante_translations/l10n_pending/translations/itembank/item-bank-translations.csv"
DEFAULT_OUTPUT_PATH = "translation_text/item_bank_translations.csv"

def fetch_translations(output_path: str = None, force: bool = False) -> bool:
    """
    Fetch the latest translations from the l10n_pending branch.
    
    Args:
        output_path: Where to save the file (default: translation_text/item_bank_translations.csv)
        force: If True, overwrite existing file without prompting
        
    Returns:
        True if successful, False otherwise
    """
    if not output_path:
        output_path = DEFAULT_OUTPUT_PATH
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Check if file exists and handle overwrite
    if os.path.exists(output_path) and not force:
        response = input(f"File {output_path} already exists. Overwrite? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("❌ Cancelled by user")
            return False
    
    print(f"📥 Fetching latest translations from l10n_pending branch...")
    print(f"   Source: {GITHUB_RAW_URL}")
    print(f"   Target: {output_path}")
    
    try:
        # Download the file
        response = requests.get(GITHUB_RAW_URL, timeout=30)
        response.raise_for_status()
        
        # Validate content
        content = response.content
        if len(content) == 0:
            print("❌ Downloaded file is empty")
            return False
        
        # Check if it looks like a CSV
        content_str = content.decode('utf-8', errors='ignore')
        first_line = content_str.split('\n')[0] if content_str else ""
        if not (('item_id' in first_line or 'identifier' in first_line) and ('labels' in first_line or 'en' in first_line)):
            print("⚠️  Warning: Downloaded content doesn't look like expected CSV format")
            print(f"   First line: {first_line[:100]}...")
        else:
            print(f"✅ Validated CSV format: {len(first_line.split(','))} columns detected")
        
        # Process the CSV header: map columns for dashboard compatibility
        content_lines = content_str.split('\n')
        if content_lines:
            header = content_lines[0].strip('\r')
            changes_made = []
            
            # Map identifier -> item_id for compatibility
            if 'identifier' in header:
                print("🔄 Mapping 'identifier' column to 'item_id' for compatibility...")
                header = header.replace('identifier', 'item_id', 1)
                changes_made.append("identifier→item_id")
            
            # Map text -> en for dashboard compatibility
            if 'text' in header:
                print("🔄 Mapping 'text' column to 'en' for dashboard compatibility...")
                header = header.replace('text', 'en', 1)
                changes_made.append("text→en")
            
            if changes_made:
                content_lines[0] = header
                processed_content = '\n'.join(content_lines)
                content = processed_content.encode('utf-8')
                print(f"✅ Applied column mappings: {', '.join(changes_made)}")
        
        # Write the file
        with open(output_path, 'wb') as f:
            f.write(content)
        
        file_size = len(content)
        line_count = content_str.count('\n')
        
        print(f"✅ Successfully downloaded translations!")
        print(f"   File size: {file_size:,} bytes")
        print(f"   Lines: {line_count:,}")
        print(f"   Saved to: {os.path.abspath(output_path)}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to download file: {e}")
        print(f"   URL: {GITHUB_RAW_URL}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description='Fetch the latest item_bank_translations.csv from l10n_pending branch'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Overwrite existing file without prompting'
    )
    parser.add_argument(
        '--output', '-o',
        help=f'Output file path (default: {DEFAULT_OUTPUT_PATH})'
    )
    parser.add_argument(
        '--check-only', '-c',
        action='store_true',
        help='Check if local file is outdated without downloading'
    )
    
    args = parser.parse_args()
    
    if args.check_only:
        # TODO: Implement age check logic
        print("📋 Check-only mode not yet implemented")
        print("   Use --force to always download the latest version")
        return
    
    success = fetch_translations(args.output, args.force)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()