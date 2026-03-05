import pandas as pd
import os
import numpy as np
import sys
import argparse
import sqlite3
import utilities.config as conf
import utilities.utilities as u

# TTS imports are now conditional - moved to where they're actually used

# Remove module-level cache; always fetch latest when generating
# language_dict = conf.get_languages()


def _load_translation_data_from_csv(csv_path: str) -> pd.DataFrame:
    print(f"Loading source translations from: {csv_path}")
    try:
        # Try with robust CSV parser first
        from utilities.robust_csv_parser import parse_csv_robust
        data_list = parse_csv_robust(csv_path)
        translationData = pd.DataFrame(data_list)
        print(f"SUCCESS: Loaded {len(translationData)} translation items with robust parser")
    except Exception as robust_error:
        print(f"Robust parser failed: {robust_error}")
        print("Falling back to standard pandas parsing...")
        try:
            # Try with explicit UTF-8 encoding
            translationData = pd.read_csv(csv_path, encoding='utf-8')
            print(f"SUCCESS: Loaded {len(translationData)} translation items")
        except UnicodeDecodeError:
            print("UTF-8 encoding failed, trying latin1...")
            # If UTF-8 fails, try with a more permissive encoding
            translationData = pd.read_csv(csv_path, encoding='latin1')
            print(f"SUCCESS: Loaded {len(translationData)} translation items with latin1 encoding")
        except FileNotFoundError:
            print(f"ERROR: Source translation file not found: {csv_path}")
            print("Make sure the file exists in the correct location.")
            raise
        except Exception as e:
            print(f"ERROR: Failed to load source translations: {str(e)}")
            raise

    # Handle mixed column formats in the CSV
    translationData = translationData.rename(columns={'identifier': 'item_id'})
    # If both 'identifier' and 'item_id' exist due to upstream processing, drop the extra
    if 'identifier' in translationData.columns and 'item_id' in translationData.columns:
        try:
            translationData = translationData.drop(columns=['identifier'])
            print("Dropped duplicate 'identifier' column after renaming to 'item_id'")
        except Exception:
            pass

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

    # Convert any language columns that use "_" to use "-" instead
    # (e.g., "es_AR" -> "es-AR", "en_US" -> "en-US")
    translationData = u.normalize_language_columns(translationData)

    return translationData


def _load_translation_data_from_sqlite(
    db_path: str,
    language_dict: dict
) -> pd.DataFrame:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"SQLite DB not found: {db_path}")

    print(f"Loading source translations from SQLite: {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            ("items_current",),
        ).fetchone()
        if not table_exists:
            raise ValueError(
                "SQLite DB is missing required table 'items_current'. "
                "Run utilities/itembank_by_task_regen_report.py to initialize the versioned schema."
            )
        rows = conn.execute(
            "SELECT item_id, task, lang, source_text, target_text FROM items_current"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        raise ValueError(f"No rows found in SQLite translations table (items_current) of {db_path}")

    items: dict = {}
    for item_id, task, lang, source_text, target_text in rows:
        if item_id is None or lang is None:
            continue
        item_id_str = str(item_id)
        item = items.setdefault(item_id_str, {"item_id": item_id_str})
        if task and not item.get("labels"):
            item["labels"] = str(task)

        text_val = target_text if target_text not in (None, "") else source_text
        if text_val not in (None, ""):
            item[str(lang)] = text_val

    translationData = pd.DataFrame(items.values())
    translationData = u.normalize_language_columns(translationData)

    # Ensure language columns exist for configured languages
    for lang_config in language_dict.values():
        lang_code = lang_config["lang_code"]
        if lang_code not in translationData.columns:
            translationData[lang_code] = None

    print(f"SUCCESS: Loaded {len(translationData)} translation items from SQLite")
    return translationData


def generate_audio(
    language,
    force_regenerate: bool = False,
    hi_fi: bool = False,
    force_id: bool = False,
    translation_source: str = "sqlite",
    sqlite_db_path: str = "tmp/itembank_by_task_regen.sqlite"
):
    print("=== Starting Audio Generation for Levante Translations ===")
    print(f"Target Language: {language}")
    print(f"Using simplified folder structure: audio_files/<language_code>/")
    print("Audio quality: " + ("High-fidelity (mp3_44100_64)" if hi_fi else "Compressed default (mp3_22050_32)"))
    if force_regenerate:
        print("🔄 FORCE MODE: Will regenerate all audio files, even if they exist")
    if force_id:
        print("🔄 FORCE-ID MODE: Will regenerate files without ID3 tags")
    else:
        print("⏭️  SKIP MODE: Will skip existing files without ID3 tags (use --force-id to regenerate)")
    print("="*60)

    # Always re-read latest language configuration (from GCS when available)
    try:
        language_dict = conf.get_languages()
    except Exception as e:
        print(f"⚠️  Warning: Could not load latest language configuration: {e}")
        language_dict = {}
    
    if translation_source == "csv":
        # Fetch the latest translations from l10n_pending branch
        print("📥 Fetching latest translations from l10n_pending branch...")
        try:
            from utilities.fetch_latest_translations import fetch_translations
            if not fetch_translations(force=True):
                print("❌ Failed to fetch latest translations - continuing with local copy")
            else:
                print("✅ Successfully updated to latest translations")
        except Exception as e:
            print(f"⚠️  Warning: Could not fetch latest translations: {e}")
            print("   Continuing with local copy...")
        print("="*60)
    
# Retrieve translations.csv from the repo
# NOTE: If special characters get munged, will need to
#       arrange for an export/download directly from Crowdin
#
# For testing don't co-host with Text Translation repo
    #input_file_name = "translated_fixed.csv"
    input_file_name = conf.item_bank_translations
    diff_file_name = "needed_item_bank_translations.csv"
    master_file_path = None

# Raw Github URL for translations uploaded from Crowdin
# for debugging use the service branch, later change to main
# Right now this is our repo, but it might wind up somewhere else,
# so use a webURL

    selected_translation_source = translation_source
    try:
        if translation_source == "sqlite":
            translationData = _load_translation_data_from_sqlite(sqlite_db_path, language_dict)
        else:
            translationData = _load_translation_data_from_csv(conf.item_bank_translations)
    except Exception as e:
        if translation_source == "sqlite":
            print(f"⚠️  Warning: Failed to load from SQLite ({e}). Falling back to CSV.")
            try:
                translationData = _load_translation_data_from_csv(conf.item_bank_translations)
                selected_translation_source = "csv"
            except Exception as csv_error:
                print(f"ERROR: Failed to load source translations from CSV: {csv_error}")
                return
        else:
            print(f"ERROR: Failed to load source translations: {e}")
            return

    # Trying to get save files co-erced into our desired path
    audio_base_dir = "audio_files"

    # DEBUG: Show available columns
    print(f"Available columns in translation data: {list(translationData.columns)}")
    
    # All data that we need to make sure is or has been generated
    if selected_translation_source == "csv":
        translationData.to_csv(input_file_name, encoding='utf-8', errors='replace')

    masterData = None
    if selected_translation_source == "csv":
        master_file_path = "translation_master.csv"
        # The "master file" of already generated strings
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
            masterData = translationData.copy(deep=True)

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
    else:
        print("Using SQLite-backed generation state; skipping translation_master.csv cache.")

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
    
    # If force-regenerate is enabled, clear master cache for this language
    if force_regenerate and masterData is not None and master_file_path:
        try:
            if lang_code not in masterData.columns:
                print(f"Master data missing column {lang_code}; creating it before clearing cache...")
                masterData[lang_code] = None
            else:
                print(f"🧹 Clearing translation cache for language column '{lang_code}' in {master_file_path}")
                masterData[lang_code] = None
            masterData.to_csv(master_file_path, index=False, encoding='utf-8', errors='replace')
            print(f"✅ Cleared master cache for {lang_code}")
        except Exception as e:
            print(f"⚠️  Warning: Failed to clear master cache for {lang_code}: {e}")
    elif force_regenerate:
        print("🔄 FORCE MODE: skipping translation_master.csv cache clear in SQLite mode.")

    # DEBUG: Show language column status
    print(f"Looking for language column: {lang_code}")
    if lang_code in translationData.columns:
        non_null_count = translationData[lang_code].notna().sum()
        print(f"Found {lang_code} column with {non_null_count} non-null entries out of {len(translationData)}")
    else:
        # Column not present; we will attempt fallbacks per-row (base code and close variants)
        print(f"Column {lang_code} not found in CSV; will attempt fallbacks during row processing")

    # Now that we have the current language, handle column renaming carefully
    # Don't rename the column we're currently working with to avoid cache issues
    # Do not rename masterData language columns implicitly

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
        # Resolve translation text from primary language column, then fallbacks.
        # Important: fallbacks should also run when the primary column exists but is empty.
        candidates = [lang_code]
        base = (lang_code or '').split('-')[0]
        if base and base != lang_code:
            candidates.append(base)

        regional_fallbacks = {
            'es-AR': 'es-CO',
            'es-MX': 'es-CO',
            'fr-FR': 'fr-CA',
            'de-CH': 'de',
        }
        reverse_regional = {
            'en': 'en-US',
            'de': 'de-DE',
            'es': 'es-CO',
            'fr': 'fr-CA',
            'nl': 'nl-NL',
        }
        cand = regional_fallbacks.get(lang_code)
        if cand:
            candidates.append(cand)
        reverse_cand = reverse_regional.get(lang_code)
        if reverse_cand:
            candidates.append(reverse_cand)

        simplified_lang_codes = {
            'en-US': 'en', 'es-CO': 'es', 'de-DE': 'de', 'fr-CA': 'fr', 'nl-NL': 'nl'
        }
        simp = simplified_lang_codes.get(lang_code)
        if simp:
            candidates.append(simp)

        # Deduplicate while preserving order.
        candidates = list(dict.fromkeys(candidates))

        translation_text = None
        used_col = None
        for cand in candidates:
            if cand in ourRow:
                candidate_text = ourRow[cand]
                if not (pd.isna(candidate_text) or candidate_text == '' or candidate_text is None):
                    translation_text = candidate_text
                    used_col = cand
                    break

        if translation_text is None:
            print(f"Warning: No translation found for {lang_code} (or fallbacks) in row {ourRow['item_id']}")
            continue
        if used_col and used_col != lang_code:
            print(f"Using fallback column '{used_col}' for {lang_code} in row {ourRow['item_id']}")
            
        print(f'Our lang: {lang_code} our row lang: {translation_text[:50]}...')
        
        # Ensure scalar string item_id even if duplicate column names exist
        item_id_raw = ourRow['item_id']
        try:
            # If duplicate labels caused a Series, take first non-null
            if hasattr(item_id_raw, 'iloc'):
                item_id = str(item_id_raw.iloc[0])
            else:
                item_id = str(item_id_raw)
        except Exception:
            item_id = str(item_id_raw)
        
        # Check if audio file needs regeneration (text/voice validation)
        from utilities.utilities import audio_file_path
        from utilities.audio_validation import needs_regeneration
        
        # Safely coerce task name to string
        task_name_val = ourRow.get('labels', 'general')
        task_name = str(task_name_val.iloc[0]) if hasattr(task_name_val, 'iloc') else str(task_name_val)
        expected_audio_path = audio_file_path(task_name, item_id, audio_base_dir, lang_code)
        
        if not force_regenerate:
            # Use validation system to check if regeneration is needed
            needs_regen, reason = needs_regeneration(
                expected_audio_path,
                translation_text,
                voice,
                service,
                lang_code,
                force_id
            )
            
            if not needs_regen:
                print(f'✅ Audio file is up to date: {expected_audio_path}')
                continue
            else:
                print(f'🔄 Audio needs regeneration: {reason}')
        else:
            print(f'🔄 FORCE MODE: Regenerating existing file: {expected_audio_path}')
        
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
            # Import PlayHT only when needed
            try:
                from PlayHt import playHt_tts
            except ImportError as e:
                print(f"Error importing PlayHT: {e}")
                print("PlayHT dependencies may not be properly installed or configured")
                return None
                
            result = playHt_tts.main(
                input_file_path = diff_file_name, 
                lang_code = lang_code,
                retry_seconds= retry_seconds,
                master_file_path=master_file_path, 
                voice=voice, 
                audio_base_dir = audio_base_dir)
        else:
            # Import ElevenLabs only when needed
            try:
                from ELabs import elevenlabs_tts
            except ImportError as e:
                print(f"Error importing ElevenLabs: {e}")
                print("ElevenLabs dependencies may not be properly installed or configured")
                return None
                
            result = elevenlabs_tts.main(
                input_file_path = diff_file_name, 
                lang_code = lang_code,
                retry_seconds= retry_seconds,
                master_file_path=master_file_path, 
                voice=voice, 
                audio_base_dir = audio_base_dir,
                output_format = ("mp3_44100_64" if hi_fi else "mp3_22050_32")
            )
        
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
        print(f"   Items attempted this run: {total_attempted}")
    else:
        print(f"   Items attempted this run: {len(diffData) if not diffData.empty else 0}")
    
    print(f"\n   📊 Dataset Overview:")
    print(f"   Total items in dataset: {len(translationData)}")
    
    # Count items with valid translations
    valid_translation_count = 0
    empty_translation_count = 0
    for index, row in translationData.iterrows():
        translation = row.get(lang_code, '')
        if pd.isna(translation) or translation == '' or translation is None:
            empty_translation_count += 1
        else:
            valid_translation_count += 1
    
    print(f"   Items with valid {lang_code} translations: {valid_translation_count}")
    if empty_translation_count > 0:
        print(f"   Items with empty/missing translations: {empty_translation_count}")
    
    # Count total audio files for this language (for reference)
    try:
        total_audio_files = int(u.count_audio_files(lang_code))
        print(f"\n   💾 Audio Files on Disk:")
        print(f"   Total existing audio files: {total_audio_files}")
        print(f"   Expected audio files: {valid_translation_count}")
        
        diff = total_audio_files - valid_translation_count
        if diff > 0:
            print(f"   ⚠️  Extra files on disk: {diff} (possibly orphaned)")
        elif diff < 0:
            print(f"   ⚠️  Missing files: {abs(diff)}")
        else:
            print(f"   ✅ Audio files match expected count")
    except Exception as e:
        print(f"\n   💾 Audio Files on Disk:")
        print(f"   Total existing audio files: Unable to count (error: {e})")
    
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
    api_key: str = None,
    force_regenerate: bool = False,
    hi_fi: bool = False,
    validate_only: bool = False,
    force_id: bool = False,
    translation_source: str = "sqlite",
    sqlite_db_path: str = "tmp/itembank_by_task_regen.sqlite"
):
    
    if validate_only:
        # Only validate audio files without regenerating
        from utilities.audio_validation import validate_audio_files_for_language
        import utilities.config as conf
        
        try:
            language_dict = conf.get_languages()
            if translation_source == "sqlite":
                translation_data = _load_translation_data_from_sqlite(sqlite_db_path, language_dict)
            else:
                translation_data = _load_translation_data_from_csv(conf.item_bank_translations)
            audio_base_dir = "audio_files"
            
            items_to_regenerate = validate_audio_files_for_language(
                language, language_dict, translation_data, audio_base_dir, force_id
            )
            
            if not items_to_regenerate.empty:
                print(f"\n📝 Items that need regeneration saved to: needed_item_bank_translations.csv")
                items_to_regenerate.to_csv("needed_item_bank_translations.csv", index=False)
            else:
                print(f"\n✅ All audio files for {language} are up to date!")
                
        except Exception as e:
            print(f"❌ Validation failed: {e}")
            return
    else:
        # Normal audio generation
        generate_audio(
            language=language,
            force_regenerate=force_regenerate,
            hi_fi=hi_fi,
            force_id=force_id,
            translation_source=translation_source,
            sqlite_db_path=sqlite_db_path
        )
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate speech audio for translations')
    parser.add_argument('language', help='Language to generate audio for (e.g., German, Spanish, French, Dutch, English)')
    parser.add_argument('--force', '-f', action='store_true', 
                        help='Force regenerate: regenerates ALL audio items using the current voice from config')
    parser.add_argument('--force-id', action='store_true', 
                        help='Force regenerate files without ID3 tags (by default, files without ID3 tags are skipped)')
    parser.add_argument('--user-id', help='User ID (optional)')
    parser.add_argument('--api-key', help='API key (optional)')
    parser.add_argument('--hi-fi', action='store_true', help='Use high-fidelity MP3 (mp3_44100_64) instead of compressed default')
    parser.add_argument('--validate-only', action='store_true', help='Only validate audio files without regenerating them')
    parser.add_argument('--translation-source', choices=['sqlite', 'csv'], default='sqlite',
                        help='Source for translations (default: sqlite)')
    parser.add_argument('--sqlite-db', default='tmp/itembank_by_task_regen.sqlite',
                        help='Path to SQLite DB from itembank_by_task regen report')
    
    args = parser.parse_args()
    
    main(language=args.language, 
         user_id=args.user_id, 
         api_key=args.api_key,
         force_regenerate=args.force,
         hi_fi=args.hi_fi,
         validate_only=args.validate_only,
         force_id=args.force_id,
         translation_source=args.translation_source,
         sqlite_db_path=args.sqlite_db)

# IF we're happy with the output then
# gsutil rsync -d -r <src> gs://<bucket> 
