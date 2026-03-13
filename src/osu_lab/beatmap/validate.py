from __future__ import annotations

from osu_lab.core.models import BeatmapIR, ValidationIssue


def _timing_point_at(beatmap: BeatmapIR, at_ms: int):
    selected = None
    for point in beatmap.timing_grid.uninherited_points:
        if point.offset_ms <= at_ms:
            selected = point
        else:
            break
    return selected


def _snap_error_ms(beatmap: BeatmapIR, at_ms: int) -> float:
    point = _timing_point_at(beatmap, at_ms)
    if point is None or point.beat_length_ms <= 0:
        return 0.0
    best = float("inf")
    for divisor in beatmap.timing_grid.snap_divisors or [1, 2, 4, 8]:
        step = point.beat_length_ms / divisor
        if step <= 0:
            continue
        position = (at_ms - point.offset_ms) / step
        nearest = round(position)
        snapped = point.offset_ms + nearest * step
        best = min(best, abs(at_ms - snapped))
    return 0.0 if best == float("inf") else best


def verify_beatmap(beatmap: BeatmapIR) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    previous = None
    for index, item in enumerate(sorted(beatmap.objects, key=lambda obj: obj.start_ms)):
        if not 0 <= item.x <= 512 or not 0 <= item.y <= 384:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="bounds",
                    message=f"object {index} is outside osu!standard playfield",
                    object_index=index,
                )
            )
        if previous is not None:
            gap = item.start_ms - previous.end_ms
            minimum_gap = 20 if previous.type == "slider" else 10
            if gap < minimum_gap:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="object-gap",
                        message=f"object {index} starts {gap}ms after previous object; expected >= {minimum_gap}ms",
                        object_index=index,
                    )
                )
        start_snap_error = _snap_error_ms(beatmap, item.start_ms)
        if start_snap_error >= 2.0:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="snap-start",
                    message=f"object {index} is {start_snap_error:.2f}ms away from the nearest snap tick",
                    object_index=index,
                )
            )
        if item.type == "slider":
            end_snap_error = _snap_error_ms(beatmap, item.end_ms)
            if end_snap_error >= 2.0:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="snap-end",
                        message=f"slider {index} ends {end_snap_error:.2f}ms away from the nearest snap tick",
                        object_index=index,
                    )
                )
        previous = item
    if not beatmap.timing_grid.uninherited_points:
        issues.append(ValidationIssue(severity="warning", code="timing", message="beatmap has no uninherited timing points"))
    return issues
