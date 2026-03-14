import json
import os
import struct
import subprocess
import sys
import wave
from pathlib import Path


def _run_cli(*args: str) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    result = subprocess.run([sys.executable, "-m", "osu_lab", *args], check=True, capture_output=True, text=True, env=env)
    return json.loads(result.stdout)


def _write_click_track(path: Path, bpm: float = 140.0, seconds: int = 4, sample_rate: int = 44100) -> None:
    frames = []
    total_samples = seconds * sample_rate
    beat_interval = int(sample_rate * 60.0 / bpm)
    for index in range(total_samples):
        phase = index % beat_interval
        amplitude = 25000 if phase < 300 else 0
        frames.append(struct.pack("<h", amplitude))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"".join(frames))


def test_schema_dump_cli():
    payload = _run_cli("schema", "dump")
    assert "BeatmapIR" in payload


def test_map_verify_cli():
    payload = _run_cli("map", "verify", "tests/fixtures/sample_map.osu")
    assert payload["issue_count"] == 0
    assert "external" in payload


def test_map_quality_cli():
    payload = _run_cli("map", "quality", "tests/fixtures/sample_map.osu")
    assert "overall_score" in payload
    assert "metrics" in payload


def test_map_auto_cli(tmp_path: Path):
    audio = tmp_path / "song.wav"
    out_dir = tmp_path / "auto"
    _write_click_track(audio)
    payload = _run_cli(
        "map",
        "auto",
        "--audio",
        str(audio),
        "--prompt",
        "flow aim with chorus jump lift",
        "--refs",
        "tests/fixtures",
        "--candidate-count",
        "2",
        "--out",
        str(out_dir),
    )
    assert payload["status"] == "ok"
    assert payload["candidate_search"]["candidate_count"] == 2
    assert Path(payload["best_candidate"]["osu"]).exists()
    assert Path(payload["final_artifacts"]["osu"]).exists()
