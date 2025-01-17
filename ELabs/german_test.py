import os
from elevenlabs import play, voices
from elevenlabs.client import ElevenLabs 
import pprint 

client = ElevenLabs( 
    api_key=os.getenv('elevenlabs_test'),  # enter your API key here 
) 

voice_list = client.voices.get_all()

# Generate German audio
audio = client.generate(
    text="Hallo! Wie geht es Ihnen? Ich bin eine deutsche KI-Stimme.",
    voice="v3V1d2rk6528UrLKRuy8",  # A German voice
    model="eleven_multilingual_v2"
)

# Play the generated audio
play(audio)
