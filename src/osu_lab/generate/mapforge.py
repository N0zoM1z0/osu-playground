from __future__ import annotations

import copy
import random
import tempfile
from pathlib import Path

from osu_lab.audio.analyze import analyze_audio
from osu_lab.beatmap.io import package_osz, write_ir_json, write_osu
from osu_lab.beatmap.validate import verify_beatmap
from osu_lab.core.models import AudioAnalysis, BeatmapIR, HitObjectIR, Segment, StyleProfile, StyleTarget, TimingGrid, TimingPoint, default_metadata
from osu_lab.core.utils import clamp, dataclass_to_dict
from osu_lab.integration.scoring import score_map
from osu_lab.style.profile import build_style_profile
from osu_lab.style.prompt import parse_style_prompt


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


def _tag_set(style_target: StyleTarget) -> set[str]:
    return {tag.lower().strip() for tag in style_target.prompt_tags if tag.strip()}


def _base_spacing(tags: set[str]) -> int:
    if "farm jump" in tags:
        return 220
    if "jump" in tags:
        return 180
    if "flow aim" in tags:
        return 140
    if "stream" in tags:
        return 70
    if "deathstream" in tags:
        return 50
    return 90


def _density_step(style_target: StyleTarget, bpm: float, density_scale: float = 1.0) -> int:
    tags = _tag_set(style_target)
    base = 1
    if "jump" in tags or "farm jump" in tags:
        base = 2 if bpm >= 180 else 1
    elif "mixed" in tags or "control" in tags:
        base = 2
    return max(1, round(base / max(0.25, density_scale)))


def _slider_probability(tags: set[str], slider_ratio_bias: float) -> float:
    base = 0.08
    if "flow aim" in tags:
        base = 0.22
    elif "mixed" in tags:
        base = 0.12
    return clamp(base * slider_ratio_bias, 0.02, 0.45)


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
    return BeatmapIR(
        metadata=metadata,
        difficulty_settings=difficulty,
        audio_ref=Path(audio_analysis.path).name,
        timing_grid=timing_grid,
    )


def build_section_density_plan(audio_analysis: AudioAnalysis, style_target: StyleTarget, style_profile: StyleProfile | None = None) -> list[dict[str, float | str | int]]:
    tags = _tag_set(style_target)
    base_density = 1.0
    if "deathstream" in tags:
        base_density = 1.65
    elif "stream" in tags:
        base_density = 1.35
    elif "jump" in tags or "farm jump" in tags:
        base_density = 0.85
    elif "flow aim" in tags:
        base_density = 1.05
    profile_curve = style_profile.section_density_curve if style_profile else []
    segments = audio_analysis.segments or [Segment(start_ms=0, end_ms=audio_analysis.duration_ms, label="main", confidence=0.5)]
    plan: list[dict[str, float | str | int]] = []
    average_profile_density = sum(profile_curve) / len(profile_curve) if profile_curve else 1.0
    for index, segment in enumerate(segments):
        label = segment.label.lower()
        multiplier = base_density
        if label in {"chorus", "drop", "climax", "drive"}:
            multiplier *= 1.15
        elif label in {"break", "outro", "bridge"}:
            multiplier *= 0.8
        if profile_curve:
            profile_multiplier = profile_curve[min(index, len(profile_curve) - 1)]
            multiplier *= clamp(profile_multiplier / max(1.0, average_profile_density), 0.75, 1.35)
        plan.append(
            {
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
                "label": segment.label,
                "density_multiplier": round(multiplier, 3),
            }
        )
    return plan


def _plan_for_time(section_density_plan: list[dict[str, float | str | int]], at_ms: int) -> dict[str, float | str | int]:
    for section in section_density_plan:
        if int(section["start_ms"]) <= at_ms < int(section["end_ms"]):
            return section
    return section_density_plan[-1] if section_density_plan else {"density_multiplier": 1.0, "label": "main", "start_ms": 0, "end_ms": at_ms}


def _select_style_profile(reference_maps: list[str | Path] | None, profile: StyleProfile | None) -> StyleProfile | None:
    if reference_maps:
        resolved = [str(Path(path)) for path in reference_maps]
        return build_style_profile(resolved)
    return profile


def arrange_objects(
    beatmap_ir: BeatmapIR,
    audio_analysis: AudioAnalysis | None = None,
    style_profile: StyleProfile | None = None,
    style_target: StyleTarget | None = None,
    seed: int = 1,
    spacing_scale: float = 1.0,
    density_scale: float = 1.0,
    slider_ratio_bias: float = 1.0,
) -> BeatmapIR:
    style_target = style_target or StyleTarget(prompt_tags=["mixed"])
    rng = random.Random(seed)
    tags = _tag_set(style_target)
    beat_length = beatmap_ir.timing_grid.uninherited_points[0].beat_length_ms if beatmap_ir.timing_grid.uninherited_points else 500.0
    start = int(beatmap_ir.timing_grid.offset_ms)
    beats = [beat for beat in (audio_analysis.beats_ms if audio_analysis and audio_analysis.beats_ms else []) if beat >= start]
    if not beats:
        beats = list(range(start, start + int(beat_length * 96), int(beat_length)))
    spacing = int(_base_spacing(tags) * spacing_scale)
    if style_profile:
        spacing *= 1.0 + max(0.0, style_profile.jump_stream_tech_scores.get("jump", 0.0) - 0.2) * 0.25
        spacing *= 1.0 - max(0.0, style_profile.jump_stream_tech_scores.get("flow", 0.0) - 0.15) * 0.15
    section_density_plan = style_target.section_density_plan or build_section_density_plan(
        audio_analysis or AudioAnalysis(path="", duration_ms=int(beat_length * 96), bpm=60000.0 / beat_length if beat_length else 120.0),
        style_target,
        style_profile=style_profile,
    )
    slider_probability = _slider_probability(tags, slider_ratio_bias)

    objects: list[HitObjectIR] = []
    x = 128
    y = 192
    direction = 1
    emitted = 0
    previous_start = None
    for index, beat in enumerate(beats):
        section = _plan_for_time(section_density_plan, beat)
        local_density_scale = density_scale * float(section["density_multiplier"])
        step = _density_step(style_target, 60000.0 / beat_length if beat_length else 120.0, density_scale=local_density_scale)
        if index % step != 0:
            continue
        object_interval_ms = max(1, int(round(beat_length * step)))
        if previous_start is not None and beat - previous_start < max(10, int(round(beat_length / 4))):
            continue

        if "flow aim" in tags:
            angle = emitted * 0.58
            x = int(clamp(256 + math_cos(angle) * spacing, 32, 480))
            y = int(clamp(192 + math_sin(angle) * (spacing * 0.8), 32, 352))
        elif "stream" in tags or "deathstream" in tags:
            x = int(clamp(x + direction * spacing, 32, 480))
            y = int(clamp(192 + ((emitted % 6) - 2.5) * 18, 32, 352))
            if x in {32, 480}:
                direction *= -1
        else:
            anchor_x = 96 if emitted % 2 == 0 else 416
            x = int(clamp(anchor_x + rng.randint(-18, 18), 32, 480))
            y = int(clamp(88 + (emitted % 6) * 44 + rng.randint(-14, 14), 32, 352))

        object_type = "circle"
        length = 0.0
        curve: list[tuple[int, int]] = []
        end_ms = beat
        if rng.random() < slider_probability and emitted % 2 == 1:
            max_safe_length = max(
                0.0,
                ((object_interval_ms - 24) / beat_length) * (float(beatmap_ir.difficulty_settings["SliderMultiplier"]) * 100.0),
            )
            proposed_length = float(max(120, min(260, spacing * 1.2)))
            if max_safe_length >= 80:
                proposed_length = min(proposed_length, max_safe_length)
            else:
                proposed_length = 0.0
            if proposed_length > 0:
                object_type = "slider"
                anchor = int(clamp(x + direction * max(40, spacing // 2), 32, 480))
                curve = [(anchor, y), (anchor, int(clamp(y + 40, 32, 352)))]
                length = proposed_length
                end_ms = int(round(beat + (length / (float(beatmap_ir.difficulty_settings["SliderMultiplier"]) * 100.0)) * beat_length))

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
                semantic_role=f"generated:{section['label']}",
            )
        )
        emitted += 1
        previous_start = beat
        direction *= -1

    beatmap_ir.objects = objects
    beatmap_ir.validation_report = verify_beatmap(beatmap_ir)
    return beatmap_ir


def _estimate_map_stats(beatmap: BeatmapIR) -> dict[str, float]:
    with tempfile.TemporaryDirectory(prefix="osu-lab-score-") as tmpdir:
        temp_path = Path(tmpdir) / "candidate.osu"
        write_osu(beatmap, temp_path)
        score = score_map(temp_path)
    return {"stars": float(score["stars"]), "pp": float(score["pp"])}


def _tune_map(
    beatmap: BeatmapIR,
    audio_analysis: AudioAnalysis,
    style_profile: StyleProfile | None,
    style_target: StyleTarget,
    seed: int,
    ai_recipe: dict[str, object] | None,
) -> tuple[BeatmapIR, list[dict[str, float]]]:
    spacing_scale = float((ai_recipe or {}).get("spacing_bias", 1.0))
    density_scale = float((ai_recipe or {}).get("density_bias", 1.0))
    slider_ratio_bias = float((ai_recipe or {}).get("slider_ratio_bias", 1.0))
    history: list[dict[str, float]] = []
    best_map = None
    best_error = float("inf")

    for _ in range(5):
        candidate = arrange_objects(
            copy.deepcopy(beatmap),
            audio_analysis=audio_analysis,
            style_profile=style_profile,
            style_target=style_target,
            seed=seed,
            spacing_scale=spacing_scale,
            density_scale=density_scale,
            slider_ratio_bias=slider_ratio_bias,
        )
        stats = _estimate_map_stats(candidate)
        star_target = style_target.target_star
        pp_target = style_target.target_pp
        star_error = abs(stats["stars"] - star_target) if star_target is not None else 0.0
        pp_error = abs(stats["pp"] - pp_target) / max(1.0, pp_target or 1.0) if pp_target is not None else 0.0
        error = star_error + pp_error
        history.append(
            {
                "spacing_scale": spacing_scale,
                "density_scale": density_scale,
                "slider_ratio_bias": slider_ratio_bias,
                "stars": stats["stars"],
                "pp": stats["pp"],
                "error": error,
            }
        )
        if error < best_error:
            best_error = error
            best_map = candidate
        if star_target is not None:
            if stats["stars"] < star_target:
                spacing_scale *= 1.08
                density_scale *= 1.06
            else:
                spacing_scale *= 0.94
                density_scale *= 0.95
        if pp_target is not None:
            if stats["pp"] < pp_target:
                spacing_scale *= 1.03
                density_scale *= 1.04
            else:
                spacing_scale *= 0.98
                density_scale *= 0.98
        slider_ratio_bias = clamp(slider_ratio_bias, 0.5, 1.5)
        spacing_scale = clamp(spacing_scale, 0.5, 2.2)
        density_scale = clamp(density_scale, 0.4, 2.2)

    return best_map or arrange_objects(beatmap, audio_analysis=audio_analysis, style_profile=style_profile, style_target=style_target, seed=seed), history


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
    ai_recipe: dict[str, object] | None = None,
    reference_maps: list[str | Path] | None = None,
) -> dict[str, object]:
    output_dir = Path(output_dir)
    analysis = analyze_audio(audio_path)
    style_target = parse_style_prompt(prompt, target_star=target_star, target_pp=target_pp)
    style_target.difficulty_bias = float((ai_recipe or {}).get("difficulty_bias", style_target.difficulty_bias))
    if reference_maps:
        style_target.reference_maps = [str(Path(path)) for path in reference_maps]
    style_profile = _select_style_profile(reference_maps, profile)
    style_target.section_density_plan = build_section_density_plan(analysis, style_target, style_profile=style_profile)
    beatmap = draft_skeleton(analysis, style_target)
    beatmap, tuning_history = _tune_map(
        beatmap,
        audio_analysis=analysis,
        style_profile=style_profile,
        style_target=style_target,
        seed=seed,
        ai_recipe=ai_recipe,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = Path(audio_path).stem.replace(" ", "_")
    osu_path = output_dir / f"{slug}.osu"
    ir_path = output_dir / f"{slug}.ir.json"
    osz_path = output_dir / f"{slug}.osz"
    write_osu(beatmap, osu_path)
    write_ir_json(beatmap, ir_path)
    package_osz(osu_path, osz_path, asset_paths=[analysis.path])
    final_score = score_map(osu_path)
    return {
        "osu": str(osu_path),
        "osz": str(osz_path),
        "ir": str(ir_path),
        "analysis_path": analysis.path,
        "style_target": dataclass_to_dict(style_target),
        "style_profile": dataclass_to_dict(style_profile) if style_profile else None,
        "tuning_history": tuning_history,
        "final_score": final_score,
        "validation_issues": [dataclass_to_dict(issue) for issue in beatmap.validation_report],
    }
