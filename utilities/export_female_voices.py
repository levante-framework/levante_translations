#!/usr/bin/env python3
"""
Export only female voices (excluding advertising voices) from PlayHT and ElevenLabs to CSV
Gets voice name, service, language, gender, and other metadata
"""

import os
import sys
import csv
import requests
from datetime import datetime
from typing import List, Dict, Any

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ELabs import elevenlabs_utilities
from elevenlabs.client import ElevenLabs

def is_advertising_voice(voice_name: str, voice_type: str = "", style: str = "") -> bool:
    """Check if a voice is advertising-related"""
    advertising_keywords = [
        'advertising', 'commercial', 'promo', 'marketing', 'sales', 'ad ',
        'promotional', 'business', 'corporate', 'brand'
    ]
    
    # Check voice name
    name_lower = voice_name.lower()
    for keyword in advertising_keywords:
        if keyword in name_lower:
            return True
    
    # Check voice type and style
    type_style_lower = f"{voice_type} {style}".lower()
    for keyword in advertising_keywords:
        if keyword in type_style_lower:
            return True
    
    return False

def get_playht_voices() -> List[Dict[str, Any]]:
    """Get all female PlayHT voices (excluding advertising voices) with metadata"""
    print("Fetching PlayHT female voices...")
    
    voices = []
    
    try:
        # PlayHT API v2 endpoint
        url = "https://api.play.ht/api/v2/voices"
        headers = {
            "AUTHORIZATION": os.environ.get("PLAY_DOT_HT_API_KEY"),
            "X-USER-ID": os.environ.get("PLAY_DOT_HT_USER_ID"),
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            voices_data = response.json()
            
            for voice in voices_data:
                # Filter for female voices only
                if voice.get('gender', '').lower() != 'female':
                    continue
                
                voice_name = voice.get('name', '')
                voice_type = voice.get('voiceType', '')
                style = voice.get('style', '')
                
                # Skip advertising voices
                if is_advertising_voice(voice_name, voice_type, style):
                    continue
                
                voice_info = {
                    'service': 'PlayHT',
                    'name': voice_name,
                    'id': voice.get('id', voice.get('value', '')),
                    'language': voice.get('language', ''),
                    'language_code': voice.get('languageCode', ''),
                    'gender': voice.get('gender', ''),
                    'age': voice.get('age', ''),
                    'accent': voice.get('accent', ''),
                    'voice_type': voice_type,
                    'style': style,
                    'sample_url': voice.get('sample', ''),
                    'description': voice.get('description', ''),
                    'category': 'PlayHT'
                }
                voices.append(voice_info)
                
            print(f"Found {len(voices)} female PlayHT voices (excluding advertising)")
            
        else:
            print(f"Error fetching PlayHT voices: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Error getting PlayHT voices: {e}")
    
    return voices

def get_elevenlabs_voices() -> List[Dict[str, Any]]:
    """Get all female ElevenLabs voices (excluding advertising voices) with metadata"""
    print("Fetching ElevenLabs female voices...")
    
    voices = []
    
    try:
        # Initialize ElevenLabs client
        api_key = os.getenv('elevenlabs_test')
        if not api_key:
            print("No ElevenLabs API key found")
            return voices
            
        client = ElevenLabs(api_key=api_key)
        
        # Get all voices (both personal and shared)
        response = client.voices.get_all()
        voice_list = response.voices
        
        for voice in voice_list:
            # Get labels safely
            labels = voice.labels if hasattr(voice, 'labels') and voice.labels else {}
            
            # Filter for female voices only
            if labels.get('gender', '').lower() != 'female':
                continue
            
            voice_name = voice.name
            voice_type = labels.get('use_case', '')
            style = labels.get('style', '')
            
            # Skip advertising voices
            if is_advertising_voice(voice_name, voice_type, style):
                continue
            
            voice_info = {
                'service': 'ElevenLabs',
                'name': voice_name,
                'id': voice.voice_id,
                'language': labels.get('language', ''),
                'language_code': labels.get('language', ''),
                'gender': labels.get('gender', ''),
                'age': labels.get('age', ''),
                'accent': labels.get('accent', ''),
                'voice_type': voice_type,
                'style': style,
                'sample_url': voice.preview_url if hasattr(voice, 'preview_url') else '',
                'description': labels.get('description', ''),
                'category': voice.category if hasattr(voice, 'category') else 'personal'
            }
            voices.append(voice_info)
            
        print(f"Found {len(voices)} female ElevenLabs voices from personal library")
        
        # Also try to get shared voices for more comprehensive data
        try:
            shared_response = client.voices.get_shared(page_size=100)
            shared_voices = shared_response.voices
            
            shared_count = 0
            for voice in shared_voices:
                labels = voice.labels if hasattr(voice, 'labels') and voice.labels else {}
                
                # Filter for female voices only
                if labels.get('gender', '').lower() != 'female':
                    continue
                
                voice_name = voice.name
                voice_type = labels.get('use_case', '')
                style = labels.get('style', '')
                
                # Skip advertising voices
                if is_advertising_voice(voice_name, voice_type, style):
                    continue
                
                voice_info = {
                    'service': 'ElevenLabs',
                    'name': voice_name,
                    'id': voice.voice_id,
                    'language': labels.get('language', ''),
                    'language_code': labels.get('language', ''),
                    'gender': labels.get('gender', ''),
                    'age': labels.get('age', ''),
                    'accent': labels.get('accent', ''),
                    'voice_type': voice_type,
                    'style': style,
                    'sample_url': voice.preview_url if hasattr(voice, 'preview_url') else '',
                    'description': labels.get('description', ''),
                    'category': 'shared'
                }
                voices.append(voice_info)
                shared_count += 1
                
            print(f"Found {shared_count} additional female ElevenLabs voices from shared library")
            
        except Exception as e:
            print(f"Note: Could not fetch shared voices: {e}")
            
    except Exception as e:
        print(f"Error getting ElevenLabs voices: {e}")
    
    return voices

def export_voices_to_csv(voices: List[Dict[str, Any]], filename: str = "female_voices.csv"):
    """Export voices to CSV file"""
    print(f"Exporting {len(voices)} female voices to {filename}...")
    
    if not voices:
        print("No voices to export")
        return
    
    # Define CSV columns
    fieldnames = [
        'service',
        'name', 
        'id',
        'language',
        'language_code',
        'gender',
        'age',
        'accent',
        'voice_type',
        'style',
        'sample_url',
        'description',
        'category'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Write header
        writer.writeheader()
        
        # Write voice data
        for voice in voices:
            writer.writerow(voice)
    
    print(f"Successfully exported female voices to {filename}")

def main():
    """Main function to export female voices only"""
    print("Starting female voice export process...")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Filtering for: Female voices only, excluding advertising voices")
    
    # Check for required environment variables
    if not os.environ.get("PLAY_DOT_HT_API_KEY"):
        print("Warning: PLAY_DOT_HT_API_KEY not found - PlayHT voices will be skipped")
    
    if not os.environ.get("elevenlabs_test"):
        print("Warning: elevenlabs_test API key not found - ElevenLabs voices will be skipped")
    
    # Collect all female voices
    all_voices = []
    
    # Get PlayHT female voices
    playht_voices = get_playht_voices()
    all_voices.extend(playht_voices)
    
    # Get ElevenLabs female voices
    elevenlabs_voices = get_elevenlabs_voices()
    all_voices.extend(elevenlabs_voices)
    
    # Sort voices by service, then by name
    all_voices.sort(key=lambda x: (x['service'], x['name']))
    
    # Export to CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"female_voices_{timestamp}.csv"
    export_voices_to_csv(all_voices, filename)
    
    # Print summary
    print(f"\n=== FEMALE VOICES SUMMARY ===")
    print(f"Total female voices exported: {len(all_voices)}")
    
    # Count by service
    service_counts = {}
    for voice in all_voices:
        service = voice['service']
        service_counts[service] = service_counts.get(service, 0) + 1
    
    for service, count in service_counts.items():
        print(f"{service}: {count} female voices")
    
    # Count by language
    language_counts = {}
    for voice in all_voices:
        lang = voice['language'] or 'Unknown'
        language_counts[lang] = language_counts.get(lang, 0) + 1
    
    print(f"\nLanguages found: {len(language_counts)}")
    for lang, count in sorted(language_counts.items()):
        print(f"  {lang}: {count} female voices")
    
    # Count by voice type
    type_counts = {}
    for voice in all_voices:
        voice_type = voice['voice_type'] or 'Unknown'
        type_counts[voice_type] = type_counts.get(voice_type, 0) + 1
    
    print(f"\nVoice types:")
    for voice_type, count in sorted(type_counts.items()):
        print(f"  {voice_type}: {count} voices")
    
    # Count by age
    age_counts = {}
    for voice in all_voices:
        age = voice['age'] or 'Unknown'
        age_counts[age] = age_counts.get(age, 0) + 1
    
    print(f"\nAge distribution:")
    for age, count in sorted(age_counts.items()):
        print(f"  {age}: {count} voices")
    
    print(f"\nFemale voices exported to: {filename}")

if __name__ == "__main__":
    main() 