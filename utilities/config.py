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

def get_languages(): 

# Updated for PlayHt API v2 with correct voice IDs and language codes
    language_list = {\
        'English': {'lang_code':'en', 'service' : 'ElevenLabs', 'voice': 'Alexandra - Conversational and Real'},
        'Spanish': {'lang_code': 'es', 'service' : 'PlayHt', 'voice': 's3://voice-cloning-zero-shot/326c3793-b5b1-4ce3-a8ec-22c95d8553f0/original/manifest.json'},
        'German': {'lang_code': 'de', 'service' : 'PlayHt', 'voice' :'s3://voice-cloning-zero-shot/2f91566e-215a-4234-96e2-60acf07fed5e/original/manifest.json'},
        'French': {'lang_code': 'fr', 'service' : 'PlayHt', 'voice' : 's3://voice-cloning-zero-shot/067f8a04-9138-440b-971d-5cce69f4c271/original/manifest.json'},
        'Dutch': {'lang_code': 'nl', 'service' : 'ElevenLabs', 'voice' : 'Xander'},
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

    