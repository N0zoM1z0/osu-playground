import struct
import wave
from pathlib import Path

from osu_lab.audio.analyze import analyze_audio
from osu_lab.beatmap.io import parse_osu
from osu_lab.eval.map_quality import evaluate_map_quality
from osu_lab.generate.note_selection import note_selection_report
from osu_lab.generate.phrase_planner import build_phrase_plan
from osu_lab.generate.timing_author import author_timing
from osu_lab.style.prompt_parser import resolve_style_prompt


def _write_click_track(path: Path, bpm: float = 150.0, seconds: int = 6, sample_rate: int = 44100) -> None:
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


def test_note_selection_report_explains_selected_and_rejected(tmp_path: Path):
    audio = tmp_path / "song.wav"
    _write_click_track(audio, bpm=120.0)
    analysis = analyze_audio(audio)
    target, policy, _ = resolve_style_prompt("flow aim with chorus jump lift")
    target.section_density_plan = [
        {"start_ms": 0, "end_ms": analysis.duration_ms // 2, "label": "verse", "density_multiplier": 1.0},
        {"start_ms": analysis.duration_ms // 2, "end_ms": analysis.duration_ms, "label": "chorus", "density_multiplier": 1.15},
    ]
    report = note_selection_report(analysis, density_plan=target.section_density_plan, policy=policy)
    assert report["selected"]
    assert report["rejected"]
    assert report["selected"][0].reason
    assert report["summary"]["role_histogram"]


def test_timing_author_emits_sections_breaks_and_kiai(tmp_path: Path):
    audio = tmp_path / "song.wav"
    _write_click_track(audio, bpm=140.0)
    analysis = analyze_audio(audio)
    analysis.segments[0].label = "intro"
    analysis.segments[1].label = "break"
    analysis.segments[2].label = "chorus"
    draft = author_timing(analysis, style_pack={"chorus": 1.1})
    assert draft.uninherited_points
    assert draft.breaks
    assert draft.kiai_ranges
    assert draft.preview_time_ms >= 0


def test_prompt_resolution_changes_policy_behavior():
    _, flow_policy, flow_constraints = resolve_style_prompt("melodic flow aim, low slider spam")
    _, stream_policy, _ = resolve_style_prompt("deathstream but not too tech")
    assert flow_policy.slider_policy["ratio"] < 0.28
    assert flow_constraints["melodic"] is True
    assert stream_policy.angle_policy["volatility"] < 0.18 or stream_policy.density_policy > flow_policy.density_policy


def test_map_quality_returns_metric_breakdown():
    beatmap = parse_osu("tests/fixtures/sample_map.osu")
    quality = evaluate_map_quality(beatmap)
    assert quality.metrics["pattern_diversity_score"] >= 0.0
    assert "readability_proxy" in quality.metrics
