#!/usr/bin/env python3
"""
Rebuild translation_master.csv by scanning existing audio files.
This prevents the script from trying to regenerate all existing audio.
"""

import pandas as pd
import os
import glob
import utilities.config as conf

def rebuild_master_from_audio():
    """Rebuild translation_master.csv by scanning existing audio files"""
    
    # Load the source translations
    print("Loading source translations...")
    source_df = pd.read_csv(conf.item_bank_translations)
    source_df = source_df.rename(columns={'identifier': 'item_id'})
    
    # Initialize master with source data
    master_df = source_df.copy()
    
    # Language mappings - map to actual column names in source
    lang_mappings = {
        'en': ['en', 'en-US'],
        'es-CO': ['es', 'es-CO'], 
        'de': ['de', 'de-DE'],
        'fr-CA': ['fr', 'fr-CA'],
        'nl': ['nl', 'nl-NL']
    }
    
    # For each language, scan for existing audio files
    for column_name, possible_codes in lang_mappings.items():
        print(f"Scanning {column_name} audio files...")
        
        items_with_audio = set()
        
        # Check both possible directory formats
        for lang_code in possible_codes:
            pattern = f'audio_files/*/{lang_code}/shared/*.mp3'
            audio_files = glob.glob(pattern)
            
            for audio_file in audio_files:
                # Extract item_id from filename (remove .mp3 extension)
                item_id = os.path.basename(audio_file).replace('.mp3', '')
                items_with_audio.add(item_id)
        
        print(f"  Found {len(items_with_audio)} {column_name} audio files")
        
        # Mark items that have audio in the master file
        if column_name in master_df.columns:
            # Set values for items that have audio - use the actual translation text from source
            for item_id in items_with_audio:
                if item_id in master_df['item_id'].values:
                    idx = master_df[master_df['item_id'] == item_id].index[0]
                    # Get the actual translation text from the source data
                    if item_id in source_df['item_id'].values:
                        source_idx = source_df[source_df['item_id'] == item_id].index[0]
                        if column_name in source_df.columns:
                            actual_text = source_df.at[source_idx, column_name]
                            master_df.at[idx, column_name] = actual_text
                        else:
                            # Fallback to placeholder if source text not found
                            master_df.at[idx, column_name] = "HAS_AUDIO"
                    else:
                        # Fallback to placeholder if item not found in source
                        master_df.at[idx, column_name] = "HAS_AUDIO"
        else:
            # Add column if it doesn't exist
            master_df[column_name] = ''
            for item_id in items_with_audio:
                if item_id in master_df['item_id'].values:
                    idx = master_df[master_df['item_id'] == item_id].index[0]
                    # Get the actual translation text from the source data
                    if item_id in source_df['item_id'].values:
                        source_idx = source_df[source_df['item_id'] == item_id].index[0]
                        if column_name in source_df.columns:
                            actual_text = source_df.at[source_idx, column_name]
                            master_df.at[idx, column_name] = actual_text
                        else:
                            # Fallback to placeholder if source text not found
                            master_df.at[idx, column_name] = "HAS_AUDIO"
                    else:
                        # Fallback to placeholder if item not found in source
                        master_df.at[idx, column_name] = "HAS_AUDIO"
    
    # Save the rebuilt master file
    print("Saving rebuilt translation_master.csv...")
    master_df.to_csv('translation_master.csv', index=False)
    
    # Print summary
    for lang in ['en', 'es-CO', 'de', 'fr-CA', 'nl']:
        if lang in master_df.columns:
            completed = (master_df[lang].notna() & (master_df[lang] != '')).sum()
            total = len(master_df)
            print(f"  {lang}: {completed}/{total} items have audio")
    
    print("✅ Master file rebuilt successfully!")

if __name__ == "__main__":
    rebuild_master_from_audio() 