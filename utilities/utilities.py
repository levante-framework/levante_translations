# wrapper so trying to create a directory that exists doesn't fail
import os
import textwrap
import subprocess

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path

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
# Execute the command and capture the output
    raw_result = subprocess.run(f'ls audio_files/*/{lang_code}/shared/* | wc -l', shell=True, capture_output=True, text=True)
    return raw_result.stdout.strip()

# debug/test code
# foo = count_audio_files('en')
# print(f'Audio: {foo}')