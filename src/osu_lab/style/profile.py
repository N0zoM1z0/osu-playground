from __future__ import annotations

import math
from pathlib import Path

from osu_lab.beatmap.io import parse_osu
from osu_lab.core.models import BeatmapIR, StyleProfile


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


def build_style_profile(map_paths: list[str | Path]) -> StyleProfile:
    spacing_histogram: dict[str, int] = {}
    angle_histogram: dict[str, int] = {}
    slider_count = 0
    object_count = 0
    burst_count = 0
    stream_count = 0
    density_curve: list[float] = []
    for raw_path in map_paths:
        beatmap = parse_osu(raw_path)
        ordered = sorted(beatmap.objects, key=lambda item: item.start_ms)
        object_count += len(ordered)
        slider_count += sum(1 for item in ordered if item.type == "slider")
        for value in _spacing_values(beatmap):
            spacing_histogram[_bucket(value, 50)] = spacing_histogram.get(_bucket(value, 50), 0) + 1
        for angle in _angle_values(beatmap):
            angle_histogram[_bucket(angle, 30)] = angle_histogram.get(_bucket(angle, 30), 0) + 1
        gaps = [current.start_ms - previous.start_ms for previous, current in zip(ordered[:-1], ordered[1:])]
        burst_count += sum(1 for gap in gaps if gap <= 125)
        stream_count += sum(1 for gap in gaps if gap <= 95)
        if ordered:
            last_time = max(item.end_ms for item in ordered)
            window_ms = 5000
            for start in range(0, last_time + window_ms, window_ms):
                end = start + window_ms
                density_curve.append(sum(1 for item in ordered if start <= item.start_ms < end) / 5.0)
    slider_ratio = slider_count / object_count if object_count else 0.0
    jump_signal = sum(count for bucket, count in spacing_histogram.items() if int(bucket.split("-")[0]) >= 150)
    tight_signal = sum(count for bucket, count in spacing_histogram.items() if int(bucket.split("-")[0]) < 100)
    angle_variety = sum(count for bucket, count in angle_histogram.items() if int(bucket.split("-")[0]) >= 90)
    total_spacing = max(1, sum(spacing_histogram.values()))
    total_angles = max(1, sum(angle_histogram.values()))
    return StyleProfile(
        spacing_histogram=spacing_histogram,
        angle_histogram=angle_histogram,
        slider_ratio=slider_ratio,
        burst_profile={
            "burst_ratio": burst_count / max(1, object_count),
            "stream_ratio": stream_count / max(1, object_count),
        },
        jump_stream_tech_scores={
            "jump": jump_signal / total_spacing,
            "stream": stream_count / max(1, object_count),
            "tech": angle_variety / total_angles,
            "flow": tight_signal / total_spacing,
        },
        section_density_curve=density_curve,
        source_maps=[str(Path(path)) for path in map_paths],
    )


def classify_map(map_path: str | Path) -> dict[str, float]:
    profile = build_style_profile([map_path])
    return profile.jump_stream_tech_scores
