from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TXXX
import librosa
import numpy as np

def get_metadata(file_path):
    """Extracts metadata from an MP3 file."""
    audio = MP3(file_path, ID3=ID3)
    metadata = {}
    if audio.tags:
        for tag in audio.tags:
            metadata[tag] = str(audio.tags[tag])
    return metadata

def get_bpm(file_path):
    """Analyzes BPM using Librosa."""
    y, sr = librosa.load(file_path, sr=None)  # Load audio file
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)  # Detect beats
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_env)  # Estimate BPM
    return round(tempo, 2)  # Return BPM as a rounded value

def add_bpm_metadata(file_path, bpm):
    """Adds a BPM tag to the MP3 metadata."""
    audio = MP3(file_path, ID3=ID3)
    
    # Ensure the MP3 has ID3 tags, otherwise create them
    if not audio.tags:
        audio.tags = ID3()
    
    # Add or update the BPM tag
    audio.tags.add(TXXX(encoding=3, desc="BPM", text=str(bpm)))
    audio.save()
    print(f"BPM ({bpm}) added to metadata.")

# --- Test the functions ---
song_path = "/Users/nickarruzza/Desktop/anxiety.mp3"  # Replace with your file path

# Step 1: Read existing metadata
print("Original Metadata:", get_metadata(song_path))

# Step 2: Analyze BPM
bpm = get_bpm(song_path)
print(f"Detected BPM: {bpm}")

# Step 3: Add BPM to metadata
add_bpm_metadata(song_path, bpm)

# Step 4: Verify new metadata
print("Updated Metadata:", get_metadata(song_path))