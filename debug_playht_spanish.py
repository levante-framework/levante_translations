#!/usr/bin/env python3
"""
Debug PlayHT Spanish Voice Issues

This script tests various parameters to identify the cause of:
- Clipped words
- Audio repetitions
- Quality issues with Spanish voices

Usage:
    python debug_playht_spanish.py
"""

import requests
import os
import json
import time
import tempfile
import playsound
from datetime import datetime

# PlayHT API v2 constants
API_URL = "https://api.play.ht/api/v2/tts/stream"
VOICES_URL = "https://api.play.ht/api/v2/voices"

def get_headers():
    """Get API headers for PlayHT"""
    return {
        "AUTHORIZATION": os.environ.get("PLAY_DOT_HT_API_KEY"),
        "X-USER-ID": os.environ.get("PLAY_DOT_HT_USER_ID"),
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    }

def get_spanish_voices():
    """Fetch available Spanish voices from PlayHT"""
    headers = get_headers()
    
    try:
        response = requests.get(VOICES_URL, headers=headers)
        if response.status_code == 200:
            voices_data = response.json()
            
            # Filter for Spanish voices
            spanish_voices = []
            for voice in voices_data:
                language = voice.get('language', '').lower()
                language_code = voice.get('languageCode', '').lower()
                
                if ('spanish' in language or 'es' in language_code or 
                    'es-' in language_code or 'spa' in language):
                    spanish_voices.append({
                        'name': voice.get('name', 'Unknown'),
                        'id': voice.get('id', voice.get('value', '')),
                        'language': voice.get('language', 'Unknown'),
                        'language_code': voice.get('languageCode', 'Unknown'),
                        'gender': voice.get('gender', 'Unknown'),
                        'age': voice.get('age', 'Unknown'),
                        'accent': voice.get('accent', 'Unknown'),
                        'style': voice.get('style', 'Unknown')
                    })
            
            return spanish_voices
        else:
            print(f"Error fetching voices: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Exception fetching voices: {e}")
        return []

def test_voice_parameters(voice_id, test_text):
    """Test different voice engine and parameter combinations"""
    headers = get_headers()
    
    # Test different voice engines
    engines = ["PlayDialog", "Play3.0-mini", "PlayHT2.0-turbo"]
    
    # Test different sample rates
    sample_rates = [24000, 22050, 44100]
    
    # Test different output formats
    formats = ["mp3", "wav"]
    
    results = []
    
    for engine in engines:
        for sample_rate in sample_rates:
            for format_type in formats:
                print(f"\nTesting: Engine={engine}, Rate={sample_rate}, Format={format_type}")
                
                # Basic request data
                data = {
                    "text": test_text,
                    "voice": voice_id,
                    "voice_engine": engine,
                    "output_format": format_type,
                    "sample_rate": sample_rate
                }
                
                # Test with plain text
                result = make_api_call(data, headers, f"{engine}_{sample_rate}_{format_type}_plain")
                if result:
                    results.append(result)
                
                # Test with SSML (if not PlayDialog - it sometimes has issues with SSML)
                if engine != "PlayDialog":
                    ssml_data = data.copy()
                    ssml_data["text_type"] = "ssml"
                    ssml_data["text"] = f"<emphasis>{test_text}</emphasis>"
                    
                    result = make_api_call(ssml_data, headers, f"{engine}_{sample_rate}_{format_type}_ssml")
                    if result:
                        results.append(result)
    
    return results

def make_api_call(data, headers, test_name):
    """Make API call and analyze response"""
    start_time = time.time()
    
    try:
        response = requests.post(API_URL, headers=headers, json=data, timeout=30)
        end_time = time.time()
        
        result = {
            'test_name': test_name,
            'status_code': response.status_code,
            'response_time': end_time - start_time,
            'content_length': len(response.content) if response.content else 0,
            'data': data.copy(),
            'success': response.status_code == 200
        }
        
        if response.status_code == 200:
            print(f"✅ Success: {len(response.content)} bytes in {result['response_time']:.2f}s")
            
            # Save audio file for manual inspection
            save_audio_sample(response.content, test_name)
            
        elif response.status_code == 500:
            error_text = response.text
            print(f"❌ Server Error 500: {error_text}")
            result['error'] = error_text
            
            # Log detailed error info for 500 errors
            print(f"   Voice: {data.get('voice', 'N/A')}")
            print(f"   Engine: {data.get('voice_engine', 'N/A')}")
            print(f"   Text: '{data.get('text', '')[:50]}...'")
            print(f"   Text Length: {len(data.get('text', ''))}")
            
        else:
            error_text = response.text
            print(f"❌ Error {response.status_code}: {error_text}")
            result['error'] = error_text
        
        return result
        
    except requests.exceptions.Timeout:
        print(f"⏰ Timeout after 30 seconds")
        return {
            'test_name': test_name,
            'status_code': 'TIMEOUT',
            'error': 'Request timeout',
            'data': data.copy(),
            'success': False
        }
    except Exception as e:
        print(f"💥 Exception: {e}")
        return {
            'test_name': test_name,
            'status_code': 'EXCEPTION',
            'error': str(e),
            'data': data.copy(),
            'success': False
        }

def save_audio_sample(audio_data, test_name):
    """Save audio sample for manual inspection"""
    if not os.path.exists('debug_audio_samples'):
        os.makedirs('debug_audio_samples')
    
    filename = f"debug_audio_samples/{test_name}_{datetime.now().strftime('%H%M%S')}.mp3"
    
    try:
        with open(filename, 'wb') as f:
            f.write(audio_data)
        print(f"   Saved audio sample: {filename}")
    except Exception as e:
        print(f"   Failed to save audio: {e}")

def test_text_variations():
    """Test different text inputs to identify problematic patterns"""
    test_texts = [
        # Original problematic text
        "¡Hola! ¡Estamos encantados de que juegues hoy con nosotros!",
        
        # Simplified versions
        "Hola! Estamos encantados de que juegues hoy con nosotros!",
        "Hola. Estamos encantados de que juegues hoy con nosotros.",
        "Estamos encantados de que juegues hoy con nosotros",
        
        # Short test
        "Hola mundo",
        
        # No punctuation
        "Estamos encantados de que juegues hoy",
        
        # Different punctuation
        "¡Hola! Estamos encantados.",
        
        # SSML versions
        "<emphasis>Hola</emphasis>! Estamos encantados de que juegues hoy con nosotros!",
        "Hola! <break time='0.5s'/> Estamos encantados de que juegues hoy con nosotros!",
    ]
    
    return test_texts

def analyze_voice_usage():
    """Analyze the specific voice being used in the dashboard"""
    # This is the voice ID from your request
    problematic_voice = "s3://voice-cloning-zero-shot/326c3793-b5b1-4ce3-a8ec-22c95d8553f0/original/manifest.json"
    
    print(f"Analyzing problematic voice: {problematic_voice}")
    
    # Test with various texts
    test_texts = test_text_variations()
    
    all_results = []
    
    for i, text in enumerate(test_texts):
        print(f"\n=== Test {i+1}: '{text[:50]}...' ===")
        
        # Test with basic PlayDialog settings (matching your current setup)
        basic_data = {
            "text": text,
            "voice": problematic_voice,
            "voice_engine": "PlayDialog",
            "output_format": "mp3",
            "sample_rate": 24000
        }
        
        result = make_api_call(basic_data, get_headers(), f"text_test_{i+1}_basic")
        if result:
            all_results.append(result)
        
        # Test with alternative engine
        alt_data = basic_data.copy()
        alt_data["voice_engine"] = "Play3.0-mini"
        
        result = make_api_call(alt_data, get_headers(), f"text_test_{i+1}_alt")
        if result:
            all_results.append(result)
    
    return all_results

def main():
    """Main debugging function"""
    print("🔍 PlayHT Spanish Voice Debugging Tool")
    print("=" * 50)
    
    # Check API credentials
    api_key = os.environ.get("PLAY_DOT_HT_API_KEY")
    user_id = os.environ.get("PLAY_DOT_HT_USER_ID")
    
    if not api_key or not user_id:
        print("❌ Missing PlayHT API credentials!")
        print("Set PLAY_DOT_HT_API_KEY and PLAY_DOT_HT_USER_ID environment variables")
        return
    
    print(f"✅ API Key: {api_key[:4]}...{api_key[-4:]}")
    print(f"✅ User ID: {user_id[:4]}...{user_id[-4:]}")
    
    # 1. Fetch available Spanish voices
    print("\n1. Fetching Spanish voices...")
    spanish_voices = get_spanish_voices()
    
    if spanish_voices:
        print(f"Found {len(spanish_voices)} Spanish voices:")
        for voice in spanish_voices[:5]:  # Show first 5
            print(f"  - {voice['name']} ({voice['gender']}, {voice['language']})")
    
    # 2. Test the problematic voice with various parameters
    print("\n2. Testing problematic voice with different parameters...")
    problematic_voice = "s3://voice-cloning-zero-shot/326c3793-b5b1-4ce3-a8ec-22c95d8553f0/original/manifest.json"
    test_text = "¡Hola! ¡Estamos encantados de que juegues hoy con nosotros!"
    
    param_results = test_voice_parameters(problematic_voice, test_text)
    
    # 3. Test different text variations
    print("\n3. Testing different text variations...")
    text_results = analyze_voice_usage()
    
    # 4. Generate summary report
    print("\n" + "=" * 50)
    print("📊 SUMMARY REPORT")
    print("=" * 50)
    
    all_results = param_results + text_results
    successful_tests = [r for r in all_results if r['success']]
    failed_tests = [r for r in all_results if not r['success']]
    
    print(f"Total tests: {len(all_results)}")
    print(f"Successful: {len(successful_tests)}")
    print(f"Failed: {len(failed_tests)}")
    
    if successful_tests:
        print("\n✅ SUCCESSFUL CONFIGURATIONS:")
        for result in successful_tests:
            data = result['data']
            print(f"  {result['test_name']}: {data['voice_engine']}, {data['sample_rate']}Hz, {data['output_format']}")
            print(f"    Response time: {result['response_time']:.2f}s, Size: {result['content_length']} bytes")
    
    if failed_tests:
        print("\n❌ FAILED CONFIGURATIONS:")
        for result in failed_tests:
            print(f"  {result['test_name']}: {result['status_code']} - {result.get('error', 'Unknown error')}")
    
    # 5. Recommendations
    print("\n🔧 RECOMMENDATIONS:")
    
    if len(successful_tests) > 0:
        # Find the best performing configuration
        best_result = max(successful_tests, key=lambda x: x['content_length'])
        best_data = best_result['data']
        
        print(f"1. Use voice engine: {best_data['voice_engine']}")
        print(f"2. Use sample rate: {best_data['sample_rate']}Hz")
        print(f"3. Use output format: {best_data['output_format']}")
        
        if 'text_type' in best_data:
            print(f"4. Text type: {best_data['text_type']}")
        
        print(f"5. Best test generated {best_result['content_length']} bytes in {best_result['response_time']:.2f}s")
    
    print("\n6. Check generated audio samples in 'debug_audio_samples/' folder")
    print("7. Listen to samples to identify which settings produce the best quality")
    
    # 6. Specific recommendations for the Spanish voice issue
    print("\n🎯 SPECIFIC SPANISH VOICE RECOMMENDATIONS:")
    print("- Try using 'Play3.0-mini' instead of 'PlayDialog' for more stable results")
    print("- Consider removing exclamation marks if they cause issues")
    print("- Test with simpler punctuation")
    print("- Check if the voice ID is still valid (voices can be deprecated)")
    
if __name__ == "__main__":
    main() 