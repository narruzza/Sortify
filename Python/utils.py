import os
import re

#Recursively finds all music files in the selected folder
def scan_folder(folder):
    music_files = []
    for root, _, files in os.walk(folder):
        for file in files:
            if file.lower().endswith((".mp3", ".wav", ".flac", ".aiff")):
                music_files.append(os.path.join(root, file))
    return music_files

#Removes all empty folders from the selected root
def delete_empty_folders(folder):
    for root, dirs, _ in os.walk(folder, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            if not os.listdir(dir_path):
                os.rmdir(dir_path)

#Replaces some characters in filenames
def sanitize_filename(filename):
    return re.sub(r'[\\/:*?"<>|]', '_', filename)