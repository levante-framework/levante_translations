#!/usr/bin/env python3

import json
import os

def debug_browser_data():
    """Debug what the browser is actually loading"""
    
    print("🔍 Debugging Data Loading Issue")
    print("=" * 50)
    
    # Check if the CSV file exists locally
    csv_path = 'translation_text/complete_translations.csv'
    if os.path.exists(csv_path):
        print(f"✅ Local CSV exists: {csv_path}")
        
        # Read and count lines
        with open(csv_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        
        print(f"📊 CSV lines: {len(lines)} (including header)")
        print(f"📊 Data rows: {len(lines) - 1}")
        
        # Check for any obvious duplication in the file
        if len(lines) > 1:
            header = lines[0]
            data_lines = lines[1:]
            print(f"📋 Header: {header[:100]}...")
            
            # Check first few identifiers for duplicates
            identifiers = []
            for i, line in enumerate(data_lines[:10]):
                parts = line.split(',')
                if len(parts) > 0:
                    identifier = parts[0].strip('"')
                    identifiers.append(identifier)
                    if i < 5:
                        print(f"   Row {i+1}: {identifier}")
            
            # Check for duplicate identifiers in sample
            from collections import Counter
            id_counts = Counter(identifiers)
            duplicates = [id for id, count in id_counts.items() if count > 1]
            if duplicates:
                print(f"❌ Found duplicates in sample: {duplicates}")
            else:
                print("✅ No duplicates in first 10 rows")
    else:
        print(f"❌ Local CSV not found: {csv_path}")
    
    print()
    
    # Suggest debugging steps
    print("🛠️ Debugging Steps:")
    print("1. Open browser dev tools (F12)")
    print("2. Go to Console tab")
    print("3. Look for these log messages:")
    print("   - 'Loaded XXX complete translation items from GitHub'")
    print("   - 'CSV Headers: [...]'")
    print("   - 'Normalized data sample: [...]'")
    print("4. Check the Network tab for:")
    print("   - Multiple requests to the CSV file")
    print("   - The actual response size")
    print("5. In the Application/Storage tab:")
    print("   - Check localStorage for 'levante_translations_cache'")
    print("   - Clear it if it contains old/corrupted data")
    
    print()
    print("🔧 Quick Fixes to Try:")
    print("1. Hard refresh the page (Ctrl+F5)")
    print("2. Clear localStorage cache")
    print("3. Check if data is being loaded twice somehow")

if __name__ == "__main__":
    debug_browser_data()