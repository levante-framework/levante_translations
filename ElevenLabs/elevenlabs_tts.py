# generate audio using ElevenLabs
import os
from elevenlabs import play
from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key=os.getenv('ELEVEN_API_KEY'))


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


