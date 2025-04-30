import time
import librosa

def get_bpm_with_timing(file_path):
    start = time.time()

    y, sr = librosa.load(file_path, sr=None)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_env)
    bpm = round(float(tempo[0]), 2)

    end = time.time()
    duration = round(end - start, 2)
    print(f"BPM: {bpm} | Time taken: {duration} seconds")
    return bpm, duration

# Replace with your test track path
get_bpm_with_timing("/Users/nickarruzza/Desktop/Bulletproof - Top 100.mp3")
