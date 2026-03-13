import json
import struct
import wave
from pathlib import Path

from osu_lab.beatmap.io import parse_osu, write_osu
from osu_lab.eval.acceptance import run_acceptance


def _write_click_track(path: Path, bpm: float = 160.0, seconds: int = 5, sample_rate: int = 44100) -> None:
    frames = []
    total_samples = seconds * sample_rate
    beat_interval = int(sample_rate * 60.0 / bpm)
    for index in range(total_samples):
        phase = index % beat_interval
        amplitude = 24000 if phase < 300 else 0
        frames.append(struct.pack("<h", amplitude))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"".join(frames))


def _fixture_corpus(root: Path, count: int = 50) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        beatmap = parse_osu("tests/fixtures/sample_map.osu")
        beatmap.metadata["Title"] = f"Synthetic Fixture {index}"
        beatmap.metadata["Version"] = f"Case {index}"
        beatmap.metadata["BeatmapID"] = index
        beatmap.metadata["BeatmapSetID"] = -1000 - index
        write_osu(beatmap, root / f"fixture_{index:02d}.osu")
    return root


def test_run_acceptance_reports_roundtrip_and_generation(tmp_path: Path):
    fixtures = _fixture_corpus(tmp_path / "fixtures")
    audio = tmp_path / "song.wav"
    _write_click_track(audio, bpm=120.0)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "audio_path": str(audio),
                        "expected_bpm": 120.0,
                        "expected_beats_ms": [500, 1000, 1500, 2000],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report = run_acceptance(
        fixtures_dir=fixtures,
        audio_path=audio,
        audio_manifest=manifest,
        output_dir=tmp_path / "out",
        prompts=["jump", "flow aim"],
        reference_maps=["tests/fixtures/sample_map.osu"],
        seed=3,
        target_star=1.0,
    )
    assert report["roundtrip"]["map_count"] >= 50
    assert report["replay"]["deterministic_rate"] == 1.0
    assert report["audio"]["median_bpm_abs_error"] < 1.0
    assert "style_control" in report
    assert "generation" in report
