#!/usr/bin/env python3
"""
Script to seed a new language in Crowdin by creating a translation CSV.

This script reads item_bank_translations.csv and creates a new CSV file
in Crowdin-compatible format with columns: identifier, source_phrase, context, and target_language.
The target language column is pre-filled with source text as a starting point for translators.

Usage:
    python3 seed_crowdin_language.py <source_lang_code> <new_lang_code>
    
Examples:
    python3 seed_crowdin_language.py en pt-BR
    python3 seed_crowdin_language.py en fr
    python3 seed_crowdin_language.py es-CO es-MX
"""

import argparse
import csv
import os
import sys
from pathlib import Path


def validate_language_code(lang_code, available_codes):
    """Validate that the source language code exists in the CSV."""
    if lang_code not in available_codes:
        print(f"❌ Error: Language code '{lang_code}' not found in item_bank_translations.csv")
        print(f"📋 Available language codes: {', '.join(sorted(available_codes))}")
        return False
    return True


def create_crowdin_seed_csv(source_lang, new_lang, input_file, output_file, mode: str = 'source'):
    """Create a new CSV file for Crowdin with proper structure.

    mode:
      - 'source': monolingual CSV (identifier, source_phrase, context)
      - 'translations': bilingual CSV (identifier, new_lang) with targets prefilled with source
    """
    
    try:
        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            # Validate source language exists
            if source_lang not in reader.fieldnames:
                available_langs = [field for field in reader.fieldnames if field not in ['identifier', 'labels']]
                print(f"❌ Error: Source language '{source_lang}' not found in CSV")
                print(f"📋 Available languages: {', '.join(sorted(available_langs))}")
                return False
            
            # Create output CSV according to mode
            with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
                writer = csv.writer(outfile)
                
                rows_written = 0
                if mode == 'source':
                    # Monolingual CSV: identifier, source_phrase, context
                    writer.writerow(['identifier', 'source_phrase', 'context'])
                    for row in reader:
                        identifier = row.get('identifier', '').strip()
                        source_text = row.get(source_lang, '').strip()
                        context = row.get('labels', '').strip()
                        if identifier and source_text:
                            writer.writerow([identifier, source_text, context])
                            rows_written += 1
                    print(f"✅ Created {output_file}")
                    print(f"📊 Wrote {rows_written} source entries")
                    print(f"📝 Format: Monolingual CSV (identifier, source_phrase, context)")
                    print(f"🎯 Intended use: Add source strings; Crowdin will manage targets for {new_lang}")
                else:
                    # Translations CSV: identifier, source_phrase, <new_lang> with target prefilled as source
                    writer.writerow(['identifier', 'source_phrase', new_lang])
                    for row in reader:
                        identifier = row.get('identifier', '').strip()
                        source_text = row.get(source_lang, '').strip()
                        if identifier and source_text:
                            writer.writerow([identifier, source_text, source_text])
                            rows_written += 1
                    print(f"✅ Created {output_file}")
                    print(f"📊 Wrote {rows_written} translation entries")
                    print(f"📝 Format: Bilingual CSV (identifier, source_phrase, {new_lang})")
                    print(f"🎯 Intended use: Import translations; targets prefilled with source text")
                
                return True
                
    except FileNotFoundError:
        print(f"❌ Error: Input file '{input_file}' not found")
        return False
    except Exception as e:
        print(f"❌ Error creating seed CSV: {e}")
        return False


def create_crowdin_seed_xliff(source_lang, new_lang, input_file, output_file, mode: str = 'source'):
    """Create a new XLIFF file for Crowdin with proper structure.

    mode:
      - 'source': targets empty and state='new'
      - 'translations': targets prefilled with source and state='translated'
    """
    
    try:
        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            # Validate source language exists
            if source_lang not in reader.fieldnames:
                available_langs = [field for field in reader.fieldnames if field not in ['identifier', 'labels']]
                print(f"❌ Error: Source language '{source_lang}' not found in CSV")
                print(f"📋 Available languages: {', '.join(sorted(available_langs))}")
                return False
            
            # Create XLIFF content
            xliff_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="item_bank_translations.csv" source-language="{source_lang}" target-language="{new_lang}" datatype="plaintext">
    <header>
      <tool tool-id="levante-translations" tool-name="Levante Translation Seeder" tool-version="1.0"/>
    </header>
    <body>
'''
            
            rows_written = 0
            with open(input_file, 'r', encoding='utf-8') as infile2:
                reader2 = csv.DictReader(infile2)
                for row in reader2:
                    identifier = row.get('identifier', '').strip()
                    source_text = row.get(source_lang, '').strip()
                    context = row.get('labels', '').strip()
                    if identifier and source_text:
                        # Escape XML characters
                        def esc(s: str) -> str:
                            return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                        source_text_escaped = esc(source_text)
                        context_escaped = esc(context)
                        if mode == 'source':
                            xliff_content += f'''      <trans-unit id="{identifier}" state="new">
        <source>{source_text_escaped}</source>
        <target></target>
        <note>{context_escaped}</note>
      </trans-unit>
'''
                        else:
                            xliff_content += f'''      <trans-unit id="{identifier}">
        <source>{source_text_escaped}</source>
        <target state="translated">{source_text_escaped}</target>
        <note>{context_escaped}</note>
      </trans-unit>
'''
                        rows_written += 1
            
            xliff_content += '''    </body>
  </file>
</xliff>'''
            
            # Write XLIFF file
            with open(output_file, 'w', encoding='utf-8') as outfile:
                outfile.write(xliff_content)
            
            print(f"✅ Created {output_file}")
            print(f"📊 Wrote {rows_written} translation units")
            if mode == 'source':
                print(f"📝 Format: XLIFF 1.2 (targets empty, state='new')")
                print(f"🎯 Intended use: Add source strings for {new_lang}; translators fill targets")
            else:
                print(f"📝 Format: XLIFF 1.2 (targets prefilled, state='translated')")
                print(f"🎯 Intended use: Import translations (seed targets with source text)")
            return True
            
    except FileNotFoundError:
        print(f"❌ Error: Input file '{input_file}' not found")
        return False
    except Exception as e:
        print(f"❌ Error creating seed XLIFF: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Create a Crowdin seed CSV for a new language",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 seed_crowdin_language.py en pt-BR              # English to Portuguese (Brazil) - CSV format
  python3 seed_crowdin_language.py en fr --format xliff  # English to French - XLIFF format
  python3 seed_crowdin_language.py es-CO es-MX -f csv    # Spanish (Colombia) to Spanish (Mexico) - CSV format
  
Output formats:
- CSV: Crowdin-compatible CSV with columns: identifier, source_phrase, context, target_language
- XLIFF: Standard XLIFF 1.2 format with translation units
Both formats contain source text as a starting point for translators.
        """
    )
    
    parser.add_argument('source_lang', 
                       help='Source language code (e.g., en, es-CO, de)')
    parser.add_argument('new_lang', 
                       help='New target language code (e.g., pt-BR, fr, es-MX)')
    parser.add_argument('--input', '-i',
                       default='translation_text/item_bank_translations.csv',
                       help='Input CSV file (default: translation_text/item_bank_translations.csv)')
    parser.add_argument('--format', '-f',
                       choices=['csv', 'xliff'],
                       default='csv',
                       help='Output format: csv (Crowdin CSV) or xliff (XLIFF 1.2) (default: csv)')
    parser.add_argument('--mode', '-m',
                       choices=['source', 'translations'],
                       default='source',
                       help='File intent: source (add strings) or translations (import prefilled targets) (default: source)')
    
    args = parser.parse_args()
    
    # Determine paths
    script_dir = Path(__file__).parent
    input_file = script_dir / args.input
    output_dir = script_dir / 'translation_text'
    
    # Determine output file extension based on format
    file_extension = 'csv' if args.format == 'csv' else 'xlf'
    output_file = output_dir / f"{args.new_lang}_translations.{file_extension}"
    
    # Ensure output directory exists
    output_dir.mkdir(exist_ok=True)
    
    # Validate input file exists
    if not input_file.exists():
        print(f"❌ Error: Input file '{input_file}' not found")
        sys.exit(1)
    
    # Check if output file already exists
    if output_file.exists():
        response = input(f"⚠️  Output file '{output_file}' already exists. Overwrite? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("❌ Operation cancelled")
            sys.exit(1)
    
    print(f"🌍 Creating Crowdin seed {args.format.upper()} for {args.new_lang}")
    print(f"📖 Source language: {args.source_lang}")
    print(f"🎯 Target language: {args.new_lang}")
    print(f"📄 Output format: {args.format.upper()}")
    print(f"📁 Input file: {input_file}")
    print(f"📁 Output file: {output_file}")
    print()
    
    # Create the seed file based on format
    if args.format == 'csv':
        success = create_crowdin_seed_csv(args.source_lang, args.new_lang, input_file, output_file, args.mode)
    else:  # xliff
        success = create_crowdin_seed_xliff(args.source_lang, args.new_lang, input_file, output_file, args.mode)
    
    if success:
        print()
        format_name = "CSV" if args.format == 'csv' else "XLIFF"
        print(f"🎉 Crowdin seed {format_name} created successfully!")
        print()
        print("📋 Next steps:")
        print(f"1. Upload '{output_file.name}' to Crowdin")
        print("2. Set up the translation project with source and target languages")
        print("3. Assign translators to begin translation work")
        print("4. Download completed translations and update item_bank_translations.csv")
        if args.format == 'csv':
            print()
            print("💡 Tip: If CSV import fails, try XLIFF format with --format xliff")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
