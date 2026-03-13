from __future__ import annotations

import random
from pathlib import Path

from osu_lab.audio.analyze import analyze_audio
from osu_lab.beatmap.io import package_osz, write_ir_json, write_osu
from osu_lab.beatmap.validate import verify_beatmap
from osu_lab.core.models import AudioAnalysis, BeatmapIR, HitObjectIR, StyleProfile, StyleTarget, TimingGrid, TimingPoint, default_metadata
from osu_lab.core.utils import clamp


def build_timing_grid(audio_analysis: AudioAnalysis) -> TimingGrid:
    beat_length = 60000.0 / audio_analysis.bpm if audio_analysis.bpm else 500.0
    return TimingGrid(
        uninherited_points=[TimingPoint(offset_ms=audio_analysis.beats_ms[0] if audio_analysis.beats_ms else 0.0, beat_length_ms=beat_length)],
        inherited_points=[],
        meter_sections=[{"start_ms": 0, "meter": 4}],
        kiai_ranges=[],
        snap_divisors=[1, 2, 3, 4, 6, 8],
        offset_ms=float(audio_analysis.beats_ms[0] if audio_analysis.beats_ms else 0.0),
    )


def _density_step(style_target: StyleTarget, bpm: float) -> int:
    base = 1
    tags = {tag.lower() for tag in style_target.prompt_tags}
    if "deathstream" in tags:
        return 1
    if "stream" in tags:
        return 1
    if "jump" in tags or "farm jump" in tags:
        return 2 if bpm >= 180 else 1
    if "mixed" in tags or "control" in tags:
        return 2
    return base


def draft_skeleton(audio_analysis: AudioAnalysis, style_target: StyleTarget) -> BeatmapIR:
    timing_grid = build_timing_grid(audio_analysis)
    metadata = default_metadata(audio_filename=Path(audio_analysis.path).name, title=Path(audio_analysis.path).stem, version="Draft")
    difficulty = {
        "HPDrainRate": 5,
        "CircleSize": 4,
        "OverallDifficulty": 8,
        "ApproachRate": 9,
        "SliderMultiplier": 1.4,
        "SliderTickRate": 1,
    }
    beatmap = BeatmapIR(
        metadata=metadata,
        difficulty_settings=difficulty,
        audio_ref=Path(audio_analysis.path).name,
        timing_grid=timing_grid,
    )
    return beatmap


def arrange_objects(beatmap_ir: BeatmapIR, style_profile: StyleProfile | None = None, style_target: StyleTarget | None = None, seed: int = 1) -> BeatmapIR:
    style_target = style_target or StyleTarget(prompt_tags=["mixed"])
    rng = random.Random(seed)
    tags = {tag.lower() for tag in style_target.prompt_tags}
    beat_length = beatmap_ir.timing_grid.uninherited_points[0].beat_length_ms if beatmap_ir.timing_grid.uninherited_points else 500.0
    start = int(beatmap_ir.timing_grid.offset_ms)
    beats = list(range(start, start + int(beat_length * 64), int(beat_length)))
    spacing = 90
    if "farm jump" in tags:
        spacing = 220
    elif "jump" in tags:
        spacing = 180
    elif "flow aim" in tags:
        spacing = 140
    elif "stream" in tags:
        spacing = 70
    elif "deathstream" in tags:
        spacing = 50
    step = _density_step(style_target, 60000.0 / beat_length if beat_length else 120.0)

    objects: list[HitObjectIR] = []
    x = 128
    y = 192
    direction = 1
    for index, beat in enumerate(beats[::step]):
        if "flow aim" in tags:
            angle = index * 0.6
            x = int(clamp(256 + math_cos(angle) * spacing, 32, 480))
            y = int(clamp(192 + math_sin(angle) * (spacing * 0.8), 32, 352))
        elif "stream" in tags or "deathstream" in tags:
            x = int(clamp(x + direction * spacing, 32, 480))
            y = int(clamp(192 + ((index % 4) - 1.5) * 24, 32, 352))
            if x in {32, 480}:
                direction *= -1
        else:
            x = int(clamp((96 if index % 2 == 0 else 416) + rng.randint(-16, 16), 32, 480))
            y = int(clamp(96 + (index % 5) * 56 + rng.randint(-12, 12), 32, 352))
        object_type = "circle"
        length = 0.0
        curve: list[tuple[int, int]] = []
        end_ms = beat
        if "flow aim" in tags and index % 6 == 3:
            object_type = "slider"
            anchor = int(clamp(x + direction * 60, 32, 480))
            curve = [(anchor, y), (anchor, int(clamp(y + 40, 32, 352)))]
            length = 160.0
            end_ms = int(round(beat + (length / (beatmap_ir.difficulty_settings["SliderMultiplier"] * 100)) * beat_length))
        objects.append(
            HitObjectIR(
                type=object_type,
                start_ms=beat,
                end_ms=end_ms,
                x=x,
                y=y,
                curve=curve,
                repeats=1,
                length=length,
                semantic_role="generated",
            )
        )
        direction *= -1
    beatmap_ir.objects = objects
    beatmap_ir.validation_report = verify_beatmap(beatmap_ir)
    return beatmap_ir


def math_sin(value: float) -> float:
    import math

    return math.sin(value)


def math_cos(value: float) -> float:
    import math

    return math.cos(value)


def generate_map(
    audio_path: str | Path,
    output_dir: str | Path,
    prompt: str,
    seed: int = 1,
    target_star: float | None = None,
    target_pp: float | None = None,
    profile: StyleProfile | None = None,
) -> dict[str, str]:
    output_dir = Path(output_dir)
    analysis = analyze_audio(audio_path)
    style_target = StyleTarget(
        prompt_tags=[part.strip() for part in prompt.split(",") if part.strip()],
        target_star=target_star,
        target_pp=target_pp,
    )
    beatmap = draft_skeleton(analysis, style_target)
    beatmap = arrange_objects(beatmap, style_profile=profile, style_target=style_target, seed=seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = Path(audio_path).stem.replace(" ", "_")
    osu_path = output_dir / f"{slug}.osu"
    ir_path = output_dir / f"{slug}.ir.json"
    osz_path = output_dir / f"{slug}.osz"
    write_osu(beatmap, osu_path)
    write_ir_json(beatmap, ir_path)
    package_osz(osu_path, osz_path, asset_paths=[analysis.path])
    return {"osu": str(osu_path), "osz": str(osz_path), "ir": str(ir_path), "analysis_path": analysis.path}
