from PlayHt import playHt_tts
# for future Google integration
# from google import google_cloud
# from google import google_tts

import pandas as pd
import os
import numpy as np
import sys

def generate_audio(lang_code, voice): 
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


    # Turn into dataframe so we can do any needed edits
    translationData = pd.read_csv(conf.translatedTextURL)

    # Trying to get save files co-erced into our desired path
    audio_base_dir = "audio_files"

    # Current export from Crowdin has columns of
    # identifier -> item_id
    # labels -> task
    # text -> en
    translationData = translationData.rename(columns={'identifier': 'item_id'})
    translationData = translationData.rename(columns={'text': 'en'})
    #translationData = translationData.rename(columns={'labels': 'task'})

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

    # Now we have masterData & translationData
    # We want to compare the appropriate column to see if we need to generate

    # translationData is the exported csv from Crowdin
    # masterData is our state of generated audio files

    for index, ourRow in translationData.iterrows():
        print(f'Our lang: {lang_code} our row lang: {ourRow["en"]}')
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
    retry_seconds = 1
    playHt_tts.main(
        input_file_path = diff_file_name, 
        lang_code = lang_code,
        retry_seconds= retry_seconds,
        master_file_path=master_file_path, 
        voice=voice, 
        audio_base_dir = audio_base_dir)

"""
    Args:
        
        lang_code (str): A locale code, e.g.: 'es-CO' and the name for the column to select for tts transcription
        voice (str): The name of the play.ht voice to use, e.g.: 'es-CO-SalomeNeural'
    """

def main(
    lang_code: str,
    voice: str,
    user_id: str = None,
    api_key: str = None
):
    generate_audio(lang_code=lang_code, voice=voice)
        
if __name__ == "__main__":
    main(*sys.argv[1:])

# IF we're happy with the output then
# gsutil rsync -d -r <src> gs://<bucket> 
