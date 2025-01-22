# generate audio using ElevenLabs
import os
import pandas as pd
from elevenlabs import play
from elevenlabs.client import ElevenLabs
import utilities as u

client = ElevenLabs(api_key=os.getenv('ELEVEN_API_KEY'))
# These are the two functions we need to support

def list_voices(lang_code):
    # Fetch all available voices
    voices = client.voices.get_all()
    for voice in voices:
        print(repr(voice))

    # Function to filter voices by language
    def filter_voices_by_language(voices, language):
        return [voice for voice in voices if language.lower() in str(voice[3]).lower()]
    # 
    #Example: List all Korean voices
    korean_voices = filter_voices_by_language(voices, "korean")

    # Print the filtered voices
    for voice in korean_voices:
        print(f"Name: {voice.name}, ID: {voice.voice_id}")
        
def get_audio(text, voice):
    print("TBD")

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

    inputData = pd.read_csv(input_file_path, index_col=0)
    masterData = pd.read_csv(master_file_path, index_col=0)

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

def example():
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

# Called to process each row of the input csv (now dataframe)
def processRow(index, ourRow, lang_code, voice, \
               masterData, audio_base_dir, headers):

    # reset local error count for new row
    errorCount = 0
    retrySeconds = 1 # sort of arbitrary backoff to recheck status

    if not (type(ourRow['labels']) == type('str')):
        print(f"Item {ourRow['item_id']} doesn't have task assigned")
        return 'NoTask'

    audio_client = ElevenLabs(api_key=os.getenv('ELEVEN_API_KEY'))

    audio = audio_client.generate(
        text=ourRow[lang_code],
        #voice=voice,
        model="eleven_multilingual_v2"
    )

    with open(u.audio_file_path(ourRow["labels"], ourRow["item_id"], \
                                audio_base_dir, lang_code), "wb") as file:
        file.write(audio)

        # Update our "cache" of successful transcriptions                            
        masterData[lang_code] = \
            np.where(masterData["item_id"] == ourRow["item_id"], \
            ourRow[lang_code], masterData[lang_code])

        # write as we go, so erroring out doesn't lose progress
        # Translated, so we can save it to a master sheet
        masterData.to_csv("translation_master.csv")
        # finished with the if statement        
        return 'Success'    

