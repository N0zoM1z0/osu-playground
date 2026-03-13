from __future__ import annotations

from osu_lab.core.models import BeatmapIR, ValidationIssue


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
        previous = item
    if not beatmap.timing_grid.uninherited_points:
        issues.append(ValidationIssue(severity="warning", code="timing", message="beatmap has no uninherited timing points"))
    return issues
