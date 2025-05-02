import sys
import os
import time
import shutil
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QFileDialog,
    QVBoxLayout, QHBoxLayout, QTextEdit, QCheckBox, QListWidget, QListWidgetItem,
    QAbstractItemView, QProgressBar
)
from PyQt6.QtCore import Qt
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
    metadata = {
        "filename": os.path.basename(file_path),
        "path": file_path
    }

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
    music_files = []
    for root, _, files in os.walk(folder):
        for file in files:
            if file.lower().endswith((".mp3", ".wav")):
                music_files.append(os.path.join(root, file))
    return music_files


def delete_empty_folders(folder):
    for root, dirs, _ in os.walk(folder, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            if not os.listdir(dir_path):
                os.rmdir(dir_path)


class SortifyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sortify - Advanced Sorter")
        self.resize(700, 700)

        self.folder_path = None
        self.file_list = []
        self.last_sort_map = {}  # file: original_path

        # UI elements
        self.folder_label = QLabel("No folder selected.")
        self.select_button = QPushButton("Select Folder")
        self.bpm_checkbox = QCheckBox("Enable BPM Analysis")

        self.criteria_label = QLabel("Select Sort Criteria (drag to reorder):")
        self.criteria_list = QListWidget()
        self.criteria_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.criteria_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        for option in ["Artist", "Genre", "BPM Range", "Alphabetical"]:
            item = QListWidgetItem(option)
            self.criteria_list.addItem(item)

        self.preview_button = QPushButton("Preview Sort")
        self.sort_button = QPushButton("Sort")
        self.undo_button = QPushButton("Undo Last Sort")
        self.undo_button.setEnabled(False)

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.progress_bar = QProgressBar()

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.folder_label)
        layout.addWidget(self.select_button)
        layout.addWidget(self.bpm_checkbox)
        layout.addWidget(self.criteria_label)
        layout.addWidget(self.criteria_list)
        layout.addWidget(self.preview_button)
        layout.addWidget(self.sort_button)
        layout.addWidget(self.undo_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.output_box)
        self.setLayout(layout)

        # Connections
        self.select_button.clicked.connect(self.select_folder)
        self.preview_button.clicked.connect(lambda: self.process_files(preview=True))
        self.sort_button.clicked.connect(lambda: self.process_files(preview=False))
        self.undo_button.clicked.connect(self.undo_sort)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_path = folder
            self.file_list = scan_folder(folder)
            self.folder_label.setText(f"Selected: {os.path.basename(folder)} ({len(self.file_list)} files)")

    def get_sort_order(self):
        return [item.text() for item in self.criteria_list.selectedItems()]

    def build_sort_path(self, meta, sort_order):
        parts = []
        for criterion in sort_order:
            if criterion == "Artist":
                parts.append(meta.get("Artist", "Unknown Artist"))
            elif criterion == "Genre":
                parts.append(meta.get("Genre", "Unknown Genre"))
            elif criterion == "BPM Range":
                bpm = meta.get("BPM", None)
                if bpm:
                    low = int(bpm // 10 * 10)
                    high = low + 9
                    parts.append(f"{low}-{high} BPM")
                else:
                    parts.append("Unknown BPM")
            elif criterion == "Alphabetical":
                first_char = meta["filename"][0].upper()
                parts.append(first_char if first_char.isalpha() else "#")
        return os.path.join(*parts)

    def process_files(self, preview=False):
        self.output_box.clear()
        self.progress_bar.setValue(0)
        self.last_sort_map.clear()

        self.file_list = scan_folder(self.folder_path)
        sort_order = self.get_sort_order()
        if not sort_order:
            self.output_box.append("⚠️ No sort criteria selected.")
            return

        self.progress_bar.setMaximum(len(self.file_list))

        for i, file_path in enumerate(self.file_list):
            if not os.path.exists(file_path):
                continue

            meta = get_metadata(file_path)

            if "BPM Range" in sort_order and ("BPM" not in meta or not isinstance(meta["BPM"], (float, int))):
                if self.bpm_checkbox.isChecked():
                    bpm = get_bpm(file_path)
                    meta["BPM"] = bpm
                    if file_path.lower().endswith(".mp3"):
                        update_bpm_metadata(file_path, bpm)

            sort_path = self.build_sort_path(meta, sort_order)
            target_dir = os.path.join(self.folder_path, *sort_path.split(os.sep))
            os.makedirs(target_dir, exist_ok=True)

            if not preview:
                new_path = os.path.join(target_dir, os.path.basename(file_path))
                self.last_sort_map[file_path] = new_path
                shutil.move(file_path, new_path)
                self.output_box.append(f"✅ Moved: {meta['filename']} → {sort_path}")
            else:
                self.output_box.append(f"📂 Preview: {meta['filename']} → {sort_path}")

            self.progress_bar.setValue(i + 1)

        if not preview:
            delete_empty_folders(self.folder_path)
            self.undo_button.setEnabled(True)
            self.output_box.append("\n✅ Sort Complete!")
        else:
            self.output_box.append("\nPreview Complete.")

    def undo_sort(self):
        self.output_box.append("\n🔄 Undoing last sort...")
        moved_count = 0

        all_files = scan_folder(self.folder_path)

        for file_path in all_files:
            # Skip if it's already in the root folder
            if os.path.dirname(file_path) == self.folder_path:
                continue

            # Build target path
            dest_path = os.path.join(self.folder_path, os.path.basename(file_path))

            # If the destination file already exists, skip to avoid overwrite
            if os.path.exists(dest_path):
                self.output_box.append(f"⚠️ Skipped (already exists in root): {os.path.basename(file_path)}")
                continue

            try:
                shutil.move(file_path, dest_path)
                self.output_box.append(f"↩️ Moved back: {os.path.basename(file_path)}")
                moved_count += 1
            except Exception as e:
                self.output_box.append(f"❌ Failed to move: {file_path} ({str(e)})")

        delete_empty_folders(self.folder_path)
        self.output_box.append(f"\nUndo complete. {moved_count} file(s) moved back to root folder.")
        self.undo_button.setEnabled(False)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SortifyApp()
    window.show()
    sys.exit(app.exec())