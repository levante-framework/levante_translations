#!/usr/bin/env python
"""
Debug script to list all ElevenLabs voices and check for Spanish voices
"""
import os
from elevenlabs.client import ElevenLabs

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
    
    # Filter for Spanish voices
    spanish_voices = []
    for voice in voice_list:
        language = voice.labels.get('language', '')
        voice_name = voice.name.lower()
        
        # Check if voice is Spanish by language label or name
        if ('spanish' in language.lower() or 
            'español' in language.lower() or 
            'es' in language.lower() or
            'malena' in voice_name or
            'tango' in voice_name):
            spanish_voices.append(voice)
    
    print(f"\n=== SPANISH/SPANISH-RELATED VOICES ({len(spanish_voices)}) ===")
    for i, voice in enumerate(spanish_voices, 1):
        language = voice.labels.get('language', 'unknown')
        category = voice.category
        gender = voice.labels.get('gender', 'unknown')
        print(f"{i:3d}. '{voice.name}' (ID: {voice.voice_id})")
        print(f"     Language: {language}")
        print(f"     Category: {category}")
        print(f"     Gender: {gender}")
        print()
    
    # Specifically look for Malena Tango
    malena_voices = [v for v in voice_list if 'malena' in v.name.lower()]
    tango_voices = [v for v in voice_list if 'tango' in v.name.lower()]
    
    print(f"\n=== VOICES WITH 'MALENA' IN NAME ({len(malena_voices)}) ===")
    for voice in malena_voices:
        print(f"'{voice.name}' (ID: {voice.voice_id})")
    
    print(f"\n=== VOICES WITH 'TANGO' IN NAME ({len(tango_voices)}) ===")
    for voice in tango_voices:
        print(f"'{voice.name}' (ID: {voice.voice_id})")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()