#!/usr/bin/env python3
"""
Check specifically for ClassNice and other items that might have been missed in the change analysis.
"""

import pandas as pd
import os

def check_classnice_changes():
    """Check for ClassNice and other potentially missed changes."""
    print("🔍 Checking for ClassNice and other missed changes...")
    
    # Load master file
    master_file = "translation_master.csv"
    current_file = "translation_text/item_bank_translations.csv"
    
    try:
        master_data = pd.read_csv(master_file)
        current_data = pd.read_csv(current_file)
        print(f"✅ Loaded master: {len(master_data)} rows, current: {len(current_data)} rows")
    except Exception as e:
        print(f"❌ Error loading files: {e}")
        return
    
    # Check ClassNice specifically
    print(f"\n🔍 Checking ClassNice specifically...")
    
    master_classnice = master_data[master_data['item_id'] == 'ClassNice']
    current_classnice = current_data[current_data['item_id'] == 'ClassNice']
    
    if len(master_classnice) > 0 and len(current_classnice) > 0:
        master_es_co = master_classnice['es-CO'].iloc[0] if 'es-CO' in master_classnice.columns else ""
        current_es_co = current_classnice['es-CO'].iloc[0] if 'es-CO' in current_classnice.columns else ""
        
        print(f"Master es-CO: '{master_es_co}'")
        print(f"Current es-CO: '{current_es_co}'")
        
        if str(master_es_co) != str(current_es_co):
            print(f"🔄 ClassNice HAS CHANGED!")
            print(f"   Old: '{master_es_co}'")
            print(f"   New: '{current_es_co}'")
        else:
            print(f"✅ ClassNice has NOT changed")
    else:
        print(f"❌ ClassNice not found in one or both files")
    
    # Let's also check for other survey items that might have changed
    print(f"\n🔍 Checking other survey items...")
    
    survey_items = current_data[current_data['labels'].str.contains('survey', case=False, na=False)]
    print(f"Found {len(survey_items)} survey items in current data")
    
    # Check each survey item for changes
    survey_changes = []
    for _, row in survey_items.iterrows():
        item_id = row['item_id']
        current_es_co = row.get('es-CO', '')
        
        # Find in master
        master_row = master_data[master_data['item_id'] == item_id]
        if len(master_row) > 0:
            master_es_co = master_row['es-CO'].iloc[0] if 'es-CO' in master_row.columns else ""
            
            if str(master_es_co) != str(current_es_co):
                survey_changes.append({
                    'item_id': item_id,
                    'master_text': str(master_es_co),
                    'current_text': str(current_es_co)
                })
                print(f"🔄 {item_id}: CHANGED")
                print(f"   Old: '{master_es_co}'")
                print(f"   New: '{current_es_co}'")
    
    if survey_changes:
        print(f"\n📊 Found {len(survey_changes)} survey items with changes:")
        for change in survey_changes:
            print(f"   • {change['item_id']}")
    else:
        print(f"\n✅ No survey items have changed")
    
    # Let's also do a broader check for any items that might have been missed
    print(f"\n🔍 Doing broader change detection...")
    
    # Merge on item_id
    merged = pd.merge(
        master_data[['item_id', 'es-CO']], 
        current_data[['item_id', 'es-CO']], 
        on='item_id', 
        how='outer', 
        suffixes=('_master', '_current')
    )
    
    all_changes = []
    for _, row in merged.iterrows():
        item_id = row['item_id']
        master_text = str(row['es-CO_master']) if pd.notna(row['es-CO_master']) else ""
        current_text = str(row['es-CO_current']) if pd.notna(row['es-CO_current']) else ""
        
        if master_text != current_text and (master_text != "" or current_text != ""):
            all_changes.append({
                'item_id': item_id,
                'master_text': master_text,
                'current_text': current_text
            })
    
    print(f"📊 Total items with changes: {len(all_changes)}")
    
    # Show items that weren't in our original 27
    original_27 = [
        "general-intro5", "math-instructions1", "number-line-instruct1",
        "number-identification-21", "number-identification-36", "number-identification-41",
        "trog-item-100", "trog-item-103", "ToM-intro", "ToM-scene4-q3",
        "ToM-scene4-q4-false_belief", "ToM-scene5-instruct1", "ToM-scene6-instruct2",
        "ToM-scene6-q1", "ToM-scene6-instruct4", "same-different-selection-instruct3",
        "sds-2match-prompt1", "sds-2match-prompt2", "sds-3unique-prompt1",
        "vocab-item-114", "ToM-scene-9-instruct1", "ToM-scene-10-instruct3",
        "data-questionnaire-button-text3", "math-instructions1-heavy",
        "mental-rotation-instruct1", "number-identification-42", "number-identification-45"
    ]
    
    missed_items = []
    for change in all_changes:
        if change['item_id'] not in original_27:
            missed_items.append(change)
    
    if missed_items:
        print(f"\n⚠️  Found {len(missed_items)} items that were missed in original analysis:")
        for item in missed_items:
            print(f"   • {item['item_id']}")
            print(f"     Old: '{item['master_text'][:50]}...'")
            print(f"     New: '{item['current_text'][:50]}...'")
    else:
        print(f"\n✅ No missed items found")

if __name__ == "__main__":
    check_classnice_changes()
