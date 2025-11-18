#!/usr/bin/env python3
"""
Add Portuguese (pt) translations to Crowdin using Google Translate.

This script:
1. Reads source strings from item_bank_translations.csv (English)
2. Translates them to Portuguese using Google Translate API
3. Creates a CSV/XLIFF file with translations
4. Optionally uploads to Crowdin

Usage:
    python3 add_portuguese_translations.py [--api-key GOOGLE_API_KEY] [--upload] [--dry-run]
    
Environment variables:
    GOOGLE_TRANSLATE_API_KEY: Google Translate API key (or use --api-key)
    CROWDIN_API_TOKEN: Crowdin API token (required for --upload)
    CROWDIN_PROJECT_ID: Crowdin project ID (required for --upload)
"""

import argparse
import csv
import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Optional

# Prefer requests if available
try:
    import requests
except ImportError:
    requests = None

import urllib.request
import urllib.parse
import urllib.error


def get_google_translate_api_key(args_api_key: Optional[str]) -> Optional[str]:
    """Get Google Translate API key from args or environment."""
    if args_api_key:
        return args_api_key
    return os.environ.get('GOOGLE_TRANSLATE_API_KEY')


def translate_text(text: str, source_lang: str, target_lang: str, api_key: str) -> Optional[str]:
    """Translate text using Google Translate API."""
    if not text or not text.strip():
        return text
    
    translate_url = f"https://translation.googleapis.com/language/translate/v2?key={api_key}"
    
    # Use form-encoded data
    form_data = urllib.parse.urlencode({
        'q': text,
        'source': source_lang,
        'target': target_lang,
        'format': 'text'
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(translate_url, data=form_data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            
            if not data.get('data') or not data['data'].get('translations'):
                print(f"⚠️  Warning: Invalid response for text: {text[:50]}...")
                return None
            
            translated_text = data['data']['translations'][0]['translatedText']
            return translated_text
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if hasattr(e, 'read') else str(e)
        print(f"❌ HTTP Error translating text: {e.code} - {error_body[:200]}")
        return None
    except Exception as e:
        print(f"❌ Error translating text: {e}")
        return None


def create_translations_csv(
    input_file: Path,
    output_file: Path,
    source_lang: str,
    target_lang: str,
    api_key: str,
    dry_run: bool = False
) -> bool:
    """Create CSV file with Portuguese translations."""
    
    if not input_file.exists():
        print(f"❌ Error: Input file '{input_file}' not found")
        return False
    
    translations = []
    total_rows = 0
    translated_rows = 0
    failed_rows = 0
    
    print(f"📖 Reading source strings from: {input_file}")
    print(f"🌍 Translating from {source_lang} to {target_lang}")
    print(f"🔑 Using Google Translate API")
    if dry_run:
        print("🔍 DRY RUN MODE - No translations will be performed")
    print()
    
    try:
        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            if source_lang not in reader.fieldnames:
                available_langs = [f for f in reader.fieldnames if f not in ['identifier', 'labels']]
                print(f"❌ Error: Source language '{source_lang}' not found in CSV")
                print(f"📋 Available languages: {', '.join(sorted(available_langs))}")
                return False
            
            # Read all rows first
            rows = list(reader)
            total_rows = len(rows)
            
            print(f"📊 Found {total_rows} rows to translate")
            print()
            
            for idx, row in enumerate(rows, 1):
                identifier = row.get('identifier', '').strip()
                source_text = row.get(source_lang, '').strip()
                context = row.get('labels', '').strip()
                
                if not identifier:
                    continue
                
                if not source_text:
                    # Empty source, skip
                    translations.append({
                        'identifier': identifier,
                        'source_phrase': '',
                        target_lang: '',
                        'context': context
                    })
                    continue
                
                if dry_run:
                    print(f"[{idx}/{total_rows}] Would translate: {identifier} -> {source_text[:50]}...")
                    translations.append({
                        'identifier': identifier,
                        'source_phrase': source_text,
                        target_lang: f"[TRANSLATED: {source_text}]",
                        'context': context
                    })
                else:
                    print(f"[{idx}/{total_rows}] Translating: {identifier}...", end=' ', flush=True)
                    
                    translated_text = translate_text(source_text, source_lang, target_lang, api_key)
                    
                    if translated_text:
                        translations.append({
                            'identifier': identifier,
                            'source_phrase': source_text,
                            target_lang: translated_text,
                            'context': context
                        })
                        translated_rows += 1
                        print("✅")
                    else:
                        translations.append({
                            'identifier': identifier,
                            'source_phrase': source_text,
                            target_lang: '',
                            'context': context
                        })
                        failed_rows += 1
                        print("❌")
                    
                    # Rate limiting - be nice to the API
                    if idx % 10 == 0:
                        time.sleep(0.5)  # Small delay every 10 requests
            
            # Write output CSV
            if not dry_run:
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                fieldnames = ['identifier', 'source_phrase', target_lang, 'context']
                with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
                    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(translations)
                
                print()
                print(f"✅ Created translation CSV: {output_file}")
                print(f"📊 Statistics:")
                print(f"   Total rows: {total_rows}")
                print(f"   Successfully translated: {translated_rows}")
                print(f"   Failed: {failed_rows}")
                print(f"   Empty source: {total_rows - translated_rows - failed_rows}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error processing CSV: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_translations_xliff(
    input_file: Path,
    output_file: Path,
    source_lang: str,
    target_lang: str,
    api_key: str,
    dry_run: bool = False
) -> bool:
    """Create XLIFF file with Portuguese translations."""
    
    if not input_file.exists():
        print(f"❌ Error: Input file '{input_file}' not found")
        return False
    
    translations = []
    total_rows = 0
    translated_rows = 0
    failed_rows = 0
    
    print(f"📖 Reading source strings from: {input_file}")
    print(f"🌍 Translating from {source_lang} to {target_lang}")
    print(f"🔑 Using Google Translate API")
    if dry_run:
        print("🔍 DRY RUN MODE - No translations will be performed")
    print()
    
    try:
        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            if source_lang not in reader.fieldnames:
                available_langs = [f for f in reader.fieldnames if f not in ['identifier', 'labels']]
                print(f"❌ Error: Source language '{source_lang}' not found in CSV")
                print(f"📋 Available languages: {', '.join(sorted(available_langs))}")
                return False
            
            rows = list(reader)
            total_rows = len(rows)
            
            print(f"📊 Found {total_rows} rows to translate")
            print()
            
            for idx, row in enumerate(rows, 1):
                identifier = row.get('identifier', '').strip()
                source_text = row.get(source_lang, '').strip()
                context = row.get('labels', '').strip()
                
                if not identifier:
                    continue
                
                if not source_text:
                    translations.append({
                        'id': identifier,
                        'source': '',
                        'target': '',
                        'context': context
                    })
                    continue
                
                if dry_run:
                    print(f"[{idx}/{total_rows}] Would translate: {identifier} -> {source_text[:50]}...")
                    translations.append({
                        'id': identifier,
                        'source': source_text,
                        'target': f"[TRANSLATED: {source_text}]",
                        'context': context
                    })
                else:
                    print(f"[{idx}/{total_rows}] Translating: {identifier}...", end=' ', flush=True)
                    
                    translated_text = translate_text(source_text, source_lang, target_lang, api_key)
                    
                    if translated_text:
                        translations.append({
                            'id': identifier,
                            'source': source_text,
                            'target': translated_text,
                            'context': context
                        })
                        translated_rows += 1
                        print("✅")
                    else:
                        translations.append({
                            'id': identifier,
                            'source': source_text,
                            'target': '',
                            'context': context
                        })
                        failed_rows += 1
                        print("❌")
                    
                    if idx % 10 == 0:
                        time.sleep(0.5)
            
            # Write XLIFF file
            if not dry_run:
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                def esc(s: str) -> str:
                    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                
                xliff_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="item_bank_translations.csv" source-language="{source_lang}" target-language="{target_lang}" datatype="plaintext">
    <header>
      <tool tool-id="levante-translations" tool-name="Portuguese Translation Generator" tool-version="1.0"/>
    </header>
    <body>
'''
                
                for trans in translations:
                    source_escaped = esc(trans['source'])
                    target_escaped = esc(trans['target'])
                    context_escaped = esc(trans['context'])
                    
                    xliff_content += f'''      <trans-unit id="{trans['id']}" state="translated">
        <source>{source_escaped}</source>
        <target>{target_escaped}</target>
        <note>{context_escaped}</note>
      </trans-unit>
'''
                
                xliff_content += '''    </body>
  </file>
</xliff>'''
                
                with open(output_file, 'w', encoding='utf-8') as outfile:
                    outfile.write(xliff_content)
                
                print()
                print(f"✅ Created translation XLIFF: {output_file}")
                print(f"📊 Statistics:")
                print(f"   Total rows: {total_rows}")
                print(f"   Successfully translated: {translated_rows}")
                print(f"   Failed: {failed_rows}")
                print(f"   Empty source: {total_rows - translated_rows - failed_rows}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error processing CSV: {e}")
        import traceback
        traceback.print_exc()
        return False


def upload_to_crowdin(file_path: Path, project_id: str, api_token: str, crowdin_path: str = "/translations/") -> bool:
    """Upload translation file to Crowdin."""
    try:
        # Import the XLIFF manager utilities
        sys.path.insert(0, str(Path(__file__).parent))
        from utilities.crowdin_xliff_manager import upload_xliff_file
        
        # Create headers with API token
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        file_name = file_path.name
        
        # Determine Crowdin path
        if file_path.suffix in ['.xlf', '.xliff']:
            crowdin_file_path = f"{crowdin_path.rstrip('/')}/{file_name}"
        else:
            # For CSV, we might need to convert or use a different method
            print("⚠️  Warning: CSV upload not directly supported. Converting to XLIFF or use Crowdin web UI.")
            print(f"   You can manually upload {file_path} via Crowdin web UI")
            return False
        
        print(f"📤 Uploading {file_name} to Crowdin...")
        result = upload_xliff_file(project_id, headers, str(file_path), crowdin_file_path, update_existing=True)
        
        if result:
            print(f"✅ Successfully uploaded to Crowdin: {crowdin_file_path}")
            return True
        else:
            print(f"❌ Failed to upload to Crowdin")
            return False
            
    except Exception as e:
        print(f"❌ Error uploading to Crowdin: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Add Portuguese translations using Google Translate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 add_portuguese_translations.py --api-key YOUR_API_KEY
  python3 add_portuguese_translations.py --upload
  python3 add_portuguese_translations.py --dry-run
  
The script will:
1. Read English source strings from item_bank_translations.csv
2. Translate them to Portuguese using Google Translate API
3. Create a CSV/XLIFF file with translations
4. Optionally upload to Crowdin
        """
    )
    
    parser.add_argument('--api-key', '-k',
                       help='Google Translate API key (or set GOOGLE_TRANSLATE_API_KEY env var)')
    parser.add_argument('--input', '-i',
                       default='translation_text/item_bank_translations.csv',
                       help='Input CSV file (default: translation_text/item_bank_translations.csv)')
    parser.add_argument('--output', '-o',
                       help='Output file path (default: translation_text/eo_translations.csv or .xlf)')
    parser.add_argument('--format', '-f',
                       choices=['csv', 'xliff', 'xlf'],
                       default='csv',
                       help='Output format: csv or xliff (default: csv)')
    parser.add_argument('--source-lang', '-s',
                       default='en',
                       help='Source language code (default: en)')
    parser.add_argument('--target-lang', '-t',
                       default='pt',
                       help='Target language code (default: pt for Portuguese)')
    parser.add_argument('--upload', '-u',
                       action='store_true',
                       help='Upload translations to Crowdin (requires CROWDIN_API_TOKEN and CROWDIN_PROJECT_ID)')
    parser.add_argument('--dry-run',
                       action='store_true',
                       help='Dry run mode - show what would be translated without actually translating')
    
    args = parser.parse_args()
    
    # Get API key
    api_key = get_google_translate_api_key(args.api_key)
    if not api_key and not args.dry_run:
        print("❌ Error: Google Translate API key required")
        print("   Set GOOGLE_TRANSLATE_API_KEY environment variable or use --api-key")
        sys.exit(1)
    
    # Determine paths
    script_dir = Path(__file__).parent
    input_file = script_dir / args.input
    
    if args.output:
        output_file = Path(args.output)
    else:
        output_dir = script_dir / 'translation_text'
        extension = 'csv' if args.format == 'csv' else 'xlf'
        output_file = output_dir / f"{args.target_lang}_translations.{extension}"
    
    # Validate input file
    if not input_file.exists():
        print(f"❌ Error: Input file '{input_file}' not found")
        sys.exit(1)
    
    print(f"🌍 Adding {args.target_lang} translations")
    print(f"📖 Source language: {args.source_lang}")
    print(f"🎯 Target language: {args.target_lang}")
    print(f"📄 Input file: {input_file}")
    print(f"📄 Output file: {output_file}")
    print(f"📝 Format: {args.format.upper()}")
    print()
    
    # Create translations
    if args.format == 'csv':
        success = create_translations_csv(
            input_file, output_file, args.source_lang, args.target_lang,
            api_key or 'dummy-key', args.dry_run
        )
    else:  # xliff
        success = create_translations_xliff(
            input_file, output_file, args.source_lang, args.target_lang,
            api_key or 'dummy-key', args.dry_run
        )
    
    if not success:
        sys.exit(1)
    
    # Upload to Crowdin if requested
    if args.upload and not args.dry_run:
        project_id = os.environ.get('CROWDIN_PROJECT_ID')
        api_token = os.environ.get('CROWDIN_API_TOKEN')
        
        if not project_id or not api_token:
            print("⚠️  Warning: CROWDIN_PROJECT_ID and CROWDIN_API_TOKEN required for upload")
            print("   Skipping upload. You can upload manually via Crowdin web UI.")
        else:
            upload_to_crowdin(output_file, project_id, api_token)
    
    print()
    print("🎉 Translation generation complete!")
    if not args.upload:
        print(f"📋 Next steps:")
        print(f"1. Review the translations in: {output_file}")
        print(f"2. Upload to Crowdin via web UI or use --upload flag")
        print(f"3. Review and refine translations in Crowdin")


if __name__ == "__main__":
    main()

