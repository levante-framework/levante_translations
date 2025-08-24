# Simplified interface to Play.Ht for translations

import os
import sys
import logging
import time

def retry_with_backoff(func, max_retries=3, base_delay=1, max_delay=60, backoff_factor=2):
    """
    Retry a function with exponential backoff
    """
    for attempt in range(max_retries):
        try:
            return func()
        except KeyboardInterrupt:
            print(f"\n🛑 Process interrupted by user. Stopping gracefully...")
            sys.exit(0)
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"❌ Final attempt failed: {str(e)}")
                raise e
            
            delay = min(base_delay * (backoff_factor ** attempt), max_delay)
            print(f"⚠️  Attempt {attempt + 1} failed: {str(e)}")
            print(f"🔄 Retrying in {delay} seconds...")
            time.sleep(delay)
    
    return None

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Warning: pandas and numpy not available. Some functionality may be limited.")
    # Create mock objects for basic functionality
    class MockPandas:
        def read_csv(self, *args, **kwargs):
            raise ImportError("pandas not available - install with: pip install pandas")
        def DataFrame(self, *args, **kwargs):
            raise ImportError("pandas not available - install with: pip install pandas")
    
    class MockNumpy:
        def array(self, *args, **kwargs):
            raise ImportError("numpy not available - install with: pip install numpy")
    
    pd = MockPandas()
    np = MockNumpy()
import requests
from dataclasses import dataclass, replace
from datetime import datetime
import utilities.utilities as u
from . import voice_mapping
import utilities.config as conf

# Constants for API v2 - Updated to new PlayHt API
API_URL = "https://api.play.ht/api/v2/tts/stream"
RATE_LIMIT = 10

start_time = time.perf_counter()
request_count = 0

# Called to process each row of the input csv (now dataframe)
def processRow(index, ourRow, lang_code, voice, \
               masterData, audio_base_dir, headers, ssml):
    # reset local error count for new row
    errorCount = 0
    retrySeconds = 1 # sort of arbitrary backoff to recheck status
    service = 'PlayHt'

    # used to limit number of requests to < 10 per minute
    global request_count
    global start_time
    global rate_limit

    # we should potentially filter these out when we generate diffs
    # instead of waiting until now. But at some point we might
    # want to generate them as part of an "unassigned" task or something
    if not (type(ourRow['labels']) == type('str')):
        print(f"Item {ourRow['item_id']} doesn't have task assigned")
        return 'NoTask'

    # Handle column mapping for translation text lookup
    translation_text = ''
    if lang_code in ourRow:
        translation_text = ourRow[lang_code]
    else:
        # Try simplified version mapping
        simplified_lang_codes = {
            'en-US': 'en',
            'es-CO': 'es',
            'de-DE': 'de', 
            'fr-CA': 'fr',
            'nl-NL': 'nl'
        }
        simplified_code = simplified_lang_codes.get(lang_code, lang_code)
        if simplified_code in ourRow:
            translation_text = ourRow[simplified_code]
        else:
            print(f"Warning: No translation found for {lang_code} in row {ourRow['item_id']}")
            return 'Error'

    # Assemble data packet for PlayHT API v2
    # see https://docs.play.ht/reference/api-generate-tts-audio-stream
    
    # Convert to SSML if needed, but remove <speak> wrapper for PlayHT API v2
    ssml_text = u.html_to_ssml(translation_text)
    # PlayHT API v2 doesn't want the <speak> wrapper tags
    if ssml_text.startswith('<speak>') and ssml_text.endswith('</speak>'):
        ssml_text = ssml_text[7:-8]  # Remove <speak> and </speak>
    
    # Convert readable voice name to PlayHT voice ID if needed
    voice_id = voice_mapping.get_voice_id(voice)
    if voice_id:
        voice = voice_id
    else:
        print(f"Warning: Using voice '{voice}' directly (no mapping found)")
    
    data = {
        "text": ssml_text if ssml else translation_text,
        "voice": voice,
        "voice_engine": "PlayDialog",  # Use PlayDialog for better emotion and natural speech
        "output_format": "mp3",
        "sample_rate": 24000
    }
    
    # Add text_type if SSML tags are present
    if '<' in ssml_text and '>' in ssml_text:
        data["text_type"] = "ssml"

    # current plan allows 10 requests per minute, so wait for end of minute after 10 requests
    request_count += 1
    if request_count > RATE_LIMIT:
      print(f"🕒 Waiting to avoid exceeding rate limit of {RATE_LIMIT} requests per minute...")
      end_time = time.perf_counter()
      time_left = 60 - (end_time - start_time)
      time.sleep(time_left)
      start_time = time.perf_counter()
      request_count = 1

    ## Use a While loop so we can retry odd failure cases
    while True and errorCount < 5:
        try:
            response = requests.post(API_URL, headers=headers, json=data, timeout=30)
            
            # Handle different status codes for v2 API
            if response.status_code == 200:
                # v2 API returns audio content directly
                print(f"✅ PlayHt v2 API success for item {ourRow['item_id']} - received {len(response.content)} bytes")
                
                # Create a response object that mimics the old audioData structure
                class AudioResponse:
                    def __init__(self, content):
                        self.content = content
                        self.status_code = 200
                
                audioData = AudioResponse(response.content)
                
                if ourRow['labels'] != float('nan'):
                    return u.save_audio(ourRow, lang_code, service, audioData, audio_base_dir, masterData, voice)
                else:
                    return 'Success'
                    
            elif response.status_code == 503:
                # Service unavailable - likely rate limiting or server overload
                print(f"PlayHt service unavailable (503) for item {ourRow['item_id']}. Waiting {retrySeconds * 2} seconds before retry...")
                time.sleep(retrySeconds * 2)  # Wait longer for 503 errors
                errorCount += 1
                retrySeconds = min(retrySeconds * 2, 30)  # Exponential backoff, max 30 seconds
                continue
                
            elif response.status_code == 429:
                # Rate limit exceeded
                retry_after = response.headers.get('Retry-After', retrySeconds * 2)
                print(f"Rate limit exceeded for item {ourRow['item_id']}. Waiting {retry_after} seconds...")
                time.sleep(int(retry_after))
                errorCount += 1
                continue
                
            elif response.status_code == 400:
                print(f"PlayHt API error 400 for item {ourRow['item_id']} - Bad request: {response.text}")
                # For 400 errors, don't retry - likely a permanent issue
                return 'Error'
                
            else:
                # Parse error response for better debugging
                try:
                    error_data = response.json()
                    error_message = error_data.get('error_message', 'Unknown error')
                    error_id = error_data.get('error_id', 'Unknown')
                    print(f"PlayHt API error: {response.status_code} - {error_message} (ID: {error_id})")
                    
                    # For voice-related errors, provide additional context
                    if 'voice' in error_message.lower() or response.status_code == 500:
                        print(f"Voice used: {voice} (original: {data['voice']})")
                        print(f"Text length: {len(ssml_text)} characters")
                        print(f"Voice engine: {data.get('voice_engine', 'N/A')}")
                        
                except:
                    print(f"PlayHt API error: {response.status_code} - {response.text}")
                
                logging.error(f"convert_tts: API error for item={ourRow['item_id']}: status code={response.status_code}, response={response.text}")
                errorCount += 1
                
                # For 500 errors, wait longer before retrying
                if response.status_code == 500:
                    time.sleep(retrySeconds * 3)
                else:
                    time.sleep(retrySeconds)
                continue
                
        except requests.exceptions.Timeout:
            print(f"PlayHt API timeout for item {ourRow['item_id']}. Retrying... ({errorCount + 1}/5)")
            errorCount += 1
            time.sleep(retrySeconds)
            continue
            
        except requests.exceptions.RequestException as e:
            print(f"PlayHt API request failed for item {ourRow['item_id']}: {e}")
            errorCount += 1
            time.sleep(retrySeconds)
            continue
    
    # If we get here, we've exhausted all retries
    print(f"❌ PlayHt API failed after 5 retries for item {ourRow['item_id']}")
    return 'Error'
    
"""
The main function to process the transcription jobs.
NOTE: Not all arguments are impleented!
Args:
    input_file_path (str): The path of the input CSV file where details of text and of past tts transactions are extracted.
    lang_code (str): A locale code, e.g.: 'es-CO' and the name for the column to select for tts transcription
    voice (str): The name of the play.ht voice to use, e.g.: 'es-CO-SalomeNeural'
    retry_seconds (float64): How many seconds to wait to retry translation
    user_id (str, optional): The user ID for authentication. If not provided, it will be read from the environment variable 'PLAY_DOT_HT_USER_ID'.
    api_key (str, optional): The api key authenticating our API calls. If not provided, it will be read from the environment variable 'PLAY_DOT_HT_API_KEY'.
    item_id_column (str, optional): column name in the input file for stable and unique item ID. Defaults to 'item_id'.
    audio_dir (str, optional): The directory to store the audio files. Defaults to "audio_files/{lang_code}/".
"""
def main(
        input_file_path: str,
        master_file_path: str,
        lang_code: str,
        voice: str,
        retry_seconds: float,
        user_id: str = None,
        api_key: str = None,
        output_file_path: str = None,
        item_id_column: str = 'item_id',
        audio_base_dir: str = None
        ):
        

    if user_id is None:
        user_id = os.environ['PLAY_DOT_HT_USER_ID']
        if user_id is None:
            raise ValueError("user_id cannot be None")
    if api_key is None:
        api_key = os.environ['PLAY_DOT_HT_API_KEY']
        if api_key is None:
            raise ValueError("auth_token cannot be None")

    # basically we want to iterate through rows,
    # specifying the column (language) we want translated.
    # We assume that our caller has already massaged our input file as needed
    # columnts might be:
    # item_id,labels,en,es-CO,de,context

    if not PANDAS_AVAILABLE:
        raise ImportError("pandas is required for CSV processing. Install with: pip install pandas")
    
    inputData = pd.read_csv(input_file_path)
    masterData = pd.read_csv(master_file_path)

    # Rename columns to match lang_codes used in the script
    masterData = masterData.rename(columns={'en': 'en-US',
                                             'de': 'de-DE',
                                             'es': 'es-CO',
                                             'fr': 'fr-CA',
                                             'nl': 'nl-NL'})

    # build API call for v2 API
    headers = {
        'AUTHORIZATION': api_key,  # Changed from Authorization
        'X-USER-ID': user_id,
        'Accept': 'audio/mpeg',  # Changed from application/json
        'Content-Type': 'application/json'
    }
    
    stats = {'Errors': 0, 'Processed' : 0, 'NoTask': 0}
    for index, ourRow in inputData.iterrows():

        result = processRow(index, ourRow, lang_code=lang_code, voice=voice, \
                            audio_base_dir=audio_base_dir, masterData=masterData, \
                            headers=headers, ssml=False)
        
        # replace with match once we are past python 3.10
        if result == 'Error':
            stats['Errors']+= 1
        elif result == 'NoTask':
            stats['NoTask']+= 1
        elif result == 'Success':
            stats['Processed']+= 1
    
    # start tracking voice
    stats['Voice'] = voice

    # Store stats for retrieval by dashboard
    u.store_stats(lang_code, stats['Errors'], stats['NoTask'], stats['Voice'])

    print(f"Processed: {stats['Processed']}, Errors: {stats['Errors']}, \
          No Task: {stats['NoTask']}")

if __name__ == "__main__":
    main(*sys.argv[1:])

