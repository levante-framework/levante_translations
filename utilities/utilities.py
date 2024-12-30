# wrapper so trying to create a directory that exists doesn't fail
import os

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path

# find the full path for an audio file to write
# we want to echo the repo & GCP heirarchy to save re-doing later
# e.g. <base>/task/language/shared/<item>.mp3
def audio_file_path(task_name, item_name, audio_base_dir, lang_code):
    full_file_folder = \
        os.path.join(task_name, item_name, audio_base_dir, lang_code, "shared")
    if not os.path.exists(full_file_folder):
        os.makedirs(full_file_folder, exist_ok=True)
    full_file_path = os.path.join(full_file_folder, item_name + ".mp3")
    return full_file_path
