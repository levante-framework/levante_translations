from PlayHt import playHt_tts
# for future Google integration
# from google import google_cloud
# from google import google_tts

import pandas as pd
import os
import numpy as np
import sys
import csv
import shutil
import urllib

"""

    Args:
        
        ## Hard-coded so far
        lang_code (str): A locale code, e.g.: 'es-CO' and the name for the column to select for tts transcription
        voice (str): The name of the play.ht voice to use, e.g.: 'es-CO-SalomeNeural'

    """

# Retrieve translations.csv from the repo
# NOTE: If special characters get munged, will need to
#       arrange for an export/download directly from Crowdin
#
# For testing don't co-host with Text Translation repo
input_file_name = "item_bank_translations.csv"
diff_file_name = "needed_item_bank_translations.csv"
master_file_path = "translation_master.csv"

# Raw Github URL for translations uploaded from Crowdin
# for debugging use the service branch, later change to main
# Right now this is our repo, but it might wind up somewhere else,
# so use a webURL
#### Switch to audio-generation repo once there is a real Crowdin account
#    with permission to write to it
webURL = "https://raw.githubusercontent.com/digital-pro/levante-audio/l10n_main2/translated.csv"

# Turn into dataframe so we can do any needed edits
translationData = pd.read_csv(webURL)


# Current export from Crowdin has columns of
# identifier -> item_id
# labels -> task
# text -> en-US

# Columns that are okay
# es-CO OK
# de OK

# Trying to get save files co-erced into our desired path
audio_base_dir = "audio_files"

# column edits to match what we need
translationData = translationData.rename(columns={'identifier': 'item_id'})
translationData = translationData.rename(columns={'text': 'en'})
#translationData = translationData.rename(columns={'labels': 'task'})

# we need to stash translation data, now or later
# NOTE: This is the full data -- write back to our file

# All data that we need to make sure is or has been generated
translationData.to_csv(input_file_name)

# The "master file" of already generated strings
# There is/may also be an existing .csv file (translation_master.csv)
if os.path.exists("translation_master.csv"):
    masterData = pd.read_csv(master_file_path)
else:
    # Create a "null state" generation status file
    # so that we know what needs to be generated
    masterData = translationData.copy(deep = True)
    masterData['en'] = None
    masterData['es-CO'] = None
    masterData['de'] = None
    masterData.to_csv(master_file_path)
    # Create baseline masterData

# Currently used play.ht voices for reference
# Hard-coded as a test 
# should get these as parameters

voice = 'es-CO-SalomeNeural'
lang_code = 'es-CO'
retry_seconds = .5

#voice = 'VickiNeural'
#lang_code = 'de'
#retry_seconds = 5

#voice = 'en-US-AriaNeural'
#lang_code = 'en'
#retry_seconds = .5

# We can check for filler columns if they the same as English??
# But sometimes they are the same??
# Or maybe generate unless we get an error (then what?)
source_lang_code = 'en'


# Now we have masterData & translationData
# We want to compare the appropriate column to see if we need to generate

# Find differences in the language code column
# translationData is the exported csv from Crowdin
# masterData is our state of generated audio files

for index, ourRow in translationData.iterrows():
    # check to see if our lang_code is already matched 
    # this is the language phrase we need to see if we have generated
    translationNeeded = ourRow[lang_code]
    item_id = ourRow['item_id']

    # Find what we have generated for that phrase currently
    try:
        translationCurrent = masterData.loc[masterData['item_id'] == item_id, lang_code].iloc[0]
    except:
        translationCurrent = masterData.loc[masterData['item_id'] == item_id, lang_code][1]
    
    if translationCurrent == translationNeeded:
        continue

    try:
        if isinstance(diffData, pd.DataFrame):

            ##### This Still doesn't work:)
            diffData.loc[len(diffData)] = ourRow
        else:
            print("The variable 'diffData' exists but is not a DataFrame")
    except NameError:
        # seed diffData with ourRow
        # There _has_ to be a more flexible way!!
        starterRow = {'item_id' : ourRow['item_id'],
                      'en'      : ourRow['en'],
                      'es-CO'   : ourRow['es-CO'],
                      'de'      : ourRow['de'],
                      'labels'  : ourRow['labels']
                      }
        diffData = pd.DataFrame(starterRow, index=[0])

diffData.to_csv(diff_file_name)

"""
Args:

input_file_path (str): The path of the input CSV file where details of text and of past tts transactions are extracted.
        
user_id (str, optional): The user ID for authentication. If not provided, it will be read from the environment variable 'PLAY_DOT_HT_USER_ID'.
api_key (str, optional): The api key authenticating our API calls. If not provided, it will be read from the environment variable 'PLAY_DOT_HT_API_KEY'.
output_file_path (str, optional): The path for the output CSV files to create and where to store the state of our transactions. Defaults to './snapshots_{user_id}/tts_{timestamp}_{user_id}.csv'
audio_dir (str, optional): The directory to store the audio files. Defaults to "audio_files/{lang_code}/".

"""
playHt_tts.main(
    input_file_path = diff_file_name, 
    lang_code = lang_code,
    master_file_path=master_file_path, 
    voice=voice, 
    retry_seconds = retry_seconds,
    audio_base_dir = audio_base_dir)

# IF we're happy with the output then
# gsutil rsync -d -r <src> gs://<bucket> 

def main(
    lang_code: str,
    voice: str,
    #user_id: str = None,
    #api_key: str = None,
):
    if __name__ == "__main__":
        main(*sys.argv[1:])
