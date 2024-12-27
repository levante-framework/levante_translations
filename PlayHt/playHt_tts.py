# Simplified interface to Play.Ht for translations

import os
import sys
import pandas as pd
import requests
import logging
import time
import numpy as np
from dataclasses import dataclass, replace
from datetime import datetime

# Constants for API, in this case for Play.Ht, maybe
API_URL = "https://api.play.ht/api/v1/convert"
STATUS_URL = "https://api.play.ht/api/v1/articleStatus"

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path

def main(
        input_file_path: str,
        master_file_path: str,
        lang_code: str,
        voice: str,
        user_id: str = None,
        api_key: str = None,
        output_file_path: str = None,
        item_id_column: str = 'item_id',
        audio_base_dir: str = None,
        # save_task_audio: str = None,  # saving audio only for specified task (e.g. 'theory-of-mind')
    ):
    """
    The main function to process the transcription jobs.

    Args:
        input_file_path (str): The path of the input CSV file where details of text and of past tts transactions are extracted.
        lang_code (str): A locale code, e.g.: 'es-CO' and the name for the column to select for tts transcription
        voice (str): The name of the play.ht voice to use, e.g.: 'es-CO-SalomeNeural'
        user_id (str, optional): The user ID for authentication. If not provided, it will be read from the environment variable 'PLAY_DOT_HT_USER_ID'.
        api_key (str, optional): The api key authenticating our API calls. If not provided, it will be read from the environment variable 'PLAY_DOT_HT_API_KEY'.
        item_id_column (str, optional): column name in the input file for stable and unique item ID. Defaults to 'item_id'.
        audio_dir (str, optional): The directory to store the audio files. Defaults to "audio_files/{lang_code}/".
    """
    
    # find the full path for an audio file to write
    # we want to echo the repo & GCP heirarchy to save re-doing later
    # e.g. <base>/task/language/shared/<item>.mp3
    def audio_file_path(task_name, item_name):
        full_file_folder = \
            os.path.join(audio_base_dir, task_name,
            lang_code, "shared")
        if not os.path.exists(full_file_folder):
            os.makedirs(full_file_folder, exist_ok=True)
        full_file_path = os.path.join(full_file_folder, item_name + ".mp3")
        return full_file_path
    

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

    # to check translation status should we use translation time
    # or whether the output audio file exists?

    # build API call
    headers = {
        'Authorization': api_key,
        'X-USER-ID': user_id,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    for index, ourRow in inputData.iterrows():

        # we should potentially filter these out when we generate diffs
        if not (type(ourRow['labels']) == type('str')):
            print("Item {ourRow['item_id']} doesn't have task assigned")
            continue
        data = {
            # content needs to be an array, even if we only do one at a time
            "content" : [ourRow[lang_code]],
            "voice": voice,
            "title": "Individual Audio",
            "trimSilence": True
        }
        # see https://docs.play.ht/reference/api-convert-tts-standard-premium-voices
        response = requests.post(API_URL, headers=headers, json=data) 

        if response.status_code == 201:
            result = response.json()
            logging.info(f"convert_tts: response for item={ourRow['item_id']}: transcriptionId={result['transcriptionId']}")
        else:
            logging.error(f"convert_tts: no response for item={ourRow['item_id']}: status code={response.status_code}")
            #return (status='error') # , resp_body=f'NO RESPONSE (convert), status code={response.status_code}')
            continue

        json_status = response.json()
        if "transcriptionId" in json_status:
            transcription_id = json_status["transcriptionId"]
            print(f"Conversion initiated. Transcription ID: {transcription_id}")
        
            # Poll the status until completion
            while True:
                downloadURL = None # clear each time
                status_params = {"transcriptionId": transcription_id}
                status_response = requests.get(STATUS_URL, params=status_params, headers=headers)
                status_data = status_response.json()

                if status_data["converted"] == True:
                    print(f"Conversion for {ourRow['item_id']} completed successfully!")
                    print(f"Audio URL: {status_data['audioUrl']}")
                    # set the download URL for retrieval or get it right here?
                    downloadURL = status_data['audioUrl']

                    # At this point we should have an "audioURL" that we can retrieve
                    # and then write out to the appropriate directory
                    audioData = requests.get(downloadURL)

                    # open file for writing
                    # Download the MP3 file
                    if audioData.status_code == 200 and ourRow['labels'] != float('nan'):
                        with open(audio_file_path(ourRow["labels"], ourRow["item_id"]), "wb") as file:
                            file.write(audioData.content)
                            # Write label ourRow in PD as translated?
                            # write content to masterData
                            
                            # this doesn't work right!! Extra Column already added
                            masterData[lang_code] = \
                                np.where(masterData["item_id"] == ourRow["item_id"], \
                                          ourRow[lang_code], masterData[lang_code])

                            # write as we go, so erroring out doesn't lose progress
                            # Translated, so we can save it to a master sheet
                            masterData.to_csv("translation_master.csv")
                        break
                    else:
                        print("Failed to download the MP3 file")
                else:
                    # print(f"Conversion in progress. Status: {status_data['converted']}")
                    # currently most tasks complet in about 1 second, so .5 seconds
                    # seems like a good tradeoff between "over-polling" and "over-waiting"
                    time.sleep(.5)  # Wait before checking again
    

if __name__ == "__main__":
    main(*sys.argv[1:])

