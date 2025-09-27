#!/usr/bin/env python3
"""
Create a CSV file with the 27 items that have updated es-CO text.
Extracts the specific items from the translation changes analysis.
"""

import pandas as pd
import os

def create_updated_items_csv():
    """Create a CSV with the 27 items that have updated es-CO text."""
    print("📝 Creating CSV of 27 items with updated es-CO text...")
    
    # Load the current translations
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
    
    # List of the 27 items that need audio regeneration
    updated_items = [
        # Text content changes (24 items)
        "general-intro5",
        "math-instructions1", 
        "number-line-instruct1",
        "number-identification-21",
        "number-identification-36",
        "number-identification-41",
        "trog-item-100",
        "trog-item-103",
        "ToM-intro",
        "ToM-scene4-q3",
        "ToM-scene4-q4-false_belief",
        "ToM-scene5-instruct1",
        "ToM-scene6-instruct2",
        "ToM-scene6-q1",
        "ToM-scene6-instruct4",
        "same-different-selection-instruct3",
        "sds-2match-prompt1",
        "sds-2match-prompt2",
        "sds-3unique-prompt1",
        "vocab-item-114",
        "ToM-scene-9-instruct1",
        "ToM-scene-10-instruct3",
        "data-questionnaire-button-text3",
        "math-instructions1-heavy",
        
        # New items (3 items)
        "mental-rotation-instruct1",
        "number-identification-42",
        "number-identification-45"
    ]
    
    print(f"🔍 Filtering for {len(updated_items)} updated items...")
    
    # Filter the current data for these specific items
    updated_data = current_data[current_data['item_id'].isin(updated_items)].copy()
    
    if len(updated_data) == 0:
        print("❌ No matching items found in current translations")
        return
    
    print(f"✅ Found {len(updated_data)} matching items")
    
    # Add a column to indicate the type of change
    def get_change_type(item_id):
        new_items = ["mental-rotation-instruct1", "number-identification-42", "number-identification-45"]
        return "new" if item_id in new_items else "updated"
    
    updated_data['change_type'] = updated_data['item_id'].apply(get_change_type)
    
    # Reorder columns to put important ones first
    column_order = ['item_id', 'change_type', 'labels', 'es-CO', 'en']
    
    # Add any other columns that exist
    other_columns = [col for col in updated_data.columns if col not in column_order]
    final_columns = column_order + other_columns
    
    # Reorder the dataframe
    updated_data = updated_data[final_columns]
    
    # Save to CSV
    output_file = "es_co_updated_items.csv"
    updated_data.to_csv(output_file, index=False, encoding='utf-8')
    
    print(f"💾 Saved {len(updated_data)} updated items to: {output_file}")
    
    # Show summary
    print(f"\n📊 SUMMARY")
    print("=" * 50)
    print(f"Total items: {len(updated_data)}")
    print(f"Updated items: {len(updated_data[updated_data['change_type'] == 'updated'])}")
    print(f"New items: {len(updated_data[updated_data['change_type'] == 'new'])}")
    
    # Show first few items as preview
    print(f"\n📋 PREVIEW (first 10 items):")
    print("-" * 50)
    for i, (_, row) in enumerate(updated_data.head(10).iterrows(), 1):
        item_id = row['item_id']
        change_type = row['change_type']
        es_co_text = str(row['es-CO'])[:60] + "..." if len(str(row['es-CO'])) > 60 else str(row['es-CO'])
        print(f"{i:2d}. {item_id} ({change_type}): {es_co_text}")
    
    if len(updated_data) > 10:
        print(f"    ... and {len(updated_data) - 10} more items")
    
    return output_file

if __name__ == "__main__":
    output_file = create_updated_items_csv()
    if output_file:
        print(f"\n✅ Successfully created: {output_file}")
    else:
        print(f"\n❌ Failed to create CSV file")
