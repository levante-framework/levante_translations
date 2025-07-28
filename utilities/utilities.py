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

# Add mutagen for ID3v2 tag handling
try:
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, COMM, TXXX
    from mutagen.mp3 import MP3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    print("Warning: mutagen not available. ID3 tag functions will not work.")
    print("Install with: pip install mutagen")

# Default audio tags template - create copies when needed
# Standard ID3v2 tags
audio_tags = {
    'title': None,
    'artist': None,
    'album': None,
    'date': None,
    'genre': None,
    'comment': None,
    'created': None

}

# Standard ID3v2 tag fields (these use specific ID3 frames)
STANDARD_ID3_FIELDS = {'title', 'artist', 'album', 'date', 'genre', 'comment'}


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
    
        # Play the temporary file - block=True ensures it waits for completion
        playsound.playsound(temp_filename, block=True)
    finally:
        # Clean up the temporary file after playback completes
        try:
            os.unlink(temp_filename)
        except OSError:
            # File might already be deleted or in use, ignore the error
            pass

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

        

def read_id3_tags(file_path):
    """
    Read ID3v2 tags from an MP3 file, including custom fields.
    
    Args:
        file_path (str): Path to the MP3 file
        
    Returns:
        dict: Dictionary containing ID3 tag information, or empty dict if no tags or error
    """
    if not MUTAGEN_AVAILABLE:
        print("Warning: mutagen not available. Cannot read ID3 tags.")
        return {}
    
    if not os.path.exists(file_path):
        print(f"Warning: File {file_path} does not exist.")
        return {}
    
    try:
        audio_file = MP3(file_path, ID3=ID3)
        tags = {}
        
        # Read standard ID3v2 tags
        if audio_file.tags:
            tags['title'] = str(audio_file.tags.get('TIT2', [''])[0]) if audio_file.tags.get('TIT2') else ''
            tags['artist'] = str(audio_file.tags.get('TPE1', [''])[0]) if audio_file.tags.get('TPE1') else ''
            tags['album'] = str(audio_file.tags.get('TALB', [''])[0]) if audio_file.tags.get('TALB') else ''
            tags['date'] = str(audio_file.tags.get('TDRC', [''])[0]) if audio_file.tags.get('TDRC') else ''
            tags['genre'] = str(audio_file.tags.get('TCON', [''])[0]) if audio_file.tags.get('TCON') else ''
            
            # Read comment (if any)
            comment_frames = audio_file.tags.getall('COMM')
            tags['comment'] = str(comment_frames[0].text[0]) if comment_frames else ''
            
            # Read custom fields (TXXX frames)
            txxx_frames = audio_file.tags.getall('TXXX')
            for frame in txxx_frames:
                if frame.desc and frame.text:
                    # Use the description as the field name
                    custom_field_name = frame.desc
                    custom_field_value = str(frame.text[0]) if frame.text else ''
                    tags[custom_field_name] = custom_field_value
        
        return tags
        
    except Exception as e:
        print(f"Error reading ID3 tags from {file_path}: {e}")
        return {}


def write_id3_tags(file_path, tags):
    """
    Write ID3v2 tags to an MP3 file, including custom fields.
    
    Args:
        file_path (str): Path to the MP3 file
        tags (dict): Dictionary of tags to write (uses audio_tags template structure)
                    Any fields beyond standard ID3v2 fields will be stored as custom TXXX frames
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not MUTAGEN_AVAILABLE:
        print("Warning: mutagen not available. Cannot write ID3 tags.")
        return False
    
    if not os.path.exists(file_path):
        print(f"Warning: File {file_path} does not exist.")
        return False
    
    if not tags:
        print("Warning: No tags dictionary provided.")
        return False
    
    try:
        audio_file = MP3(file_path, ID3=ID3)
        
        # Create ID3 tag if it doesn't exist
        if audio_file.tags is None:
            audio_file.add_tags()
        
        # Write standard ID3v2 tags
        if tags.get('title'):
            audio_file.tags.add(TIT2(encoding=3, text=tags['title']))
        if tags.get('artist'):
            audio_file.tags.add(TPE1(encoding=3, text=tags['artist']))
        if tags.get('album'):
            audio_file.tags.add(TALB(encoding=3, text=tags['album']))
        if tags.get('date'):
            audio_file.tags.add(TDRC(encoding=3, text=tags['date']))
        if tags.get('genre'):
            audio_file.tags.add(TCON(encoding=3, text=tags['genre']))
        if tags.get('comment'):
            audio_file.tags.add(COMM(encoding=3, lang='eng', desc='', text=tags['comment']))
        
        # Write custom fields as TXXX frames
        for field_name, field_value in tags.items():
            if field_name not in STANDARD_ID3_FIELDS and field_value:
                # Store custom fields as user-defined text frames (TXXX)
                audio_file.tags.add(TXXX(encoding=3, desc=field_name, text=str(field_value)))
        
        # Save the tags
        audio_file.save()
        return True
        
    except Exception as e:
        print(f"Error writing ID3 tags to {file_path}: {e}")
        return False


def save_audio(ourRow, lang_code, service, audioData, audio_base_dir, masterData, voice=""):
    file_path = audio_file_path(ourRow["labels"], ourRow["item_id"], audio_base_dir, lang_code)
    
    with open(file_path, "wb") as file:
        file.write(audioData.content)

    # Add ID3v2 tags to the saved MP3 file
    try:
        # Create a copy of the default audio_tags template
        tags = audio_tags.copy()
        
        # Populate the tags with metadata from the row data
        tags['title'] = f"{ourRow['item_id']}"  # Use item_id as title
        tags['artist'] = f"Levante Framework - {service}"  # Service used
        tags['album'] = f"{ourRow['labels']}"  # Task name as album
        tags['date'] = str(pd.Timestamp.now().year)  # Current year
        tags['genre'] = "Speech Synthesis"
        tags['created'] = str(pd.Timestamp.now())  # Full timestamp when file was created
        
        # Add our custom tags
        tags['lang_code'] = lang_code
        tags['service'] = service
        tags['voice'] = voice

        # Create a descriptive comment with translation text
        comment_text = str(ourRow.get(lang_code, ''))[:100]  # First 100 chars of text
        if len(str(ourRow.get(lang_code, ''))) > 100:
            comment_text += "..."
        tags['comment'] = comment_text
        
        # Write ID3 tags using the tags dictionary
        write_id3_tags(file_path=file_path, tags=tags)
        
    except Exception as e:
        print(f"Warning: Could not add ID3 tags to {file_path}: {e}")

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
