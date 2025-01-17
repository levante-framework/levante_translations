import os
from elevenlabs import play
from elevenlabs.client import ElevenLabs 
import pprint 

client = ElevenLabs( 
    api_key=os.getenv('elevenlabs_test'),  # enter your API key here 
) 

response = client.voices.get_shared(
    page_size=100,  # Adjust as needed, max 100
    category='professional',  # Optional filter
    gender=None,    # Optional filter
    age=None,       # Optional filter
    accent=None,    # Optional filter
    language='es', #None,  # Optional filter
    search=None,    # Optional search term
    use_cases='conversational',  # Optional filter
    featured=None,  # Optional filter
    sort=None       # Optional sorting criteria
)

formatted_voices = pprint.pformat(response.voices) 

with open("voices.txt", "w", encoding="utf-8") as file: 
    file.write(formatted_voices) 
print("Voice information has been written to voices.txt") 
print(f"Number of voices: {len(response.voices)}") 

# Generate audio from text
audio = client.generate(
    text="Hello, this is a test phrase using ElevenLabs.",
    voice="Rachel"  # You can change this to any available voice
)

# Play the generated audio
play(audio)


