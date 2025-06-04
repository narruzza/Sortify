from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton

class HelpWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sortify - User Guide")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout()

        self.text_browser = QTextBrowser()
        self.text_browser.setHtml("""
        <h2>📘 Sortify User Guide</h2>
        <p>Welcome to <b>Sortify</b>! Here's how to get started:</p>
        <ol>
            <li><b>Select a folder</b> with your music files.</li>
            <li><b>Enable BPM analysis</b> if you want BPM detection (optional).</li>
            <li><b>Choose sort criteria</b> like Artist, Genre, BPM, etc. You can drag to change order.</li>
            <li><b>Preview Sort</b> to see what will happen.</li>
            <li><b>Click Sort</b> to move files into sorted folders.</li>
            <li><b>Undo Sort</b> will return all files to the root folder.</li>
            <li><b>Stats Panel</b> shows a breakdown of your music library.</li>
        </ol>
        <p>If your genres are mismatched, enable genre cleaning or check your file metadata manually.</p>
        <hr>
        <p><i>Supported formats:</i> MP3, WAV, FLAC, AIFF</p>
        """)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)

        layout.addWidget(self.text_browser)
        layout.addWidget(self.close_button)
        self.setLayout(layout)
