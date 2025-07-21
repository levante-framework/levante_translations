#!/usr/bin/env python3
"""
Comprehensive voice export script for ElevenLabs
Searches for female voices in all supported languages using multiple strategies:
1. Personal library voices
2. Shared library search with language filters
3. Shared library search with search terms
4. Professional voices
Filters out old and advertising voices
"""

import os
import sys
import csv
import requests
from datetime import datetime
from typing import List, Dict, Any, Set

# Add the current directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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

def is_old_voice(voice_name: str, age: str = "", description: str = "") -> bool:
    """Check if a voice is marked as old or elderly"""
    old_keywords = [
        'old', 'elderly', 'senior', 'grandpa', 'grandma',
        'grandfather', 'grandmother', 'granny', 'old man', 'old woman'
    ]
    # Note: Removed 'mature' and 'aged' as they typically mean sophisticated/professional or middle-aged, not elderly
    
    # Check voice name
    name_lower = voice_name.lower()
    for keyword in old_keywords:
        if keyword in name_lower:
            return True
    
    # Check age field - be more specific about what constitutes "old"
    if age and age.lower() in ['old', 'elderly', 'senior']:
        return True
    # Note: Don't filter 'aged', 'mature', or 'middle_aged' age descriptors as they refer to middle-aged adults
    
    # Check description
    description_lower = description.lower()
    for keyword in old_keywords:
        if keyword in description_lower:
            return True
    
    return False

def get_comprehensive_elevenlabs_voices() -> List[Dict[str, Any]]:
    """Get comprehensive list of female ElevenLabs voices from all sources"""
    print("Fetching comprehensive ElevenLabs female voices...")
    
    voices = []
    seen_voice_ids = set()
    
    try:
        # Initialize ElevenLabs client
        api_key = os.getenv('elevenlabs_test')
        if not api_key:
            print("No ElevenLabs API key found")
            return voices
            
        client = ElevenLabs(api_key=api_key)
        
        # Strategy 1: Get personal library voices
        print("Strategy 1: Fetching personal library voices...")
        try:
            response = client.voices.get_all()
            voice_list = response.voices
            
            for voice in voice_list:
                if voice.voice_id in seen_voice_ids:
                    continue
                    
                labels = voice.labels if hasattr(voice, 'labels') and voice.labels else {}
                
                # Filter for female voices only
                if labels.get('gender', '').lower() != 'female':
                    continue
                
                voice_name = voice.name
                voice_type = labels.get('use_case', '')
                style = labels.get('style', '')
                age = labels.get('age', '')
                description = labels.get('description', '')
                
                # Skip advertising and old voices
                if is_advertising_voice(voice_name, voice_type, style):
                    continue
                if is_old_voice(voice_name, age, description):
                    continue
                
                voice_info = {
                    'service': 'ElevenLabs',
                    'name': voice_name,
                    'id': voice.voice_id,
                    'language': labels.get('language', ''),
                    'language_code': labels.get('language', ''),
                    'gender': labels.get('gender', ''),
                    'age': age,
                    'accent': labels.get('accent', ''),
                    'voice_type': voice_type,
                    'style': style,
                    'sample_url': voice.preview_url if hasattr(voice, 'preview_url') else '',
                    'description': description,
                    'category': voice.category if hasattr(voice, 'category') else 'personal'
                }
                
                # Auto-assign language based on accent if language is empty
                if not voice_info['language'] and not voice_info['language_code']:
                    accent = (voice_info['accent'] or '').lower()
                    if 'american' in accent or 'us' in accent or 'english' in accent:
                        voice_info['language'] = 'English'
                        voice_info['language_code'] = 'en'
                    elif 'british' in accent or 'uk' in accent:
                        voice_info['language'] = 'English (GB)'
                        voice_info['language_code'] = 'en'
                    elif 'australian' in accent:
                        voice_info['language'] = 'English (AU)'
                        voice_info['language_code'] = 'en'
                    elif 'canadian' in accent:
                        voice_info['language'] = 'English (CA)'
                        voice_info['language_code'] = 'en'
                    elif 'spanish' in accent:
                        voice_info['language'] = 'Spanish'
                        voice_info['language_code'] = 'es'
                    elif 'german' in accent:
                        voice_info['language'] = 'German'
                        voice_info['language_code'] = 'de'
                    elif 'french' in accent:
                        voice_info['language'] = 'French'
                        voice_info['language_code'] = 'fr'
                    elif 'dutch' in accent:
                        voice_info['language'] = 'Dutch'
                        voice_info['language_code'] = 'nl'
                
                voices.append(voice_info)
                seen_voice_ids.add(voice.voice_id)
                
            print(f"Found {len(voices)} female voices from personal library")
            
        except Exception as e:
            print(f"Error getting personal voices: {e}")
        
        # Strategy 2: Search shared library by language
        print("Strategy 2: Searching shared library by language...")
        languages_to_search = ['en', 'es', 'de', 'fr', 'nl', 'it', 'pt', 'pl', 'hi', 'ar', 'zh', 'ja', 'ko']
        
        for lang in languages_to_search:
            try:
                print(f"  Searching for {lang} voices...")
                shared_response = client.voices.get_shared(
                    page_size=100,
                    language=lang,
                    gender='female'
                )
                shared_voices = shared_response.voices
                
                lang_count = 0
                for voice in shared_voices:
                    if voice.voice_id in seen_voice_ids:
                        continue
                        
                    labels = voice.labels if hasattr(voice, 'labels') and voice.labels else {}
                    
                    # Filter for female voices only
                    if labels.get('gender', '').lower() != 'female':
                        continue
                    
                    voice_name = voice.name
                    voice_type = labels.get('use_case', '')
                    style = labels.get('style', '')
                    age = labels.get('age', '')
                    description = labels.get('description', '')
                    
                    # Skip advertising and old voices
                    if is_advertising_voice(voice_name, voice_type, style):
                        continue
                    if is_old_voice(voice_name, age, description):
                        continue
                    
                    voice_info = {
                        'service': 'ElevenLabs',
                        'name': voice_name,
                        'id': voice.voice_id,
                        'language': labels.get('language', ''),
                        'language_code': labels.get('language', ''),
                        'gender': labels.get('gender', ''),
                        'age': age,
                        'accent': labels.get('accent', ''),
                        'voice_type': voice_type,
                        'style': style,
                        'sample_url': voice.preview_url if hasattr(voice, 'preview_url') else '',
                        'description': description,
                        'category': 'shared'
                    }
                    
                    # Auto-assign language based on accent if language is empty
                    if not voice_info['language'] and not voice_info['language_code']:
                        accent = (voice_info['accent'] or '').lower()
                        if 'american' in accent or 'us' in accent or 'english' in accent:
                            voice_info['language'] = 'English'
                            voice_info['language_code'] = 'en'
                        elif 'british' in accent or 'uk' in accent:
                            voice_info['language'] = 'English (GB)'
                            voice_info['language_code'] = 'en'
                        elif 'australian' in accent:
                            voice_info['language'] = 'English (AU)'
                            voice_info['language_code'] = 'en'
                        elif 'canadian' in accent:
                            voice_info['language'] = 'English (CA)'
                            voice_info['language_code'] = 'en'
                        elif 'spanish' in accent:
                            voice_info['language'] = 'Spanish'
                            voice_info['language_code'] = 'es'
                        elif 'german' in accent:
                            voice_info['language'] = 'German'
                            voice_info['language_code'] = 'de'
                        elif 'french' in accent:
                            voice_info['language'] = 'French'
                            voice_info['language_code'] = 'fr'
                        elif 'dutch' in accent:
                            voice_info['language'] = 'Dutch'
                            voice_info['language_code'] = 'nl'
                
                    voices.append(voice_info)
                    seen_voice_ids.add(voice.voice_id)
                    lang_count += 1
                    
                print(f"    Found {lang_count} new female voices for {lang}")
                
            except Exception as e:
                print(f"    Error searching {lang} voices: {e}")
        
        # Strategy 3: Search by language names and terms
        print("Strategy 3: Searching by language names and terms...")
        search_terms = [
            'dutch', 'spanish', 'french', 'german', 'english', 'italian', 
            'portuguese', 'polish', 'multilingual', 'conversational', 'narrative'
        ]
        
        for term in search_terms:
            try:
                print(f"  Searching for '{term}' voices...")
                
                # For Dutch, Spanish, and French, search without gender filter since they might have missing metadata
                if term in ['dutch', 'spanish', 'french']:
                    search_response = client.voices.get_shared(
                        page_size=100,
                        search=term
                    )
                else:
                    search_response = client.voices.get_shared(
                        page_size=100,
                        search=term,
                        gender='female'
                    )
                search_voices = search_response.voices
                
                term_count = 0
                for voice in search_voices:
                    if voice.voice_id in seen_voice_ids:
                        continue
                        
                    labels = voice.labels if hasattr(voice, 'labels') and voice.labels else {}
                    
                    # Special handling for Dutch, Spanish, and French voices
                    if term in ['dutch', 'spanish', 'french']:
                        voice_name = voice.name.lower()
                        voice_desc = labels.get('description', '').lower()
                        voice_accent = labels.get('accent', '').lower()
                        
                        # Check if this is likely a voice for the target language
                        if term == 'dutch':
                            is_target_lang = (
                                'dutch' in voice_name or 'dutch' in voice_desc or 'dutch' in voice_accent or
                                'netherlands' in voice_name or 'netherlands' in voice_desc or 'netherlands' in voice_accent or
                                'holland' in voice_name or 'holland' in voice_desc or 'holland' in voice_accent
                            )
                            target_lang_code = 'nl'
                        elif term == 'spanish':
                            is_target_lang = (
                                'spanish' in voice_name or 'spanish' in voice_desc or 'spanish' in voice_accent or
                                'español' in voice_name or 'español' in voice_desc or 'español' in voice_accent or
                                'mexico' in voice_name or 'mexico' in voice_desc or 'mexico' in voice_accent or
                                'argentina' in voice_name or 'argentina' in voice_desc or 'argentina' in voice_accent or
                                'colombia' in voice_name or 'colombia' in voice_desc or 'colombia' in voice_accent or
                                'spain' in voice_name or 'spain' in voice_desc or 'spain' in voice_accent
                            )
                            target_lang_code = 'es'
                        elif term == 'french':
                            is_target_lang = (
                                'french' in voice_name or 'french' in voice_desc or 'french' in voice_accent or
                                'français' in voice_name or 'français' in voice_desc or 'français' in voice_accent or
                                'france' in voice_name or 'france' in voice_desc or 'france' in voice_accent or
                                'quebec' in voice_name or 'quebec' in voice_desc or 'quebec' in voice_accent or
                                'canada' in voice_name or 'canada' in voice_desc or 'canada' in voice_accent or
                                'belgian' in voice_name or 'belgian' in voice_desc or 'belgian' in voice_accent
                            )
                            target_lang_code = 'fr'
                        
                        if not is_target_lang:
                            continue
                            
                        # Identify female voices by name/description
                        is_female = (
                            'female' in voice_name or 'female' in voice_desc or
                            'woman' in voice_name or 'woman' in voice_desc or
                            'girl' in voice_name or 'girl' in voice_desc or
                            'mademoiselle' in voice_name or 'mademoiselle' in voice_desc or
                            # Common female names for each language
                            any(name in voice_name for name in [
                                # Dutch female names
                                'emma', 'ruth', 'maria', 'anna', 'lisa', 'sarah', 'sophie', 'eva',
                                # Spanish female names
                                'carmen', 'lucia', 'ana', 'elena', 'sofia', 'isabel', 'patricia', 'alejandra',
                                'carmen', 'dolores', 'pilar', 'rosa', 'teresa', 'mercedes', 'cristina',
                                # French female names
                                'marie', 'claire', 'camille', 'julie', 'charlotte', 'aurelie', 'celine',
                                'caroline', 'chloé', 'brigitte', 'sylvie', 'nathalie', 'isabelle', 'martine'
                            ])
                        )
                        
                        # Skip male voices (identified by name/description) - be more comprehensive
                        male_indicators = [
                            'male', 'man', 'boy', 'guy', 'monsieur', 'señor', 'mister', 'mr.',
                            # Dutch male names
                            'james', 'koen', 'arjen', 'rick', 'gerard', 'milan', 'victor', 'jaimie',
                            # Spanish male names
                            'carlos', 'miguel', 'antonio', 'jose', 'luis', 'francisco', 'pablo', 'diego',
                            'alejandro', 'fernando', 'rafael', 'manuel', 'jaider', 'molete',
                            # French male names
                            'pierre', 'jean', 'michel', 'philippe', 'antoine', 'nicolas', 'laurent', 'david',
                            'charles', 'clément', 'fabien', 'marcel', 'kev', 'olly', 'steven', 'teddy'
                        ]
                        
                        is_male = any(indicator in voice_name or indicator in voice_desc for indicator in male_indicators)
                        
                        # Only include if clearly female or if ambiguous but not clearly male
                        if is_male or (not is_female and not is_male):
                            # If it's clearly male, skip it
                            # If it's neither clearly male nor female, also skip to be safe
                            continue
                    else:
                        # For non-target language voices, filter for female voices as before
                        if labels.get('gender', '').lower() != 'female':
                            continue
                        target_lang_code = labels.get('language', '')
                    
                    voice_name = voice.name
                    voice_type = labels.get('use_case', '')
                    style = labels.get('style', '')
                    age = labels.get('age', '')
                    description = labels.get('description', '')
                    
                    # Skip advertising and old voices
                    if is_advertising_voice(voice_name, voice_type, style):
                        continue
                    if is_old_voice(voice_name, age, description):
                        continue
                    
                    # For target language voices, set language code if not already set
                    language = labels.get('language', '')
                    if term in ['dutch', 'spanish', 'french'] and not language:
                        language = target_lang_code
                    
                    voice_info = {
                        'service': 'ElevenLabs',
                        'name': voice_name,
                        'id': voice.voice_id,
                        'language': language,
                        'language_code': language,
                        'gender': labels.get('gender', '') or ('female' if term in ['dutch', 'spanish', 'french'] else ''),
                        'age': age,
                        'accent': labels.get('accent', ''),
                        'voice_type': voice_type,
                        'style': style,
                        'sample_url': voice.preview_url if hasattr(voice, 'preview_url') else '',
                        'description': description,
                        'category': 'shared'
                    }
                    voices.append(voice_info)
                    seen_voice_ids.add(voice.voice_id)
                    term_count += 1
                    
                print(f"    Found {term_count} new female voices for '{term}'")
                
            except Exception as e:
                print(f"    Error searching '{term}' voices: {e}")
        
        # Strategy 4: Get professional voices without language filter
        print("Strategy 4: Searching professional voices...")
        try:
            prof_response = client.voices.get_shared(
                page_size=100,
                category='professional',
                gender='female'
            )
            prof_voices = prof_response.voices
            
            prof_count = 0
            for voice in prof_voices:
                if voice.voice_id in seen_voice_ids:
                    continue
                    
                labels = voice.labels if hasattr(voice, 'labels') and voice.labels else {}
                
                # Filter for female voices only
                if labels.get('gender', '').lower() != 'female':
                    continue
                
                voice_name = voice.name
                voice_type = labels.get('use_case', '')
                style = labels.get('style', '')
                age = labels.get('age', '')
                description = labels.get('description', '')
                
                # Skip advertising and old voices
                if is_advertising_voice(voice_name, voice_type, style):
                    continue
                if is_old_voice(voice_name, age, description):
                    continue
                
                voice_info = {
                    'service': 'ElevenLabs',
                    'name': voice_name,
                    'id': voice.voice_id,
                    'language': labels.get('language', ''),
                    'language_code': labels.get('language', ''),
                    'gender': labels.get('gender', ''),
                    'age': age,
                    'accent': labels.get('accent', ''),
                    'voice_type': voice_type,
                    'style': style,
                    'sample_url': voice.preview_url if hasattr(voice, 'preview_url') else '',
                    'description': description,
                    'category': 'professional'
                }
                voices.append(voice_info)
                seen_voice_ids.add(voice.voice_id)
                prof_count += 1
                
            print(f"Found {prof_count} new professional female voices")
            
        except Exception as e:
            print(f"Error searching professional voices: {e}")
            
    except Exception as e:
        print(f"Error initializing ElevenLabs client: {e}")
    
    print(f"Total unique female voices found: {len(voices)}")
    return voices

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
                age = voice.get('age', '')
                description = voice.get('description', '')
                
                # Skip advertising and old voices
                if is_advertising_voice(voice_name, voice_type, style):
                    continue
                if is_old_voice(voice_name, age, description):
                    continue
                
                voice_info = {
                    'service': 'PlayHT',
                    'name': voice_name,
                    'id': voice.get('id', voice.get('value', '')),
                    'language': voice.get('language', ''),
                    'language_code': voice.get('languageCode', ''),
                    'gender': voice.get('gender', ''),
                    'age': age,
                    'accent': voice.get('accent', ''),
                    'voice_type': voice_type,
                    'style': style,
                    'sample_url': voice.get('sample', ''),
                    'description': description,
                    'category': 'PlayHT'
                }
                voices.append(voice_info)
                
            print(f"Found {len(voices)} female PlayHT voices (excluding advertising/old)")
            
        else:
            print(f"Error fetching PlayHT voices: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Error getting PlayHT voices: {e}")
    
    return voices

def export_voices_to_csv(voices: List[Dict[str, Any]], filename: str = "comprehensive_voices.csv"):
    """Export voices to CSV file"""
    if not voices:
        print("No voices to export")
        return
        
    print(f"Exporting {len(voices)} voices to {filename}...")
    
    # Define CSV columns
    fieldnames = [
        'service', 'name', 'id', 'language', 'language_code', 'gender', 
        'age', 'accent', 'voice_type', 'style', 'sample_url', 'description', 'category'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for voice in voices:
            writer.writerow(voice)
    
    print(f"Successfully exported to {filename}")

def main():
    """Main function to export comprehensive female voices"""
    print("Starting comprehensive female voice export process...")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Filtering for: Female voices only, excluding advertising and old voices")
    
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
    
    # Get comprehensive ElevenLabs female voices
    elevenlabs_voices = get_comprehensive_elevenlabs_voices()
    all_voices.extend(elevenlabs_voices)
    
    # Sort voices by service, then by language, then by name
    all_voices.sort(key=lambda x: (x['service'], x['language'] or 'zzz', x['name']))
    
    # Export to CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"comprehensive_female_voices_{timestamp}.csv"
    export_voices_to_csv(all_voices, filename)
    
    # Print summary
    print(f"\n=== COMPREHENSIVE FEMALE VOICES SUMMARY ===")
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
        print(f"  {lang}: {count} voices")
    
    # Count by category
    category_counts = {}
    for voice in all_voices:
        category = voice['category'] or 'Unknown'
        category_counts[category] = category_counts.get(category, 0) + 1
    
    print(f"\nCategories:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category}: {count} voices")
    
    print(f"\nExport completed successfully!")
    print(f"File saved as: {filename}")

if __name__ == "__main__":
    main() 