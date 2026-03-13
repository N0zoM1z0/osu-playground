import math
import struct
import wave
from pathlib import Path

from osu_lab.audio.analyze import analyze_audio


def _write_click_track(path: Path, bpm: float = 120.0, seconds: int = 4, sample_rate: int = 44100) -> None:
    frames = []
    total_samples = seconds * sample_rate
    beat_interval = int(sample_rate * 60.0 / bpm)
    for index in range(total_samples):
        phase = index % beat_interval
        amplitude = 28000 if phase < 400 else 0
        frames.append(struct.pack("<h", amplitude))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"".join(frames))


def test_audio_analysis_estimates_bpm(tmp_path: Path):
    wav_path = tmp_path / "click.wav"
    _write_click_track(wav_path, bpm=120.0)
    analysis = analyze_audio(wav_path, normalize=False)
    assert math.isclose(analysis.bpm, 120.0, abs_tol=3.0)
    assert analysis.beats_ms

