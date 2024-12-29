# Simplified interface to Play.Ht for translations

import os
import sys
import pandas as pd
import logging
import time
import numpy as np
import requests
from dataclasses import dataclass, replace
from datetime import datetime

# Constants for API, in this case for Play.Ht, maybe
API_URL = "https://api.play.ht/api/v1/convert"
STATUS_URL = "https://api.play.ht/api/v1/articleStatus"

# wrapper so trying to create a directory that exists doesn't fail
def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path

# find the full path for an audio file to write
# we want to echo the repo & GCP heirarchy to save re-doing later
# e.g. <base>/task/language/shared/<item>.mp3
def audio_file_path(task_name, item_name, audio_base_dir, lang_code):
    full_file_folder = \
        os.path.join(audio_base_dir, task_name, lang_code, "shared")
    if not os.path.exists(full_file_folder):
        os.makedirs(full_file_folder, exist_ok=True)
    full_file_path = os.path.join(full_file_folder, item_name + ".mp3")
    return full_file_path

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

    # Assemble data packet to pass to PlayHT
    # see https://docs.play.ht/reference/api-convert-tts-standard-premium-voices
    data = {
        # content needs to be an array, even if we only do one at a time
        "content" : [ourRow[lang_code]],
        "voice": voice,
        "title": "Levante Audio", # not sure where this matters?
        "trimSilence": True
    }


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
                        with open(audio_file_path(ourRow["labels"], ourRow["item_id"], \
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

    print(f"Processed: {stats['Processed']}, Errors: {stats['Errors']}, \
          No Task: {stats['NoTask']}")

if __name__ == "__main__":
    main(*sys.argv[1:])

