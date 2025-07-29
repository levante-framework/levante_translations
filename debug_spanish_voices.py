#!/usr/bin/env python3

import os
from elevenlabs.client import ElevenLabs

try:
    api_key = os.getenv('elevenlabs_test')
    if not api_key:
        print("No ElevenLabs API key found in environment variable 'elevenlabs_test'")
        exit(1)
    
    client = ElevenLabs(api_key=api_key)
    
    # Get all voices
    response = client.voices.get_all()
    voice_list = response.voices
    
    print(f"Total voices found: {len(voice_list)}")
    print(f"API Key: {api_key[:10]}...{api_key[-5:]}")
    
    # Show ALL voices first
    print("\nALL voices available:")
    for i, voice in enumerate(voice_list[:20]):  # Show first 20 to avoid too much output
        voice_lang = voice.labels.get('language', '') if voice.labels else ''
        print(f"  {i+1}. Name: '{voice.name}'")
        print(f"     Language: '{voice_lang}'")
        print(f"     Category: {voice.category}")
        print()
    
    if len(voice_list) > 20:
        print(f"... and {len(voice_list) - 20} more voices")
    
    print("\n" + "="*50)
    print("Searching for Spanish-related voices:")
    
    spanish_voices = []
    for voice in voice_list:
        # Check for Spanish language voices
        voice_lang = voice.labels.get('language', '') if voice.labels else ''
        voice_name_lower = voice.name.lower()
        
        # More broad search criteria
        is_spanish = (
            voice_lang == 'es' or 
            voice_lang == 'spanish' or
            'spanish' in voice_name_lower or 
            'maría' in voice_name_lower or
            'ana' in voice_name_lower or
            'es-' in voice_lang or
            'spain' in voice_name_lower
        )
        
        if is_spanish:
            spanish_voices.append(voice)
            print(f"  Name: '{voice.name}'")
            print(f"  Voice ID: {voice.voice_id}")
            print(f"  Category: {voice.category}")
            print(f"  Language: '{voice_lang}'")
            print(f"  Labels: {voice.labels}")
            print()
    
    print(f"\nFound {len(spanish_voices)} potentially Spanish voices")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc() 