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
from collections import Counter
from PyQt6.QtWidgets import QTextBrowser

#Sortify logo in MacOS dock
if sys.platform == "darwin":
    try:
        from AppKit import NSApplication, NSImage
        app_icon_path = os.path.abspath("sortify_logo.png")
        if os.path.exists(app_icon_path):
            app = NSApplication.sharedApplication()
            icon = NSImage.alloc().initByReferencingFile_(app_icon_path)
            app.setApplicationIconImage_(icon)
    except Exception as e:
        print(f"Could not set macOS Dock icon: {e}")

# --- Utility Functions ---

#Gets bpm from files in selected folder
def get_bpm(file_path):
    y, sr = librosa.load(file_path, sr=None)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_env)
    return round(float(tempo[0]), 2)

#Gets musical key from audio using chroma features
def get_key(file_path):
    y, sr = librosa.load(file_path, sr=None)
    chroma = librosa.feature.chroma_cens(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)
    key_idx = chroma_mean.argmax()
    key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    return key_names[key_idx]

#Writes bpm value into mp3 metadata tag
def update_bpm_metadata(file_path, bpm):
    if not file_path.lower().endswith(".mp3"):
        return
    audio = MP3(file_path, ID3=ID3)
    if not audio.tags:
        audio.tags = ID3()
    audio.tags.add(TXXX(encoding=3, desc="BPM", text=str(bpm)))
    audio.save()

#Extracts metadata from supported audio formats
def get_metadata(file_path):
    metadata = {"filename": os.path.basename(file_path), "path": file_path}
    try:
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

        elif file_path.lower().endswith(".flac"):
            from mutagen.flac import FLAC
            audio = FLAC(file_path)
            metadata["Artist"] = audio.get("artist", ["Unknown Artist"])[0]
            metadata["Genre"] = audio.get("genre", ["Unknown Genre"])[0]

        elif file_path.lower().endswith(".aiff"):
            from mutagen.aiff import AIFF
            audio = AIFF(file_path)
            metadata["Artist"] = audio.get("TPE1", ["Unknown Artist"])[0]
            metadata["Genre"] = audio.get("TCON", ["Unknown Genre"])[0]

    except Exception as e:
        metadata["error"] = str(e)
    return metadata

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


# --- Worker Thread ---

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
                    "ukg": "UK Garage",
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


# --- Main App Class ---

from PyQt6.QtCore import QPropertyAnimation, QRect, QEasingCurve

class SortifyApp(QWidget):
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    #Handles folder drop via drag-and-drop
    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            paths.append(url.toLocalFile())
        
        folders = []
        for p in paths:
            if os.path.isdir(p):
                folders.append(p)
        
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
        self.stats_panel = QTextBrowser()
      
        self.stats_panel.setVisible(False)
        self.stats_panel.setMaximumWidth(300)
        self.stats_panel.setStyleSheet("background-color: #222; color: white; padding: 8px;")
        
        self.stats_button = QPushButton("📊 Show Stats")
        self.stats_button.setStyleSheet("QPushButton:hover { background-color: #444; color: white; }")
        self.stats_button.clicked.connect(self.toggle_stats_panel)

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
        controls.addWidget(self.stats_button)

        output = QVBoxLayout()
        output.addWidget(QLabel("Output:"))
        output.addWidget(self.output_box)
        output.addWidget(self.progress_bar)

        main_split = QHBoxLayout()
        main_split.addLayout(controls, 2)
        main_split.addLayout(output, 3)
        main_split.addWidget(self.stats_panel)

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

    #Returns selected sort order from the drag-drop list
    def get_sort_order(self):
        return [item.text() for item in self.criteria_list.selectedItems()]

    #Starts sort worker thread for preview or move
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
    
    #Updates progress bar and log during sorting
    def handle_progress(self, value, msg):
        self.progress_bar.setValue(value)
        self.output_box.append(msg)
        self.output_box.append("🌟 Sort complete. Tags: 🎵 Genre, 🎤 Artist, 🧠 Key, 🔊 BPM")

    #Final handler once sorting is complete
    def handle_finish(self, msg):
        self.animate_label(self.output_box)
        self.output_box.append(msg)
        delete_empty_folders(self.folder_path)
        if not self.worker.preview:
            self.last_sort_map = self.worker.last_sort_map
            self.undo_button.setEnabled(True)

    #Animation for ui feedback
    def animate_label(self, widget):
        anim = QPropertyAnimation(widget, b"geometry")
        anim.setDuration(250)
        anim.setEasingCurve(QEasingCurve.Type.OutBounce)
        rect = widget.geometry()
        anim.setStartValue(QRect(rect.x(), rect.y() - 5, rect.width(), rect.height()))
        anim.setEndValue(rect)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    #Undoes the last sort by moving files back to root
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

    #Toggles the stats panel on and off
    def toggle_stats_panel(self):
        if self.stats_panel.isVisible():
            self.stats_panel.setVisible(False)
            self.stats_button.setText("📊 Show Stats")
        else:
            self.refresh_stats()
            self.stats_panel.setVisible(True)
            self.stats_button.setText("❌ Hide Stats")
    
    #Refreshes statistics panel content from current folder
    def refresh_stats(self):
        files = scan_folder(self.folder_path)
        genre_counts, artist_counts, bpm_ranges = self.compute_statistics(files)
        total_size = self.compute_total_size(files)
    
        html = "<h3>📊 Library Stats</h3>"
        html += f"<p><b>💾 Total Size:</b> {self.format_bytes(total_size)}</p>"
    
        html += "<p><b>🎵 Genres:</b><br>"
        for genre, count in genre_counts.items():
            html += f"{genre}: {count}<br>"
        html += "</p><p><b>🎤 Artists:</b><br>"
        for artist, count in artist_counts.items():
            html += f"{artist}: {count}<br>"
        html += "</p><p><b>🔊 BPM Ranges:</b><br>"
        for bpm, count in bpm_ranges.items():
            html += f"{bpm}: {count}<br>"
        html += "</p>"
    
        self.stats_panel.setHtml(html)
    
    #Counts genres, artists and bpm ranges from files
    def compute_statistics(self, file_paths):
        genre_counts = Counter()
        artist_counts = Counter()
        bpm_ranges = Counter()
        for path in file_paths:
            meta = get_metadata(path)
            genre = meta.get("Genre", "Unknown Genre")
            artist = meta.get("Artist", "Unknown Artist")
            bpm = meta.get("BPM")
            genre_counts[genre] += 1
            artist_counts[artist] += 1
            if bpm:
                range_key = f"{(int(bpm) // 10) * 10}-{(int(bpm) // 10) * 10 + 9} BPM"
                bpm_ranges[range_key] += 1
        return genre_counts, artist_counts, bpm_ranges
    
    #Sums up total file sizes for stats panel
    def compute_total_size(self, file_paths):
        return sum(os.path.getsize(path) for path in file_paths if os.path.exists(path))
    
    #Formats file size into readable units
    def format_bytes(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

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