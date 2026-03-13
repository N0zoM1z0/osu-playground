import struct
import wave
from pathlib import Path

from osu_lab.eval.bench import benchmark_style_control, benchmark_summary


def _write_click_track(path: Path, bpm: float = 150.0, seconds: int = 4, sample_rate: int = 44100) -> None:
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


def test_benchmark_summary_reports_fixture_stats():
    summary = benchmark_summary("tests/fixtures")
    assert summary["map_count"] >= 1
    assert "dominant_class_histogram" in summary


def test_benchmark_style_control_reports_match_rates(tmp_path: Path):
    audio = tmp_path / "bench.wav"
    _write_click_track(audio)
    result = benchmark_style_control(
        audio_path=audio,
        output_dir=tmp_path / "out",
        prompts=["jump", "flow aim"],
        reference_maps=["tests/fixtures/sample_map.osu"],
    )
    assert "styled_match_rate" in result
    assert len(result["results"]) == 2
    assert "mean_reference_improvement_ratio" in result
