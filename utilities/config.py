# Re-factoring language settings out of code
# Work in progress

# if we add it here can we use it throughout?
language_list = {}

# current location of translated items
# at some point can integrate with crowdin output
translatedTextURL = "https://raw.githubusercontent.com/levante-framework/levante_translations/l10n_pending/text/translated.csv"

# currently we read right from there
item_bank_translations = translatedTextURL

stats_file_path = 'stats.csv'

def get_languages(): 

    language_list = {\
        #'English': {'lang_code':'en', 'service' : 'ElevenLabs', 'voice': 'Alexandra - Conversational and Real'},
        'English': {'lang_code':'en', 'service' : 'PlayHt', 'voice': 'en-US-AriaNeural'},
        'Spanish': {'lang_code': 'es-CO', 'service' : 'PlayHt', 'voice': 'es-CO-SalomeNeural'},
        'German': {'lang_code': 'de', 'service' : 'PlayHt', 'voice' :'VickiNeural'},
        #'French': {'lang_code': 'fr', 'service' : 'PlayHt', 'voice' : 'LeaNeural'}
        }

#        'English': {'lang_code':'en', 'service' : 'PlayHt', 'voice': 'en-US-AriaNeural'},

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

    