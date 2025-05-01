import sys
import os
import time
import shutil
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QFileDialog,
    QVBoxLayout, QHBoxLayout, QTextEdit, QCheckBox, QComboBox
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


def move_to_sorted_folder(base_folder, file_path, sort_value, category):
    target_folder = os.path.join(base_folder, category, sort_value)
    os.makedirs(target_folder, exist_ok=True)
    shutil.move(file_path, os.path.join(target_folder, os.path.basename(file_path)))


class SortifyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sortify - Music Sorter")
        self.resize(600, 600)

        self.folder_path = None
        self.file_list = []

        # Widgets
        self.folder_label = QLabel("No folder selected.")
        self.select_folder_button = QPushButton("Select Music Folder")
        self.bpm_checkbox = QCheckBox("Enable BPM Analysis")
        self.sort_by_label = QLabel("Sort by:")
        self.sort_dropdown = QComboBox()
        self.sort_dropdown.addItems(["Artist", "Genre", "BPM Range"])
        self.submit_button = QPushButton("Sort Music")
        self.submit_button.setEnabled(False)
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.folder_label)
        layout.addWidget(self.select_folder_button)
        layout.addWidget(self.bpm_checkbox)

        row = QHBoxLayout()
        row.addWidget(self.sort_by_label)
        row.addWidget(self.sort_dropdown)
        layout.addLayout(row)

        layout.addWidget(self.submit_button)
        layout.addWidget(self.output_box)
        self.setLayout(layout)

        # Events
        self.select_folder_button.clicked.connect(self.select_folder)
        self.submit_button.clicked.connect(self.sort_files)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_path = folder
            self.file_list = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.lower().endswith((".mp3", ".wav"))
            ]
            self.folder_label.setText(f"Selected: {os.path.basename(folder)} ({len(self.file_list)} files)")
            self.submit_button.setEnabled(len(self.file_list) > 0)

    def sort_files(self):
        self.output_box.clear()
        sort_option = self.sort_dropdown.currentText()

        for file_path in self.file_list:
            meta = get_metadata(file_path)

            # BPM fallback if not found and analysis is enabled
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

            # Move file
            move_to_sorted_folder(self.folder_path, file_path, value, sort_option)
            self.output_box.append(f"✅ {meta['filename']} → {sort_option}/{value}")

        self.output_box.append("\nDone! Files sorted.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SortifyApp()
    window.show()
    sys.exit(app.exec())