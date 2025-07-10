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
    # Handle mixed column formats in the CSV
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
        
        # Handle column format mismatch between old master file and new system
        # The master file might have old column names, so rename them to match our new format
        master_column_mapping = {
            'en-US': 'en',
            'es-CO': 'es', 
            'de-DE': 'de',
            'fr-CA': 'fr',
            'nl-NL': 'nl'
        }
        
        # Rename columns in master data to match our simplified format
        for old_col, new_col in master_column_mapping.items():
            if old_col in masterData.columns:
                masterData = masterData.rename(columns={old_col: new_col})
                print(f"📋 Renamed master column {old_col} -> {new_col}")
        
        # Add any missing language columns that might be needed
        for lang_config in language_dict.values():
            lang_code = lang_config['lang_code']
            if lang_code not in masterData.columns:
                masterData[lang_code] = None
                print(f"📋 Added missing column {lang_code} to master data")
                
    else:
        # Create a "null state" generation status file
        # so that we know what needs to be generated
        masterData = translationData.copy(deep = True)
        
        # Initialize all language columns from config
        for lang_config in language_dict.values():
            lang_code = lang_config['lang_code']
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
        # Check if the column exists for simplified language codes
        if lang_code in ourRow:
            translation_text = ourRow[lang_code]
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
            for lang_config in language_dict.values():
                lang_code = lang_config['lang_code']
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
        
        print(f"\n🎯 Starting audio generation for {language}...")
        print(f"📊 Processing {len(diffData)} items that need audio generation")
        
        if service == 'PlayHt':
            result = playHt_tts.main(
                input_file_path = diff_file_name, 
                lang_code = lang_code,
                retry_seconds= retry_seconds,
                master_file_path=master_file_path, 
                voice=voice, 
                audio_base_dir = audio_base_dir)
        else:
            result = elevenlabs_tts.main(
                input_file_path = diff_file_name, 
                lang_code = lang_code,
                retry_seconds= retry_seconds,
                master_file_path=master_file_path, 
                voice=voice, 
                audio_base_dir = audio_base_dir)
        
        print(f"✅ Audio generation completed for {language}")
        
    else:
        print(f"✅ No new audio files needed for {language} - all translations are up to date!")
    
    # Display final statistics
    print(f"\n📈 Final Statistics for {language}:")
    print(f"   Language: {language}")
    print(f"   Language Code: {lang_code}")
    print(f"   Service: {service}")
    print(f"   Voice: {voice[:50]}..." if len(voice) > 50 else f"   Voice: {voice}")
    
    # Count total audio files for this language
    try:
        import utilities.utilities as u
        total_audio_files = u.count_audio_files(lang_code)
        print(f"   Total Audio Files: {total_audio_files}")
    except:
        print(f"   Total Audio Files: Unable to count")
    
    print(f"   Items processed this run: {len(diffData) if not diffData.empty else 0}")
    print(f"   Total items in dataset: {len(translationData)}")
    
    print(f"\n🎉 Audio generation for {language} complete!")
    print("=" * 60)

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
    if len(sys.argv) < 2:
        print("❌ ERROR: No language specified!")
        print("Usage: python generate_speech.py <language>")
        print("Available languages: German, Spanish, French, Dutch, English")
        sys.exit(1)
    main(*sys.argv[1:])

# IF we're happy with the output then
# gsutil rsync -d -r <src> gs://<bucket> 
