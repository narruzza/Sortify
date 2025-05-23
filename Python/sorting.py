import os
import shutil
import traceback
from PyQt6.QtCore import QThread, pyqtSignal

from Python.genre_aliases import GENRE_ALIASES
from Python.metadata import get_metadata, get_bpm, get_key, update_bpm_metadata
from Python.utils import sanitize_filename, delete_empty_folders

class SortWorker(QThread):
    update_progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)

#Initializes the sort worker thread with all parameters
    def __init__(self, files, folder_path, sort_order, bpm_enabled, preview):
        super().__init__()
        self.files = files
        self.folder_path = folder_path
        self.sort_order = sort_order
        self.bpm_enabled = bpm_enabled
        self.preview = preview
        self.last_sort_map = {}

#Sorts songs into genres despite metadata aliases
    def build_sort_path(self, meta):
        parts = []
        for crit in self.sort_order:
            if crit == "Artist":
                parts.append(meta.get("Artist", "Unknown Artist"))
            elif crit == "Genre":
                genre = str(meta.get("Genre", "Unknown Genre")).strip().lower()
                parts.append(GENRE_ALIASES.get(genre, genre.title()))
            elif crit == "BPM Range":
                bpm = meta.get("BPM")
                parts.append(f"{int(bpm // 10) * 10}-{int(bpm // 10) * 10 + 9} BPM" if bpm else "Unknown BPM")
            elif crit == "Alphabetical":
                char = meta["filename"][0].upper()
                parts.append(char if char.isalpha() else "#")
            elif crit == "Key":
                parts.append(meta.get("Key", "Unknown Key"))
        return os.path.join(*parts)

#Builds destination path based on metadata and selected sort order
    def run(self):
        try:
            for i, file_path in enumerate(self.files):
                if not os.path.exists(file_path):
                    continue
                meta = get_metadata(file_path)
                if "error" in meta:
                    self.update_progress.emit(i + 1, f"⚠️ Skipped: {meta['filename']} (metadata error: {meta['error']})")
                    continue

                if "BPM Range" in self.sort_order and ("BPM" not in meta) and self.bpm_enabled:
                    meta["BPM"] = get_bpm(file_path)
                    if file_path.lower().endswith(".mp3"):
                        update_bpm_metadata(file_path, meta["BPM"])

                if "Key" in self.sort_order:
                    meta["Key"] = get_key(file_path)

                folder_structure = self.build_sort_path(meta)
                destination_dir = os.path.join(self.folder_path, folder_structure)
                os.makedirs(destination_dir, exist_ok=True)

                sanitized_name = sanitize_filename(os.path.basename(file_path))
                dest_path = os.path.join(destination_dir, sanitized_name)

                if self.preview:
                    self.update_progress.emit(i + 1, f"\U0001F4C2 {meta['filename']} → {folder_structure}")
                else:
                    shutil.move(file_path, dest_path)
                    self.last_sort_map[file_path] = dest_path
                    self.update_progress.emit(i + 1, f"\u2705 Moved: {meta['filename']} → {folder_structure}")

            msg = "\nPreview Complete." if self.preview else "\n\u2705 Sorting Complete."
            if not self.preview:
                delete_empty_folders(self.folder_path)
            self.finished.emit(msg)
        except Exception as e:
            error_msg = traceback.format_exc()
            self.finished.emit(f"\n\u274C Error: {e}\n{error_msg}")
