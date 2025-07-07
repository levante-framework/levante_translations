# wrapper so trying to create a directory that exists doesn't fail
import os
import textwrap
import subprocess
import pandas as pd
import re
import tempfile
import playsound
import tkinter as tk
from tkinter import font as tkfont
from utilities import config as conf
from PlayHt import playHt_utilities
from ELabs import elevenlabs_utilities
import numpy as np

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def html_to_ssml(html):
    def convert_tags(html):
        # Convert <bold> tags to <emphasis> tags
        ssml = re.sub(r'<\s*bold\s*>', '<emphasis>', html)
        ssml = re.sub(r'<\s*/\s*bold\s*>', '</emphasis>', ssml)

        # Convert <br> and <p> tags to <break> tags
        # time is arbitrary
        ssml = re.sub(r'<\s*br\s*/?>', '<break time="400ms"/>', ssml)
        ssml = re.sub(r'<\s*p\s*/?>', '<break time="400ms"/>', ssml)

        return ssml

    def wrap_ssml(content):
        # Wrap the content in a properly formatted SSML string
        # PlayHt doesn't require the xml header
        #return f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis">{content}</speak>'
        return f"<speak>{content}</speak>"

    converted_content = convert_tags(html)
    ssml_output = wrap_ssml(converted_content)
    
    return ssml_output


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

def wrap_text(text, width=40):
    return "\n".join(textwrap.wrap(text, width=width))

def count_audio_files(lang_code):
    """Count audio files for a given language code, checking both old and new directory formats"""
    import glob
    
    # Map simplified codes to old codes for backward compatibility
    old_lang_codes = {
        'en': 'en-US',
        'es': 'es-CO', 
        'de': 'de-DE',
        'fr': 'fr-CA',
        'nl': 'nl-NL'
    }
    
    total_count = 0
    
    # Check new simplified directory structure
    new_pattern = f'audio_files/*/{lang_code}/shared/*.mp3'
    new_files = glob.glob(new_pattern)
    total_count += len(new_files)
    
    # Check old directory structure for backward compatibility
    old_lang_code = old_lang_codes.get(lang_code, lang_code)
    if old_lang_code != lang_code:  # Only check if there's a different old format
        old_pattern = f'audio_files/*/{old_lang_code}/shared/*.mp3'
        old_files = glob.glob(old_pattern)
        total_count += len(old_files)
    
    return str(total_count)

def play_audio_from_text(service, language, voice, text ):
    if service == 'PlayHt':
        translated_audio = playHt_utilities.get_audio(text, voice)
        if len(translated_audio) == 0:
            return
        play_data_object(translated_audio)
    elif service == 'ElevenLabs':
        # we need to look up the voice id (or not!)
        #voice_id = use_voicedict[voice]
        elevenlabs_utilities.play_audio(text, voice)
        #print("NOT IMPLEMENTED")

def store_stats(lang_code, errors, notask, voice):

    stats_file_path = 'stats.csv'
    # first initialize our statistics data
    if os.path.exists(stats_file_path):
        statsData = pd.read_csv(stats_file_path)
    else:
        # create a new dataframe
        statsData = pd.DataFrame(columns=['Language', 'Errors', 'No Task', 'Voice'])
        new_rows = [
            ['English', 0, 0 ,''],
            ['Spanish', 0, 0, ''],
            ['German', 0, 0, ''],
            ['French', 0, 0, ''],
            ['Dutch', 0, 0, '']
        ]
    
        for row in new_rows:
            statsData.loc[len(statsData)] = row
        
    if lang_code == 'en':
        language = 'English'
    elif lang_code == 'es':
        language = 'Spanish'
    elif lang_code == 'de':
        language = 'German'
    elif lang_code == 'fr':
        language = 'French'
    elif lang_code == 'nl':
        language = 'Dutch'
    else:
        return()
            
    # now that we have a DataFrame with rows modify our stats
    # Correct way to update values
    statsData.loc[statsData['Language'] == language, ['Errors', 'No Task', 'Voice']] = [errors, notask, voice]

    statsData.to_csv(stats_file_path, index=False)

def get_stats():
    if not os.path.exists(conf.stats_file_path):
        return(False)
    else:
        statsData = pd.read_csv(conf.stats_file_path)
    print(f'Stats: {statsData}')
    return(statsData)

def play_data_object(audio_data):
    # Create a temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp_filename = temp_file.name

    try:
    # Write the audio data to the temporary file
        temp_file.write(audio_data)
        temp_file.close()
    
        # Play the temporary file
        playsound.playsound(temp_filename)
    finally:
        # Clean up the temporary file
        os.unlink(temp_filename)

def show_intro_messagebox(self):
    dialog = tk.Toplevel(self)
    dialog.title("Quick notes on using the Audio Dashboard")
    bold_font = tkfont.Font(family="Helvetica", size=24, weight="bold")

    message = tk.Message(dialog, text= \
            "1. Choose a language tab.\n"
            "2. Select or search for an item of interest.\n"
            "3. That will play our current audio for the item.\n"
            "4. OPTIONALLY: Add desired SSML tags to the SSML Edit box.\n"
            "5. Choose a voice from the PlayHt or ElevenLabs dropdowns.\n"
            "   That generates audio for the text in the Editor in that voice.\n"
            "   Be a bit patient as it can take some time to generate the audio.\n", \
            width=1200, font=bold_font)
    
    # Put the dialog box somewhere useful
    x = 400
    y = 400
    dialog.geometry(f"+{x}+{y}")
    
    message.pack(padx=20, pady=20)
    
    ok_button = tk.Button(dialog, text="Let's get to it!", font=("Arial", 24), command=dialog.destroy)
    ok_button.pack(pady=10)
    dialog.transient(self)

def show_ssml_tips(self):
    dialog = tk.Toplevel(self)
    dialog.title("Quick Tips for using SSML")
    bold_font = tkfont.Font(family="Helvetica", size=24, weight="bold")

    message = tk.Message(dialog, text= \
            "<break time='1.0s'/> -- Add a pause\n"
            "<emphasis>TEXT</> -- More emphatic tone\n"
            "<p> -- Pause between paragraphs (when using PlayHt)\n" 
            "<phoneme alphabet=\"ipa\" ph=\"your-IPA-Pronunciation-here\">\n \
              word</phoneme> -- tag for IPA"
            "<phoneme alphabet=\"cmu-arpabet\" ph=\"your-CMU-pronunciation-here\">\n \
              word</phoneme> -- tag for CMU Arpabet\n"
            "Replace \"your-IPA-Pronunciation-here\" or \"your-CMU-pronunciation-here\"",
            width=1200, font=bold_font)
    
    # Put the dialog box somewhere useful
    x = 400
    y = 400
    dialog.geometry(f"+{x}+{y}")
    
    message.pack(padx=20, pady=20)
    
    ok_button = tk.Button(dialog, text="OK", font=("Arial", 24), command=dialog.destroy)
    ok_button.pack(pady=10)
    dialog.transient(self)

        

def save_audio(ourRow, lang_code, service, audioData, audio_base_dir, masterData):
    with open(audio_file_path(ourRow["labels"], ourRow["item_id"], \
        audio_base_dir, lang_code), "wb") as file:
        file.write(audioData.content)

    # Handle column format mismatch - masterData might have old column names
    # Map simplified codes to old codes for backward compatibility
    old_lang_codes = {
        'en': 'en-US',
        'es': 'es-CO', 
        'de': 'de-DE',
        'fr': 'fr-CA',
        'nl': 'nl-NL'
    }
    
    # Determine which column name to use in masterData
    master_lang_col = lang_code
    if lang_code not in masterData.columns:
        # Try the old format
        old_lang_code = old_lang_codes.get(lang_code, lang_code)
        if old_lang_code in masterData.columns:
            master_lang_col = old_lang_code
        else:
            # Add the new column if neither exists
            masterData[lang_code] = None
            master_lang_col = lang_code

    # Update our "cache" of successful transcriptions                            
    masterData[master_lang_col] = \
        np.where(masterData["item_id"] == ourRow["item_id"], \
        ourRow[lang_code], masterData[master_lang_col])

    # write as we go, so erroring out doesn't lose progress
    # Translated, so we can save it to a master sheet
    masterData.to_csv("translation_master.csv")
    # finished with the if statement        
    return 'Success'    
