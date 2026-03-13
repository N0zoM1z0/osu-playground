from __future__ import annotations

import math
from pathlib import Path

from osu_lab.beatmap.io import parse_osu


def _pattern_signature(objects) -> dict[str, object]:
    anchors = [(item.x, item.y, item.start_ms, item.type) for item in objects]
    if len(anchors) < 2:
        return {}
    points = []
    gaps = []
    types = []
    base_x, base_y, _, _ = anchors[0]
    for current, previous in zip(anchors[1:], anchors[:-1]):
        dx = current[0] - previous[0]
        dy = current[1] - previous[1]
        gap = current[2] - previous[2]
        points.append((dx, dy))
        gaps.append(gap)
        types.append(current[3])
    span = max(math.hypot(dx, dy) for dx, dy in points) if points else 0.0
    return {
        "length": len(objects),
        "start_type": anchors[0][3],
        "points": points,
        "gaps": gaps,
        "types": types,
        "span": span,
        "source_start": anchors[0][2],
    }


def extract_pattern_bank(map_paths: list[str | Path], window_size: int = 4) -> list[dict[str, object]]:
    bank: list[dict[str, object]] = []
    for raw_path in map_paths:
        beatmap = parse_osu(raw_path)
        ordered = sorted(beatmap.objects, key=lambda item: item.start_ms)
        for index in range(0, max(0, len(ordered) - window_size + 1)):
            window = ordered[index : index + window_size]
            signature = _pattern_signature(window)
            if not signature:
                continue
            signature["source_map"] = str(Path(raw_path))
            bank.append(signature)
    return bank


def select_patterns(pattern_bank: list[dict[str, object]], mode: str, limit: int = 16) -> list[dict[str, object]]:
    ranked = []
    for pattern in pattern_bank:
        score = 0.0
        span = float(pattern.get("span", 0.0))
        mean_gap = sum(pattern.get("gaps", []) or [0]) / max(1, len(pattern.get("gaps", [])))
        if mode == "jump":
            score = span - mean_gap * 0.1
        elif mode == "stream":
            score = -mean_gap + span * 0.1
        elif mode == "flow aim":
            score = span * 0.6 + len([item for item in pattern.get("types", []) if item == "slider"]) * 10
        else:
            score = span
        ranked.append((score, pattern))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [pattern for _, pattern in ranked[:limit]]
