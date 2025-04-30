import sys
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QFileDialog, QVBoxLayout
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
    audio = MP3(file_path, ID3=ID3)
    if not audio.tags:
        audio.tags = ID3()
    audio.tags.add(TXXX(encoding=3, desc="BPM", text=str(bpm)))
    audio.save()


def get_readable_metadata(file_path):
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
        self.setWindowTitle("Sortify - Single Track BPM Tagger")

        self.file_path = None

        self.select_button = QPushButton("Choose a Song")
        self.select_button.clicked.connect(self.select_file)

        self.submit_button = QPushButton("Submit")
        self.submit_button.setEnabled(False)
        self.submit_button.clicked.connect(self.process_file)

        self.info_label = QLabel("No file selected.")
        self.output_label = QLabel("")

        layout = QVBoxLayout()
        layout.addWidget(self.select_button)
        layout.addWidget(self.submit_button)
        layout.addWidget(self.info_label)
        layout.addWidget(self.output_label)

        self.setLayout(layout)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select MP3 File", "", "MP3 Files (*.mp3)")
        if file_path:
            self.file_path = file_path
            self.info_label.setText(f"Selected: {file_path.split('/')[-1]}")
            self.submit_button.setEnabled(True)

    def process_file(self):
        if self.file_path:
            self.output_label.setText("Estimating BPM time...")
            bpm, duration = get_bpm(self.file_path)
            update_bpm_metadata(self.file_path, bpm)
            metadata = get_readable_metadata(self.file_path)

            output = f"BPM Detected: {bpm} (Analysis Time: {duration}s)\n\nUpdated Metadata:\n"
            for k, v in metadata.items():
                output += f"{k}: {v}\n"

            self.output_label.setText(output)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SortifyApp()
    window.show()
    sys.exit(app.exec())