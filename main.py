import sys
import os
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QFileDialog,
    QVBoxLayout, QHBoxLayout, QTextEdit, QCheckBox
)
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TXXX
import librosa


def get_bpm(file_path):
    start = time.time()
    y, sr = librosa.load(file_path, sr=None)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_env)
    bpm = round(float(tempo[0]), 2)
    duration = round(time.time() - start, 2)
    return bpm, duration


def update_bpm_metadata(file_path, bpm):
    if not file_path.lower().endswith(".mp3"):
        return  # Don't try to write metadata to non-MP3 files

    audio = MP3(file_path, ID3=ID3)
    if not audio.tags:
        audio.tags = ID3()
    audio.tags.add(TXXX(encoding=3, desc="BPM", text=str(bpm)))
    audio.save()


def get_readable_metadata(file_path):
    if not file_path.lower().endswith(".mp3"):
        return {"Note": "No metadata (non-MP3 file)"}

    audio = MP3(file_path, ID3=ID3)
    metadata = {}
    if audio.tags:
        for tag in audio.tags.values():
            try:
                if hasattr(tag, "desc") and tag.desc.lower() == "bpm":
                    metadata["BPM"] = tag.text[0]
                elif hasattr(tag, "text"):
                    metadata[tag.FrameID] = tag.text[0]
            except Exception:
                continue
    return metadata


class SortifyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sortify - Folder BPM & Metadata Organizer")
        self.resize(600, 600)

        self.folder_path = None
        self.file_list = []

        # Widgets
        self.folder_label = QLabel("No folder selected.")
        self.select_folder_button = QPushButton("Select Music Folder")
        self.bpm_checkbox = QCheckBox("Include BPM Analysis (Slower)")
        self.estimate_label = QLabel("")
        self.submit_button = QPushButton("Submit")
        self.submit_button.setEnabled(False)
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.folder_label)
        layout.addWidget(self.select_folder_button)
        layout.addWidget(self.bpm_checkbox)
        layout.addWidget(self.estimate_label)
        layout.addWidget(self.submit_button)
        layout.addWidget(self.output_box)

        self.setLayout(layout)

        # Events
        self.select_folder_button.clicked.connect(self.select_folder)
        self.submit_button.clicked.connect(self.process_files)
        self.bpm_checkbox.stateChanged.connect(self.update_estimate)

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
            self.update_estimate()
            self.submit_button.setEnabled(len(self.file_list) > 0)

    def update_estimate(self):
        if self.bpm_checkbox.isChecked() and self.file_list:
            estimated_time = round(len(self.file_list) * 2.0, 1)  # ~2 sec per file
            self.estimate_label.setText(f"Estimated time: ~{estimated_time}s")
        else:
            self.estimate_label.setText("")

    def process_files(self):
        self.output_box.clear()
        for file_path in self.file_list:
            filename = os.path.basename(file_path)
            bpm = None
            time_taken = 0

            if self.bpm_checkbox.isChecked():
                bpm, time_taken = get_bpm(file_path)
                update_bpm_metadata(file_path, bpm)

            metadata = get_readable_metadata(file_path)

            # Display
            self.output_box.append(f"🎵 {filename}")
            if bpm:
                self.output_box.append(f"BPM: {bpm} (Took {time_taken:.2f}s)")

            for key, value in metadata.items():
                self.output_box.append(f"{key}: {value}")
            self.output_box.append("-" * 50)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SortifyApp()
    window.show()
    sys.exit(app.exec())