from PlayHt import playHt_tts
from ELabs import elevenlabs_tts

import pandas as pd
import os
import numpy as np
import sys
import utilities.config as conf

language_dict = conf.get_languages()

def generate_audio(language): 
# Retrieve translations.csv from the repo
# NOTE: If special characters get munged, will need to
#       arrange for an export/download directly from Crowdin
#
# For testing don't co-host with Text Translation repo
    #input_file_name = "translated_fixed.csv"
    input_file_name = conf.item_bank_translations
    diff_file_name = "needed_item_bank_translations.csv"
    master_file_path = "../translation_master.csv"

# Raw Github URL for translations uploaded from Crowdin
# for debugging use the service branch, later change to main
# Right now this is our repo, but it might wind up somewhere else,
# so use a webURL

    # Turn into dataframe so we can do any needed edits
    try:
        # Try with explicit UTF-8 encoding
        translationData = pd.read_csv(conf.item_bank_translations, encoding='utf-8')
    except UnicodeDecodeError:
        # If UTF-8 fails, try with a more permissive encoding
        translationData = pd.read_csv(conf.item_bank_translations, encoding='latin1')

    # Trying to get save files co-erced into our desired path
    audio_base_dir = "audio_files"

    # Current export from Crowdin has columns of
    # identifier -> item_id
    # labels -> task
    # text -> en
    translationData = translationData.rename(columns={'identifier': 'item_id'})
    translationData = translationData.rename(columns={'es-CO': 'es-co'})
    translationData = translationData.rename(columns={'fr': 'fr-ca'})

    #translationData = translationData.rename(columns={'labels': 'task'})

    # All data that we need to make sure is or has been generated
    translationData.to_csv(input_file_name, encoding='utf-8', errors='replace')

    # The "master file" of already generated strings
    # There is/may also be an existing .csv file (translation_master.csv)
    if os.path.exists(master_file_path):
        masterData = pd.read_csv(master_file_path)
    else:
        # Create a "null state" generation status file
        # so that we know what needs to be generated
        masterData = translationData.copy(deep = True)
        
        # Initialize all language columns from config
        for language in language_dict.values():
            lang_code = language['lang_code']
            masterData[lang_code] = None
        masterData.to_csv(master_file_path, encoding='utf-8', errors='replace')
        # Create baseline masterData

    # Now we have masterData & translationData
    # We want to compare the appropriate column to see if we need to generate

    # translationData is the exported csv from Crowdin
    # masterData is our state of generated audio files

    # get lang_code from language config
    our_language = language_dict[language]
    lang_code = our_language['lang_code']
    # We need to support different services for different languages
    service = our_language['service']
    voice = our_language['voice']

    # remove the diff file to reset
    if os.path.exists(diff_file_name):
        try:
            os.remove(diff_file_name)
        except PermissionError:
            # Force removal of locked file on Windows
            import stat
            os.chmod(diff_file_name, stat.S_IWRITE)
            os.remove(diff_file_name)
            
    # Initialize diffData to an empty DataFrame before the loop
    diffData = pd.DataFrame()
    
    for index, ourRow in translationData.iterrows():
        # Check if the column exists, if not try the original column name
        if lang_code in ourRow:
            translation_text = ourRow[lang_code]
        elif lang_code == 'en-US' and 'en' in ourRow:
            translation_text = ourRow['en']
        elif lang_code == 'de-DE' and 'de' in ourRow:
            translation_text = ourRow['de']
        elif lang_code == 'es-CO' and 'es-CO' in ourRow:
            translation_text = ourRow['es-CO']
        elif lang_code == 'fr-CA' and 'fr-CA' in ourRow:
            translation_text = ourRow['fr-CA']
        elif lang_code == 'nl-NL' and 'nl' in ourRow:
            translation_text = ourRow['nl']
        else:
            print(f"Warning: No translation found for {lang_code} in row {ourRow['item_id']}")
            continue
            
        print(f'Our lang: {lang_code} our row lang: {translation_text[:50]}...')
        # check to see if our lang_code is already matched 
        # this is the language phrase we need to see if we have generated
        translationNeeded = translation_text
        item_id = ourRow['item_id']

        # Find what we have generated for that phrase currently
        try:
            matched_rows = masterData.loc[masterData['item_id'] == item_id, lang_code]
            if len(matched_rows) > 0:
                translationCurrent = matched_rows.iloc[0]
            else:
                translationCurrent = None
        except Exception as e:
            print(f"Error finding translation for {item_id}: {e}")
            translationCurrent = None
    
        if translationCurrent == translationNeeded:
            continue

        # for debugging
        print(f'Current: {translationCurrent}, Needed: {translationNeeded}')

        try:
            # Create a DataFrame with the same columns as translationData if diffData is empty
            if diffData.empty:
                diffData = pd.DataFrame(columns=translationData.columns)
            if isinstance(diffData, pd.DataFrame):
                diffData.loc[len(diffData)] = ourRow
            else:
                print("The variable 'diffData' exists but is not a DataFrame")
        except NameError:
            # This block should never be reached now that we initialize diffData
            starterRow = {'item_id': ourRow['item_id'], 'labels': ourRow['labels']}
            # Add all language columns from config
            for language in language_dict.values():
                lang_code = language['lang_code']
                starterRow[lang_code] = ourRow[lang_code]
            diffData = pd.DataFrame(starterRow, index=[0])

    if not diffData.empty:

        # for debugging
        #print(f'Writing diff data {diffData}')

        # diff_file_name contains the items that need audio
        # Write diff data and ensure file is properly closed
        with open(diff_file_name, 'w', encoding='utf-8', errors='replace') as f:
            diffData.to_csv(f)
        retry_seconds = 1
        
        if service == 'PlayHt':
            playHt_tts.main(
                input_file_path = diff_file_name, 
                lang_code = lang_code,
                retry_seconds= retry_seconds,
                master_file_path=master_file_path, 
                voice=voice, 
                audio_base_dir = audio_base_dir)
        else:
            elevenlabs_tts.main(
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
    language: str,
    user_id: str = None,
    api_key: str = None
):
    
    # is a language which can then
    # trigger the lang_code and voice
    generate_audio(language=language)
        
if __name__ == "__main__":
    main(*sys.argv[1:])

# IF we're happy with the output then
# gsutil rsync -d -r <src> gs://<bucket> 
