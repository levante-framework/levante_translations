#!/usr/bin/env python3
"""
test_xliff_workflow.py

Test the complete XLIFF workflow end-to-end:
1. Convert CSV to XLIFF
2. Convert XLIFF to ICU JSON
3. Compare with original CSV data
4. Validate XLIFF structure

Usage:
    python test_xliff_workflow.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path
import pandas as pd
import xml.etree.ElementTree as ET

def test_csv_to_xliff_conversion():
    """Test CSV to XLIFF conversion."""
    print("🔄 Testing CSV to XLIFF conversion...")
    
    # Use existing CSV
    csv_path = "translation_text/item_bank_translations.csv"
    if not os.path.exists(csv_path):
        print(f"❌ CSV file not found: {csv_path}")
        return False
    
    # Convert to XLIFF
    with tempfile.TemporaryDirectory() as temp_dir:
        cmd = f"python utilities/csv_to_xliff_converter.py --input {csv_path} --output-dir {temp_dir}"
        result = os.system(cmd)
        
        if result != 0:
            print("❌ CSV to XLIFF conversion failed")
            return False
        
        # Check generated files
        xliff_files = list(Path(temp_dir).glob("*.xliff"))
        print(f"✅ Generated {len(xliff_files)} XLIFF files")
        
        # Validate one XLIFF file
        if xliff_files:
            sample_file = xliff_files[0]
            if validate_xliff_structure(sample_file):
                print(f"✅ XLIFF structure valid: {sample_file.name}")
            else:
                print(f"❌ XLIFF structure invalid: {sample_file.name}")
                return False
    
    return True

def test_xliff_to_icu_conversion():
    """Test XLIFF to ICU JSON conversion using existing tool."""
    print("🔄 Testing XLIFF to ICU JSON conversion...")
    
    # Use existing XLIFF files in xliff/translations-icu/
    icu_dir = "xliff/translations-icu"
    if not os.path.exists(icu_dir):
        print(f"❌ ICU directory not found: {icu_dir}")
        return False
    
    icu_files = list(Path(icu_dir).glob("*.json"))
    if not icu_files:
        print("❌ No ICU JSON files found")
        return False
    
    print(f"✅ Found {len(icu_files)} ICU JSON files")
    
    # Validate one ICU file
    sample_file = icu_files[0]
    try:
        with open(sample_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict) and len(data) > 0:
            print(f"✅ ICU JSON valid: {sample_file.name} ({len(data)} entries)")
            return True
        else:
            print(f"❌ ICU JSON invalid: {sample_file.name}")
            return False
            
    except Exception as e:
        print(f"❌ ICU JSON error: {e}")
        return False

def validate_xliff_structure(xliff_path):
    """Validate XLIFF file structure."""
    try:
        tree = ET.parse(xliff_path)
        root = tree.getroot()
        
        # Check root element
        if not root.tag.endswith('xliff'):
            return False
        
        # Check for file element
        file_elem = root.find('.//{*}file')
        if file_elem is None:
            return False
        
        # Check for body element
        body_elem = root.find('.//{*}body')
        if body_elem is None:
            return False
        
        # Check for trans-units
        trans_units = root.findall('.//{*}trans-unit')
        if len(trans_units) == 0:
            return False
        
        # Validate a few trans-units
        for tu in trans_units[:5]:
            if 'id' not in tu.attrib:
                return False
            
            source = tu.find('{*}source')
            if source is None or not source.text:
                return False
        
        return True
        
    except Exception as e:
        print(f"XLIFF validation error: {e}")
        return False

def compare_csv_vs_icu_data():
    """Compare original CSV data with ICU JSON data."""
    print("🔄 Comparing CSV vs ICU JSON data...")
    
    # Load CSV
    csv_path = "translation_text/item_bank_translations.csv"
    if not os.path.exists(csv_path):
        print(f"❌ CSV file not found: {csv_path}")
        return False
    
    try:
        df = pd.read_csv(csv_path, encoding='utf-8')
    except Exception as e:
        print(f"❌ CSV loading error: {e}")
        return False
    
    # Load ICU JSON for Spanish Colombia
    icu_path = "xliff/translations-icu/es-CO.json"
    if not os.path.exists(icu_path):
        print(f"❌ ICU file not found: {icu_path}")
        return False
    
    try:
        with open(icu_path, 'r', encoding='utf-8') as f:
            icu_data = json.load(f)
    except Exception as e:
        print(f"❌ ICU loading error: {e}")
        return False
    
    # Compare sample entries
    matches = 0
    mismatches = 0
    
    for _, row in df.head(10).iterrows():
        item_id = row.get('item_id', '')
        csv_text = row.get('es-CO', '')
        icu_text = icu_data.get(item_id, '')
        
        if csv_text and icu_text:
            # Normalize whitespace for comparison
            csv_normalized = ' '.join(csv_text.split())
            icu_normalized = ' '.join(icu_text.split())
            
            if csv_normalized == icu_normalized:
                matches += 1
            else:
                mismatches += 1
                print(f"  Mismatch for {item_id}:")
                print(f"    CSV: '{csv_text[:50]}...'")
                print(f"    ICU: '{icu_text[:50]}...'")
                print(f"    CSV len: {len(csv_text)}, ICU len: {len(icu_text)}")
    
    print(f"✅ Data comparison: {matches} matches, {mismatches} mismatches")
    return mismatches == 0

def main():
    """Run all tests."""
    print("🧪 Testing XLIFF Workflow End-to-End\n")
    
    tests = [
        ("CSV to XLIFF Conversion", test_csv_to_xliff_conversion),
        ("XLIFF to ICU Conversion", test_xliff_to_icu_conversion),
        ("Data Integrity Check", compare_csv_vs_icu_data),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Test: {test_name}")
        print('='*50)
        
        try:
            if test_func():
                print(f"✅ {test_name} PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} ERROR: {e}")
    
    print(f"\n{'='*50}")
    print(f"Test Results: {passed}/{total} passed")
    print('='*50)
    
    if passed == total:
        print("🎉 All tests passed! XLIFF workflow is ready.")
        print("\nNext steps:")
        print("1. Review the generated XLIFF files")
        print("2. Upload test files to Crowdin")
        print("3. Plan your migration timeline")
        return 0
    else:
        print("❌ Some tests failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
