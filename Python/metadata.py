import os
import librosa
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TXXX

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