# Utility to list voices
import requests
import os
from playsound import playsound 
from utilities import utilities as u
from pyht import Client
import utilities.config as conf
import time

# Constants for API v2 - Updated to new PlayHt API
API_URL = "https://api.play.ht/api/v2/tts/stream"
VOICES_URL = "https://api.play.ht/api/v2/voices"

headers = {
    "AUTHORIZATION": os.environ["PLAY_DOT_HT_API_KEY"],  # Changed from Authorization
    "X-USER-ID": os.environ["PLAY_DOT_HT_USER_ID"],
    'Accept': 'audio/mpeg',  # Changed from application/json
    "Content-Type": "application/json"
}

def list_voices(lang_code):
    # Set up the API request for v2 API
    url = VOICES_URL

    # Make the API request
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        response_data = response.json()
        voices = response_data.get("voices", [])
    
         # Specify the language you want to filter by
         # This needs to be parameterized!
        language_dict = conf.get_languages()
        # Find the language key by searching for matching lang_code
        language = next(lang for lang, attrs in language_dict.items() if attrs['lang_code'] == lang_code)
        target_language = language_dict[language]['lang_code']

        # Filter voices by the specified language
        filtered_voices = [voice for voice in voices if \
                           voice.get('languageCode') == target_language \
                    and voice.get('gender') == 'Female'] #\
                    #and voice.get('voiceType') == 'Neural']

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

# Updated for PlayHt API v2 - Direct streaming response
def get_audio(text, voice):
    """
    Get audio using PlayHt API v2 streaming endpoint
    Returns audio content directly (no more polling)
    """
    retrySeconds = 1
    errorCount = 0

    # Convert HTML to SSML if needed
    ssml_text = u.html_to_ssml(text)
    
    # API v2 data format
    data = {
        "text": ssml_text,
        "voice": voice,
        "voice_engine": "PlayDialog",  # Use PlayDialog for better emotion and natural speech
        "output_format": "mp3",
        "sample_rate": 24000
    }

    ## Use a While loop so we can retry odd failure cases
    while True and errorCount < 5:
        try:
            response = requests.post(API_URL, headers=headers, json=data, timeout=30)

            # Handle different status codes
            if response.status_code == 200:
                # v2 API returns audio content directly
                print(f"✅ PlayHt v2 API success - received {len(response.content)} bytes")
                return response.content
                
            elif response.status_code == 503:
                # Service unavailable - likely rate limiting or server overload
                print(f"PlayHt service unavailable (503). Waiting {retrySeconds * 2} seconds before retry...")
                time.sleep(retrySeconds * 2)  # Wait longer for 503 errors
                errorCount += 1
                retrySeconds = min(retrySeconds * 2, 30)  # Exponential backoff, max 30 seconds
                continue
                
            elif response.status_code == 429:
                # Rate limit exceeded
                retry_after = response.headers.get('Retry-After', retrySeconds * 2)
                print(f"Rate limit exceeded. Waiting {retry_after} seconds...")
                time.sleep(int(retry_after))
                errorCount += 1
                continue

            elif response.status_code == 400:
                print(f"PlayHt API error 400 - Bad request: {response.text}")
                # For 400 errors, don't retry - likely a permanent issue
                return b''
                
            else:
                # Other error codes
                print(f"PlayHt API error: {response.status_code} - {response.text}")
                errorCount += 1
                time.sleep(retrySeconds)
                continue
                
        except requests.exceptions.Timeout:
            print(f"PlayHt API timeout. Retrying... ({errorCount + 1}/5)")
            errorCount += 1
            time.sleep(retrySeconds)
            continue
            
        except requests.exceptions.RequestException as e:
            print(f"PlayHt API request failed: {e}")
            errorCount += 1
            time.sleep(retrySeconds)
            continue
    
    # If we get here, we've exhausted all retries
    print("❌ PlayHt API failed after 5 retries")
    return b'' 