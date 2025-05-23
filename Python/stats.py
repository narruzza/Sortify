import os
from collections import Counter

from Python.metadata import get_metadata
from Python.utils import scan_folder

#Toggles the stats panel on and off
def toggle_stats_panel(app):
    if app.stats_panel.isVisible():
        app.stats_panel.setVisible(False)
        app.stats_button.setText("📊 Show Stats")
    else:
        refresh_stats(app)
        app.stats_panel.setVisible(True)
        app.stats_button.setText("❌ Hide Stats")

#Refreshes statistics panel content from current folder
def refresh_stats(app):
    files = scan_folder(app.folder_path)
    genre_counts, artist_counts, bpm_ranges = compute_statistics(files)
    total_size = compute_total_size(files)

    html = "<h3>📊 Library Stats</h3>"
    html += f"<p><b>💾 Total Size:</b> {format_bytes(total_size)}</p>"

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

    app.stats_panel.setHtml(html)

#Counts genres, artists and bpm ranges from files
def compute_statistics(file_paths):
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
def compute_total_size(file_paths):
    return sum(os.path.getsize(path) for path in file_paths if os.path.exists(path))

#Formats file size into readable units
def format_bytes(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
