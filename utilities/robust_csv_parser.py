#!/usr/bin/env python3
"""
Robust CSV parsing utility that handles embedded newlines and malformed CSV files.
This module provides functions to safely parse CSV files that may contain
embedded newlines within quoted fields.
"""

import csv
import re
import io
from typing import List, Dict, Any, Optional

def parse_csv_robust(file_path: str, encoding: str = 'utf-8') -> List[Dict[str, Any]]:
    """
    Robustly parse a CSV file that may contain embedded newlines.
    
    Args:
        file_path: Path to the CSV file
        encoding: File encoding (default: utf-8)
        
    Returns:
        List of dictionaries representing the CSV rows
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        Exception: For other parsing errors
    """
    try:
        with open(file_path, 'r', encoding=encoding, newline='') as file:
            content = file.read()
        
        return parse_csv_content_robust(content)
        
    except FileNotFoundError:
        raise FileNotFoundError(f"CSV file not found: {file_path}")
    except Exception as e:
        print(f"Error reading CSV file {file_path}: {e}")
        raise

def parse_csv_content_robust(csv_content: str) -> List[Dict[str, Any]]:
    """
    Robustly parse CSV content that may contain embedded newlines.
    
    Args:
        csv_content: Raw CSV content as string
        
    Returns:
        List of dictionaries representing the CSV rows
    """
    if not csv_content or not csv_content.strip():
        return []
    
    print("🔧 Robust CSV Parser: Starting parse...")
    
    # Parse the CSV content into rows
    rows = _parse_csv_with_embedded_newlines(csv_content)
    
    if not rows:
        print("⚠️  No valid rows found in CSV")
        return []
    
    # Use first row as headers
    headers = rows[0]
    data = []
    
    print(f"📋 Headers: {headers}")
    
    # Process data rows
    for i, row in enumerate(rows[1:], 1):
        if len(row) >= len(headers):
            row_dict = {}
            for j, header in enumerate(headers):
                value = row[j] if j < len(row) else ''
                
                # Clean up embedded newlines
                if isinstance(value, str):
                    # Replace literal newlines with <br> for HTML display
                    value = value.replace('\n', '<br>')
                    # Clean up extra whitespace
                    value = re.sub(r'\s+', ' ', value).strip()
                
                row_dict[header] = value
            
            data.append(row_dict)
        else:
            print(f"⚠️  Row {i} has {len(row)} columns, expected {len(headers)} - skipping")
    
    print(f"✅ Parsed {len(data)} rows successfully")
    
    # Normalize field names for compatibility
    normalized_data = _normalize_field_names(data)
    
    return normalized_data

def _parse_csv_with_embedded_newlines(csv_content: str) -> List[List[str]]:
    """
    Parse CSV content handling embedded newlines within quoted fields.
    
    Args:
        csv_content: Raw CSV content
        
    Returns:
        List of rows, where each row is a list of field values
    """
    rows = []
    current_row = []
    current_field = ''
    in_quotes = False
    i = 0
    
    while i < len(csv_content):
        char = csv_content[i]
        next_char = csv_content[i + 1] if i + 1 < len(csv_content) else None
        
        if char == '"':
            if in_quotes and next_char == '"':
                # Escaped quote - add literal quote to field
                current_field += '"'
                i += 2  # Skip both quotes
            else:
                # Toggle quote state
                in_quotes = not in_quotes
                i += 1
        elif char == ',' and not in_quotes:
            # Field separator outside quotes
            current_row.append(current_field.strip())
            current_field = ''
            i += 1
        elif char in ['\n', '\r'] and not in_quotes:
            # Row separator outside quotes
            if current_field.strip() or current_row:
                current_row.append(current_field.strip())
                if any(field.strip() for field in current_row):
                    rows.append(current_row)
                current_row = []
                current_field = ''
            
            # Skip \r\n combinations
            if char == '\r' and next_char == '\n':
                i += 2
            else:
                i += 1
        else:
            # Regular character or newline inside quotes
            current_field += char
            i += 1
    
    # Handle final field/row
    if current_field.strip() or current_row:
        current_row.append(current_field.strip())
        if any(field.strip() for field in current_row):
            rows.append(current_row)
    
    # Filter out completely empty rows
    valid_rows = [row for row in rows if any(field.strip() for field in row)]
    
    print(f"🔧 Found {len(valid_rows)} valid rows")
    return valid_rows

def _normalize_field_names(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize field names for consistency across different CSV formats.
    
    Args:
        data: List of row dictionaries
        
    Returns:
        List of normalized row dictionaries
    """
    normalized_data = []
    
    for item in data:
        # Create normalized item
        normalized_item = dict(item)  # Copy all original fields
        
        # Handle different possible column names for ID
        item_id = (item.get('identifier') or 
                  item.get('item_id') or 
                  item.get('id') or 
                  item.get('ID') or 
                  item.get('Item_ID'))
        
        if item_id:
            normalized_item['item_id'] = item_id
        
        # Handle different possible column names for task/labels
        task = (item.get('task') or 
               item.get('labels') or 
               item.get('category') or 
               item.get('type') or 
               'general')
        
        normalized_item['labels'] = task
        
        normalized_data.append(normalized_item)
    
    return normalized_data

def fix_csv_file(input_file: str, output_file: Optional[str] = None) -> bool:
    """
    Fix a CSV file with embedded newlines and save the corrected version.
    
    Args:
        input_file: Path to the input CSV file
        output_file: Path for the output file (defaults to input_file with '_fixed' suffix)
        
    Returns:
        True if successful, False otherwise
    """
    if not output_file:
        base, ext = input_file.rsplit('.', 1) if '.' in input_file else (input_file, 'csv')
        output_file = f"{base}_fixed.{ext}"
    
    try:
        # Parse with robust parser
        data = parse_csv_robust(input_file)
        
        if not data:
            print("❌ No data found in input file")
            return False
        
        # Write corrected CSV
        with open(output_file, 'w', encoding='utf-8', newline='') as file:
            if data:
                headers = list(data[0].keys())
                writer = csv.DictWriter(file, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)
        
        print(f"✅ Fixed CSV saved to: {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing CSV file: {e}")
        return False

# Convenience function for backward compatibility
def load_csv_data(file_path: str) -> List[Dict[str, Any]]:
    """
    Load CSV data with robust parsing.
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        List of dictionaries representing the CSV rows
    """
    return parse_csv_robust(file_path)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python robust_csv_parser.py <csv_file> [output_file]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("🔧 Robust CSV Parser")
    print("=" * 40)
    
    try:
        if output_file:
            # Fix mode
            success = fix_csv_file(input_file, output_file)
            sys.exit(0 if success else 1)
        else:
            # Parse and display mode
            data = parse_csv_robust(input_file)
            print(f"\n📊 Loaded {len(data)} items")
            
            if data:
                print("\n🔍 Sample items:")
                for i, item in enumerate(data[:3]):
                    print(f"  {i+1}. ID: {item.get('item_id', 'N/A')}")
                    print(f"     Labels: {item.get('labels', 'N/A')}")
                    en_text = item.get('en', item.get('text', 'N/A'))
                    if len(str(en_text)) > 50:
                        en_text = str(en_text)[:50] + "..."
                    print(f"     Text: {en_text}")
                    print()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)