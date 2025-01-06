# Re-factoring language settings out of code
# Work in progress

# if we add it here can we use it throughout?
language_list = {}

def get_languages(): 

    language_list = {\
        'English': {'lang_code':'en', 'voice': 'en-US-AriaNeural'},
        'Spanish': {'lang_code': 'es-CO', 'voice': 'es-CO-SalomeNeural'},
        'German': {'lang_code': 'de', 'voice' :'VickiNeural'},
        }
    
    # Later we can add HT voices and Eleven voices to each of these
    # e.g. language_list['English']['ht_voices' : ht_english_voice_list]
    return language_list       

def add_voice_list(language, service, voice_list):
    print('put add voice list here')

    