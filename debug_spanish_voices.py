#!/usr/bin/env python3
"""
Debug script to list available Spanish voices in ElevenLabs account.
"""

import os
from elevenlabs.client import ElevenLabs

print("=== Debugging Spanish ElevenLabs Voices ===")

try:
    # Force reload environment variables
    import importlib
    importlib.reload(os)
    
    # Initialize ElevenLabs client
    api_key = os.getenv('elevenlabs_test')
    if not api_key:
        print("ERROR: No ElevenLabs API key found in 'elevenlabs_test' environment variable")
        print("Available env vars starting with 'eleven':")
        for key in os.environ:
            if 'eleven' in key.lower():
                print(f"  {key}")
        exit(1)
    
    print(f"✓ Found API key: {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else '***'}")
    
    client = ElevenLabs(api_key=api_key)
    print("✓ ElevenLabs client initialized successfully")
    
    # Get all voices
    response = client.voices.get_all()
    voice_list = response.voices
    print(f"✓ Found {len(voice_list)} total voices in account")
    
    # Filter for Spanish voices
    spanish_voices = []
    for voice in voice_list:
        language = voice.labels.get('language', '')
        if language == 'es' or 'spanish' in language.lower():
            spanish_voices.append({
                'name': voice.name,
                'id': voice.voice_id,
                'language': language,
                'category': voice.category,
                'gender': voice.labels.get('gender', 'unknown')
            })
    
    print(f"\n=== ALL VOICES IN ACCOUNT ({len(voice_list)}) ===")
    for i, voice in enumerate(voice_list, 1):
        language = voice.labels.get('language', 'unknown')
        category = voice.category
        gender = voice.labels.get('gender', 'unknown')
        print(f"{i:3d}. '{voice.name}'")
        print(f"     ID: {voice.voice_id}")
        print(f"     Language: {language}")
        print(f"     Category: {category}")
        print(f"     Gender: {gender}")
        print()
    
    print(f"\n=== Spanish Voices Found ({len(spanish_voices)}) ===")
    if spanish_voices:
        for i, voice in enumerate(spanish_voices, 1):
            print(f"{i:2d}. '{voice['name']}'")
            print(f"    ID: {voice['id']}")
            print(f"    Language: {voice['language']}")
            print(f"    Category: {voice['category']}")
            print(f"    Gender: {voice['gender']}")
            print()
    else:
        print("❌ No Spanish voices found!")
        
    # Check specifically for "Malena Tango"
    malena_voices = [v for v in spanish_voices if 'malena' in v['name'].lower()]
    if malena_voices:
        print("=== Malena Voices Found ===")
        for voice in malena_voices:
            print(f"Found: '{voice['name']}' (ID: {voice['id']})")
    else:
        print("❌ No 'Malena' voices found in Spanish voices")
        
        # Look for any Malena in all voices
        all_malena = [v for v in voice_list if 'malena' in v.name.lower()]
        if all_malena:
            print("\n=== Malena Voices in Other Languages ===")
            for voice in all_malena:
                lang = voice.labels.get('language', 'unknown')
                print(f"'{voice.name}' - Language: {lang}")

except Exception as e:
    print(f"❌ ERROR: {str(e)}") 