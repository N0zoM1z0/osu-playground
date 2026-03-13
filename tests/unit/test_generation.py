import struct
import wave
from pathlib import Path

from osu_lab.core.models import AudioAnalysis, Segment
from osu_lab.generate.mapforge import arrange_objects, draft_skeleton, generate_map
from osu_lab.style.prompt import parse_style_prompt


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


def test_generate_map_uses_reference_patterns(tmp_path: Path):
    wav_path = tmp_path / "song.wav"
    out_dir = tmp_path / "out"
    _write_click_track(wav_path)
    result = generate_map(wav_path, out_dir, prompt="jump", seed=2, reference_maps=["tests/fixtures/sample_map.osu"])
    assert result["pattern_count"] > 0


def test_reference_patterns_are_stitched_into_output(tmp_path: Path):
    wav_path = tmp_path / "song.wav"
    out_dir = tmp_path / "out"
    _write_click_track(wav_path, bpm=180.0)
    result = generate_map(wav_path, out_dir, prompt="jump", seed=8, reference_maps=["tests/fixtures/sample_map.osu"])
    generated = Path(result["osu"]).read_text(encoding="utf-8")
    assert result["pattern_count"] > 0
    assert "sample_map" not in generated


def test_generate_map_emits_hitsound_summary(tmp_path: Path):
    wav_path = tmp_path / "song.wav"
    out_dir = tmp_path / "out"
    _write_click_track(wav_path)
    result = generate_map(wav_path, out_dir, prompt="flow aim", seed=3)
    assert result["hitsound_summary"]["finish"] >= 1
    assert result["hitsound_summary"]["clap"] >= 1


def test_section_arrangement_can_emit_break_spinner():
    analysis = AudioAnalysis(
        path="virtual.wav",
        duration_ms=5000,
        bpm=120.0,
        beats_ms=list(range(0, 5000, 500)),
        segments=[
            Segment(start_ms=0, end_ms=1500, label="intro", confidence=1.0),
            Segment(start_ms=1500, end_ms=3000, label="break", confidence=1.0),
            Segment(start_ms=3000, end_ms=5000, label="chorus", confidence=1.0),
        ],
    )
    target = parse_style_prompt("mixed")
    beatmap = draft_skeleton(analysis, target)
    arranged = arrange_objects(beatmap, audio_analysis=analysis, style_target=target, seed=4)
    assert any(item.hitsounds > 0 for item in arranged.objects)
    assert any("chorus" in item.semantic_role or "break" in item.semantic_role for item in arranged.objects)


def test_pattern_stitching_marks_transformed_semantics():
    analysis = AudioAnalysis(
        path="virtual.wav",
        duration_ms=6000,
        bpm=180.0,
        beats_ms=list(range(0, 6000, 333)),
        segments=[Segment(start_ms=0, end_ms=6000, label="chorus", confidence=1.0)],
    )
    target = parse_style_prompt("jump")
    beatmap = draft_skeleton(analysis, target)
    arranged = arrange_objects(
        beatmap,
        audio_analysis=analysis,
        style_target=target,
        seed=8,
        pattern_bank=[{"start_type": "circle", "points": [(180, 0), (180, 0)], "gaps": [333, 333], "types": ["circle", "circle"], "span": 180.0, "label": "jump"}],
    )
    assert any("generated:pattern:chorus" in item.semantic_role for item in arranged.objects)
