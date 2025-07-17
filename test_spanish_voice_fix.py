#!/usr/bin/env python3
"""
Test and Fix Spanish PlayHT Voice Issues

Specific test for the voice causing problems:
s3://voice-cloning-zero-shot/326c3793-b5b1-4ce3-a8ec-22c95d8553f0/original/manifest.json

Issues to solve:
- Clipped words
- Audio repetitions
- Quality inconsistency
"""

import requests
import os
import json
import time

# PlayHT API configuration
API_URL = "https://api.play.ht/api/v2/tts/stream"

def test_spanish_voice_fixes():
    """Test various fixes for the Spanish voice issues"""
    
    # The problematic voice from your request
    voice_id = "s3://voice-cloning-zero-shot/326c3793-b5b1-4ce3-a8ec-22c95d8553f0/original/manifest.json"
    
    # The problematic text
    original_text = "¡Hola! ¡Estamos encantados de que juegues hoy con nosotros!"
    
    # API headers
    headers = {
        "AUTHORIZATION": os.environ.get("PLAY_DOT_HT_API_KEY"),
        "X-USER-ID": os.environ.get("PLAY_DOT_HT_USER_ID"),
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    }
    
    print("🔍 Testing Spanish Voice Fixes")
    print(f"Voice ID: {voice_id}")
    print(f"Text: {original_text}")
    print("=" * 60)
    
    tests = [
        {
            "name": "Original Configuration (PlayDialog)",
            "data": {
                "text": original_text,
                "voice": voice_id,
                "voice_engine": "PlayDialog",
                "output_format": "mp3",
                "sample_rate": 24000
            }
        },
        {
            "name": "Alternative Engine (Play3.0-mini)",
            "data": {
                "text": original_text,
                "voice": voice_id,
                "voice_engine": "Play3.0-mini",
                "output_format": "mp3",
                "sample_rate": 24000
            }
        },
        {
            "name": "Lower Sample Rate (PlayDialog)",
            "data": {
                "text": original_text,
                "voice": voice_id,
                "voice_engine": "PlayDialog",
                "output_format": "mp3",
                "sample_rate": 22050
            }
        },
        {
            "name": "Simplified Text (PlayDialog)",
            "data": {
                "text": "Hola! Estamos encantados de que juegues hoy con nosotros!",
                "voice": voice_id,
                "voice_engine": "PlayDialog",
                "output_format": "mp3",
                "sample_rate": 24000
            }
        },
        {
            "name": "No Exclamations (PlayDialog)",
            "data": {
                "text": "Hola. Estamos encantados de que juegues hoy con nosotros.",
                "voice": voice_id,
                "voice_engine": "PlayDialog",
                "output_format": "mp3",
                "sample_rate": 24000
            }
        },
        {
            "name": "With SSML Breaks (Play3.0-mini)",
            "data": {
                "text": "Hola! <break time='0.3s'/> Estamos encantados de que juegues hoy con nosotros!",
                "voice": voice_id,
                "voice_engine": "Play3.0-mini",
                "output_format": "mp3",
                "sample_rate": 24000,
                "text_type": "ssml"
            }
        }
    ]
    
    results = []
    
    for i, test in enumerate(tests, 1):
        print(f"\n{i}. Testing: {test['name']}")
        print(f"   Engine: {test['data']['voice_engine']}")
        print(f"   Text: {test['data']['text'][:50]}...")
        
        try:
            start_time = time.time()
            response = requests.post(API_URL, headers=headers, json=test['data'], timeout=30)
            end_time = time.time()
            
            if response.status_code == 200:
                audio_size = len(response.content)
                duration = end_time - start_time
                
                print(f"   ✅ Success: {audio_size} bytes in {duration:.2f}s")
                
                # Save audio file for comparison
                filename = f"spanish_test_{i}_{test['name'].replace(' ', '_').replace('(', '').replace(')', '')}.mp3"
                with open(filename, 'wb') as f:
                    f.write(response.content)
                print(f"   💾 Saved: {filename}")
                
                results.append({
                    'test': test['name'],
                    'success': True,
                    'size': audio_size,
                    'duration': duration,
                    'config': test['data']
                })
                
            else:
                error_text = response.text
                print(f"   ❌ Error {response.status_code}: {error_text}")
                
                results.append({
                    'test': test['name'],
                    'success': False,
                    'error': f"{response.status_code}: {error_text}",
                    'config': test['data']
                })
                
        except Exception as e:
            print(f"   💥 Exception: {e}")
            results.append({
                'test': test['name'],
                'success': False,
                'error': str(e),
                'config': test['data']
            })
    
    # Generate recommendations
    print("\n" + "=" * 60)
    print("📊 RESULTS SUMMARY")
    print("=" * 60)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"Successful tests: {len(successful)}/{len(results)}")
    print(f"Failed tests: {len(failed)}/{len(results)}")
    
    if successful:
        print("\n✅ WORKING CONFIGURATIONS:")
        for result in successful:
            config = result['config']
            print(f"  • {result['test']}")
            print(f"    Engine: {config['voice_engine']}")
            print(f"    Sample Rate: {config['sample_rate']}Hz")
            print(f"    Audio Size: {result['size']} bytes")
            print(f"    Generation Time: {result['duration']:.2f}s")
            print()
    
    if failed:
        print("❌ FAILED CONFIGURATIONS:")
        for result in failed:
            print(f"  • {result['test']}: {result['error']}")
    
    # Specific recommendations
    print("\n🔧 RECOMMENDATIONS FOR DASHBOARD:")
    
    if successful:
        best_result = max(successful, key=lambda x: x['size'])
        best_config = best_result['config']
        
        print(f"1. RECOMMENDED ENGINE: {best_config['voice_engine']}")
        print(f"2. RECOMMENDED SAMPLE RATE: {best_config['sample_rate']}Hz")
        
        if 'text_type' in best_config:
            print(f"3. USE SSML: {best_config['text_type']}")
        
        print("\n4. UPDATE DASHBOARD SETTINGS:")
        print("   In dashboard.js, modify the generatePlayHTAudio function:")
        print(f"   - Change voice_engine to: '{best_config['voice_engine']}'")
        print(f"   - Change sample_rate to: {best_config['sample_rate']}")
        
        if best_config['voice_engine'] != 'PlayDialog':
            print("   - Consider adding fallback from PlayDialog to Play3.0-mini")
    
    print("\n5. GENERAL IMPROVEMENTS:")
    print("   - Add retry logic for failed requests")
    print("   - Implement automatic fallback between engines")
    print("   - Pre-process text to remove problematic punctuation")
    print("   - Add audio quality validation")
    
    return results

def main():
    # Check credentials
    if not os.environ.get("PLAY_DOT_HT_API_KEY") or not os.environ.get("PLAY_DOT_HT_USER_ID"):
        print("❌ Missing PlayHT credentials!")
        print("Set PLAY_DOT_HT_API_KEY and PLAY_DOT_HT_USER_ID environment variables")
        return
    
    results = test_spanish_voice_fixes()
    
    print("\n🎧 NEXT STEPS:")
    print("1. Listen to the generated audio files")
    print("2. Compare quality and identify the best configuration")
    print("3. Update your dashboard code with the recommended settings")
    print("4. Test with more Spanish text samples")

if __name__ == "__main__":
    main() 