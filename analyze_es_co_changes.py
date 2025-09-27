#!/usr/bin/env python3
"""
Analyze es-CO translation changes since last audio generation.
Compares current translations with the master file to identify changes.
"""

import pandas as pd
import os
import sys
from pathlib import Path

def analyze_es_co_changes():
    """Analyze how many es-CO translations have changed since last audio generation."""
    print("🔍 Analyzing es-CO Translation Changes")
    print("=" * 60)
    
    # Load the master file (tracks what audio has been generated)
    master_file = "translation_master.csv"
    if not os.path.exists(master_file):
        print(f"❌ Master file not found: {master_file}")
        return
    
    print(f"📁 Loading master file: {master_file}")
    try:
        master_data = pd.read_csv(master_file)
        print(f"✅ Loaded {len(master_data)} rows from master file")
    except Exception as e:
        print(f"❌ Error loading master file: {e}")
        return
    
    # Load current translations
    current_file = "translation_text/item_bank_translations.csv"
    if not os.path.exists(current_file):
        print(f"❌ Current translations file not found: {current_file}")
        return
    
    print(f"📁 Loading current translations: {current_file}")
    try:
        current_data = pd.read_csv(current_file)
        print(f"✅ Loaded {len(current_data)} rows from current translations")
    except Exception as e:
        print(f"❌ Error loading current translations: {e}")
        return
    
    # Check if es-CO column exists in both files
    if 'es-CO' not in master_data.columns:
        print("❌ es-CO column not found in master file")
        return
    
    if 'es-CO' not in current_data.columns:
        print("❌ es-CO column not found in current translations")
        return
    
    print(f"\n📊 Column Analysis:")
    print(f"   Master file columns: {list(master_data.columns)}")
    print(f"   Current file columns: {list(current_data.columns)}")
    
    # Merge the data on item_id to compare
    print(f"\n🔄 Comparing translations...")
    
    # Ensure both have item_id column
    if 'item_id' not in master_data.columns or 'item_id' not in current_data.columns:
        print("❌ item_id column missing from one or both files")
        return
    
    # Merge on item_id
    merged = pd.merge(
        master_data[['item_id', 'es-CO']], 
        current_data[['item_id', 'es-CO']], 
        on='item_id', 
        how='outer', 
        suffixes=('_master', '_current')
    )
    
    print(f"✅ Merged {len(merged)} items for comparison")
    
    # Analyze changes
    changes = []
    new_items = []
    removed_items = []
    unchanged_items = []
    
    for _, row in merged.iterrows():
        item_id = row['item_id']
        master_text = row['es-CO_master']
        current_text = row['es-CO_current']
        
        # Handle NaN values
        master_text = str(master_text) if pd.notna(master_text) else ""
        current_text = str(current_text) if pd.notna(current_text) else ""
        
        # Skip if both are empty
        if not master_text and not current_text:
            continue
        
        # New item (not in master)
        if pd.isna(row['es-CO_master']) or master_text == "":
            if current_text and current_text != "nan":
                new_items.append({
                    'item_id': item_id,
                    'current_text': current_text[:100] + "..." if len(current_text) > 100 else current_text
                })
        
        # Removed item (not in current)
        elif pd.isna(row['es-CO_current']) or current_text == "":
            if master_text and master_text != "nan":
                removed_items.append({
                    'item_id': item_id,
                    'master_text': master_text[:100] + "..." if len(master_text) > 100 else master_text
                })
        
        # Changed item
        elif master_text != current_text:
            changes.append({
                'item_id': item_id,
                'master_text': master_text[:100] + "..." if len(master_text) > 100 else master_text,
                'current_text': current_text[:100] + "..." if len(current_text) > 100 else current_text
            })
        
        # Unchanged item
        else:
            unchanged_items.append(item_id)
    
    # Print results
    print(f"\n📈 CHANGE ANALYSIS RESULTS")
    print("=" * 60)
    print(f"Total items compared: {len(merged)}")
    print(f"Items with changes: {len(changes)}")
    print(f"New items: {len(new_items)}")
    print(f"Removed items: {len(removed_items)}")
    print(f"Unchanged items: {len(unchanged_items)}")
    
    # Show changed items
    if changes:
        print(f"\n🔄 CHANGED ITEMS ({len(changes)}):")
        print("-" * 40)
        for i, change in enumerate(changes[:10], 1):  # Show first 10
            print(f"{i:2d}. {change['item_id']}")
            print(f"    Old: {change['master_text']}")
            print(f"    New: {change['current_text']}")
            print()
        
        if len(changes) > 10:
            print(f"    ... and {len(changes) - 10} more changes")
    
    # Show new items
    if new_items:
        print(f"\n➕ NEW ITEMS ({len(new_items)}):")
        print("-" * 40)
        for i, item in enumerate(new_items[:10], 1):  # Show first 10
            print(f"{i:2d}. {item['item_id']}: {item['current_text']}")
        
        if len(new_items) > 10:
            print(f"    ... and {len(new_items) - 10} more new items")
    
    # Show removed items
    if removed_items:
        print(f"\n➖ REMOVED ITEMS ({len(removed_items)}):")
        print("-" * 40)
        for i, item in enumerate(removed_items[:10], 1):  # Show first 10
            print(f"{i:2d}. {item['item_id']}: {item['master_text']}")
        
        if len(removed_items) > 10:
            print(f"    ... and {len(removed_items) - 10} more removed items")
    
    # Summary statistics
    total_changes = len(changes) + len(new_items) + len(removed_items)
    change_percentage = (total_changes / len(merged)) * 100 if len(merged) > 0 else 0
    
    print(f"\n📊 SUMMARY")
    print("=" * 60)
    print(f"Total items: {len(merged)}")
    print(f"Items needing audio regeneration: {total_changes}")
    print(f"Change percentage: {change_percentage:.1f}%")
    print(f"Unchanged items: {len(unchanged_items)} ({100 - change_percentage:.1f}%)")
    
    # Save detailed results
    if changes or new_items or removed_items:
        results_file = "es_co_translation_changes.csv"
        
        # Create detailed results
        detailed_results = []
        
        for change in changes:
            detailed_results.append({
                'item_id': change['item_id'],
                'change_type': 'changed',
                'old_text': change['master_text'],
                'new_text': change['current_text']
            })
        
        for item in new_items:
            detailed_results.append({
                'item_id': item['item_id'],
                'change_type': 'new',
                'old_text': '',
                'new_text': item['current_text']
            })
        
        for item in removed_items:
            detailed_results.append({
                'item_id': item['item_id'],
                'change_type': 'removed',
                'old_text': item['master_text'],
                'new_text': ''
            })
        
        if detailed_results:
            results_df = pd.DataFrame(detailed_results)
            results_df.to_csv(results_file, index=False)
            print(f"\n💾 Detailed results saved to: {results_file}")
    
    return {
        'total_items': len(merged),
        'changed_items': len(changes),
        'new_items': len(new_items),
        'removed_items': len(removed_items),
        'unchanged_items': len(unchanged_items),
        'change_percentage': change_percentage
    }

if __name__ == "__main__":
    results = analyze_es_co_changes()
    if results:
        print(f"\n🎯 CONCLUSION")
        print("=" * 60)
        if results['change_percentage'] > 0:
            print(f"⚠️  {results['changed_items'] + results['new_items'] + results['removed_items']} es-CO translations have changed since last audio generation")
            print(f"   This means audio regeneration is needed for these items")
        else:
            print(f"✅ No es-CO translations have changed since last audio generation")
            print(f"   All audio files are up to date")
