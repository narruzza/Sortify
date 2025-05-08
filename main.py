import sys
import os
import shutil
import librosa
import re
import traceback
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QFileDialog, QListWidget, QListWidgetItem,
    QCheckBox, QTextEdit, QHBoxLayout, QVBoxLayout, QProgressBar, QMessageBox, QAbstractItemView
)
from PyQt6.QtGui import QPixmap, QFont, QPalette, QColor, QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TXXX

# Sortify Logo as app icon in MacOS dock
if sys.platform == "darwin":
    try:
        from AppKit import NSApplication, NSImage
        from Foundation import NSURL
        import objc

        app_icon_path = os.path.abspath("sortify_logo.png")
        if os.path.exists(app_icon_path):
            app = NSApplication.sharedApplication()
            icon = NSImage.alloc().initByReferencingFile_(app_icon_path)
            app.setApplicationIconImage_(icon)
    except Exception as e:
        print(f"Could not set macOS Dock icon: {e}")

# --- Utility Functions ---

def get_bpm(file_path):
    y, sr = librosa.load(file_path, sr=None)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_env)
    return round(float(tempo[0]), 2)

def get_key(file_path):
    y, sr = librosa.load(file_path, sr=None)
    chroma = librosa.feature.chroma_cens(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)
    key_idx = chroma_mean.argmax()
    key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    return key_names[key_idx]

def update_bpm_metadata(file_path, bpm):
    if not file_path.lower().endswith(".mp3"):
        return
    audio = MP3(file_path, ID3=ID3)
    if not audio.tags:
        audio.tags = ID3()
    audio.tags.add(TXXX(encoding=3, desc="BPM", text=str(bpm)))
    audio.save()

def get_metadata(file_path):
    metadata = {"filename": os.path.basename(file_path), "path": file_path}
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

def sanitize_filename(filename):
    return re.sub(r'[\\/:*?"<>|]', '_', filename)


# --- Worker Thread ---

class SortWorker(QThread):
    update_progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)

    def __init__(self, files, folder_path, sort_order, bpm_enabled, preview):
        super().__init__()
        self.files = files
        self.folder_path = folder_path
        self.sort_order = sort_order
        self.bpm_enabled = bpm_enabled
        self.preview = preview
        self.last_sort_map = {}

    def build_sort_path(self, meta):
        parts = []
        for crit in self.sort_order:
            if crit == "Artist":
                parts.append(meta.get("Artist", "Unknown Artist"))
            elif crit == "Genre":
                genre = str(meta.get("Genre", "Unknown Genre")).strip().lower()
                genre_aliases = {
                    "drum and bass": "Drum & Bass",
                    "d&b": "Drum & Bass",
                    "drum&bass": "Drum & Bass",
                    "dnb": "Drum & Bass",
                    "neurofunk": "Drum & Bass",
                    "liquid dnb": "Drum & Bass",
                    "liquid funk": "Drum & Bass",
                    "jungle": "Jungle",
                    "rnb": "R&B",
                    "hip hop": "Hip-Hop",
                    "hip-hop": "Hip-Hop",
                    "trap": "Trap",
                    "dubstep": "Dubstep",
                    "future bass": "Future Bass",
                    "electro": "Electronic",
                    "electronic": "Electronic",
                    "edm": "Electronic",
                    "house": "House",
                    "deep house": "House",
                    "tech house": "House",
                    "progressive house": "House",
                    "techno": "Techno",
                    "trance": "Trance",
                    "hardstyle": "Hardstyle",
                    "psytrance": "Psytrance",
                    "goa": "Psytrance",
                    "breakbeat": "Breakbeat",
                    "glitch hop": "Glitch Hop",
                    "hardcore": "Hardcore",
                    "uk hardcore": "Hardcore",
                    "hard techno": "Hard Techno",
                    "garage": "UK Garage",
                    "uk garage": "UK Garage",
                    "speed garage": "UK Garage",
                    "bassline": "Bassline"
                }
                parts.append(genre_aliases.get(genre, genre.title()))
            elif crit == "BPM Range":
                bpm = meta.get("BPM")
                parts.append(f"{int(bpm // 10) * 10}-{int(bpm // 10) * 10 + 9} BPM" if bpm else "Unknown BPM")
            elif crit == "Alphabetical":
                char = meta["filename"][0].upper()
                parts.append(char if char.isalpha() else "#")
            elif crit == "Key":
                parts.append(meta.get("Key", "Unknown Key"))
        return os.path.join(*parts)

    def run(self):
        try:
            for i, file_path in enumerate(self.files):
                if not os.path.exists(file_path):
                    continue
                meta = get_metadata(file_path)

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


# --- Main App Class ---

from PyQt6.QtCore import QPropertyAnimation, QRect, QEasingCurve

class SortifyApp(QWidget):
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        folders = [p for p in paths if os.path.isdir(p)]
        if folders:
            self.folder_path = folders[0]
            self.folder_label.setText(f"Dropped: {os.path.basename(self.folder_path)}")
            self.animate_label(self.folder_label)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sortify")
        self.resize(850, 600)
        self.setWindowIcon(QIcon("sortify_logo.png"))

        self.folder_path = None
        self.worker = None
        self.last_sort_map = {}

        # GUI setup
        logo = QPixmap("sortify_logo.png").scaledToHeight(50, Qt.TransformationMode.SmoothTransformation)
        self.logo_label = QLabel()
        self.logo_label.setPixmap(logo)

        self.title_label = QLabel("Sortify")
        self.title_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.subtitle_label = QLabel("Organize your music by artist, genre, BPM, key, or alphabet.")

        self.folder_label = QLabel("No folder selected.")
        self.select_button = QPushButton("Select Folder")
        self.select_button.setStyleSheet("QPushButton:hover { background-color: #444; color: white; }")

        self.bpm_checkbox = QCheckBox("Enable BPM Analysis")
        self.criteria_list = QListWidget()
        self.criteria_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.criteria_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        for c in ["Artist", "Genre", "BPM Range", "Key", "Alphabetical"]:
            self.criteria_list.addItem(QListWidgetItem(c))

        self.preview_button = QPushButton("Preview Sort")
        self.preview_button.setStyleSheet("QPushButton:hover { background-color: #444; color: white; }")
        self.sort_button = QPushButton("Sort")
        self.sort_button.setStyleSheet("QPushButton:hover { background-color: #444; color: white; }")
        self.undo_button = QPushButton("Undo Last Sort")
        self.undo_button.setStyleSheet("QPushButton:hover { background-color: #444; color: white; }")
        self.undo_button.setEnabled(False)

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #5cb85c; } QProgressBar { text-align: center; }")

        # Layout
        controls = QVBoxLayout()
        controls.addWidget(self.folder_label)
        controls.addWidget(self.select_button)
        controls.addWidget(self.bpm_checkbox)
        controls.addWidget(QLabel("Select Sort Criteria (drag to reorder):"))
        controls.addWidget(self.criteria_list)
        controls.addWidget(self.preview_button)
        controls.addWidget(self.sort_button)
        controls.addWidget(self.undo_button)

        output = QVBoxLayout()
        output.addWidget(QLabel("Output:"))
        output.addWidget(self.output_box)
        output.addWidget(self.progress_bar)

        main_split = QHBoxLayout()
        main_split.addLayout(controls, 2)
        main_split.addLayout(output, 3)

        layout = QVBoxLayout()
        layout.addWidget(self.logo_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addSpacing(10)
        layout.addLayout(main_split)
        self.setLayout(layout)
        self.setAcceptDrops(True)

        # Connect
        self.select_button.clicked.connect(self.select_folder)
        self.preview_button.clicked.connect(lambda: self.run_sort(preview=True))
        self.sort_button.clicked.connect(lambda: self.run_sort(preview=False))
        self.undo_button.clicked.connect(self.undo_sort)
        self.set_dark_or_light_mode()

    def set_dark_or_light_mode(self):
        palette = self.palette()
        is_dark = palette.color(QPalette.ColorRole.Window).value() < 128
        self.setStyleSheet("QWidget { color: white; }" if is_dark else "QWidget { color: black; }")

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_path = folder
            self.folder_label.setText(f"Selected: {os.path.basename(folder)}")
            self.animate_label(self.folder_label)

    def get_sort_order(self):
        return [item.text() for item in self.criteria_list.selectedItems()]

    def run_sort(self, preview):
        self.animate_label(self.output_box)
        self.output_box.clear()
        sort_order = self.get_sort_order()
        if not sort_order:
            self.output_box.append("⚠️ No sort criteria selected.")
            return

        files = scan_folder(self.folder_path)
        self.progress_bar.setMaximum(len(files))
        self.progress_bar.setValue(0)

        self.worker = SortWorker(files, self.folder_path, sort_order, self.bpm_checkbox.isChecked(), preview)
        self.worker.update_progress.connect(self.handle_progress)
        self.worker.finished.connect(self.handle_finish)
        self.worker.start()

    def handle_progress(self, value, msg):
        self.progress_bar.setValue(value)
        self.output_box.append(msg)

    def handle_finish(self, msg):
        self.animate_label(self.output_box)
        self.output_box.append(msg)
        delete_empty_folders(self.folder_path)
        if not self.worker.preview:
            self.last_sort_map = self.worker.last_sort_map
            self.undo_button.setEnabled(True)

    def animate_label(self, widget):
        anim = QPropertyAnimation(widget, b"geometry")
        anim.setDuration(250)
        anim.setEasingCurve(QEasingCurve.Type.OutBounce)
        rect = widget.geometry()
        anim.setStartValue(QRect(rect.x(), rect.y() - 5, rect.width(), rect.height()))
        anim.setEndValue(rect)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def undo_sort(self):
        confirm = QMessageBox.question(self, "Undo Sort", "Are you sure you want to move all songs back to the root folder?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes:
            return

        moved = 0
        files = scan_folder(self.folder_path)

        for file_path in files:
            if os.path.dirname(file_path) == self.folder_path:
                continue
            dest_path = os.path.join(self.folder_path, os.path.basename(file_path))
            try:
                shutil.move(file_path, dest_path)
                moved += 1
                self.output_box.append(f"↩️ {os.path.basename(file_path)} → root")
            except Exception as e:
                self.output_box.append(f"❌ Failed to move: {file_path} ({e})")

        delete_empty_folders(self.folder_path)
        self.undo_button.setEnabled(False)
        self.output_box.append(f"Undo complete. {moved} files returned to root.")
        delete_empty_folders(self.folder_path)


if __name__ == "__main__":
    if sys.platform == "darwin":
        try:
            from Foundation import NSBundle
            bundle = NSBundle.mainBundle()
            if bundle:
                info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                if info is not None:
                    info["CFBundleName"] = "Sortify"
        except Exception as e:
            print(f"Could not set macOS Dock name: {e}")
    app = QApplication(sys.argv)
    window = SortifyApp()
    window.show()
    sys.exit(app.exec())