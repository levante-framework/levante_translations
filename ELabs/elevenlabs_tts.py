# generate audio using ElevenLabs
import os
import pandas as pd
import numpy as np
from elevenlabs import play
from elevenlabs import save
from elevenlabs.client import ElevenLabs
import utilities.utilities as u

# this doesn't work?
# from elevenlabs import set_api_key

# this doesn't work?
# set_api_key(os.getenv('ELEVEN_API_KEY'))

audio_client = ElevenLabs(api_key=os.getenv('elevenlabs_test'))

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

    # Rename columns to match lang_codes used in the script
    masterData = masterData.rename(columns={'en': 'en-US',
                                             'de': 'de-DE',
                                             'es': 'es-CO',
                                             'fr': 'fr-CA',
                                             'nl': 'nl-NL'})

    # build API call
    headers = {
        'Authorization': api_key,
        'X-USER-ID': user_id,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    stats = {'Errors': 0, 'Processed' : 0, 'NoTask': 0}

    for index, ourRow in inputData.iterrows():

        result = processRow(index, ourRow, lang_code=lang_code, voice=voice, \
                            audio_base_dir=audio_base_dir, masterData=masterData, \
                            headers=headers)
        
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


# Called to process each row of the input csv (now dataframe)
def processRow(index, ourRow, lang_code, voice, \
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
            voice=voice,
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
            masterData.to_csv("translation_master.csv")
            return 'Success'

    except Exception as e:
        print(f'❌ Failed to generate audio for {ourRow["item_id"]}: {translation_text[:50]}... - Error: {e}')
        return 'Failure'
