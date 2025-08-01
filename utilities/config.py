# Re-factoring language settings out of code
# Work in progress

# General settings
playht_stability = 1.2
elevenlabs_stability = .65

# if we add it here can we use it throughout?
language_list = {}

# current location of translated items
translatedTextURL = "https://raw.githubusercontent.com/levante-framework/levante_translations/l10n_pending/text/translated_prompts.csv"

# currently we read right from there
item_bank_translations = translatedTextURL

stats_file_path = 'stats.csv'

# define language codes as a constant here``
LANGUAGE_CODES = {
  'English': 'en', 
  'Spanish': 'es-CO', 
  'German': 'de', 
  'French': 'fr-CA', 
  'Dutch': 'nl',
}

def get_languages(): 

# Updated for PlayHt API v2 with correct voice IDs and language codes
    language_list = {\
        'English': {'lang_code':'en', 'service' : 'ElevenLabs', 'voice': 'Clara - Children\'s Storyteller'},
        'Spanish': {'lang_code': 'es-CO', 'service' : 'ElevenLabs', 'voice': 'Malena Tango'},
        'German': {'lang_code': 'de', 'service' : 'ElevenLabs', 'voice': 'Julia'},
        'French': {'lang_code': 'fr-CA', 'service' : 'ElevenLabs', 'voice': 'Caroline - Top France - Narrative, warm, sweet'},
        'Dutch': {'lang_code': 'nl', 'service' : 'ElevenLabs', 'voice' : 'Emma - Natural conversations in Dutch'},
    }

    # Later we can add HT voices and Eleven voices to each of these
    # e.g. language_list['English']['ht_voices' : ht_english_voice_list]
    return language_list       

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

    