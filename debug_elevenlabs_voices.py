#!/usr/bin/env python3
"""
Debug script to examine ElevenLabs voice structure and find language information
"""

import os
import sys
import json
from datetime import datetime

# Add the current directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from elevenlabs.client import ElevenLabs

def debug_elevenlabs_voices():
    """Debug ElevenLabs voice structure to find language information"""
    print("Debugging ElevenLabs voice structure...")
    
    try:
        # Initialize ElevenLabs client
        api_key = os.getenv('elevenlabs_test')
        if not api_key:
            print("No ElevenLabs API key found")
            return
            
        client = ElevenLabs(api_key=api_key)
        
        # Get all voices (both personal and shared)
        print("Getting personal voices...")
        response = client.voices.get_all()
        voice_list = response.voices
        
        print(f"Found {len(voice_list)} personal voices")
        
        # Examine the first few voices in detail
        for i, voice in enumerate(voice_list[:5]):
            print(f"\n=== VOICE {i+1}: {voice.name} ===")
            print(f"Voice ID: {voice.voice_id}")
            
            # Print all available attributes
            print("All attributes:")
            for attr in dir(voice):
                if not attr.startswith('_'):
                    try:
                        value = getattr(voice, attr)
                        if not callable(value):
                            print(f"  {attr}: {value}")
                    except:
                        print(f"  {attr}: <could not access>")
            
            # Examine labels in detail
            if hasattr(voice, 'labels') and voice.labels:
                print(f"\nLabels detail:")
                for key, value in voice.labels.items():
                    print(f"  {key}: {value}")
            else:
                print("No labels found")
            
            # Check if there are any language-related fields
            print("\nLanguage-related fields:")
            for attr in dir(voice):
                if 'lang' in attr.lower() or 'locale' in attr.lower():
                    try:
                        value = getattr(voice, attr)
                        if not callable(value):
                            print(f"  {attr}: {value}")
                    except:
                        print(f"  {attr}: <could not access>")
        
        # Also check shared voices
        print("\n" + "="*50)
        print("Getting shared voices...")
        try:
            shared_response = client.voices.get_shared(page_size=10)
            shared_voices = shared_response.voices
            
            print(f"Found {len(shared_voices)} shared voices (showing first 3)")
            
            for i, voice in enumerate(shared_voices[:3]):
                print(f"\n=== SHARED VOICE {i+1}: {voice.name} ===")
                print(f"Voice ID: {voice.voice_id}")
                
                # Print all available attributes
                print("All attributes:")
                for attr in dir(voice):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(voice, attr)
                            if not callable(value):
                                print(f"  {attr}: {value}")
                        except:
                            print(f"  {attr}: <could not access>")
                
                # Examine labels in detail
                if hasattr(voice, 'labels') and voice.labels:
                    print(f"\nLabels detail:")
                    for key, value in voice.labels.items():
                        print(f"  {key}: {value}")
                else:
                    print("No labels found")
                    
        except Exception as e:
            print(f"Could not get shared voices: {e}")
        
        # Check if there's a way to get voice details with more info
        print("\n" + "="*50)
        print("Trying to get detailed voice information...")
        
        # Try to get detailed info for the first voice
        if voice_list:
            first_voice = voice_list[0]
            print(f"Getting detailed info for: {first_voice.name}")
            
            try:
                # Try to get voice details if the method exists
                if hasattr(client.voices, 'get'):
                    detailed_voice = client.voices.get(first_voice.voice_id)
                    print("Detailed voice info:")
                    for attr in dir(detailed_voice):
                        if not attr.startswith('_'):
                            try:
                                value = getattr(detailed_voice, attr)
                                if not callable(value):
                                    print(f"  {attr}: {value}")
                            except:
                                print(f"  {attr}: <could not access>")
                else:
                    print("No get method available for detailed voice info")
                    
            except Exception as e:
                print(f"Could not get detailed voice info: {e}")
        
        # Summary of findings
        print("\n" + "="*50)
        print("SUMMARY OF LANGUAGE INFORMATION:")
        
        voices_with_lang = 0
        voices_without_lang = 0
        all_lang_fields = set()
        
        for voice in voice_list:
            has_lang = False
            
            # Check labels
            if hasattr(voice, 'labels') and voice.labels:
                for key in voice.labels.keys():
                    if 'lang' in key.lower():
                        all_lang_fields.add(f"labels.{key}")
                        if voice.labels[key]:
                            has_lang = True
            
            # Check direct attributes
            for attr in dir(voice):
                if 'lang' in attr.lower() and not attr.startswith('_'):
                    all_lang_fields.add(attr)
                    try:
                        value = getattr(voice, attr)
                        if value and not callable(value):
                            has_lang = True
                    except:
                        pass
            
            if has_lang:
                voices_with_lang += 1
            else:
                voices_without_lang += 1
        
        print(f"Voices with language info: {voices_with_lang}")
        print(f"Voices without language info: {voices_without_lang}")
        print(f"All language-related fields found: {all_lang_fields}")
        
    except Exception as e:
        print(f"Error debugging ElevenLabs voices: {e}")

if __name__ == "__main__":
    debug_elevenlabs_voices() 