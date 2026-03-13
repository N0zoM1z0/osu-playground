import struct
import wave
from pathlib import Path

from osu_lab.generate.mapforge import generate_map


def _write_click_track(path: Path, bpm: float = 160.0, seconds: int = 6, sample_rate: int = 44100) -> None:
    frames = []
    total_samples = seconds * sample_rate
    beat_interval = int(sample_rate * 60.0 / bpm)
    for index in range(total_samples):
        phase = index % beat_interval
        amplitude = 26000 if phase < 300 else 0
        frames.append(struct.pack("<h", amplitude))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"".join(frames))


def test_generate_map_returns_tuning_history(tmp_path: Path):
    wav_path = tmp_path / "song.wav"
    out_dir = tmp_path / "out"
    _write_click_track(wav_path)
    result = generate_map(wav_path, out_dir, prompt="jump", target_star=1.0, seed=2)
    assert Path(result["osu"]).exists()
    assert result["tuning_history"]
    assert "stars" in result["final_score"]

