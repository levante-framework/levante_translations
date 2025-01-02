# Utility to list voices
import requests
import os

# Set up the API request
url = "https://play.ht/api/v1/getVoices"
headers = {
    "Authorization": os.environ["PLAY_DOT_HT_API_KEY"],
    "X-User-ID": os.environ["PLAY_DOT_HT_USER_ID"],
    "Content-Type": "application/json"
}

# Make the API request
response = requests.get(url, headers=headers)

# Check if the request was successful
if response.status_code == 200:
    response_data = response.json()
    voices = response_data.get("voices", [])
    
     # Specify the language you want to filter by
    target_language = "English (US)"  # Change this to your desired language
    target_language = "German"  # Change this to your desired language
    target_language = "Spanish (Colombia)"  # Change this to your desired language
    
    # Filter voices by the specified language
    filtered_voices = [voice for voice in voices if voice.get('language') == target_language]

    # debug language
    #filtered_voices = [voice for voice in voices]

    # Print voice details
    for voice in filtered_voices:
        print(f"Name: {voice.get('name', 'N/A')}")
#        print(f"ID: {voice.get('value', 'N/A')}")
        print(f"Language: {voice.get('language', 'N/A')}")
#        print(f"Gender: {voice.get('gender', 'N/A')}")
#        print(f"Age: {voice.get('age', 'N/A')}")
#        print(f"Sample: {voice.get('sample', 'N/A')}")
#        print("---")

else:
    print(f"Error: {response.status_code} - {response.text}")



