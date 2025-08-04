#!/usr/bin/env python3
"""
Test script for ID3v2 metadata functionality in utilities.py

This script:
1. Creates a sample MP3 file with synthesized audio (or uses existing one)
2. Adds comprehensive ID3v2 metadata including custom fields
3. Reads the metadata back and displays it
4. Validates that all fields are correctly stored and retrieved
"""

import sys
import os
import tempfile
import pandas as pd
from datetime import datetime
import shutil
import glob

# Add the parent directory to sys.path to import utilities
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utilities.utilities import audio_tags, write_id3_tags, read_id3_tags

def find_existing_mp3():
    """
    Try to find an existing MP3 file in the audio_files directory to use for testing
    """
    # Look for any existing MP3 file
    mp3_patterns = [
        "audio_files/**/*.mp3",
        "*.mp3"
    ]
    
    for pattern in mp3_patterns:
        mp3_files = glob.glob(pattern, recursive=True)
        if mp3_files:
            return mp3_files[0]
    
    return None

def create_test_mp3():
    """
    Create or find a test MP3 file for metadata testing
    """
    # First, try to find an existing MP3 file
    existing_mp3 = find_existing_mp3()
    
    if existing_mp3:
        # Copy an existing MP3 to a temporary location for testing
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = temp_file.name
        
        shutil.copy2(existing_mp3, temp_path)
        print(f"✅ Using existing MP3 file: {existing_mp3}")
        print(f"✅ Copied to test location: {temp_path}")
        return temp_path
    
    else:
        # Create a minimal but more valid MP3 file
        print("ℹ️  No existing MP3 found, creating minimal test file...")
        
        # Create a very basic but more complete MP3 file
        mp3_data = create_minimal_valid_mp3()
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_file.write(mp3_data)
            temp_path = temp_file.name
        
        print(f"✅ Created minimal MP3 file: {temp_path}")
        return temp_path

def create_minimal_valid_mp3():
    """
    Create a minimal but valid MP3 file that mutagen can work with
    """
    # Create a more complete MP3 with proper frames
    # This creates a very short but valid MP3 file
    
    # ID3v2 header (minimal)
    id3v2_header = b'ID3\x03\x00\x00\x00\x00\x00\x00'
    
    # MP3 frame header for MPEG-1 Layer 3, 128kbps, 44.1kHz, stereo
    mp3_frame = bytes([
        0xFF, 0xFB, 0x90, 0x00,  # Sync word and header
        0x00, 0x00, 0x00, 0x00,  # Frame data
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00
    ])
    
    # Create multiple frames to make it more valid
    mp3_frames = mp3_frame * 10
    
    # Combine header and frames
    return id3v2_header + mp3_frames

def test_id3_metadata():
    """
    Test the complete ID3 metadata workflow
    """
    print("🎵 Testing ID3v2 Metadata Functionality")
    print("=" * 50)
    
    # Create or find a test MP3 file
    try:
        temp_path = create_test_mp3()
    except Exception as e:
        print(f"❌ Failed to create test MP3 file: {e}")
        return False
    
    # Define paths for saving files in tests folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    test_mp3_path = os.path.join(script_dir, "test_audio_with_metadata.mp3")
    test_csv_path = os.path.join(script_dir, "test_metadata_results.csv")
    
    try:
        # Create comprehensive test metadata
        test_tags = audio_tags.copy()
        
        # Standard ID3v2 tags
        test_tags['title'] = "test_item_123"
        test_tags['artist'] = "Levante Framework - PlayHT"
        test_tags['album'] = "math"
        test_tags['date'] = "2024"
        test_tags['genre'] = "Speech Synthesis"
        test_tags['comment'] = "This is a test audio file with sample text for verification purposes..."
        test_tags['created'] = str(pd.Timestamp.now())
        
        # Custom fields
        test_tags['lang_code'] = "en"
        test_tags['service'] = "PlayHT"
        test_tags['voice'] = "test_voice_id"
        test_tags['item_difficulty'] = "medium"
        test_tags['translation_quality'] = "high"
        test_tags['research_notes'] = "Test file for metadata validation"
        test_tags['participant_id'] = "TEST_001"
        test_tags['session_number'] = "1"
        
        print("\n📝 Writing metadata to MP3 file...")
        print("Standard ID3v2 tags:")
        for field in ['title', 'artist', 'album', 'date', 'genre', 'comment', 'copyright', 'created']:
            if test_tags.get(field):
                print(f"  {field}: {test_tags[field]}")
        
        print("\nCustom fields:")
        custom_fields = {k: v for k, v in test_tags.items() 
                        if k not in ['title', 'artist', 'album', 'date', 'genre', 'comment', 'copyright', 'created'] and v}
        for field, value in custom_fields.items():
            print(f"  {field}: {value}")
        
        # Write the metadata
        success = write_id3_tags(temp_path, test_tags)
        
        if not success:
            print("❌ Failed to write ID3 tags")
            return False
        
        print("\n✅ Successfully wrote metadata to MP3 file")
        
        # Read the metadata back
        print("\n📖 Reading metadata from MP3 file...")
        read_tags = read_id3_tags(temp_path)
        
        if not read_tags:
            print("❌ Failed to read ID3 tags")
            return False
        
        print("\n📊 Retrieved metadata:")
        print("-" * 30)
        
        # Display all retrieved tags
        for field, value in read_tags.items():
            if value:  # Only show non-empty fields
                print(f"{field}: {value}")
        
        # Create CSV data for comparison
        csv_data = []
        all_fields = set(test_tags.keys()) | set(read_tags.keys())
        
        for field in sorted(all_fields):
            written_value = test_tags.get(field, '')
            read_value = read_tags.get(field, '')
            match_status = "✅ MATCH" if written_value == read_value else "❌ MISMATCH"
            
            csv_data.append({
                'field': field,
                'written_value': written_value,
                'read_value': read_value,
                'status': match_status
            })
        
        # Save CSV file with tag comparison
        df = pd.DataFrame(csv_data)
        df.to_csv(test_csv_path, index=False, encoding='utf-8')
        print(f"\n💾 Saved tag comparison to: {test_csv_path}")
        
        # Validate that key fields were preserved
        print("\n🔍 Validation Results:")
        validation_fields = [
            'title', 'artist', 'album', 'copyright', 'service', 'lang_code', 
            'voice', 'item_difficulty', 'translation_quality'
        ]
        
        all_valid = True
        for field in validation_fields:
            original = test_tags.get(field, '')
            retrieved = read_tags.get(field, '')
            
            if original == retrieved:
                print(f"✅ {field}: MATCH")
            else:
                print(f"❌ {field}: MISMATCH (original: '{original}', retrieved: '{retrieved}')")
                all_valid = False
        
        # Check if we have the expected number of fields
        expected_field_count = len([v for v in test_tags.values() if v])
        actual_field_count = len([v for v in read_tags.values() if v])
        
        print(f"\n📈 Field count: {actual_field_count}/{expected_field_count}")
        
        # Copy the MP3 file to tests folder for inspection
        shutil.copy2(temp_path, test_mp3_path)
        print(f"\n💾 Saved test MP3 file to: {test_mp3_path}")
        
        if all_valid and actual_field_count >= len(validation_fields):
            print("\n🎉 All tests PASSED! ID3 metadata functionality is working correctly.")
            return True
        else:
            print("\n⚠️  Some tests FAILED. Check the validation results above.")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up the temporary file (but keep the copy in tests folder)
        try:
            os.unlink(temp_path)
            print(f"\n🧹 Cleaned up temporary file: {temp_path}")
        except OSError:
            print(f"\n⚠️  Could not delete temporary file: {temp_path}")
        
        # Show final file locations
        if os.path.exists(test_mp3_path):
            print(f"\n📁 Files saved in tests folder:")
            print(f"   🎵 MP3 with metadata: {os.path.basename(test_mp3_path)}")
        if os.path.exists(test_csv_path):
            print(f"   📊 Tag comparison CSV: {os.path.basename(test_csv_path)}")

def main():
    """
    Main test function
    """
    print("Starting ID3v2 Metadata Test Suite")
    print("=" * 50)
    
    # Check if mutagen is available
    try:
        from mutagen.mp3 import MP3
        print("✅ Mutagen library is available")
    except ImportError:
        print("❌ Mutagen library not found. Please install with: pip install mutagen")
        return False
    
    # Run the test
    success = test_id3_metadata()
    
    if success:
        print("\n🎯 Test suite completed successfully!")
        return True
    else:
        print("\n💥 Test suite failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 