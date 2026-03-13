from __future__ import annotations

import math
from pathlib import Path

from osu_lab.beatmap.io import parse_osu
from osu_lab.core.utils import clamp
from osu_lab.integration.scoring import score_map


def _safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _classify_pattern(span: float, mean_gap: float, slider_ratio: float, angle_change: float) -> str:
    if mean_gap and mean_gap <= 120:
        return "stream"
    if span >= 150:
        return "jump"
    if slider_ratio >= 0.25 or angle_change >= 70:
        return "flow aim"
    return "mixed"


def _pattern_signature(objects, source_map: str, map_stars: float) -> dict[str, object]:
    anchors = [(item.x, item.y, item.start_ms, item.type) for item in objects]
    if len(anchors) < 2:
        return {}
    points = []
    gaps = []
    types = [anchor[3] for anchor in anchors]
    headings = []
    for current, previous in zip(anchors[1:], anchors[:-1]):
        dx = current[0] - previous[0]
        dy = current[1] - previous[1]
        gap = current[2] - previous[2]
        points.append((dx, dy))
        gaps.append(gap)
        headings.append(math.degrees(math.atan2(dy, dx)))
    span_values = [math.hypot(dx, dy) for dx, dy in points]
    angle_change = 0.0
    if len(headings) >= 2:
        diffs = [abs(current - previous) for current, previous in zip(headings[1:], headings[:-1])]
        angle_change = _safe_mean([min(diff, 360 - diff) for diff in diffs])
    slider_ratio = sum(1 for item in types if item == "slider") / len(types)
    mean_gap = _safe_mean(gaps)
    density = 1000.0 / mean_gap if mean_gap else 0.0
    span = max(span_values) if span_values else 0.0
    label = _classify_pattern(span, mean_gap, slider_ratio, angle_change)
    return {
        "length": len(objects),
        "start_type": anchors[0][3],
        "points": points,
        "gaps": gaps,
        "types": types[1:],
        "span": span,
        "mean_gap_ms": mean_gap,
        "density": density,
        "angle_change": angle_change,
        "slider_ratio": slider_ratio,
        "label": label,
        "source_start": anchors[0][2],
        "source_map": source_map,
        "source_stars": map_stars,
    }


def extract_pattern_bank(map_paths: list[str | Path], window_size: int = 4) -> list[dict[str, object]]:
    bank: list[dict[str, object]] = []
    for raw_path in map_paths:
        path = Path(raw_path)
        beatmap = parse_osu(path)
        ordered = sorted(beatmap.objects, key=lambda item: item.start_ms)
        try:
            map_stars = float(score_map(path)["stars"])
        except Exception:
            map_stars = 0.0
        for index in range(0, max(0, len(ordered) - window_size + 1)):
            window = ordered[index : index + window_size]
            signature = _pattern_signature(window, source_map=str(path), map_stars=map_stars)
            if signature:
                bank.append(signature)
    return bank


def _section_label_bonus(pattern: dict[str, object], section_label: str) -> float:
    label = section_label.lower()
    density = float(pattern.get("density", 0.0))
    if label in {"chorus", "drop", "climax", "drive"}:
        return density * 18.0 + float(pattern.get("span", 0.0)) * 0.1
    if label in {"break", "outro", "bridge"}:
        return -density * 12.0 + float(pattern.get("slider_ratio", 0.0)) * 10.0
    return density * 4.0


def _mode_score(pattern: dict[str, object], mode: str) -> float:
    span = float(pattern.get("span", 0.0))
    mean_gap = float(pattern.get("mean_gap_ms", 0.0))
    slider_ratio = float(pattern.get("slider_ratio", 0.0))
    angle_change = float(pattern.get("angle_change", 0.0))
    label = str(pattern.get("label", "mixed"))
    score = 0.0
    if mode == "jump":
        score = span - mean_gap * 0.08 - slider_ratio * 20.0
        if label == "jump":
            score += 40.0
    elif mode == "stream":
        score = -mean_gap + span * 0.04 + angle_change * 0.05
        if label == "stream":
            score += 35.0
    elif mode == "flow aim":
        score = angle_change * 0.7 + slider_ratio * 35.0 + span * 0.15
        if label == "flow aim":
            score += 35.0
    else:
        score = span * 0.5 + angle_change * 0.1
        if label == "mixed":
            score += 20.0
    return score


def score_pattern_for_context(
    pattern: dict[str, object],
    mode: str,
    section_label: str = "main",
    target_stars: float | None = None,
    target_density: float | None = None,
) -> float:
    score = _mode_score(pattern, mode) + _section_label_bonus(pattern, section_label)
    if target_stars is not None:
        score -= abs(float(pattern.get("source_stars", 0.0)) - target_stars) * 18.0
    if target_density is not None:
        score -= abs(float(pattern.get("density", 0.0)) - target_density) * 25.0
    return score


def select_patterns(
    pattern_bank: list[dict[str, object]],
    mode: str,
    limit: int = 16,
    section_label: str = "main",
    target_stars: float | None = None,
    target_density: float | None = None,
) -> list[dict[str, object]]:
    ranked = sorted(
        pattern_bank,
        key=lambda pattern: score_pattern_for_context(
            pattern,
            mode=mode,
            section_label=section_label,
            target_stars=target_stars,
            target_density=target_density,
        ),
        reverse=True,
    )
    return ranked[:limit]


def transform_pattern(
    pattern: dict[str, object],
    scale: float = 1.0,
    mirror_x: bool = False,
    mirror_y: bool = False,
    rotate_quadrants: int = 0,
) -> dict[str, object]:
    transformed_points = []
    angle = rotate_quadrants % 4
    for raw_dx, raw_dy in pattern.get("points", []):
        dx = -raw_dx if mirror_x else raw_dx
        dy = -raw_dy if mirror_y else raw_dy
        dx *= scale
        dy *= scale
        if angle == 1:
            dx, dy = -dy, dx
        elif angle == 2:
            dx, dy = -dx, -dy
        elif angle == 3:
            dx, dy = dy, -dx
        transformed_points.append((int(round(dx)), int(round(dy))))
    transformed = dict(pattern)
    transformed["points"] = transformed_points
    transformed["span"] = max((math.hypot(dx, dy) for dx, dy in transformed_points), default=0.0)
    transformed["transform"] = {
        "scale": scale,
        "mirror_x": mirror_x,
        "mirror_y": mirror_y,
        "rotate_quadrants": rotate_quadrants % 4,
    }
    return transformed


def project_pattern_positions(pattern: dict[str, object], origin_x: int, origin_y: int) -> list[tuple[int, int]]:
    positions = [(origin_x, origin_y)]
    current_x = origin_x
    current_y = origin_y
    for dx, dy in pattern.get("points", []):
        current_x += int(dx)
        current_y += int(dy)
        positions.append((current_x, current_y))
    return positions


def adapt_pattern_to_context(
    pattern: dict[str, object],
    origin_x: int,
    origin_y: int,
    section_spacing: int,
    previous_vector: tuple[float, float] | None = None,
) -> dict[str, object]:
    base_span = max(1.0, float(pattern.get("span", 0.0)))
    target_scale = max(0.6, min(1.5, section_spacing / base_span))
    scale_candidates = sorted({round(target_scale, 2), round(max(0.75, target_scale * 0.9), 2), round(min(1.35, target_scale * 1.1), 2)})
    previous_heading = None
    if previous_vector is not None and (previous_vector[0] or previous_vector[1]):
        previous_heading = math.degrees(math.atan2(previous_vector[1], previous_vector[0]))

    best = dict(pattern)
    best_score = float("-inf")
    for scale in scale_candidates:
        for mirror_x in (False, True):
            for mirror_y in (False, True):
                for rotation in range(4):
                    candidate = transform_pattern(
                        pattern,
                        scale=scale,
                        mirror_x=mirror_x,
                        mirror_y=mirror_y,
                        rotate_quadrants=rotation,
                    )
                    positions = project_pattern_positions(candidate, origin_x, origin_y)
                    clamped_positions = [
                        (
                            int(clamp(x, 32, 480)),
                            int(clamp(y, 32, 352)),
                        )
                        for x, y in positions
                    ]
                    boundary_penalty = sum(
                        abs(clamped_x - x) + abs(clamped_y - y)
                        for (x, y), (clamped_x, clamped_y) in zip(positions, clamped_positions)
                    )
                    score = -boundary_penalty * 2.0
                    score -= abs(float(candidate.get("span", 0.0)) - section_spacing) * 0.2
                    points = candidate.get("points", [])
                    if previous_heading is not None and points:
                        current_heading = math.degrees(math.atan2(points[0][1], points[0][0]))
                        turn = abs(current_heading - previous_heading)
                        score -= min(turn, 360.0 - turn) * 0.25
                    if positions[-1][0] < 64 or positions[-1][0] > 448:
                        score -= 12.0
                    if positions[-1][1] < 64 or positions[-1][1] > 320:
                        score -= 8.0
                    if score > best_score:
                        best_score = score
                        best = candidate
    return best
