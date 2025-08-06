#!/usr/bin/env python3
"""
Automatically detect new languages in CSV files and update configuration.
This script will:
1. Detect new language columns
2. Automatically update utilities/config.py
3. Automatically update package.json
4. Provide voice recommendations
"""

import sys
import os
import json
import re
from pathlib import Path

def load_csv_headers(file_path):
    """Load CSV headers from file or URL"""
    import csv
    
    # Try remote file first
    if file_path.startswith('http'):
        import urllib.request
        try:
            with urllib.request.urlopen(file_path) as response:
                content = response.read().decode('utf-8')
                first_line = content.split('\n')[0]
                return first_line.split(',')
        except Exception as e:
            print(f"Failed to fetch remote file: {e}")
            return []
    
    # Try local file
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                return next(reader, [])
        except Exception as e:
            print(f"Failed to read local file: {e}")
            return []
    
    return []

def detect_new_languages():
    """Detect new language columns from multiple sources"""
    sources = [
        "translation_text/item_bank_translations.csv",
        "https://raw.githubusercontent.com/levante-framework/levante_translations/l10n_pending/item-bank-translations.csv"
    ]
    
    all_columns = set()
    
    for source in sources:
        print(f"Checking: {source}")
        headers = load_csv_headers(source)
        if headers:
            print(f"  Found columns: {headers}")
            all_columns.update(headers)
    
    # Known system columns
    system_columns = {
        'item_id', 'identifier', 'labels', 'task', 'voice', 'service',
        'created', 'modified', 'status', 'notes', 'audio_path', 'file_path', 'context'
    }
    
    # Get current configured languages
    current_langs = get_current_languages()
    
    # Find new language columns
    new_languages = []
    for col in all_columns:
        if (col not in system_columns and 
            col not in current_langs and
            len(col) >= 2 and len(col) <= 5 and
            any(c.isalpha() for c in col)):
            new_languages.append(col)
    
    return new_languages

def get_current_languages():
    """Get currently configured language codes"""
    try:
        # Read current config
        config_path = Path(__file__).parent / 'config.py'
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Extract language codes from LANGUAGE_CODES
        import re
        pattern = r"'([^']+)':\s*'([^']+)'"
        matches = re.findall(pattern, content)
        
        current_codes = set()
        for name, code in matches:
            current_codes.add(code)
        
        return current_codes
    except Exception as e:
        print(f"Error reading current config: {e}")
        return {'en', 'es-CO', 'de', 'fr-CA', 'nl'}  # fallback

def suggest_language_name(lang_code):
    """Suggest human-readable name for language code"""
    mappings = {
        'de-CH': 'German (Switzerland)',
        'de-AT': 'German (Austria)',
        'en-US': 'English (US)',
        'en-GB': 'English (UK)',
        'fr-FR': 'French (France)',
        'fr-CA': 'French (Canada)',
        'es-ES': 'Spanish (Spain)',
        'es-MX': 'Spanish (Mexico)',
        'es-CO': 'Spanish (Colombia)',
        'pt-BR': 'Portuguese (Brazil)',
        'pt-PT': 'Portuguese (Portugal)',
        'it': 'Italian',
        'zh': 'Chinese',
        'zh-CN': 'Chinese (Simplified)',
        'zh-TW': 'Chinese (Traditional)',
        'ja': 'Japanese',
        'ko': 'Korean',
        'ru': 'Russian',
        'ar': 'Arabic',
        'hi': 'Hindi'
    }
    
    return mappings.get(lang_code.lower(), f"Language_{lang_code}")

def suggest_voice(lang_code, lang_name):
    """Suggest appropriate ElevenLabs voice for the language"""
    voice_suggestions = {
        'de-CH': 'Julia',  # Same as German
        'de-AT': 'Julia',  # Same as German
        'en-US': 'Clara - Children\'s Storyteller',
        'en-GB': 'Clara - Children\'s Storyteller',
        'fr-FR': 'Caroline - Top France - Narrative, warm, sweet',
        'es-ES': 'Malena Tango',
        'es-MX': 'Malena Tango',
        'pt-BR': 'TBD - Need Portuguese voice',
        'pt-PT': 'TBD - Need Portuguese voice',
        'it': 'TBD - Need Italian voice',
        'zh': 'TBD - Need Chinese voice',
        'ja': 'TBD - Need Japanese voice',
        'ko': 'TBD - Need Korean voice'
    }
    
    return voice_suggestions.get(lang_code.lower(), 'TBD - Need to find appropriate voice')

def update_config_file(new_languages):
    """Update utilities/config.py with new languages"""
    config_path = Path(__file__).parent / 'config.py'
    
    with open(config_path, 'r') as f:
        content = f.read()
    
    # Update LANGUAGE_CODES
    for lang_code in new_languages:
        lang_name = suggest_language_name(lang_code)
        
        # Add to LANGUAGE_CODES dict
        pattern = r"(LANGUAGE_CODES = \{[^}]+)"
        replacement = f"\\1  '{lang_name}': '{lang_code}',  # AUTO-ADDED\n"
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        # Add to get_languages() function
        voice = suggest_voice(lang_code, lang_name)
        pattern = r"(language_list = \{\\[^}]+)"
        replacement = f"\\1        '{lang_name}': {{'lang_code': '{lang_code}', 'service': 'ElevenLabs', 'voice': '{voice}'}},  # AUTO-ADDED\n"
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Write back to file
    with open(config_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Updated {config_path}")

def update_package_json(new_languages):
    """Update package.json with new npm scripts"""
    package_path = Path(__file__).parent.parent / 'package.json'
    
    with open(package_path, 'r') as f:
        package_data = json.load(f)
    
    # Add new scripts
    for lang_code in new_languages:
        lang_name = suggest_language_name(lang_code)
        voice = suggest_voice(lang_code, lang_name)
        
        # Create script name (safe for npm)
        script_name = lang_code.lower().replace('(', '').replace(')', '').replace(' ', '-')
        script_command = f'python3 generate_speech.py "{lang_name}" "{voice}"'
        
        package_data['scripts'][f'generate:{script_name}'] = script_command
    
    # Write back to file
    with open(package_path, 'w') as f:
        json.dump(package_data, f, indent=2)
    
    print(f"✅ Updated {package_path}")

def main():
    print("🔍 AUTO-DETECTING AND CONFIGURING NEW LANGUAGES")
    print("=" * 60)
    
    # Detect new languages
    new_languages = detect_new_languages()
    
    if not new_languages:
        print("✅ No new languages detected")
        return 0
    
    print(f"🆕 Found {len(new_languages)} new language(s): {new_languages}")
    
    # Auto-update configuration
    print("\n🔧 Auto-updating configuration files...")
    
    try:
        update_config_file(new_languages)
        update_package_json(new_languages)
        
        print("\n🎉 SUCCESS! New languages configured automatically:")
        for lang_code in new_languages:
            lang_name = suggest_language_name(lang_code)
            voice = suggest_voice(lang_code, lang_name)
            script_name = lang_code.lower().replace('(', '').replace(')', '').replace(' ', '-')
            
            print(f"  • {lang_name} ({lang_code})")
            print(f"    Voice: {voice}")
            print(f"    Script: npm run generate:{script_name}")
            print()
        
        print("🎯 Next steps:")
        print("1. Review the auto-generated voice assignments")
        print("2. Update voices if needed using ElevenLabs voice export")
        print("3. Test generation: npm run generate:<language>")
        print("4. Deploy updated translations")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error updating configuration: {e}")
        return 1

if __name__ == "__main__":
    exit(main()) 