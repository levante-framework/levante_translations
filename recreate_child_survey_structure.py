#!/usr/bin/env python3
"""
Recreate the child_survey folder structure and populate it with latest translations.

This script:
1. Identifies all survey items from the CSV
2. Creates a child_survey folder structure organized by language
3. Copies existing audio files to the new structure
4. Generates missing audio files for survey items
"""

import os
import shutil
import sys
from pathlib import Path
import pandas as pd
from typing import List, Dict, Set

# Configuration
AUDIO_SOURCE_DIR = "audio_files"
CHILD_SURVEY_DIR = "audio_files/child_survey"
CSV_PATH = "translation_text/item_bank_translations.csv"

def load_survey_items() -> List[Dict]:
    """Load all survey items from the CSV."""
    if not os.path.exists(CSV_PATH):
        print(f"❌ CSV file not found: {CSV_PATH}")
        return []
    
    df = pd.read_csv(CSV_PATH)
    survey_items = []
    
    for _, row in df.iterrows():
        # Check if this is a survey item
        task = str(row.get('task', '')).lower()
        if 'survey' in task or 'thoughts' in task or 'feelings' in task:
            item_id = row['item_id']
            survey_items.append({
                'item_id': item_id,
                'task': row.get('task', ''),
                'en': row.get('en', ''),
                'es-CO': row.get('es-CO', ''),
                'de': row.get('de', ''),
                'fr-CA': row.get('fr-CA', ''),
                'nl': row.get('nl', ''),
                'de-CH': row.get('de-CH', ''),
                'es-AR': row.get('es-AR', ''),
                'en-GH': row.get('en-GH', '')
            })
    
    return survey_items

def get_available_languages() -> List[str]:
    """Get list of available languages from the audio_files directory."""
    audio_dir = Path(AUDIO_SOURCE_DIR)
    if not audio_dir.exists():
        return []
    
    languages = []
    for item in audio_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            languages.append(item.name)
    
    return sorted(languages)

def create_child_survey_structure(survey_items: List[Dict], languages: List[str]) -> bool:
    """Create the child_survey folder structure."""
    print("📁 Creating child_survey folder structure...")
    
    # Create main child_survey directory
    child_survey_path = Path(CHILD_SURVEY_DIR)
    child_survey_path.mkdir(parents=True, exist_ok=True)
    print(f"✅ Created: {child_survey_path}")
    
    # Create language subdirectories
    for lang in languages:
        lang_path = child_survey_path / lang
        lang_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {lang_path}")
    
    return True

def copy_existing_audio_files(survey_items: List[Dict], languages: List[str]) -> Dict[str, int]:
    """Copy existing audio files to the child_survey structure."""
    print("\n🎵 Copying existing audio files...")
    
    copy_stats = {'copied': 0, 'missing': 0, 'total': 0}
    
    for item in survey_items:
        item_id = item['item_id']
        copy_stats['total'] += len(languages)
        
        for lang in languages:
            # Source path in current structure
            source_path = Path(AUDIO_SOURCE_DIR) / lang / f"{item_id}.mp3"
            # Destination path in child_survey structure
            dest_path = Path(CHILD_SURVEY_DIR) / lang / f"{item_id}.mp3"
            
            if source_path.exists():
                try:
                    shutil.copy2(source_path, dest_path)
                    print(f"✅ Copied: {source_path} → {dest_path}")
                    copy_stats['copied'] += 1
                except Exception as e:
                    print(f"❌ Failed to copy {source_path}: {e}")
                    copy_stats['missing'] += 1
            else:
                print(f"⚠️  Missing: {source_path}")
                copy_stats['missing'] += 1
    
    return copy_stats

def identify_missing_audio_files(survey_items: List[Dict], languages: List[str]) -> List[Dict]:
    """Identify which audio files are missing and need to be generated."""
    print("\n🔍 Identifying missing audio files...")
    
    missing_files = []
    
    for item in survey_items:
        item_id = item['item_id']
        
        for lang in languages:
            # Check if file exists in child_survey structure
            child_survey_path = Path(CHILD_SURVEY_DIR) / lang / f"{item_id}.mp3"
            # Check if file exists in original structure
            original_path = Path(AUDIO_SOURCE_DIR) / lang / f"{item_id}.mp3"
            
            if not child_survey_path.exists() and not original_path.exists():
                # Get the translation text for this language
                translation_text = item.get(lang, '')
                if translation_text and translation_text.strip():
                    missing_files.append({
                        'item_id': item_id,
                        'language': lang,
                        'text': translation_text.strip(),
                        'task': item['task']
                    })
    
    return missing_files

def generate_missing_audio_files(missing_files: List[Dict]) -> bool:
    """Generate missing audio files using the existing audio generation system."""
    if not missing_files:
        print("✅ No missing audio files to generate!")
        return True
    
    print(f"\n🎤 Generating {len(missing_files)} missing audio files...")
    
    # Check if generate_speech.py exists
    if not os.path.exists("generate_speech.py"):
        print("❌ generate_speech.py not found. Cannot generate missing audio files.")
        print("💡 You can generate them manually later using:")
        for item in missing_files[:5]:  # Show first 5 as examples
            print(f"   python generate_speech.py --item-id {item['item_id']} --language {item['language']}")
        if len(missing_files) > 5:
            print(f"   ... and {len(missing_files) - 5} more")
        return False
    
    # Generate audio files
    success_count = 0
    for item in missing_files:
        item_id = item['item_id']
        language = item['language']
        text = item['text']
        
        print(f"🎤 Generating: {item_id} ({language})")
        
        # Use the existing generate_speech.py script
        cmd = [
            "python", "generate_speech.py",
            "--item-id", item_id,
            "--language", language,
            "--text", text
        ]
        
        try:
            import subprocess
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"✅ Generated: {item_id} ({language})")
            success_count += 1
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to generate {item_id} ({language}): {e}")
        except Exception as e:
            print(f"❌ Error generating {item_id} ({language}): {e}")
    
    print(f"📊 Generated {success_count}/{len(missing_files)} missing audio files")
    return success_count == len(missing_files)

def create_summary_report(survey_items: List[Dict], languages: List[str], copy_stats: Dict[str, int], missing_files: List[Dict]) -> None:
    """Create a summary report of the child_survey recreation."""
    print("\n" + "="*60)
    print("📊 CHILD_SURVEY RECREATION SUMMARY")
    print("="*60)
    
    print(f"📋 Survey items found: {len(survey_items)}")
    print(f"🌍 Languages: {', '.join(languages)}")
    print(f"📁 Total expected files: {len(survey_items) * len(languages)}")
    print(f"✅ Files copied: {copy_stats['copied']}")
    print(f"⚠️  Files missing: {copy_stats['missing']}")
    print(f"🎤 Files to generate: {len(missing_files)}")
    
    print(f"\n📂 Created structure:")
    print(f"   {CHILD_SURVEY_DIR}/")
    for lang in languages:
        print(f"   ├── {lang}/")
        # Count files in this language
        lang_path = Path(CHILD_SURVEY_DIR) / lang
        if lang_path.exists():
            file_count = len(list(lang_path.glob("*.mp3")))
            print(f"   │   └── {file_count} audio files")
    
    print(f"\n🎯 Survey items included:")
    for item in survey_items[:10]:  # Show first 10
        print(f"   • {item['item_id']}: {item['task']}")
    if len(survey_items) > 10:
        print(f"   ... and {len(survey_items) - 10} more")
    
    if missing_files:
        print(f"\n⚠️  Missing audio files to generate:")
        for item in missing_files[:5]:  # Show first 5
            print(f"   • {item['item_id']} ({item['language']})")
        if len(missing_files) > 5:
            print(f"   ... and {len(missing_files) - 5} more")

def main():
    print("🔧 Recreating Child Survey Audio Structure")
    print("="*50)
    
    # Load survey items
    print("📖 Loading survey items from CSV...")
    survey_items = load_survey_items()
    if not survey_items:
        print("❌ No survey items found!")
        return 1
    
    print(f"✅ Found {len(survey_items)} survey items")
    
    # Get available languages
    print("🌍 Detecting available languages...")
    languages = get_available_languages()
    if not languages:
        print("❌ No language directories found in audio_files!")
        return 1
    
    print(f"✅ Found languages: {', '.join(languages)}")
    
    # Create folder structure
    if not create_child_survey_structure(survey_items, languages):
        print("❌ Failed to create folder structure!")
        return 1
    
    # Copy existing audio files
    copy_stats = copy_existing_audio_files(survey_items, languages)
    
    # Identify missing files
    missing_files = identify_missing_audio_files(survey_items, languages)
    
    # Generate missing audio files
    if missing_files:
        generate_success = generate_missing_audio_files(missing_files)
        if not generate_success:
            print("⚠️  Some audio files could not be generated automatically")
    
    # Create summary report
    create_summary_report(survey_items, languages, copy_stats, missing_files)
    
    print(f"\n🎉 Child survey structure recreated successfully!")
    print(f"📁 Location: {CHILD_SURVEY_DIR}")
    print(f"💡 You can now deploy this structure using:")
    print(f"   python deploy_translations.py --environment dev --deploy-audio")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
