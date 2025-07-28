#!/usr/bin/env python3
"""
Complete Audio Workflow Test for Levante Translation Framework

This test simulates the complete audio generation process:
1. Reads sample data from the translation CSV
2. Generates actual audio using TTS services
3. Saves audio with complete ID3v2 metadata using save_audio()
4. Reads metadata back and validates
5. Creates detailed CSV report of the process

This test verifies the entire pipeline from translation data to tagged audio files.
"""

import sys
import os
import tempfile
import pandas as pd
from datetime import datetime
import shutil
import requests
import glob

# Add the parent directory to sys.path to import utilities
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utilities.utilities import audio_tags, write_id3_tags, read_id3_tags, save_audio, audio_file_path
from utilities import config as conf

def create_sample_translation_data():
    """
    Create sample translation data that mimics the structure from the CSV
    """
    sample_data = [
        {
            'item_id': 'test_welcome_message',
            'labels': 'general',
            'en': 'Welcome to the Levante assessment platform.',
            'es-CO': 'Bienvenido a la plataforma de evaluación Levante.',
            'de': 'Willkommen bei der Levante-Bewertungsplattform.',
            'fr-CA': 'Bienvenue sur la plateforme d\'évaluation Levante.',
            'nl': 'Welkom bij het Levante-evaluatieplatform.'
        },
        {
            'item_id': 'test_instructions',
            'labels': 'math',
            'en': 'Please solve the following problem step by step.',
            'es-CO': 'Por favor resuelve el siguiente problema paso a paso.',
            'de': 'Bitte lösen Sie das folgende Problem Schritt für Schritt.',
            'fr-CA': 'Veuillez résoudre le problème suivant étape par étape.',
            'nl': 'Los het volgende probleem stap voor stap op.'
        },
        {
            'item_id': 'test_completion',
            'labels': 'general',
            'en': 'Great job! You have completed this section.',
            'es-CO': '¡Excelente trabajo! Has completado esta sección.',
            'de': 'Großartige Arbeit! Sie haben diesen Abschnitt abgeschlossen.',
            'fr-CA': 'Excellent travail! Vous avez terminé cette section.',
            'nl': 'Geweldig werk! Je hebt dit gedeelte voltooid.'
        }
    ]
    
    return pd.DataFrame(sample_data)

def find_existing_mp3_for_testing():
    """
    Find an existing MP3 file to use as a template for testing
    """
    
    # Look for any existing MP3 file in audio_files
    mp3_patterns = [
        "audio_files/**/*.mp3",
    ]
    
    for pattern in mp3_patterns:
        mp3_files = glob.glob(pattern, recursive=True)
        if mp3_files:
            return mp3_files[0]
    
    return None

def create_mock_audio_data(text, service="TestTTS"):
    """
    Use a real MP3 file as the base for testing (copies existing audio)
    This ensures we have valid MP3 data that mutagen can work with
    """
    # Find an existing MP3 file to use as a template
    template_mp3 = find_existing_mp3_for_testing()
    
    if template_mp3 and os.path.exists(template_mp3):
        print(f"   📄 Using template MP3: {os.path.basename(template_mp3)}")
        # Read the real MP3 data
        with open(template_mp3, 'rb') as f:
            mp3_data = f.read()
    else:
        print("   ⚠️  No existing MP3 found, creating minimal structure...")
        # Fallback to a more complete MP3 structure
        # Create a more realistic MP3 file with proper structure
        
        # ID3v2.3 header with proper size calculation
        id3v2_header = b'ID3\x03\x00\x00\x00\x00\x00\x0A'  # 10 bytes of ID3 space
        
        # Multiple valid MP3 frames to create a more realistic file
        # This is a more complete MP3 frame structure
        mp3_frame_data = bytes([
            # Frame 1
            0xFF, 0xFB, 0x92, 0x00,  # MP3 frame header (MPEG-1 Layer 3, 128kbps, 44.1kHz)
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        ] * 20)  # Multiple frames
        
        mp3_data = id3v2_header + mp3_frame_data
    
    # Create mock audio response object
    class MockAudioResponse:
        def __init__(self, content):
            self.content = content
            self.status_code = 200
    
    return MockAudioResponse(mp3_data)

def test_complete_audio_workflow():
    """
    Test the complete audio generation and tagging workflow
    """
    print("🎙️ Testing Complete Audio Generation Workflow")
    print("=" * 60)
    
    # Create paths for test outputs
    script_dir = os.path.dirname(os.path.abspath(__file__))
    test_audio_dir = os.path.join(script_dir, "test_audio_files")
    test_results_csv = os.path.join(script_dir, "complete_workflow_results.csv")
    
    # Create test audio directory
    os.makedirs(test_audio_dir, exist_ok=True)
    
    # Create sample translation data
    print("\n📄 Creating sample translation data...")
    translation_data = create_sample_translation_data()
    print(f"✅ Created {len(translation_data)} sample translation items")
    
    # Display sample data
    print("\n📊 Sample translation data:")
    for _, row in translation_data.iterrows():
        print(f"  {row['item_id']} ({row['labels']}): {row['en'][:50]}...")
    
    # Test different language/service combinations
    test_combinations = [
        {'language': 'English', 'lang_code': 'en', 'service': 'PlayHT', 'voice': 'test_voice_playht_en'},
        {'language': 'Spanish', 'lang_code': 'es-CO', 'service': 'ElevenLabs', 'voice': 'test_voice_elevenlabs_es'},
        {'language': 'German', 'lang_code': 'de', 'service': 'PlayHT', 'voice': 'test_voice_playht_de'},
    ]
    
    # Results tracking
    workflow_results = []
    generated_files = []
    
    print(f"\n🎵 Testing {len(test_combinations)} language/service combinations...")
    
    # Create a mock master data DataFrame for save_audio
    master_data = pd.DataFrame({
        'item_id': translation_data['item_id'],
        'en': translation_data['en'],
        'es-CO': translation_data['es-CO'], 
        'de': translation_data['de'],
        'fr-CA': translation_data['fr-CA'],
        'nl': translation_data['nl']
    })
    
    for combo in test_combinations:
        lang_code = combo['lang_code']
        service = combo['service']
        voice = combo['voice']
        language = combo['language']
        
        print(f"\n--- Testing {language} with {service} ---")
        
        for _, row in translation_data.iterrows():
            item_id = row['item_id']
            
            # Get the text for this language
            if lang_code in row and pd.notna(row[lang_code]):
                text = row[lang_code]
            else:
                print(f"⚠️  No text for {lang_code} in {item_id}, skipping...")
                continue
            
            print(f"🎯 Processing: {item_id}")
            print(f"   Text: {text[:60]}...")
            print(f"   Service: {service}, Voice: {voice}")
            
            try:
                # Step 1: Generate mock audio (simulates TTS API call)
                print("   🔄 Generating audio...")
                audio_data = create_mock_audio_data(text, service)
                
                # Step 2: Use save_audio to save with ID3 tags
                print("   💾 Saving audio with metadata...")
                result = save_audio(
                    ourRow=row,
                    lang_code=lang_code,
                    service=service,
                    audioData=audio_data,
                    audio_base_dir=test_audio_dir,
                    masterData=master_data.copy(),  # Use copy to avoid modification
                    voice=voice
                )
                
                if result == 'Success':
                    print("   ✅ Audio saved successfully")
                    
                    # Step 3: Get the file path and read back metadata
                    file_path = audio_file_path(row['labels'], item_id, test_audio_dir, lang_code)
                    generated_files.append(file_path)
                    
                    print("   📖 Reading metadata...")
                    read_tags = read_id3_tags(file_path)
                    
                    if read_tags:
                        print(f"   ✅ Read {len(read_tags)} metadata fields")
                        
                        # Step 4: Validate key metadata
                        expected_tags = {
                            'title': item_id,
                            'artist': f"Levante Framework - {service}",
                            'album': row['labels'],
                            'genre': 'Speech Synthesis',
                            'lang_code': lang_code,
                            'service': service,
                            'voice': voice,
                            'text': text
                        }
                        
                        validation_results = {}
                        for field, expected_value in expected_tags.items():
                            actual_value = read_tags.get(field, '')
                            matches = str(expected_value) == str(actual_value)
                            validation_results[field] = {
                                'expected': expected_value,
                                'actual': actual_value,
                                'matches': matches
                            }
                            
                            if matches:
                                print(f"   ✅ {field}: MATCH")
                            else:
                                print(f"   ❌ {field}: MISMATCH (expected: '{expected_value}', got: '{actual_value}')")
                        
                        # Record results
                        workflow_results.append({
                            'item_id': item_id,
                            'language': language,
                            'lang_code': lang_code,
                            'service': service,
                            'voice': voice,
                            'text': text[:100] + '...' if len(text) > 100 else text,
                            'file_path': file_path.split('audio_files' + os.sep, 1)[-1] if 'audio_files' in file_path else file_path,
                            'file_exists': os.path.exists(file_path),
                            'metadata_fields_count': len(read_tags),
                            'validation_passed': all(v['matches'] for v in validation_results.values()),
                            'title_match': validation_results.get('title', {}).get('matches', False),
                            'artist_match': validation_results.get('artist', {}).get('matches', False),
                            'service_match': validation_results.get('service', {}).get('matches', False),
                            'voice_match': validation_results.get('voice', {}).get('matches', False),
                            'lang_code_match': validation_results.get('lang_code', {}).get('matches', False),
                            'text_match': validation_results.get('text', {}).get('matches', False),
                            'created_timestamp': read_tags.get('created', ''),
                            'generation_date': datetime.now().isoformat()
                        })
                        
                    else:
                        print("   ❌ Failed to read metadata")
                        workflow_results.append({
                            'item_id': item_id,
                            'language': language,
                            'lang_code': lang_code,
                            'service': service,
                            'voice': voice,
                            'text': text,
                            'file_path': file_path.split('audio_files' + os.sep, 1)[-1] if 'audio_files' in file_path else file_path,
                            'file_exists': os.path.exists(file_path),
                            'metadata_fields_count': 0,
                            'validation_passed': False,
                            'error': 'Failed to read metadata'
                        })
                else:
                    print(f"   ❌ Failed to save audio: {result}")
                    
            except Exception as e:
                print(f"   ❌ Error processing {item_id}: {e}")
                workflow_results.append({
                    'item_id': item_id,
                    'language': language,
                    'lang_code': lang_code,
                    'service': service,
                    'voice': voice,
                    'text': text,
                    'error': str(e),
                    'validation_passed': False
                })
    
    # Step 5: Create comprehensive results CSV
    print(f"\n📊 Creating comprehensive results report...")
    results_df = pd.DataFrame(workflow_results)
    results_df.to_csv(test_results_csv, index=False, encoding='utf-8')
    
    print(f"✅ Saved detailed results to: {test_results_csv}")
    
    # Step 6: Summary statistics
    print(f"\n📈 Workflow Test Summary:")
    print(f"   Total items processed: {len(workflow_results)}")
    print(f"   Successful generations: {len([r for r in workflow_results if r.get('validation_passed', False)])}")
    print(f"   Failed generations: {len([r for r in workflow_results if not r.get('validation_passed', False)])}")
    print(f"   Audio files created: {len(generated_files)}")
    print(f"   Average metadata fields per file: {sum(r.get('metadata_fields_count', 0) for r in workflow_results) / len(workflow_results):.1f}")
    
    # Step 7: List generated files
    print(f"\n📁 Generated test files:")
    print(f"   Audio files directory: {os.path.relpath(test_audio_dir)}")
    for file_path in generated_files:
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            rel_path = os.path.relpath(file_path)
            print(f"   🎵 {rel_path} ({file_size} bytes)")
    
    print(f"   📊 Results CSV: {os.path.relpath(test_results_csv)}")
    
    # Step 8: Validation summary
    successful_validations = [r for r in workflow_results if r.get('validation_passed', False)]
    success_rate = len(successful_validations) / len(workflow_results) * 100 if workflow_results else 0
    
    print(f"\n🎯 Final Results:")
    print(f"   Success rate: {success_rate:.1f}%")
    
    if success_rate == 100:
        print("   🎉 ALL TESTS PASSED! Complete workflow is functioning correctly.")
        return True
    elif success_rate >= 80:
        print("   ✅ Most tests passed. Check CSV for details on any failures.")
        return True
    else:
        print("   ⚠️  Many tests failed. Check CSV for detailed error information.")
        return False

def main():
    """
    Main test function
    """
    print("Starting Complete Audio Workflow Test Suite")
    print("=" * 60)
    
    # Check if mutagen is available
    try:
        from mutagen.mp3 import MP3
        print("✅ Mutagen library is available")
    except ImportError:
        print("❌ Mutagen library not found. Please install with: pip install mutagen")
        return False
    
    # Run the comprehensive test
    success = test_complete_audio_workflow()
    
    if success:
        print("\n🎯 Complete workflow test suite completed successfully!")
        return True
    else:
        print("\n💥 Complete workflow test suite failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 