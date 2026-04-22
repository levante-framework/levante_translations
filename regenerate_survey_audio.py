#!/usr/bin/env python3
"""
Regenerate audio for all survey items and write to both standard and child-survey directories.
"""

import pandas as pd
import os
import sys
import shutil
from pathlib import Path

# Add the current directory to Python path to import utilities
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import utilities.config as conf
import utilities.utilities as u

def get_survey_items():
    """Get all items with 'survey' in their labels."""
    print("🔍 Loading survey items...")
    
    # Load current translations
    current_data = pd.read_csv('translation_text/item_bank_translations.csv')
    
    # Filter for survey items
    survey_items = current_data[current_data['labels'].str.contains('survey', case=False, na=False)]
    
    print(f"✅ Found {len(survey_items)} survey items")
    return survey_items

def create_survey_csv(survey_items, language='Spanish'):
    """Create a CSV file with only survey items for processing."""
    print(f"📝 Creating survey items CSV for {language}...")
    
    # Get language configuration
    language_dict = conf.get_languages()
    lang_config = language_dict.get(language, {})
    lang_code = lang_config.get('lang_code', 'es-CO')
    
    # Create the CSV with survey items
    survey_csv_path = 'survey_items_for_audio.csv'
    survey_items.to_csv(survey_csv_path, index=False)
    
    print(f"✅ Created {survey_csv_path} with {len(survey_items)} items")
    return survey_csv_path, lang_code

def setup_directories(lang_code):
    """Create the necessary audio directories."""
    print(f"📁 Setting up directories for {lang_code}...")
    
    # Standard directory
    standard_dir = f"audio_files/{lang_code}"
    os.makedirs(standard_dir, exist_ok=True)
    
    # Child survey directory
    child_survey_dir = f"audio_files/child-survey/{lang_code}"
    os.makedirs(child_survey_dir, exist_ok=True)
    
    print(f"✅ Created directories:")
    print(f"   • {standard_dir}")
    print(f"   • {child_survey_dir}")
    
    return standard_dir, child_survey_dir

def copy_audio_to_child_survey(standard_dir, child_survey_dir, survey_items):
    """Copy generated audio files to the child-survey directory."""
    print(f"📋 Copying survey audio files to child-survey directory...")
    
    copied_count = 0
    for _, item in survey_items.iterrows():
        item_id = item['item_id']
        source_file = os.path.join(standard_dir, f"{item_id}.mp3")
        dest_file = os.path.join(child_survey_dir, f"{item_id}.mp3")
        
        if os.path.exists(source_file):
            shutil.copy2(source_file, dest_file)
            copied_count += 1
            print(f"   ✅ Copied {item_id}.mp3")
        else:
            print(f"   ⚠️  Source file not found: {source_file}")
    
    print(f"✅ Copied {copied_count} survey audio files to child-survey directory")

def regenerate_survey_audio(language='Spanish', force_regenerate=True):
    """Main function to regenerate all survey items."""
    print("🎯 Starting Survey Audio Regeneration")
    print("="*60)
    
    # Get survey items
    survey_items = get_survey_items()
    
    if len(survey_items) == 0:
        print("❌ No survey items found!")
        return False
    
    # Get language configuration
    language_dict = conf.get_languages()
    lang_config = language_dict.get(language, {})
    lang_code = lang_config.get('lang_code', 'es-CO')
    service = lang_config.get('service', 'ElevenLabs')
    voice = lang_config.get('voice', 'Malena Tango')
    voice_id = str(lang_config.get('voice_id', '') or '').strip()
    
    print(f"🌍 Language: {language} ({lang_code})")
    print(f"🎤 Service: {service}")
    print(f"🗣️  Voice (display): {voice}")
    if service == 'ElevenLabs':
        print(f"🆔 Voice ID: {voice_id or '(missing)'}")
    print("="*60)
    
    # Setup directories
    standard_dir, child_survey_dir = setup_directories(lang_code)
    
    # Create CSV for processing
    survey_csv_path, lang_code = create_survey_csv(survey_items, language)
    
    # Import and run the appropriate TTS service
    print(f"🎵 Starting audio generation with {service}...")
    
    try:
        if service == 'ElevenLabs':
            from ELabs import elevenlabs_tts
            if not voice_id:
                print(
                    f"❌ Missing voice_id for {language} ({lang_code}). "
                    "ElevenLabs generation is voice-id-first."
                )
                return False
            
            result = elevenlabs_tts.main(
                input_file_path=survey_csv_path,
                master_file_path="translation_master.csv",
                lang_code=lang_code,
                voice=voice,
                voice_id=voice_id,
                retry_seconds=1,
                audio_base_dir="audio_files",
                output_format="mp3_22050_32"
            )
            
        elif service == 'PlayHt':
            from PlayHt import playHt_tts
            
            result = playHt_tts.main(
                input_file_path=survey_csv_path,
                master_file_path="translation_master.csv",
                lang_code=lang_code,
                voice=voice,
                retry_seconds=1,
                audio_base_dir="audio_files"
            )
        else:
            print(f"❌ Unsupported service: {service}")
            return False
            
        if result:
            print(f"✅ Audio generation completed successfully!")
            
            # Copy files to child-survey directory
            copy_audio_to_child_survey(standard_dir, child_survey_dir, survey_items)
            
            print("="*60)
            print("🎉 Survey audio regeneration completed!")
            print(f"📁 Standard location: {standard_dir}")
            print(f"📁 Child survey location: {child_survey_dir}")
            print(f"📊 Total survey items processed: {len(survey_items)}")
            
            return True
        else:
            print("❌ Audio generation failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error during audio generation: {e}")
        return False

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Regenerate audio for all survey items')
    parser.add_argument('--language', '-l', default='Spanish', 
                       help='Language to generate audio for (default: Spanish)')
    parser.add_argument('--force', '-f', action='store_true',
                       help='Force regenerate all survey items')
    
    args = parser.parse_args()
    
    print("🎯 Survey Audio Regeneration Script")
    print("="*60)
    
    success = regenerate_survey_audio(
        language=args.language,
        force_regenerate=args.force
    )
    
    if success:
        print("\n✅ Survey audio regeneration completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Survey audio regeneration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
