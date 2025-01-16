# Re-factoring language settings out of code
# Work in progress

# if we add it here can we use it throughout?
language_list = {}

# current location of translated items
# at some point can integrate with crowdin output
item_bank_translations = "text/translated.csv"
stats_file_path = 'stats.csv'

def get_languages(): 

    language_list = {\
        'English': {'lang_code':'en', 'voice': 'en-US-AriaNeural'},
        'Spanish': {'lang_code': 'es-CO', 'voice': 'es-CO-SalomeNeural'},
        'German': {'lang_code': 'de', 'voice' :'VickiNeural'},
        #'French': {'lang_code': 'fr', 'voice' : 'Pauline'}
        }
    
    # Later we can add HT voices and Eleven voices to each of these
    # e.g. language_list['English']['ht_voices' : ht_english_voice_list]
    return language_list       

def get_default_voice(language):
    language_index = get_languages()
    language_dict = language_index[language]
    return( language_dict['voice'])

def add_voice_list(language, service, voice_list):
    print('put add voice list here')

    