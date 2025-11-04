# Re-factoring language settings out of code
# Work in progress

# General settings
playht_stability = 1.2
elevenlabs_stability = .65

# if we add it here can we use it throughout?
language_list = {}

# Preferred remote and local locations for item_bank_translations
REMOTE_ITEM_BANK_URL = "https://raw.githubusercontent.com/levante-framework/levante_translations/l10n_pending/translations/itembank/item-bank-translations.csv"
LOCAL_ITEM_BANK_PATH = "translation_text/item_bank_translations.csv"

# generate_speech will read from the local path; the fetch script keeps it updated from REMOTE_ITEM_BANK_URL
item_bank_translations = LOCAL_ITEM_BANK_PATH

stats_file_path = 'stats.csv'

# define language codes as a constant here``
LANGUAGE_CODES = {
  'English': 'en', 
  'English (UK)': 'en-GB', 
  'Spanish': 'es-CO', 
  'German': 'de', 
  'French': 'fr-CA', 
  'Dutch': 'nl',
  'German (Switzerland)': 'de-CH',  # NEW
  'Spanish (Argentina)': 'es-AR',  # NEW
}

def get_languages():
    """Return language configuration, preferring shared GCS JSON when available."""
    # Local fallback
    local_languages = {
        'English': {'lang_code': 'en', 'service': 'ElevenLabs', 'voice': 'Clara - Children\'s Storyteller'},
        'English (UK)': {'lang_code': 'en-GB', 'service': 'ElevenLabs', 'voice': 'Clara - Children\'s Storyteller'},
        'Spanish': {'lang_code': 'es-CO', 'service': 'ElevenLabs', 'voice': 'Malena Tango'},
        'German': {'lang_code': 'de', 'service': 'ElevenLabs', 'voice': 'Julia'},
        'French': {'lang_code': 'fr-CA', 'service': 'ElevenLabs', 'voice': 'Caroline - Top France - Narrative, warm, sweet'},
        'Dutch': {'lang_code': 'nl', 'service': 'ElevenLabs', 'voice': 'Emma - Natural conversations in Dutch'},
        'German (Switzerland)': {'lang_code': 'de-CH', 'service': 'ElevenLabs', 'voice': 'Heidi factual (Standard German - with Swiss Accent)'},
        # Use an ElevenLabs Spanish voice available in the account (e.g., 'Sophia')
        'Spanish (Argentina)': {'lang_code': 'es-AR', 'service': 'ElevenLabs', 'voice': 'Sophia'},
    }

    try:
        from .config_from_gcs import get_languages_config  # type: ignore
        return get_languages_config(local_languages)
    except Exception:
        return local_languages

def get_default_voice(language):
    language_index = get_languages()
    language_dict = language_index[language]
    return( language_dict['voice'])

def get_lang_code(language):
    language_index = get_languages()
    language_dict = language_index[language]
    return( language_dict['lang_code'])

def get_service(language):
    language_index = get_languages()
    language_dict = language_index[language]
    return( language_dict['service'])

def add_voice_list(language, service, voice_list):
    print('put add voice list here')

    