# Utility to list voices
import requests
import os
from playsound import playsound 
from utilities import utilities as u
from pyht import Client
import utilities.config as conf
import time
from . import voice_mapping

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

        # Update voice mappings with the fetched voices
        for voice in filtered_voices:
            voice_name = voice.get('name', '')
            voice_id = voice.get('value', '')  # Old API uses 'value' instead of 'id'
            if voice_name and voice_id:
                voice_mapping.add_voice_mapping(voice_name, voice_id)

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

    # Convert readable voice name to PlayHT voice ID if needed
    voice_id = voice_mapping.get_voice_id(voice)
    if voice_id:
        voice = voice_id
    else:
        print(f"Warning: Using voice '{voice}' directly (no mapping found)")

    # Convert HTML to SSML if needed, but remove <speak> wrapper for PlayHT API v2
    ssml_text = u.html_to_ssml(text)
    
    # PlayHT API v2 doesn't want the <speak> wrapper tags
    if ssml_text.startswith('<speak>') and ssml_text.endswith('</speak>'):
        ssml_text = ssml_text[7:-8]  # Remove <speak> and </speak>
    
    # API v2 data format - using PlayDialog for better emotion and natural speech
    # Fall back to Play3.0-mini if PlayDialog fails
    voice_engine = "PlayDialog"  # PlayDialog excels in creating highly emotive and natural speech
        
    data = {
        "text": ssml_text,
        "voice": voice,
        "voice_engine": voice_engine,
        "output_format": "mp3",
        "sample_rate": 24000
    }
    
    # Add text_type if SSML tags are present
    if '<' in ssml_text and '>' in ssml_text:
        data["text_type"] = "ssml"

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
                
            elif response.status_code == 500:
                print(f"PlayHt API error: {response.status_code} - {response.text}")
                # Debug information for 500 errors
                print("Debug info for 500 error:")
                print(f"  Voice: {voice}")
                print(f"  Text: '{text[:100]}{'...' if len(text) > 100 else ''}'")
                print(f"  Text length: {len(text)} characters")
                print(f"  Voice engine: {voice_engine}")
                print(f"  Text type: {'ssml' if '<' in ssml_text and '>' in ssml_text else 'plain'}")
                
                # Try fallback to Play3.0-mini if using PlayDialog
                if voice_engine == "PlayDialog" and errorCount == 0:
                    print("Retrying with Play3.0-mini fallback...")
                    voice_engine = "Play3.0-mini"
                    data["voice_engine"] = voice_engine
                    errorCount += 1
                    continue
                else:
                    return b''
                
            else:
                # Other error codes - add debugging for 500 errors
                print(f"PlayHt API error: {response.status_code} - {response.text}")
                
                # For 500 errors, provide additional debugging context
                if response.status_code == 500:
                    print(f"Debug info for 500 error:")
                    print(f"  Voice: {voice}")
                    print(f"  Text: '{ssml_text[:100]}{'...' if len(ssml_text) > 100 else ''}'")
                    print(f"  Text length: {len(ssml_text)} characters")
                    print(f"  Voice engine: {data.get('voice_engine', 'N/A')}")
                    print(f"  Text type: {data.get('text_type', 'plain')}")
                    time.sleep(retrySeconds * 3)  # Wait longer for 500 errors
                else:
                    time.sleep(retrySeconds)
                    
                errorCount += 1
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
