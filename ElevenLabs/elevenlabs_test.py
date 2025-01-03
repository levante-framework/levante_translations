import os
from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key=os.getenv('ELEVEN_API_KEY'))

voices_response = client.voices.get_all()

print(f"Type of voices_response: {type(voices_response)}")

# Check if the response has a 'voices' attribute
if hasattr(voices_response, 'voices'):
    voices = voices_response.voices
    print(f"Number of voices: {len(voices)}")

    # Function to safely get language
    def get_language(voice):
        if hasattr(voice, 'labels') and isinstance(voice.labels, dict):
            return voice.labels.get('language', 'Unknown')
        return 'Unknown'

    # Filter voices by language
    def filter_voices_by_language(voices, language):
        return [voice for voice in voices if language.lower() in get_language(voice).lower()]

    # Example: List all Korean voices
    korean_voices = filter_voices_by_language(voices, "korean")

    for voice in korean_voices:
        print(f"Name: {getattr(voice, 'name', 'Unknown')}")
        print(f"Voice ID: {getattr(voice, 'voice_id', 'Unknown')}")
        print(f"Language: {get_language(voice)}")
        print("---")
else:
    print("Unexpected response structure. Printing available attributes:")
    print(dir(voices_response))