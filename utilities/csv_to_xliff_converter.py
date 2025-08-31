#!/usr/bin/env python3
"""
csv_to_xliff_converter.py

Convert existing CSV translations to XLIFF 1.2 format for improved localization workflow.

This tool:
1. Reads item-bank-translations.csv and surveys.csv
2. Creates separate XLIFF files per language
3. Preserves all translation data with proper XLIFF structure
4. Adds translation states (new/translated) based on content
5. Includes context information from CSV columns

Usage:
    python utilities/csv_to_xliff_converter.py --input translation_text/item_bank_translations.csv --output-dir xliff-export/
    python utilities/csv_to_xliff_converter.py --input surveys.csv --output-dir xliff-export/ --file-type surveys
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
import xml.etree.ElementTree as ET
from xml.dom import minidom

def create_xliff_structure(source_lang: str = "en", target_lang: str = "en-US") -> ET.Element:
    """Create basic XLIFF 1.2 structure."""
    xliff = ET.Element("xliff")
    xliff.set("version", "1.2")
    xliff.set("xmlns", "urn:oasis:names:tc:xliff:document:1.2")
    
    file_elem = ET.SubElement(xliff, "file")
    file_elem.set("source-language", source_lang)
    file_elem.set("target-language", target_lang)
    file_elem.set("datatype", "plaintext")
    file_elem.set("original", "levante-translations")
    file_elem.set("date", datetime.now().isoformat())
    
    header = ET.SubElement(file_elem, "header")
    tool = ET.SubElement(header, "tool")
    tool.set("tool-id", "csv-to-xliff-converter")
    tool.set("tool-name", "Levante CSV to XLIFF Converter")
    tool.set("tool-version", "1.0")
    
    body = ET.SubElement(file_elem, "body")
    return xliff, body

def escape_xml_text(text: str) -> str:
    """Escape text for XML while preserving ICU formatting."""
    if not text:
        return ""
    
    # Convert to string and handle None
    text = str(text) if text is not None else ""
    
    # Remove or replace problematic characters
    # Remove control characters except tab, newline, carriage return
    import re
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Basic XML escaping (order matters - & first!)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&apos;")
    
    return text

def determine_translation_state(source_text: str, target_text: str, target_lang: str) -> str:
    """Determine XLIFF translation state based on content."""
    if not target_text or target_text.strip() == "":
        return "new"
    if target_text == source_text:
        # Same as source - might be intentional for English variants or untranslated
        if target_lang.startswith("en"):
            return "translated"  # English variants often keep same text
        else:
            return "new"  # Non-English should be translated
    return "translated"

def add_trans_unit(body: ET.Element, identifier: str, source_text: str, target_text: str, 
                   target_lang: str, context: Optional[str] = None, task: Optional[str] = None) -> None:
    """Add a translation unit to the XLIFF body."""
    trans_unit = ET.SubElement(body, "trans-unit")
    trans_unit.set("id", identifier)
    trans_unit.set("resname", identifier)  # Use resname as preferred identifier
    
    # Add translation state
    state = determine_translation_state(source_text, target_text, target_lang)
    trans_unit.set("approved", "yes" if state == "translated" else "no")
    
    # Source element
    source = ET.SubElement(trans_unit, "source")
    source.text = escape_xml_text(source_text)
    
    # Target element (if we have translation)
    if target_text and target_text.strip():
        target = ET.SubElement(trans_unit, "target")
        target.text = escape_xml_text(target_text)
        target.set("state", state)
    
    # Add context notes
    if context or task:
        note = ET.SubElement(trans_unit, "note")
        note.set("from", "developer")
        note_parts = []
        if task:
            note_parts.append(f"Task: {task}")
        if context:
            note_parts.append(f"Context: {context}")
        note.text = " | ".join(note_parts)

def convert_csv_to_xliff(csv_path: str, output_dir: str, file_type: str = "itembank") -> Dict[str, str]:
    """Convert CSV file to XLIFF files per language."""
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Read CSV
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    if not rows:
        raise ValueError("CSV file is empty or has no data rows")
    
    # Identify language columns (exclude metadata columns)
    metadata_columns = {'identifier', 'item_id', 'labels', 'label', 'task', 'context', 'source_text', 'text', ''}
    all_columns = set(reader.fieldnames or [])
    potential_lang_columns = all_columns - metadata_columns
    
    # Filter to valid language codes (2-5 chars, letters/hyphens only)
    import re
    language_columns = set()
    for col in potential_lang_columns:
        if col and re.match(r'^[a-zA-Z]{2}(-[a-zA-Z]{2})?$', col):
            language_columns.add(col)
    
    print(f"Found {len(language_columns)} language columns: {sorted(language_columns)}")
    print(f"Processing {len(rows)} translation entries")
    
    created_files = {}
    
    for lang_code in sorted(language_columns):
        print(f"\nProcessing language: {lang_code}")
        
        # Create XLIFF structure
        xliff_root, body = create_xliff_structure(source_lang="en", target_lang=lang_code)
        
        translated_count = 0
        total_count = 0
        
        for row in rows:
            # Get identifier (prefer item_id, fallback to identifier)
            identifier = row.get('item_id') or row.get('identifier', '')
            if not identifier:
                continue
                
            # Get source text (English)
            source_text = row.get('en-US', '') or row.get('en', '') or row.get('source_text', '')
            if not source_text:
                # Skip entries without source text
                continue
            
            # Get target text
            target_text = row.get(lang_code, '')
            
            # Get context information
            context = row.get('context', '')
            task = row.get('task') or row.get('labels') or row.get('label', '')
            
            # Add translation unit
            add_trans_unit(body, identifier, source_text, target_text, lang_code, context, task)
            
            total_count += 1
            if target_text and target_text.strip():
                translated_count += 1
        
        if total_count == 0:
            print(f"  No valid entries found for {lang_code}")
            continue
            
        # Write XLIFF file
        filename = f"{file_type}-{lang_code}.xliff"
        output_path = os.path.join(output_dir, filename)
        
        # Generate XML with proper encoding
        try:
            # Use ElementTree's built-in XML generation with UTF-8
            rough_string = ET.tostring(xliff_root, encoding='utf-8', xml_declaration=True)
            
            # Parse and pretty print
            reparsed = minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent="  ", encoding=None)
            
            # Remove empty lines and fix encoding declaration
            pretty_lines = [line for line in pretty_xml.split('\n') if line.strip()]
            if pretty_lines and pretty_lines[0].startswith('<?xml'):
                pretty_lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
            pretty_xml = '\n'.join(pretty_lines)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(pretty_xml)
                
        except Exception as xml_error:
            print(f"  ❌ XML generation error for {lang_code}: {xml_error}")
            # Try simpler approach without pretty printing
            with open(output_path, 'wb') as f:
                f.write(ET.tostring(xliff_root, encoding='utf-8', xml_declaration=True))
        
        created_files[lang_code] = output_path
        print(f"  Created: {output_path}")
        print(f"  Stats: {translated_count}/{total_count} translated ({translated_count/total_count*100:.1f}%)")
    
    return created_files

def main():
    parser = argparse.ArgumentParser(
        description="Convert CSV translations to XLIFF 1.2 format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert item bank translations
  python utilities/csv_to_xliff_converter.py --input translation_text/item_bank_translations.csv --output-dir xliff-export/
  
  # Convert surveys
  python utilities/csv_to_xliff_converter.py --input surveys.csv --output-dir xliff-export/ --file-type surveys
  
  # Convert with custom source language
  python utilities/csv_to_xliff_converter.py --input data.csv --output-dir out/ --source-lang en-US
        """
    )
    
    parser.add_argument('--input', '-i', required=True,
                       help='Input CSV file path')
    parser.add_argument('--output-dir', '-o', default='xliff-export',
                       help='Output directory for XLIFF files (default: xliff-export)')
    parser.add_argument('--file-type', '-t', default='itembank',
                       choices=['itembank', 'surveys'],
                       help='Type of translation file (affects filename prefix)')
    parser.add_argument('--source-lang', '-s', default='en',
                       help='Source language code (default: en)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without creating files')
    
    args = parser.parse_args()
    
    try:
        if args.dry_run:
            print(f"DRY RUN: Would convert {args.input} to XLIFF files in {args.output_dir}")
            return 0
            
        created_files = convert_csv_to_xliff(args.input, args.output_dir, args.file_type)
        
        print(f"\n✅ Successfully created {len(created_files)} XLIFF files:")
        for lang, path in created_files.items():
            print(f"  {lang}: {path}")
            
        print(f"\nNext steps:")
        print(f"1. Review generated XLIFF files in {args.output_dir}")
        print(f"2. Upload to Crowdin to replace CSV workflow")
        print(f"3. Update deployment pipeline to use XLIFF as primary source")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
