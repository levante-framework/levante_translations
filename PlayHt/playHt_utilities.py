# Utility to list voices
import requests
import os
import json
from playsound import playsound 
import logging
from pyht import Client
from pyht.client import TTSOptions
import asyncio
from pyht import AsyncClient


# Constants for API, in this case for Play.Ht, maybe
API_URL = "https://api.play.ht/api/v1/convert"
STATUS_URL = "https://api.play.ht/api/v1/articleStatus"

headers = {
    "Authorization": os.environ["PLAY_DOT_HT_API_KEY"],
    "X-User-ID": os.environ["PLAY_DOT_HT_USER_ID"],
    "Content-Type": "application/json"
}

def list_voices(lang_code):
    # Set up the API request
    url = "https://play.ht/api/v1/getVoices"

    # Make the API request
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        response_data = response.json()
        voices = response_data.get("voices", [])
    
         # Specify the language you want to filter by
        if lang_code == 'en':
            target_language = "English (US)"  # Change this to your desired language
        elif lang_code == 'de':
            target_language = "German"  # Change this to your desired language
        elif lang_code == 'es-CO':
            target_language = "Spanish (Colombia)"  # Change this to your desired language
        else:
            return("Error")

        # Filter voices by the specified language
        filtered_voices = [voice for voice in voices if voice.get('language') == target_language]

        # debug language
        #filtered_voices = [voice for voice in voices]

        # Do we want to return the entire dictionary? 
        return(filtered_voices)

# Print voice details for debugging
#        for voice in filtered_voices:

#            print(f"Name: {voice.get('name', 'N/A')}")
#        print(f"ID: {voice.get('value', 'N/A')}")
#            print(f"Language: {voice.get('language', 'N/A')}")
#        print(f"Gender: {voice.get('gender', 'N/A')}")
#        print(f"Age: {voice.get('age', 'N/A')}")
#        print(f"Sample: {voice.get('sample', 'N/A')}")
#        print("---")

    else:
        print(f"Error: {response.status_code} - {response.text}")


def play_audio(text, voice):

    client = Client(
        api_key = os.environ["PLAY_DOT_HT_API_KEY"],
        user_id = os.environ["PLAY_DOT_HT_USER_ID"],
    )

    options = TTSOptions(voice="s3://voice-cloning-zero-shot/775ae416-49bb-4fb6-bd45-740f205d20a1/jennifersaad/manifest.json")

    # Open a file to save the audio
    audio_filename = "voice_comparison.mp3"
    with open(audio_filename, "wb") as audio_file:
        for chunk in client.tts(text, options, voice_engine = 'PlayDialog-http'):
            # Write the audio chunk to the file
            audio_file.write(chunk)
        audio_file.close
    #print("Audio saved")
    playsound(audio_filename)


