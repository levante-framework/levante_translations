#!/usr/bin/env python3
"""
Automatically detect new language columns in item_bank_translations.csv
and suggest configuration updates for audio generation.
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to path to import config
sys.path.append(str(Path(__file__).parent.parent))

# Import config directly to avoid pandas dependency in utilities module
config_path = Path(__file__).parent / 'config.py'
spec = None
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("config", config_path)
    conf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conf)
except Exception as e:
    print(f"Could not import config: {e}")
    # Fallback to basic config
    class BasicConfig:
        item_bank_translations = "translation_text/item_bank_translations.csv"
        LANGUAGE_CODES = {'English': 'en', 'Spanish': 'es-CO', 'German': 'de', 'French': 'fr-CA', 'Dutch': 'nl'}
        def get_languages(self):
            return {
                'English': {'lang_code':'en', 'service' : 'ElevenLabs', 'voice': 'Clara - Children\'s Storyteller'},
                'Spanish': {'lang_code': 'es-CO', 'service' : 'ElevenLabs', 'voice': 'Malena Tango'},
                'German': {'lang_code': 'de', 'service' : 'ElevenLabs', 'voice': 'Julia'},
                'French': {'lang_code': 'fr-CA', 'service' : 'ElevenLabs', 'voice': 'Caroline - Top France - Narrative, warm, sweet'},
                'Dutch': {'lang_code': 'nl', 'service' : 'ElevenLabs', 'voice' : 'Emma - Natural conversations in Dutch'},
            }
    conf = BasicConfig()

def load_translation_data():
    """Load the translation data using simple CSV parsing"""
    try:
        import csv
        
        # Try remote file first (to get latest version)
        import urllib.request
        try:
            remote_url = "https://raw.githubusercontent.com/levante-framework/levante_translations/l10n_pending/item-bank-translations.csv"
            print(f"Trying to fetch from: {remote_url}")
            
            with urllib.request.urlopen(remote_url) as response:
                content = response.read().decode('utf-8')
                
            # Parse the CSV content
            data_list = []
            lines = content.strip().split('\n')
            if lines:
                headers = lines[0].split(',')
                for line in lines[1:]:
                    if line.strip():
                        values = line.split(',')
                        # Pad with empty strings if not enough values
                        while len(values) < len(headers):
                            values.append('')
                        row = dict(zip(headers, values))
                        data_list.append(row)
                        
            print(f"✅ Loaded {len(data_list)} translation items from remote file")
            return data_list
            
        except Exception as remote_error:
            print(f"Remote fetch failed: {remote_error}")
            print("Falling back to local file...")
            
            # Fall back to local file
            local_file = "translation_text/item_bank_translations.csv"
            if not os.path.exists(local_file):
                print(f"❌ File not found: {local_file}")
                return None
                
            data_list = []
            with open(local_file, 'r', encoding='utf-8') as file:
                # Use csv.DictReader for simple parsing
                reader = csv.DictReader(file)
                for row in reader:
                    data_list.append(row)
                
        print(f"✅ Loaded {len(data_list)} translation items from {local_file}")
        return data_list
    except Exception as e:
        print(f"❌ Failed to load translation data: {e}")
        return None

def detect_language_columns(data_list):
    """Detect potential language columns in the data"""
    if not data_list:
        return []
        
    # Get columns from first row (header)
    columns = list(data_list[0].keys()) if data_list else []
    
    # Known system columns that are NOT languages
    system_columns = {
        'item_id', 'identifier', 'labels', 'task', 'voice', 'service',
        'created', 'modified', 'status', 'notes', 'audio_path', 'file_path'
    }
    
    # Get current configured language codes
    current_lang_codes = set()
    for lang_name, lang_info in conf.get_languages().items():
        current_lang_codes.add(lang_info['lang_code'])
    
    # Also check the LANGUAGE_CODES mapping
    current_lang_codes.update(conf.LANGUAGE_CODES.values())
    
    # Detect potential language columns
    potential_lang_columns = []
    for col in columns:
        col_lower = col.lower().strip()
        
        # Skip system columns
        if col_lower in system_columns:
            continue
            
        # Skip if already configured
        if col in current_lang_codes or col_lower in current_lang_codes:
            print(f"✅ Already configured: {col}")
            continue
            
        # Check if it looks like a language code (2-5 chars, contains letters)
        if 2 <= len(col) <= 5 and any(c.isalpha() for c in col):
            # Check if column has actual translation data
            non_empty_count = 0
            sample_text = ''
            
            for row in data_list:
                if col in row and row[col] and str(row[col]).strip():
                    non_empty_count += 1
                    if not sample_text and str(row[col]).strip():
                        sample_text = str(row[col]).strip()
            
            total = len(data_list)
            fill_rate = non_empty_count / total if total > 0 else 0
            
            if fill_rate > 0.1:  # At least 10% filled
                potential_lang_columns.append({
                    'column': col,
                    'fill_rate': fill_rate,
                    'sample_text': sample_text,
                    'total_entries': non_empty_count
                })
    
    return potential_lang_columns

def suggest_language_mapping(lang_columns):
    """Suggest language mappings based on column names"""
    # Common language code mappings
    language_mappings = {
        'it': 'Italian',
        'pt': 'Portuguese', 
        'pt-br': 'Portuguese (Brazil)',
        'zh': 'Chinese',
        'zh-cn': 'Chinese (Simplified)',
        'zh-tw': 'Chinese (Traditional)',
        'ja': 'Japanese',
        'ko': 'Korean',
        'ru': 'Russian',
        'ar': 'Arabic',
        'hi': 'Hindi',
        'tr': 'Turkish',
        'pl': 'Polish',
        'sv': 'Swedish',
        'no': 'Norwegian',
        'da': 'Danish',
        'fi': 'Finnish',
        'he': 'Hebrew',
        'th': 'Thai',
        'vi': 'Vietnamese',
        'uk': 'Ukrainian',
        'cs': 'Czech',
        'hu': 'Hungarian',
        'ro': 'Romanian',
        'bg': 'Bulgarian',
        'hr': 'Croatian',
        'sk': 'Slovak',
        'sl': 'Slovenian',
        'et': 'Estonian',
        'lv': 'Latvian',
        'lt': 'Lithuanian',
        'mt': 'Maltese',
        'ga': 'Irish',
        'cy': 'Welsh',
        'is': 'Icelandic',
        'mk': 'Macedonian',
        'sq': 'Albanian',
        'sr': 'Serbian',
        'bs': 'Bosnian',
        'me': 'Montenegrin'
    }
    
    suggestions = []
    for lang_col in lang_columns:
        col_name = lang_col['column'].lower()
        suggested_name = language_mappings.get(col_name, f"Language_{lang_col['column']}")
        
        suggestions.append({
            'column': lang_col['column'],
            'suggested_name': suggested_name,
            'lang_code': lang_col['column'],
            'fill_rate': lang_col['fill_rate'],
            'total_entries': lang_col['total_entries'],
            'sample_text': lang_col['sample_text'][:100] + '...' if len(lang_col['sample_text']) > 100 else lang_col['sample_text']
        })
    
    return suggestions

def generate_config_updates(suggestions):
    """Generate the code needed to add new languages to config.py"""
    if not suggestions:
        return None
        
    print("\n" + "="*80)
    print("🔧 CONFIGURATION UPDATES NEEDED")
    print("="*80)
    
    # Generate LANGUAGE_CODES updates
    print("\n📝 Add to LANGUAGE_CODES in utilities/config.py:")
    print("```python")
    print("LANGUAGE_CODES = {")
    print("  'English': 'en',")
    print("  'Spanish': 'es-CO',")
    print("  'German': 'de',")
    print("  'French': 'fr-CA',")
    print("  'Dutch': 'nl',")
    for suggestion in suggestions:
        print(f"  '{suggestion['suggested_name']}': '{suggestion['lang_code']}',  # NEW")
    print("}")
    print("```")
    
    # Generate get_languages() updates
    print("\n📝 Add to get_languages() function in utilities/config.py:")
    print("```python")
    for suggestion in suggestions:
        print(f"        '{suggestion['suggested_name']}': {{'lang_code': '{suggestion['lang_code']}', 'service': 'ElevenLabs', 'voice': 'TBD - Need to find voice'}},  # NEW")
    print("```")
    
    # Generate npm scripts
    print("\n📝 Add to package.json scripts:")
    print("```json")
    for suggestion in suggestions:
        script_name = suggestion['suggested_name'].lower().replace(' ', '').replace('(', '').replace(')', '')
        print(f'    "generate:{script_name}": "python3 generate_speech.py {suggestion["suggested_name"]} \\"TBD_VOICE\\"",')
    print("```")
    
    return True

def main():
    print("🔍 DETECTING NEW LANGUAGE COLUMNS")
    print("="*50)
    
    # Load translation data
    data_list = load_translation_data()
    if data_list is None:
        print("❌ Could not load translation data")
        return 1
    
    columns = list(data_list[0].keys()) if data_list else []
    print(f"\n📊 Found {len(columns)} total columns:")
    print(f"   Columns: {columns}")
    
    # Detect potential language columns
    potential_langs = detect_language_columns(data_list)
    
    if not potential_langs:
        print("\n✅ No new language columns detected!")
        print("   All columns are either system columns or already configured.")
        return 0
    
    print(f"\n🆕 Found {len(potential_langs)} potential new language columns:")
    for lang in potential_langs:
        print(f"   • {lang['column']}: {lang['total_entries']} entries ({lang['fill_rate']:.1%} filled)")
        print(f"     Sample: '{lang['sample_text'][:50]}{'...' if len(lang['sample_text']) > 50 else ''}'")
    
    # Generate suggestions
    suggestions = suggest_language_mapping(potential_langs)
    
    # Generate configuration code
    generate_config_updates(suggestions)
    
    print(f"\n🎯 NEXT STEPS:")
    print(f"1. Update utilities/config.py with the above configuration")
    print(f"2. Find appropriate ElevenLabs voices for each language")
    print(f"3. Update package.json with the new npm scripts")
    print(f"4. Test generation: npm run generate:<language>")
    print(f"5. Add voices to web dashboard config if needed")
    
    return 0

if __name__ == "__main__":
    exit(main()) 