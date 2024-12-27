import playHt_tts
import pandas as pd
import os
import numpy as np
import csv
import shutil
import urllib

"""
    To pass to the main function to process the transcription jobs.

    Args:
        input_file_path (str): The path of the input CSV file where details of text and of past tts transactions are extracted.
        lang_code (str): A locale code, e.g.: 'es-CO' and the name for the column to select for tts transcription
        voice (str): The name of the play.ht voice to use, e.g.: 'es-CO-SalomeNeural'
        user_id (str, optional): The user ID for authentication. If not provided, it will be read from the environment variable 'PLAY_DOT_HT_USER_ID'.
        api_key (str, optional): The api key authenticating our API calls. If not provided, it will be read from the environment variable 'PLAY_DOT_HT_API_KEY'.
        overwrite_input_file_str (str, optional): A boolean string to indicate whether to overwrite the input file. Defaults to 'False'.
        output_file_path (str, optional): The path for the output CSV files to create and where to store the state of our transactions. Defaults to './snapshots_{user_id}/tts_{timestamp}_{user_id}.csv'
        item_id_column (str, optional): column name in the input file for stable and unique item ID. Defaults to 'item_id'.
        rate_limit_per_minute (str, optional): The rate limit expected for the endpoint. Defaults to 50.
        audio_dir (str, optional): The directory to store the audio files. Defaults to "audio_files/{lang_code}/".
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
webURL = "https://raw.githubusercontent.com/digital-pro/levante-audio/l10n_main/translated.csv"

# Turn into dataframe so we can do any needed edits
# Pandas can now read directly from the web
# or if we need more control we could use requests

# or could read directly if no massaging needed
translationData = pd.read_csv(webURL)

### TOTALLY EXPERIMENTAL
#translationData = translationData.drop(translationData.columns[0], axis=1)

# Current export from Crowdin has columns of
# identifier -> item_id
# labels -> task
# text -> en-US

# Columns that are okay
# es-CO OK
# de OK

# TBD: whether we want to write directly to the repo
#audio_dir = "c:/levante/levante-test/audio_files/{lang_code}/"

# Trying to get save files co-erced into our desired path
audio_base_dir = "audio_files"

# remove "Sheet" rows
#remove_sheet_rows(translationData)
# column edits to match what we need
translationData = translationData.rename(columns={'identifier': 'item_id'})
translationData = translationData.rename(columns={'text': 'en'})
#translationData = translationData.rename(columns={'labels': 'task'})

# We start with a baseline of None, but what if many prompts
# have already been translated. Can we start from there?
# That would involve reading in the previous version
# And looking for None, plus any new prompts in the current file

# we need to stash translation data, now or later
# NOTE: This is the full data -- write back to our file

# clean up the Sheet references in the Context column if they exist
# not sure we need this any more
# translationData['context'] = translationData['context'].str.replace(r'\nSheet: translation-items-v1', '', regex=True)

translationData.to_csv(input_file_name)

# There is/may also be an existing .csv file (translation_master.csv)
if os.path.exists("translation_master.csv"):
    masterData = pd.read_csv(master_file_path)
else:
    # Create a "null state" translation status file
    # so that we know what needs to be generated
    masterData = translationData.copy(deep = True)
    masterData['en'] = None
    masterData['es-CO'] = None
    masterData['de'] = None
    masterData.to_csv(master_file_path)
    # Create baseline masterData

# Current play.ht voices for reference
# es-CO -- es-CO-SalomeNeural
# de -- VickiNeural
# en-US -- en-US-AriaNeural

# Hard-coded as a test 
# should get these as parameters
voice = 'es-CO-SalomeNeural'
lang_code = 'es-CO'

# Now we have masterData & translationData
# We want to compare the appropriate column to see if we need to generate

# Find differences in the language code column
# translationData is the exported csv from Crowdin
# masterData is our state of generated audio files

## try/catch blocks may now be moot, since we kind of know
#  what we are doing

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
    
    #translationCurrent = masterRow[lang_code][0] # why is this a series??
    new_row = pd.DataFrame(ourRow)
    # separate for the Nan case and the tuple case
    try:
        foo = len(diffData)
        if type(translationCurrent) != 'pandas.core.series.Series':
            diffData.loc[len(diffData)] = ourRow
        elif (translationNeeded != translationCurrent[0]):
            diffData.loc[len(diffData)] = ourRow

        # Do something with the value
    except NameError:
        diffData = translationData.iloc[[index],:]     
diffData.to_csv(diff_file_name)

playHt_tts.main(input_file_path = diff_file_name, lang_code = lang_code,
             master_file_path=master_file_path, voice=voice, audio_base_dir = audio_base_dir)

# IF we're happy with the output then
# gsutil rsync -d -r <src> gs://<bucket> 