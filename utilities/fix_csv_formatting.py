#!/usr/bin/env python3
"""
Script to fix CSV formatting issues in translation_master.csv
Removes embedded newlines and fixes field alignment.
"""

import pandas as pd
import csv
import re

def fix_csv_file(input_file, output_file):
    """Fix CSV formatting by removing embedded newlines and normalizing fields."""
    
    print(f"Fixing CSV formatting in {input_file}...")
    
    # Read the raw file and fix newline issues
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split into lines but be careful about quoted fields
    lines = content.split('\n')
    
    # Reconstruct proper CSV rows
    fixed_lines = []
    current_row = ""
    in_quotes = False
    quote_count = 0
    
    for line in lines:
        # Count quotes in this line
        quote_count = line.count('"')
        
        if current_row:
            # We're continuing a multi-line field
            current_row += " " + line.strip()
        else:
            current_row = line
        
        # Simple heuristic: if we have an even number of quotes and the line ends properly,
        # it's probably a complete row
        total_quotes = current_row.count('"')
        
        # Check if this looks like a complete row (has the right number of commas)
        if total_quotes % 2 == 0 and current_row.strip():
            # Count fields by splitting on commas outside quotes
            try:
                # Try to parse this row
                reader = csv.reader([current_row])
                row = next(reader)
                if len(row) >= 7:  # Expected number of fields
                    fixed_lines.append(current_row)
                    current_row = ""
                else:
                    # Not enough fields, continue building
                    pass
            except:
                # Parsing error, continue building
                pass
        elif not current_row.strip():
            # Empty line, skip
            current_row = ""
    
    # Add any remaining row
    if current_row.strip():
        fixed_lines.append(current_row)
    
    # Write the fixed CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        for line in fixed_lines:
            f.write(line + '\n')
    
    print(f"Fixed CSV written to {output_file}")

def clean_text_fields(text):
    """Clean text fields by removing extra whitespace and normalizing."""
    if pd.isna(text) or text == "":
        return ""
    
    # Remove extra whitespace and newlines
    text = re.sub(r'\s+', ' ', str(text))
    text = text.strip()
    return text

def validate_and_clean_csv(file_path):
    """Load and clean the CSV using pandas."""
    
    print(f"Loading and cleaning {file_path}...")
    
    try:
        # Try to read with error handling
        df = pd.read_csv(file_path, encoding='utf-8')
        
        print(f"Successfully loaded CSV with {len(df)} rows and {len(df.columns)} columns")
        print(f"Columns: {list(df.columns)}")
        
        # Clean text fields
        for col in df.columns:
            if df[col].dtype == 'object':  # Text columns
                df[col] = df[col].apply(clean_text_fields)
        
        # Save the cleaned version
        backup_file = file_path.replace('.csv', '_backup.csv')
        df.to_csv(backup_file, index=False, encoding='utf-8')
        print(f"Backup saved to {backup_file}")
        
        # Save the main file
        df.to_csv(file_path, index=False, encoding='utf-8')
        print(f"Cleaned CSV saved to {file_path}")
        
        return True
        
    except Exception as e:
        print(f"Error processing CSV: {e}")
        return False

if __name__ == "__main__":
    input_file = "translation_master.csv"
    temp_file = "translation_master_temp.csv"
    
    # First, try to fix the raw formatting
    fix_csv_file(input_file, temp_file)
    
    # Then clean with pandas
    if validate_and_clean_csv(temp_file):
        # Replace the original with the cleaned version
        import shutil
        shutil.move(temp_file, input_file)
        print("CSV formatting fixed successfully!")
    else:
        print("Could not fix CSV automatically. Manual intervention required.")