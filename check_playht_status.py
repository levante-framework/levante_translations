#!/usr/bin/env python3
"""
PlayHt API Status Checker
Tests both voices and TTS endpoints to verify API functionality
"""

import requests
import os
from datetime import datetime
import json

# API v2 endpoints
VOICES_URL = "https://api.play.ht/api/v2/voices"
TTS_URL = "https://api.play.ht/api/v2/tts/stream"

# Headers for API v2
headers = {
    "AUTHORIZATION": os.environ.get("PLAY_DOT_HT_API_KEY"),
    "X-USER-ID": os.environ.get("PLAY_DOT_HT_USER_ID"),
    "Content-Type": "application/json"
}

# Required voices for each language
REQUIRED_VOICES = {
    'es-CO': 'Spanish_Violeta Narrative',
    'de-DE': 'German_Anke Narrative', 
    'fr-CA': 'French_Ange Narrative',
    'nl-NL': 'FennaNeural'  # Dutch uses ElevenLabs, not PlayHT
}

def check_api_credentials():
    """Check if API credentials are available"""
    api_key = os.environ.get("PLAY_DOT_HT_API_KEY")
    user_id = os.environ.get("PLAY_DOT_HT_USER_ID")
    
    if not api_key or not user_id:
        print("❌ Missing API credentials!")
        print("Please set PLAY_DOT_HT_API_KEY and PLAY_DOT_HT_USER_ID environment variables")
        return False
    
    print(f"✅ API Key: {api_key[:10]}...")
    print(f"✅ User ID: {user_id}")
    return True

def check_voices_endpoint():
    """Test the voices endpoint"""
    print("\n🔍 Testing voices endpoint...")
    
    try:
        response = requests.get(VOICES_URL, headers=headers)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, list):
                voices = data
            else:
                voices = data.get("voices", [])
                
            print(f"✅ Voices endpoint working - {len(voices)} voices available")
            
            # Show structure of first few voices to understand the data format
            print("\n🔍 Sample voice data structure:")
            for i, voice in enumerate(voices[:3]):
                print(f"Voice {i+1}:")
                for key, value in voice.items():
                    print(f"  {key}: {value}")
                print()
            
            # Show all unique language codes available
            language_codes = set()
            for voice in voices:
                lang_code = voice.get('language', voice.get('languageCode', ''))
                if lang_code:
                    language_codes.add(lang_code)
            
            print(f"\n🌍 Available language codes ({len(language_codes)}):")
            sorted_codes = sorted(language_codes)
            for i, code in enumerate(sorted_codes):
                print(f"  {code}", end="")
                if (i + 1) % 6 == 0:  # New line every 6 codes
                    print()
            print()  # Final newline
            
            # Search for voices in our target languages (using actual language names)
            print("\n🎯 Searching for voices in our target languages:")
            target_languages = {
                'Spanish': 'Spanish',
                'German': 'German', 
                'French': 'French',
                'Dutch': 'Dutch'
            }
            
            found_voices = {}
            
            for language, lang_name in target_languages.items():
                print(f"\n📍 {language} voices:")
                matching_voices = []
                
                for voice in voices:
                    voice_lang = voice.get('language', '')
                    voice_name = voice.get('name', '')
                    voice_id = voice.get('id', '')
                    
                    # Check if the language matches exactly
                    if lang_name.lower() in voice_lang.lower():
                        matching_voices.append({
                            'name': voice_name,
                            'id': voice_id,
                            'lang': voice_lang,
                            'lang_code': voice.get('language_code', ''),
                            'gender': voice.get('gender', 'N/A'),
                            'age': voice.get('age', 'N/A'),
                            'accent': voice.get('accent', 'N/A')
                        })
                
                if matching_voices:
                    # Show first 5 voices to avoid too much output
                    for i, voice in enumerate(matching_voices[:5]):
                        print(f"  {i+1}. {voice['name']}")
                        print(f"     ID: {voice['id']}")
                        print(f"     Lang: {voice['lang']} ({voice['lang_code']})")
                        print(f"     Gender: {voice['gender']}, Age: {voice['age']}, Accent: {voice['accent']}")
                    
                    if len(matching_voices) > 5:
                        print(f"  ... and {len(matching_voices) - 5} more voices")
                    
                    # Store the first female voice we find for each language
                    female_voices = [v for v in matching_voices if v['gender'].lower() == 'female']
                    if female_voices:
                        found_voices[language.lower()] = female_voices[0]
                    elif matching_voices:
                        found_voices[language.lower()] = matching_voices[0]
                else:
                    print(f"  ❌ No voices found for {language}")
            
            # Check for our original required voices
            print("\n🔍 Checking for our original required voices:")
            for lang_code, required_voice in REQUIRED_VOICES.items():
                matching_voices = []
                for voice in voices:
                    voice_name = voice.get('name', '')
                    voice_id = voice.get('value', '')
                    
                    # Check if this voice matches what we need
                    if (required_voice in voice_name or 
                        required_voice in voice_id):
                        matching_voices.append({
                            'name': voice_name,
                            'id': voice_id,
                            'lang': voice.get('languageCode', ''),
                            'gender': voice.get('gender', 'N/A'),
                            'age': voice.get('age', 'N/A')
                        })
                
                if matching_voices:
                    print(f"  ✅ {lang_code} ({required_voice}):")
                    for voice in matching_voices:
                        print(f"    - Name: {voice['name']}")
                        print(f"      ID: {voice['id']}")
                        print(f"      Lang: {voice['lang']}, Gender: {voice['gender']}, Age: {voice['age']}")
                else:
                    print(f"  ❌ {lang_code} ({required_voice}): NOT FOUND")
            
            return True, found_voices
        else:
            print(f"❌ Voices endpoint failed: {response.text}")
            return False, {}
            
    except Exception as e:
        print(f"❌ Error testing voices endpoint: {str(e)}")
        return False, {}

def check_tts_endpoint(voice_info=None):
    """Test the TTS endpoint"""
    print("\n🔍 Testing TTS endpoint with simple request...")
    
    # Use a found voice or default
    test_voice = "Play3.0-mini-http"
    if voice_info:
        # Use the first available voice from our required list
        first_voice = next(iter(voice_info.values()))
        test_voice = first_voice['id']
        print(f"Using voice: {first_voice['name']} ({test_voice})")
    
    payload = {
        "text": "Hello, this is a test of the PlayHt API version 2.",
        "voice": test_voice,
        "voice_engine": "Play3.0-mini"
    }
    
    try:
        response = requests.post(TTS_URL, json=payload, headers={
            **headers,
            "Accept": "audio/mpeg"
        })
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            audio_size = len(response.content)
            print(f"✅ TTS request successful - received {audio_size} bytes of audio")
            return True
        else:
            print(f"❌ TTS request failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing TTS endpoint: {str(e)}")
        return False

def check_rate_limiting(response):
    """Check rate limiting information from response headers"""
    print("\n🔍 Checking rate limiting information...")
    
    rate_headers = {k: v for k, v in response.headers.items() 
                   if 'rate' in k.lower() or 'limit' in k.lower()}
    
    if rate_headers:
        print("Rate limiting headers:")
        for key, value in rate_headers.items():
            print(f"  {key}: {value}")
    else:
        print("  No rate limiting headers found")

def main():
    print("PlayHt API Status Checker")
    print("=" * 30)
    
    # Check credentials
    if not check_api_credentials():
        return
    
    # Check voices endpoint
    voices_ok, found_voices = check_voices_endpoint()
    
    if voices_ok:
        # Check TTS endpoint
        tts_ok = check_tts_endpoint(found_voices)
        
        # Summary
        print("\n📊 Summary:")
        print(f"  Voices API: {'✅ Working' if voices_ok else '❌ Failed'}")
        print(f"  TTS API: {'✅ Working' if tts_ok else '❌ Failed'}")
        print(f"  Required voices found: {len(found_voices)}/{len(REQUIRED_VOICES)}")
        
        if len(found_voices) < len(REQUIRED_VOICES):
            print("\n⚠️  Some required voices were not found. You may need to:")
            print("  1. Check voice names in the PlayHt dashboard")
            print("  2. Update voice IDs in your configuration")
            print("  3. Consider using alternative voices")
    
    print(f"\n📅 Check completed at: {datetime.now()}")

if __name__ == "__main__":
    main() 