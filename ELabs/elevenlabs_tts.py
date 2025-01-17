# generate audio using ElevenLabs
import os
from elevenlabs import play
from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key=os.getenv('ELEVEN_API_KEY'))
# These are the two functions we need to support

def list_voices(lang_code):
    # Fetch all available voices
    voices = client.voices.get_all()
    for voice in voices:
        print(repr(voice))

    # Function to filter voices by language
    def filter_voices_by_language(voices, language):
        return [voice for voice in voices if language.lower() in str(voice[3]).lower()]
    # 
    #Example: List all Korean voices
    korean_voices = filter_voices_by_language(voices, "korean")

    # Print the filtered voices
    for voice in korean_voices:
        print(f"Name: {voice.name}, ID: {voice.voice_id}")
        
def get_audio(text, voice):
    print("TBD")

def example():
    # Generate audio from text
    audio = client.generate(
        text="Hello, this is a test of the ElevenLabs API!",
        voice="Rachel",
        model="eleven_monolingual_v1"
    )

    # Play the audio (works locally)
    play(audio)

    # Alternatively, save the audio to a file
    with open("output.mp3", "wb") as f:
        f.write(audio)

list_voices('en')

