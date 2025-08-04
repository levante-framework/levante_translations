# generate audio using ElevenLabs
import os
import pandas as pd
import numpy as np
from elevenlabs import play
from elevenlabs import save
from elevenlabs.client import ElevenLabs
import utilities.utilities as u
import utilities.config as conf
from ELabs import elevenlabs_utilities

# this doesn't work?
# from elevenlabs import set_api_key

# this doesn't work?
# set_api_key(os.getenv('ELEVEN_API_KEY'))

audio_client = ElevenLabs(api_key=os.getenv('elevenlabs_test'))

def get_voice_id(voice_name, lang_code):
    """
    Get the voice ID from voice name using the elevenlabs_utilities function
    """
    try:
        # Get the voice dictionary for the language
        voice_dict = elevenlabs_utilities.list_voices(lang_code)
        
        if voice_name in voice_dict:
            voice_id = voice_dict[voice_name]
            print(f"✓ Found voice '{voice_name}' with ID: {voice_id}")
            return voice_id
        else:
            print(f"❌ Voice '{voice_name}' not found in available voices for {lang_code}")
            print(f"Available voices: {list(voice_dict.keys())}")
            return None
    except Exception as e:
        print(f"❌ Error looking up voice '{voice_name}': {e}")
        return None

# This is called to generate audio for the passed string
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
        
    # basically we want to iterate through rows,
    # specifying the column (language) we want translated.
    # We assume that our caller has already massaged our input file as needed
    # columnts might be:
    # item_id,labels,en,es-CO,de,context

    inputData = pd.read_csv(input_file_path)
    masterData = pd.read_csv(master_file_path)

    # build API call
    headers = {
        'Authorization': api_key,
        'X-USER-ID': user_id,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    stats = {'Errors': 0, 'Processed' : 0, 'NoTask': 0}
    
    # Look up voice ID once at the beginning to avoid repeated API calls
    print(f"Looking up voice '{voice}' for language '{lang_code}'...")
    voice_id = get_voice_id(voice, lang_code)
    if voice_id is None:
        print(f"❌ Cannot proceed: voice '{voice}' not found for {lang_code}")
        return {'Errors': len(inputData), 'Processed': 0, 'NoTask': 0, 'Voice': voice}

    for index, ourRow in inputData.iterrows():

        result = processRow(index, ourRow, lang_code=lang_code, voice=voice, voice_id=voice_id, \
                            audio_base_dir=audio_base_dir, masterData=masterData, \
                            headers=headers)
        
        # replace with match once we are past python 3.10
        if result == 'Error':
            stats['Errors']+= 1
        elif result == 'NoTask':
            stats['NoTask']+= 1
        elif result == 'Success':
            stats['Processed']+= 1
        else:
            # Handle any unexpected return values as errors
            print(f"⚠️ Unexpected result from processRow: {result} - counting as error")
            stats['Errors']+= 1
    
    # start tracking voice
    stats['Voice'] = voice

    # Store stats for retrieval by dashboard
    u.store_stats(lang_code, stats['Errors'], stats['NoTask'], stats['Voice'])

    print(f"Processed: {stats['Processed']}, Errors: {stats['Errors']}, \
          No Task: {stats['NoTask']}")
    
    # Return stats for use by the calling function
    return stats


# Called to process each row of the input csv (now dataframe)
def processRow(index, ourRow, lang_code, voice, voice_id, \
               masterData, audio_base_dir, headers):

    # reset local error count for new row
    errorCount = 0
    retrySeconds = 1 # sort of arbitrary backoff to recheck status

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

    # Show what we're about to generate
    print(f"🎵 Generating audio for '{ourRow['item_id']}': {translation_text[:100]}{'...' if len(translation_text) > 100 else ''}")
    
    try:
        audio = audio_client.generate(
            text=translation_text,
            voice=voice_id,
            model="eleven_multilingual_v2"
        )

        # Create a response object that mimics what PlayHT returns for consistency
        class AudioResponse:
            def __init__(self, content):
                self.content = content
                self.status_code = 200
        
        # Convert the generator to bytes
        audio_bytes = b''.join(audio)
        audioData = AudioResponse(audio_bytes)
        
        print(f"✅ Successfully generated {len(audio_bytes)} bytes of audio for '{ourRow['item_id']}'")
        
        # Use our unified save_audio function with ID3 tags
        service = 'ElevenLabs'
        if ourRow['labels'] != float('nan'):
            result = u.save_audio(ourRow, lang_code, service, audioData, audio_base_dir, masterData, voice)
            print(f"💾 Saved audio file for '{ourRow['item_id']}' with result: {result}")
            return result
        else:
            print(f'Generated audio for {ourRow["item_id"]}')
            
            # Still need to update master data for tracking
            masterData[lang_code] = \
                np.where(masterData["item_id"] == ourRow["item_id"], \
                translation_text, masterData[lang_code])
            
            # write as we go, so erroring out doesn't lose progress
            masterData.to_csv("translation_master.csv", index=False)
            return 'Success'

    except Exception as e:
        print(f'❌ Failed to generate audio for {ourRow["item_id"]}: {translation_text[:50]}... - Error: {e}')
        return 'Error'
