# generate audio using ElevenLabs
import os
import pandas as pd
import numpy as np
from elevenlabs import play, save
from elevenlabs.client import ElevenLabs
import utilities.utilities as u
import utilities.config as conf
from ELabs import elevenlabs_utilities
import time
import sys

from typing import Optional
audio_client: Optional[ElevenLabs] = None

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

def get_voice_id(voice_name, lang_code, client: ElevenLabs):
    """
    Get the voice ID from voice name using the elevenlabs_utilities function
    """
    try:
        # Get the voice dictionary for the language
        voice_dict = elevenlabs_utilities.list_voices(lang_code, client=client)

        # Exact name match in filtered list
        if voice_name in voice_dict:
            voice_id = voice_dict[voice_name]
            print(f"✓ Found voice '{voice_name}' with ID: {voice_id}")
            return voice_id

        # Fallback: search across all accessible voices by name (case-insensitive)
        try:
            all_voices = client.voices.get_all().voices
            for v in all_voices:
                if (v.name or '').strip().lower() == voice_name.strip().lower():
                    print(
                        f"✓ Found voice by global search '{voice_name}' with ID: {v.voice_id} (label language: {v.labels.get('language')})"
                    )
                    return v.voice_id
        except Exception:
            pass

        print(f"❌ Voice '{voice_name}' not found for {lang_code}")
        print(f"Available (filtered) voices: {list(voice_dict.keys())}")
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
        audio_base_dir: str = None,
        output_format: str = "mp3_22050_32"
        ):
        
    # basically we want to iterate through rows,
    # specifying the column (language) we want translated.
    # We assume that our caller has already massaged our input file as needed
    # columnts might be:
    # item_id,labels,en,es-CO,de,context

    inputData = pd.read_csv(input_file_path)
    masterData = pd.read_csv(master_file_path)

    # build API call
    # Initialize ElevenLabs client once per call
    global audio_client
    if audio_client is None:
        # Prefer explicit api_key; otherwise read from env inside utilities
        audio_client = elevenlabs_utilities.get_client(api_key)
    
    stats = {'Errors': 0, 'Processed' : 0, 'NoTask': 0}
    
    # Look up voice ID once at the beginning to avoid repeated API calls
    print(f"Looking up voice '{voice}' for language '{lang_code}'...")
    # Try exact lang_code first; if missing, try base language
    voice_id = get_voice_id(voice, lang_code, client=audio_client)
    if voice_id is None and '-' in lang_code:
        base = lang_code.split('-')[0]
        print(f"Voice not found for {lang_code}, trying base language '{base}'...")
        voice_id = get_voice_id(voice, base, client=audio_client)
    if voice_id is None:
        print(f"❌ Cannot proceed: voice '{voice}' not found for {lang_code}")
        return {'Errors': len(inputData), 'Processed': 0, 'NoTask': 0, 'Voice': voice}

    total_items = len(inputData)
    for idx, (index, ourRow) in enumerate(inputData.iterrows(), 1):
        try:
            print(f"\n📊 Progress: {idx}/{total_items} ({idx/total_items*100:.1f}%) - Processing '{ourRow['item_id']}'")
            
            result = processRow(index, ourRow, lang_code=lang_code, voice=voice, voice_id=voice_id, \
                                audio_base_dir=audio_base_dir, masterData=masterData, \
                                headers=None, output_format=output_format)
            
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
                
            # Show running totals every 10 items
            if idx % 10 == 0:
                print(f"📈 Running totals: ✅ {stats['Processed']} processed, ❌ {stats['Errors']} errors, ⏭️  {stats['NoTask']} skipped")
                
        except KeyboardInterrupt:
            print(f"\n🛑 Process interrupted by user at item {idx}/{total_items}")
            print(f"📊 Final stats: ✅ {stats['Processed']} processed, ❌ {stats['Errors']} errors, ⏭️  {stats['NoTask']} skipped")
            print(f"💡 You can resume by running the same command again - it will skip already generated files.")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Unexpected error processing '{ourRow['item_id']}': {str(e)}")
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
               masterData, audio_base_dir, headers, output_format: str = "mp3_22050_56"):

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
    
    def generate_audio_with_retry():
        audio = audio_client.text_to_speech.convert(
            text=translation_text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            output_format=output_format
        )

        # Create a response object that mimics what PlayHT returns for consistency
        class AudioResponse:
            def __init__(self, content):
                self.content = content
                self.status_code = 200
        
        # The new API returns audio data directly as bytes
        if hasattr(audio, 'content'):
            audio_bytes = audio.content
        elif hasattr(audio, '__iter__') and not isinstance(audio, (str, bytes)):
            # If it's a generator, convert to bytes
            audio_bytes = b''.join(audio)
        else:
            # If it's already bytes
            audio_bytes = audio
            
        return AudioResponse(audio_bytes)
    
    try:
        # Use retry mechanism for the API call
        audioData = retry_with_backoff(generate_audio_with_retry, max_retries=3, base_delay=2)
        
        if audioData is None:
            print(f"❌ Failed to generate audio for '{ourRow['item_id']}' after all retries")
            return 'Error'
        
        print(f"✅ Successfully generated {len(audioData.content)} bytes of audio for '{ourRow['item_id']}'")
        
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
