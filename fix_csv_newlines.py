#!/usr/bin/env python3
"""
Simple script to fix embedded newlines in CSV files without requiring pandas.
"""

import csv
import re

def fix_csv_newlines(input_file, output_file):
    """Fix embedded newlines in CSV file using standard library."""
    
    print(f"Fixing embedded newlines in {input_file}...")
    
    try:
        fixed_rows = []
        affected_items = []
        
        with open(input_file, 'r', encoding='utf-8', newline='') as infile:
            reader = csv.reader(infile)
            
            for row_num, row in enumerate(reader):
                if row_num == 0:
                    # Header row
                    fixed_rows.append(row)
                    continue
                
                # Check if any field contains embedded newlines
                fixed_row = []
                item_affected = False
                
                for field in row:
                    if '\n' in field:
                        # Replace embedded newlines with <br> tags
                        fixed_field = field.replace('\n', '<br>')
                        # Clean up extra spaces
                        fixed_field = re.sub(r'\s+', ' ', fixed_field).strip()
                        fixed_row.append(fixed_field)
                        item_affected = True
                    else:
                        fixed_row.append(field)
                
                if item_affected and len(row) > 0:
                    affected_items.append(row[0])  # Assume first column is item_id
                
                fixed_rows.append(fixed_row)
        
        # Write the fixed CSV
        with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.writer(outfile)
            writer.writerows(fixed_rows)
        
        print(f"✅ Fixed CSV saved to {output_file}")
        print(f"📊 Processed {len(fixed_rows)} rows")
        
        if affected_items:
            print(f"🔧 Fixed {len(affected_items)} items with embedded newlines:")
            for item in affected_items[:10]:  # Show first 10
                print(f"  - {item}")
            if len(affected_items) > 10:
                print(f"  ... and {len(affected_items) - 10} more")
        
        return True
        
    except Exception as e:
        print(f"❌ Error processing CSV: {e}")
        return False

def validate_csv(file_path):
    """Quick validation to check if CSV is properly formatted."""
    try:
        with open(file_path, 'r', encoding='utf-8', newline='') as file:
            reader = csv.reader(file)
            rows = list(reader)
            
        print(f"📋 Validation: {len(rows)} rows, {len(rows[0]) if rows else 0} columns")
        
        # Check for consistent column count
        if rows:
            header_cols = len(rows[0])
            inconsistent_rows = [i for i, row in enumerate(rows[1:], 1) if len(row) != header_cols]
            
            if inconsistent_rows:
                print(f"⚠️  Found {len(inconsistent_rows)} rows with inconsistent column count")
                for row_num in inconsistent_rows[:5]:  # Show first 5
                    print(f"  Row {row_num}: {len(rows[row_num])} columns (expected {header_cols})")
                return False
            else:
                print("✅ All rows have consistent column count")
                return True
        
        return True
        
    except Exception as e:
        print(f"❌ Validation error: {e}")
        return False

if __name__ == "__main__":
    input_file = "translation_master.csv"
    output_file = "translation_master_fixed.csv"
    
    print("🔧 CSV Newline Fix Tool")
    print("=" * 40)
    
    if fix_csv_newlines(input_file, output_file):
        if validate_csv(output_file):
            print(f"\n🎉 Success! To apply the fix:")
            print(f"   mv {output_file} {input_file}")
            print(f"\n💡 This will fix items like 'general-intro5' that had embedded newlines.")
        else:
            print("❌ Fix validation failed")
    else:
        print("❌ Failed to fix embedded newlines")