import os
import shutil
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QFileDialog, QListWidget, QListWidgetItem, QTextBrowser,
    QCheckBox, QTextEdit, QHBoxLayout, QVBoxLayout, QProgressBar, QMessageBox, QAbstractItemView
)
from PyQt6.QtGui import QPixmap, QFont, QPalette, QIcon
from PyQt6.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve
from collections import Counter

from Python.sorting import SortWorker
from Python.metadata import get_metadata
from Python.utils import scan_folder, delete_empty_folders
from Python.stats import toggle_stats_panel

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
        self.stats_button.clicked.connect(lambda: toggle_stats_panel(self))

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