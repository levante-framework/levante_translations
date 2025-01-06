# Re-factoring language settings out of code
# Work in progress

def get_languages(): 

    language_list = {\
        'English': {'lang_code':'en', 'voice': 'en-US-AriaNeural'},
        'Spanish': {'lang_code': 'es-CO', 'voice': 'es-CO-SalomeNeural'},
        'German': {'lang_code': 'de', 'voice' :'VickiNeural'},
        }
    
    # Later we can add HT voices and Eleven voices to each of these
    
    return language_list       
