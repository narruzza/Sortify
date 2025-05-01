import sys
import os
import time
import shutil
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QFileDialog,
    QVBoxLayout, QHBoxLayout, QTextEdit, QCheckBox, QComboBox, QProgressBar
)
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TXXX
import librosa


def get_bpm(file_path):
    y, sr = librosa.load(file_path, sr=None)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_env)
    return round(float(tempo[0]), 2)


def update_bpm_metadata(file_path, bpm):
    if not file_path.lower().endswith(".mp3"):
        return
    audio = MP3(file_path, ID3=ID3)
    if not audio.tags:
        audio.tags = ID3()
    audio.tags.add(TXXX(encoding=3, desc="BPM", text=str(bpm)))
    audio.save()


def get_metadata(file_path):
    metadata = {"filename": os.path.basename(file_path)}
    if file_path.lower().endswith(".mp3"):
        audio = MP3(file_path, ID3=ID3)
        if audio.tags:
            for tag in audio.tags.values():
                try:
                    if hasattr(tag, "desc") and tag.desc.lower() == "bpm":
                        metadata["BPM"] = float(tag.text[0])
                    elif hasattr(tag, "text"):
                        if tag.FrameID == "TPE1":
                            metadata["Artist"] = tag.text[0]
                        elif tag.FrameID == "TCON":
                            metadata["Genre"] = tag.text[0]
                except Exception:
                    continue
    return metadata


def scan_folder(folder):
    """Recursively scan a folder for all MP3 and WAV files."""
    music_files = []
    for root, _, files in os.walk(folder):
        for file in files:
            if file.lower().endswith((".mp3", ".wav")):
                music_files.append(os.path.join(root, file))
    return music_files


def move_to_sorted_folder(base_folder, file_path, sort_value, category):
    target_folder = os.path.join(base_folder, category, sort_value)
    os.makedirs(target_folder, exist_ok=True)
    shutil.move(file_path, os.path.join(target_folder, os.path.basename(file_path)))


def delete_empty_folders(folder):
    """Deletes empty folders after sorting."""
    for root, dirs, _ in os.walk(folder, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            if not os.listdir(dir_path):  # If folder is empty
                os.rmdir(dir_path)


class SortifyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sortify - Music Sorter")
        self.resize(600, 600)

        self.folder_path = None
        self.file_list = []
        self.preview_mode = False  # Track if user is in preview mode

        # Widgets
        self.folder_label = QLabel("No folder selected.")
        self.select_folder_button = QPushButton("Select Music Folder")
        self.bpm_checkbox = QCheckBox("Enable BPM Analysis")
        self.sort_by_label = QLabel("Sort by:")
        self.sort_dropdown = QComboBox()
        self.sort_dropdown.addItems(["Artist", "Genre", "BPM Range"])
        self.preview_button = QPushButton("Preview Sorting")
        self.sort_button = QPushButton("Sort Music")
        self.sort_button.setEnabled(False)
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.progress_bar = QProgressBar()

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.folder_label)
        layout.addWidget(self.select_folder_button)
        layout.addWidget(self.bpm_checkbox)

        row = QHBoxLayout()
        row.addWidget(self.sort_by_label)
        row.addWidget(self.sort_dropdown)
        layout.addLayout(row)

        layout.addWidget(self.preview_button)
        layout.addWidget(self.sort_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.output_box)
        self.setLayout(layout)

        # Events
        self.select_folder_button.clicked.connect(self.select_folder)
        self.preview_button.clicked.connect(lambda: self.sort_files(preview=True))
        self.sort_button.clicked.connect(lambda: self.sort_files(preview=False))

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_path = folder
            self.file_list = scan_folder(folder)
            self.folder_label.setText(f"Selected: {os.path.basename(folder)} ({len(self.file_list)} files)")
            self.sort_button.setEnabled(len(self.file_list) > 0)
            self.preview_button.setEnabled(len(self.file_list) > 0)

    def sort_files(self, preview):
        self.preview_mode = preview
        self.output_box.clear()
        sort_option = self.sort_dropdown.currentText()
        self.file_list = scan_folder(self.folder_path)  # Refresh the file list
        total_files = len(self.file_list)
        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setValue(0)

        for i, file_path in enumerate(self.file_list):
            if not os.path.exists(file_path):
                self.output_box.append(f"⚠️ File missing: {file_path}")
                continue

            meta = get_metadata(file_path)

            # BPM fallback if missing
            if sort_option == "BPM Range" and ("BPM" not in meta or not isinstance(meta["BPM"], (float, int))):
                if self.bpm_checkbox.isChecked():
                    bpm = get_bpm(file_path)
                    meta["BPM"] = bpm
                    if file_path.lower().endswith(".mp3"):
                        update_bpm_metadata(file_path, bpm)

            # Determine subfolder name
            if sort_option == "Artist":
                value = meta.get("Artist", "Unknown Artist")
            elif sort_option == "Genre":
                value = meta.get("Genre", "Unknown Genre")
            elif sort_option == "BPM Range":
                bpm = meta.get("BPM", None)
                if bpm:
                    low = int(bpm // 10 * 10)
                    high = low + 9
                    value = f"{low}-{high} BPM"
                else:
                    value = "Unknown BPM"
            else:
                value = "Unsorted"

            # Display preview
            if preview:
                self.output_box.append(f"📂 {meta['filename']} → {sort_option}/{value}")
            else:
                move_to_sorted_folder(self.folder_path, file_path, value, sort_option)
                self.output_box.append(f"✅ {meta['filename']} → {sort_option}/{value}")

            # Update progress bar
            self.progress_bar.setValue(i + 1)

        if not preview:
            delete_empty_folders(self.folder_path)
            self.output_box.append("\n✅ Sorting Complete! Empty folders deleted.")

        self.output_box.append("\nPreview Mode Complete." if preview else "\nSorting Complete!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SortifyApp()
    window.show()
    sys.exit(app.exec())