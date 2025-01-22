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

## PASTED FROM PLAYHT -- NEEDS TO BE MODIFIED!
# Called to process each row of the input csv (now dataframe)
def processRow(index, ourRow, lang_code, voice, \
               masterData, audio_base_dir, headers):

    # reset local error count for new row
    errorCount = 0
    retrySeconds = 1 # sort of arbitrary backoff to recheck status

    # we should potentially filter these out when we generate diffs
    # instead of waiting until now. But at some point we might
    # want to generate them as part of an "unassigned" task or something
    if not (type(ourRow['labels']) == type('str')):
        print(f"Item {ourRow['item_id']} doesn't have task assigned")
        return 'NoTask'

    # we want to begin to support SSML, so convert to that format:
    #ssmlText = u.html_to_ssml(ourRow[lang_code])
    # However SSML requires different params, so experiment in the
    # dashboard first!
    data = {
        # content needs to be a list, even if we only do one at a time
        "content" : [ourRow[lang_code]],
        "voice": voice,
        "title": "Levante Audio", # not sure where this matters?
        "trimSilence": True
    }

    ## NEED TO REPLACE WITH ELEVEN LABS API
    ## Use a While loop so we can retry odd failure cases
    while True and errorCount < 5:
        response = requests.post(API_URL, headers=headers, json=data) 

        # In some cases we get an odd error that appears to suggest the
        # transcription is still in progress, but it never finishes
        # to handle that case, we abandon that transaction & start a new one
        restartRequest = False
        # 201 means that we got a response of some kind
        if response.status_code == 201:
            # results are packed into a json object
            result = response.json()
            logging.info(f"convert_tts: response for item={ourRow['item_id']}: transcriptionId={result['transcriptionId']}")
        else:
            logging.error(f"convert_tts: no response for item={ourRow['item_id']}: status code={response.status_code}")
            # sometimes a retry works after no response
            errorCount += 1
            continue

        # status is a little awkward to parse. Some errors aren't exactly errors
        json_status = response.json()

        if "transcriptionId" in json_status:
            # This means that we've successfully started the transcription
            transcription_id = json_status["transcriptionId"]
            print(f"Conversion initiated for: {ourRow['item_id']}")
        
            # Poll the status until completion or we get 5 error returns
            while True and errorCount < 5 and restartRequest == False:
                downloadURL = None # clear each time
                status_params = {"transcriptionId": transcription_id}
                status_response = requests.get(STATUS_URL, params=status_params, headers=headers)
                status_data = status_response.json()

                # Some errors are "fatal", some just mean a retry is needed
                if 'error' in status_data:
                    if status_data['error'] == True: # and \
                        #status_data['message'] != 'Transcription still in progress':
                        print(f'Error translating {ourRow["item_id"]}')
                        restartRequest = True
                        errorCount += 1
                        continue # we want to start the loop over

                # Our transcription is successful                        
                if status_data["converted"] == True:
                    print(f"Conversion for {ourRow['item_id']} completed successfully!")
                    #print(f"Audio URL: {status_data['audioUrl']}")
                    # set the download URL for retrieval or get it right here?
                    downloadURL = status_data['audioUrl']

                    # At this point we should have an "audioURL" that we can retrieve
                    # and then write out to the appropriate directory
                    audioData = requests.get(downloadURL)

                    # open file for writing
                    # Download the MP3 file
                    if audioData.status_code == 200 and ourRow['labels'] != float('nan'):
                        restartRequest = False
                        errorCount = 0
                        with open(u.audio_file_path(ourRow["labels"], ourRow["item_id"], \
                                audio_base_dir, lang_code), "wb") as file:
                            file.write(audioData.content)

                            # Update our "cache" of successful transcriptions                            
                            masterData[lang_code] = \
                                np.where(masterData["item_id"] == ourRow["item_id"], \
                                ourRow[lang_code], masterData[lang_code])

                            # write as we go, so erroring out doesn't lose progress
                            # Translated, so we can save it to a master sheet
                            masterData.to_csv("translation_master.csv")
                            # finished with the if statement        
                            return 'Success'    
                else:
                    # print(f"Conversion in progress. Status: {status_data['converted']}")
                    # currently most tasks complet in about 1 second, so .5 seconds
                    # seems like a good tradeoff between "over-polling" and "over-waiting"
                    time.sleep(retrySeconds)  # Wait before checking again
            else:
                continue
    else:
        # we've tried several times
        return 'Error'

list_voices('en')

