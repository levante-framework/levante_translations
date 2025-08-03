from PlayHt import playHt_tts
from ELabs import elevenlabs_tts

import pandas as pd
import os
import numpy as np
import sys
import utilities.config as conf

language_dict = conf.get_languages()

def generate_audio(language): 
    print("=== Starting Audio Generation for Levante Translations ===")
    print(f"Target Language: {language}")
    print(f"Using simplified folder structure: audio_files/<language_code>/")
    print("="*60)
    
# Retrieve translations.csv from the repo
# NOTE: If special characters get munged, will need to
#       arrange for an export/download directly from Crowdin
#
# For testing don't co-host with Text Translation repo
    #input_file_name = "translated_fixed.csv"
    input_file_name = conf.item_bank_translations
    diff_file_name = "needed_item_bank_translations.csv"
    master_file_path = "translation_master.csv"

# Raw Github URL for translations uploaded from Crowdin
# for debugging use the service branch, later change to main
# Right now this is our repo, but it might wind up somewhere else,
# so use a webURL

    # Turn into dataframe so we can do any needed edits
    print(f"Loading source translations from: {conf.item_bank_translations}")
    try:
        # Try with robust CSV parser first
        from utilities.robust_csv_parser import parse_csv_robust
        data_list = parse_csv_robust(conf.item_bank_translations)
        translationData = pd.DataFrame(data_list)
        print(f"SUCCESS: Loaded {len(translationData)} translation items with robust parser")
    except Exception as robust_error:
        print(f"Robust parser failed: {robust_error}")
        print("Falling back to standard pandas parsing...")
        try:
            # Try with explicit UTF-8 encoding
            translationData = pd.read_csv(conf.item_bank_translations, encoding='utf-8')
            print(f"SUCCESS: Loaded {len(translationData)} translation items")
        except UnicodeDecodeError:
            print("UTF-8 encoding failed, trying latin1...")
            # If UTF-8 fails, try with a more permissive encoding
            translationData = pd.read_csv(conf.item_bank_translations, encoding='latin1')
            print(f"SUCCESS: Loaded {len(translationData)} translation items with latin1 encoding")
        except FileNotFoundError:
            print(f"ERROR: Source translation file not found: {conf.item_bank_translations}")
            print(f"Make sure the file exists in the correct location.")
            return
        except Exception as e:
            print(f"ERROR: Failed to load source translations: {str(e)}")
            return

    # Trying to get save files co-erced into our desired path
    audio_base_dir = "audio_files"

    # DEBUG: Show available columns
    print(f"Available columns in CSV: {list(translationData.columns)}")
    
    # Current export from Crowdin has columns of
    # identifier -> item_id
    # labels -> task
    # Handle mixed column formats in the CSV
    translationData = translationData.rename(columns={'identifier': 'item_id'})
    
    # Handle duplicate language columns (keep the one that has more data)
    if 'es-CO' in translationData.columns and 'es-co' in translationData.columns:
        # Count non-null values in each column
        es_co_count = translationData['es-co'].notna().sum()
        es_CO_count = translationData['es-CO'].notna().sum()
        print(f"Found both es-co ({es_co_count} entries) and es-CO ({es_CO_count} entries)")
        
        # Keep the one with more data, drop the other
        if es_CO_count > es_co_count:
            print("Using es-CO column (has more data)")
            translationData = translationData.drop(columns=['es-co'])
            translationData = translationData.rename(columns={'es-CO': 'es-co'})
        else:
            print("Using es-co column (has more data)")
            translationData = translationData.drop(columns=['es-CO'])
    
    # Apply other column renames safely
    if 'fr-CA' in translationData.columns and conf.LANGUAGE_CODES['French'] != 'fr-CA':
        translationData = translationData.rename(columns={'fr-CA': conf.LANGUAGE_CODES['French']})

    #translationData = translationData.rename(columns={'labels': 'task'})

    # All data that we need to make sure is or has been generated
    translationData.to_csv(input_file_name, encoding='utf-8', errors='replace')

    # The "master file" of already generated strings
    # There is/may also be an existing .csv file (translation_master.csv)
    if os.path.exists(master_file_path):
        try:
            print(f"Loading existing master file: {master_file_path}")
            # Try robust parser first
            try:
                from utilities.robust_csv_parser import parse_csv_robust
                master_data_list = parse_csv_robust(master_file_path)
                masterData = pd.DataFrame(master_data_list)
                print(f"SUCCESS: Loaded {len(masterData)} rows with {len(masterData.columns)} columns using robust parser")
            except Exception as robust_error:
                print(f"Robust parser failed for master file: {robust_error}")
                print("Falling back to standard pandas parsing...")
                masterData = pd.read_csv(master_file_path)
                print(f"SUCCESS: Loaded {len(masterData)} rows with {len(masterData.columns)} columns")
            
        except pd.errors.ParserError as e:
            print(f"ERROR: The master CSV file '{master_file_path}' is corrupted or has formatting issues.")
            print(f"Details: {str(e)}")
            print(f"Solution: Use the robust CSV parser to fix it:")
            print(f"  python utilities/robust_csv_parser.py {master_file_path} {master_file_path}_fixed")
            print(f"Or delete '{master_file_path}' and run the script again to create a fresh one.")
            return
            
        except Exception as e:
            print(f"ERROR: Failed to read master file '{master_file_path}'")
            print(f"Details: {str(e)}")
            print(f"Solution: Check file permissions, try the robust parser, or delete the file to create a fresh one.")
            return
        
        # Add any missing language columns that might be needed
        for lang_config in language_dict.values():
            lang_code_temp = lang_config['lang_code']
            if lang_code_temp not in masterData.columns:
                masterData[lang_code_temp] = None
                print(f"Added missing column {lang_code_temp} to master data")
                
    else:
        # Create a "null state" generation status file
        # so that we know what needs to be generated
        masterData = translationData.copy(deep = True)
        
        # Initialize all language columns from config
        for lang_config in language_dict.values():
            lang_code = lang_config['lang_code']
            masterData[lang_code] = None
        masterData.to_csv(master_file_path, index=False, encoding='utf-8', errors='replace')
        # Create baseline masterData

    # add blank rows in master data for any missing items that are in translation data
    blank_row = [""] * (len(masterData.columns) - 1)
    currently_tracked_ids = list(masterData["item_id"])
    modified_master_data = False
    for item in translationData["item_id"]:
        if item not in currently_tracked_ids:
          masterData.loc[len(masterData)] = [item, *blank_row]
          modified_master_data = True
    
    if modified_master_data: 
      masterData.to_csv(master_file_path, encoding='utf-8', errors='replace', index=False)

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
    
    # DEBUG: Show language column status
    print(f"Looking for language column: {lang_code}")
    if lang_code in translationData.columns:
        non_null_count = translationData[lang_code].notna().sum()
        print(f"Found {lang_code} column with {non_null_count} non-null entries out of {len(translationData)}")
    else:
        print(f"Column {lang_code} not found in CSV")

    # Now that we have the current language, handle column renaming carefully
    # Don't rename the column we're currently working with to avoid cache issues
    if os.path.exists("translation_master.csv"):
        master_column_mapping = {
            'en-US': 'en',
            'es-CO': 'es', 
            'de-DE': 'de',
            'fr-CA': 'fr',
            'nl-NL': 'nl'
        }
        
        # Rename columns in master data to match our simplified format
        # BUT skip renaming the column we're currently working with to avoid cache issues
        for old_col, new_col in master_column_mapping.items():
            if old_col in masterData.columns and old_col != lang_code:
                masterData = masterData.rename(columns={old_col: new_col})
                print(f"Renamed master column {old_col} -> {new_col}")

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
            # Check if the value is null/empty
            if pd.isna(translation_text) or translation_text == '' or translation_text is None:
                print(f"Warning: Empty translation for {lang_code} in row {ourRow['item_id']}")
                continue
        else:
            # Check if we renamed the column - map back to simplified version
            simplified_lang_codes = {
                'es-CO': 'es',
                'fr-CA': 'fr', 
                'nl-NL': 'nl'
            }
            simplified_code = simplified_lang_codes.get(lang_code, lang_code)
            if simplified_code in ourRow:
                translation_text = ourRow[simplified_code]
                # Check if the value is null/empty
                if pd.isna(translation_text) or translation_text == '' or translation_text is None:
                    print(f"Warning: Empty translation for {simplified_code} in row {ourRow['item_id']}")
                    continue
            else:
                print(f"Warning: No translation found for {lang_code} in row {ourRow['item_id']}")
                continue
            
        print(f'Our lang: {lang_code} our row lang: {translation_text[:50]}...')
        
        item_id = ourRow['item_id']
        
        # Check if audio file already exists for this item
        from utilities.utilities import audio_file_path
        task_name = ourRow.get('labels', 'general')  # Use labels as task name, fallback to 'general'
        expected_audio_path = audio_file_path(task_name, item_id, audio_base_dir, lang_code)
        
        if os.path.exists(expected_audio_path):
            print(f'Audio file already exists: {expected_audio_path}')
            continue
        
        print(f'Need to generate audio for: {item_id} -> {expected_audio_path}')

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
        
        print(f"\nStarting audio generation for {language}...")
        print(f"Processing {len(diffData)} items that need audio generation")
        
        # Initialize result variable
        result = None
        
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
        
        print(f"Audio generation completed for {language}")
        
    else:
        print(f"No new audio files needed for {language} - all translations are up to date!")
        result = None  # No processing occurred
    
    # Display final statistics
    print(f"\nFinal Statistics for {language}:")
    print(f"   Language: {language}")
    print(f"   Language Code: {lang_code}")
    print(f"   Service: {service}")
    print(f"   Voice: {voice[:50]}..." if len(voice) > 50 else f"   Voice: {voice}")
    
    # Show actual processing results if available
    if result and hasattr(result, '__getitem__') and result:
        print(f"   Items successfully processed: {result.get('Processed', 0)}")
        print(f"   Items with errors: {result.get('Errors', 0)}")
        print(f"   Items with no task assigned: {result.get('NoTask', 0)}")
        total_attempted = result.get('Processed', 0) + result.get('Errors', 0) + result.get('NoTask', 0)
        print(f"   Total items attempted: {total_attempted}")
    else:
        print(f"   Items attempted this run: {len(diffData) if not diffData.empty else 0}")
    
    print(f"   Total items in dataset: {len(translationData)}")
    
    # Count total audio files for this language (for reference)
    try:
        import utilities.utilities as u
        total_audio_files = u.count_audio_files(lang_code)
        print(f"   Total existing audio files on disk: {total_audio_files}")
    except:
        print(f"   Total existing audio files on disk: Unable to count")
    
    print(f"\nAudio generation for {language} complete!")
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
