# Example voice configuration for PlayHT API
# This file shows how to set up voice mappings for easy maintenance

from . import voice_mapping

def setup_voice_mappings():
    """
    Set up custom voice mappings for your project.
    
    This function should be called once to establish mappings between
    readable names and PlayHT voice IDs. You can run this whenever
    you want to add new voice mappings.
    """
    
    # Example: Add Spanish voices
    voice_mapping.add_voice_mapping(
        "Spanish_Female_Professional", 
        "s3://voice-cloning-zero-shot/abc123-def456-ghi789/spanish-female/manifest.json"
    )
    
    voice_mapping.add_voice_mapping(
        "Spanish_Male_Conversational",
        "s3://voice-cloning-zero-shot/xyz789-abc123-def456/spanish-male/manifest.json"
    )
    
    # Example: Add German voices
    voice_mapping.add_voice_mapping(
        "German_Female_Neural",
        "s3://voice-cloning-zero-shot/def456-ghi789-jkl012/german-female/manifest.json"
    )
    
    # Example: Add French voices
    voice_mapping.add_voice_mapping(
        "French_Female_Elegant",
        "s3://voice-cloning-zero-shot/ghi789-jkl012-mno345/french-female/manifest.json"
    )
    
    # Example: Add Dutch voices
    voice_mapping.add_voice_mapping(
        "Dutch_Female_Clear",
        "s3://voice-cloning-zero-shot/jkl012-mno345-pqr678/dutch-female/manifest.json"
    )
    
    print("Voice mappings configured successfully!")

def get_recommended_voices():
    """
    Get a dictionary of recommended voices for each language.
    
    Returns:
        dict: Language codes mapped to recommended voice names
    """
    return {
        'es-CO': 'Spanish_Female_Professional',
        'de-DE': 'German_Female_Neural', 
        'fr-CA': 'French_Female_Elegant',
        'nl-NL': 'Dutch_Female_Clear',
        'en-US': 'English_Female_Conversational'  # If you add English voices
    }

def update_config_voices():
    """
    Update the main config.py file to use the new voice names.
    
    This is an example of how you might update your existing configuration
    to use the new readable voice names instead of the old ones.
    """
    
    # This is what your updated config.py might look like:
    example_config = {
        'Spanish': {
            'lang_code': 'es-CO', 
            'service': 'PlayHt', 
            'voice': 'Spanish_Female_Professional'  # Instead of 'es-CO-SalomeNeural'
        },
        'German': {
            'lang_code': 'de-DE', 
            'service': 'PlayHt', 
            'voice': 'German_Female_Neural'  # Instead of 'VickiNeural'
        },
        'French': {
            'lang_code': 'fr-CA', 
            'service': 'PlayHt', 
            'voice': 'French_Female_Elegant'  # Instead of 'Gabrielle'
        },
        'Dutch': {
            'lang_code': 'nl-NL', 
            'service': 'PlayHt', 
            'voice': 'Dutch_Female_Clear'  # Instead of 'FennaNeural'
        }
    }
    
    print("Example configuration:")
    for lang, config in example_config.items():
        print(f"{lang}: {config}")
    
    return example_config

if __name__ == "__main__":
    # Run this script to set up your voice mappings
    setup_voice_mappings()
    print("\nRecommended voices:")
    for lang, voice in get_recommended_voices().items():
        print(f"{lang}: {voice}") 