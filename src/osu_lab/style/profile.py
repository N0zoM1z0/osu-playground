from __future__ import annotations

import math
from pathlib import Path

from osu_lab.beatmap.io import parse_osu
from osu_lab.core.models import BeatmapIR, StyleProfile
from osu_lab.core.utils import mean


def _bucket(value: float, size: float) -> str:
    lower = int(value // size) * int(size)
    upper = lower + int(size)
    return f"{lower}-{upper}"


def _spacing_values(beatmap: BeatmapIR) -> list[float]:
    values = []
    ordered = sorted(beatmap.objects, key=lambda item: item.start_ms)
    for previous, current in zip(ordered[:-1], ordered[1:]):
        dx = current.x - previous.x
        dy = current.y - previous.y
        values.append(math.hypot(dx, dy))
    return values


def _angle_values(beatmap: BeatmapIR) -> list[float]:
    angles = []
    ordered = sorted(beatmap.objects, key=lambda item: item.start_ms)
    for first, second, third in zip(ordered[:-2], ordered[1:-1], ordered[2:]):
        ax = first.x - second.x
        ay = first.y - second.y
        bx = third.x - second.x
        by = third.y - second.y
        denom = math.hypot(ax, ay) * math.hypot(bx, by)
        if not denom:
            continue
        cosine = max(-1.0, min(1.0, (ax * bx + ay * by) / denom))
        angles.append(math.degrees(math.acos(cosine)))
    return angles


def _density_curve(beatmap: BeatmapIR, window_ms: int = 5000) -> list[float]:
    ordered = sorted(beatmap.objects, key=lambda item: item.start_ms)
    if not ordered:
        return []
    last_time = max(item.end_ms for item in ordered)
    values = []
    for start in range(0, last_time + window_ms, window_ms):
        end = start + window_ms
        values.append(sum(1 for item in ordered if start <= item.start_ms < end) / max(1.0, window_ms / 1000.0))
    return values


def _merge_histograms(target: dict[str, int], source: dict[str, int]) -> dict[str, int]:
    merged = dict(target)
    for key, value in source.items():
        merged[key] = merged.get(key, 0) + value
    return merged


def extract_map_style_metrics(map_path: str | Path) -> StyleProfile:
    beatmap = parse_osu(map_path)
    spacing_histogram: dict[str, int] = {}
    angle_histogram: dict[str, int] = {}
    spacing_values = _spacing_values(beatmap)
    angle_values = _angle_values(beatmap)
    ordered = sorted(beatmap.objects, key=lambda item: item.start_ms)
    slider_count = sum(1 for item in ordered if item.type == "slider")
    object_count = len(ordered)
    gaps = [current.start_ms - previous.start_ms for previous, current in zip(ordered[:-1], ordered[1:])]
    burst_count = sum(1 for gap in gaps if gap <= 125)
    stream_count = sum(1 for gap in gaps if gap <= 95)
    for value in spacing_values:
        spacing_histogram[_bucket(value, 50)] = spacing_histogram.get(_bucket(value, 50), 0) + 1
    for angle in angle_values:
        angle_histogram[_bucket(angle, 30)] = angle_histogram.get(_bucket(angle, 30), 0) + 1
    slider_ratio = slider_count / object_count if object_count else 0.0
    total_spacing = max(1, len(spacing_values))
    total_angles = max(1, len(angle_values))
    jump_signal = sum(count for bucket, count in spacing_histogram.items() if int(bucket.split("-")[0]) >= 150)
    tight_signal = sum(count for bucket, count in spacing_histogram.items() if int(bucket.split("-")[0]) < 100)
    angle_variety = sum(count for bucket, count in angle_histogram.items() if int(bucket.split("-")[0]) >= 90)
    return StyleProfile(
        spacing_histogram=spacing_histogram,
        angle_histogram=angle_histogram,
        slider_ratio=slider_ratio,
        burst_profile={
            "burst_ratio": burst_count / max(1, object_count),
            "stream_ratio": stream_count / max(1, object_count),
            "mean_gap_ms": mean(gaps, default=0.0),
            "object_count": float(object_count),
        },
        jump_stream_tech_scores={
            "jump": jump_signal / total_spacing,
            "stream": stream_count / max(1, object_count),
            "tech": angle_variety / total_angles,
            "flow": tight_signal / total_spacing,
        },
        section_density_curve=_density_curve(beatmap),
        source_maps=[str(Path(map_path))],
    )


def merge_style_profiles(profiles: list[StyleProfile]) -> StyleProfile:
    spacing_histogram: dict[str, int] = {}
    angle_histogram: dict[str, int] = {}
    source_maps: list[str] = []
    slider_ratios = []
    burst_ratios = []
    stream_ratios = []
    mean_gaps = []
    object_counts = []
    density_curve: list[float] = []
    jump_scores = []
    stream_scores = []
    tech_scores = []
    flow_scores = []
    max_density_windows = max((len(profile.section_density_curve) for profile in profiles), default=0)

    for profile in profiles:
        spacing_histogram = _merge_histograms(spacing_histogram, profile.spacing_histogram)
        angle_histogram = _merge_histograms(angle_histogram, profile.angle_histogram)
        source_maps.extend(profile.source_maps)
        slider_ratios.append(profile.slider_ratio)
        burst_ratios.append(profile.burst_profile.get("burst_ratio", 0.0))
        stream_ratios.append(profile.burst_profile.get("stream_ratio", 0.0))
        mean_gaps.append(profile.burst_profile.get("mean_gap_ms", 0.0))
        object_counts.append(profile.burst_profile.get("object_count", 0.0))
        jump_scores.append(profile.jump_stream_tech_scores.get("jump", 0.0))
        stream_scores.append(profile.jump_stream_tech_scores.get("stream", 0.0))
        tech_scores.append(profile.jump_stream_tech_scores.get("tech", 0.0))
        flow_scores.append(profile.jump_stream_tech_scores.get("flow", 0.0))
    for index in range(max_density_windows):
        values = [profile.section_density_curve[index] for profile in profiles if index < len(profile.section_density_curve)]
        density_curve.append(mean(values, default=0.0))

    return StyleProfile(
        spacing_histogram=spacing_histogram,
        angle_histogram=angle_histogram,
        slider_ratio=mean(slider_ratios, default=0.0),
        burst_profile={
            "burst_ratio": mean(burst_ratios, default=0.0),
            "stream_ratio": mean(stream_ratios, default=0.0),
            "mean_gap_ms": mean(mean_gaps, default=0.0),
            "object_count": mean(object_counts, default=0.0),
        },
        jump_stream_tech_scores={
            "jump": mean(jump_scores, default=0.0),
            "stream": mean(stream_scores, default=0.0),
            "tech": mean(tech_scores, default=0.0),
            "flow": mean(flow_scores, default=0.0),
        },
        section_density_curve=density_curve,
        source_maps=source_maps,
    )


def build_style_profile(map_paths: list[str | Path]) -> StyleProfile:
    return merge_style_profiles([extract_map_style_metrics(path) for path in map_paths])


def classify_map(map_path: str | Path) -> dict[str, float]:
    profile = extract_map_style_metrics(map_path)
    return profile.jump_stream_tech_scores


def render_style_report(profile: StyleProfile) -> str:
    dominant = max(profile.jump_stream_tech_scores, key=profile.jump_stream_tech_scores.get) if profile.jump_stream_tech_scores else "unknown"
    parts = [
        f"dominant={dominant}",
        f"slider_ratio={profile.slider_ratio:.2f}",
        f"jump={profile.jump_stream_tech_scores.get('jump', 0.0):.2f}",
        f"stream={profile.jump_stream_tech_scores.get('stream', 0.0):.2f}",
        f"tech={profile.jump_stream_tech_scores.get('tech', 0.0):.2f}",
        f"flow={profile.jump_stream_tech_scores.get('flow', 0.0):.2f}",
        f"burst_ratio={profile.burst_profile.get('burst_ratio', 0.0):.2f}",
        f"mean_gap_ms={profile.burst_profile.get('mean_gap_ms', 0.0):.1f}",
    ]
    if profile.source_maps:
        parts.append(f"sources={len(profile.source_maps)}")
    return " | ".join(parts)


def style_distance(left: StyleProfile, right: StyleProfile) -> float:
    score = 0.0
    for key in ("jump", "stream", "tech", "flow"):
        score += abs(left.jump_stream_tech_scores.get(key, 0.0) - right.jump_stream_tech_scores.get(key, 0.0))
    score += abs(left.slider_ratio - right.slider_ratio)
    score += abs(left.burst_profile.get("burst_ratio", 0.0) - right.burst_profile.get("burst_ratio", 0.0))
    score += abs(left.burst_profile.get("stream_ratio", 0.0) - right.burst_profile.get("stream_ratio", 0.0))
    max_len = max(len(left.section_density_curve), len(right.section_density_curve))
    for index in range(max_len):
        left_value = left.section_density_curve[index] if index < len(left.section_density_curve) else 0.0
        right_value = right.section_density_curve[index] if index < len(right.section_density_curve) else 0.0
        score += abs(left_value - right_value) / 10.0
    return score
