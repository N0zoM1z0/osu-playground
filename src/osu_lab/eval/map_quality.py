from __future__ import annotations

import math

from osu_lab.core.models import BeatmapIR, MapQualityReport, PhrasePlan, SelectedEvent
from osu_lab.core.utils import clamp, mean


def _ordered_objects(beatmap: BeatmapIR):
    return sorted(beatmap.objects, key=lambda item: item.start_ms)


def _gaps(beatmap: BeatmapIR) -> list[int]:
    ordered = _ordered_objects(beatmap)
    return [current.start_ms - previous.start_ms for previous, current in zip(ordered[:-1], ordered[1:])]


def _spacings(beatmap: BeatmapIR) -> list[float]:
    ordered = _ordered_objects(beatmap)
    return [math.hypot(current.x - previous.x, current.y - previous.y) for previous, current in zip(ordered[:-1], ordered[1:])]


def _angle_changes(beatmap: BeatmapIR) -> list[float]:
    ordered = _ordered_objects(beatmap)
    values = []
    for first, second, third in zip(ordered[:-2], ordered[1:-1], ordered[2:]):
        ax, ay = second.x - first.x, second.y - first.y
        bx, by = third.x - second.x, third.y - second.y
        if not (ax or ay) or not (bx or by):
            continue
        angle_a = math.degrees(math.atan2(ay, ax))
        angle_b = math.degrees(math.atan2(by, bx))
        diff = abs(angle_b - angle_a)
        values.append(min(diff, 360.0 - diff))
    return values


def evaluate_map_quality(
    beatmap: BeatmapIR,
    selected_events: list[SelectedEvent] | None = None,
    phrase_plan: list[PhrasePlan] | None = None,
) -> MapQualityReport:
    gaps = _gaps(beatmap)
    spacings = _spacings(beatmap)
    angles = _angle_changes(beatmap)
    ordered = _ordered_objects(beatmap)
    slider_ratio = sum(1 for item in ordered if item.type == "slider") / max(1, len(ordered))
    spinner_ratio = sum(1 for item in ordered if item.type == "spinner") / max(1, len(ordered))
    repeated_gaps = sum(1 for left, right in zip(gaps[:-1], gaps[1:]) if abs(left - right) <= 8) / max(1, len(gaps) - 1)
    velocity_spikes = [spacing / max(1.0, gap) for spacing, gap in zip(spacings, gaps) if gap > 0]
    velocity_mean = mean(velocity_spikes, default=0.0)
    velocity_spike_severity = max((value - velocity_mean for value in velocity_spikes), default=0.0)
    gap_deviation = mean((abs(gap - mean(gaps, default=0.0)) for gap in gaps), default=0.0)
    phrase_alignment = 0.0
    chorus_lift_score = 0.0
    section_contrast = 0.0
    if phrase_plan:
        phrase_alignment = sum(1 for phrase in phrase_plan if phrase.event_count >= 2) / max(1, len(phrase_plan))
        chorus_phrases = [phrase for phrase in phrase_plan if phrase.section_label.lower() in {"chorus", "drop", "climax"}]
        non_chorus = [phrase for phrase in phrase_plan if phrase.section_label.lower() not in {"chorus", "drop", "climax"}]
        if chorus_phrases:
            chorus_lift_score = mean(phrase.expected_density for phrase in chorus_phrases) / max(0.1, mean(phrase.expected_density for phrase in non_chorus) if non_chorus else 1.0)
        if len(phrase_plan) >= 2:
            section_contrast = max(phrase.expected_density for phrase in phrase_plan) - min(phrase.expected_density for phrase in phrase_plan)
    selection_ratio = len(ordered) / max(1, len(selected_events or ordered))
    rest_space_preservation = 1.0 - min(1.0, slider_ratio + spinner_ratio * 0.5)
    pattern_diversity = len({item.semantic_role.split(":")[0] for item in ordered}) / max(1, len(ordered))
    metrics = {
        "rhythm_awkwardness": round(gap_deviation / max(1.0, mean(gaps, default=1.0)), 4),
        "repetition_monotony": round(repeated_gaps, 4),
        "cursor_velocity_spike_severity": round(max(0.0, velocity_spike_severity), 4),
        "angle_entropy_by_section": round(mean(angles, default=0.0) / 180.0, 4),
        "continuity_stability": round(1.0 / max(1.0, gap_deviation / 50.0), 4),
        "stream_continuity": round(sum(1 for gap in gaps if gap <= 110) / max(1, len(gaps)), 4),
        "slider_abuse_ratio": round(slider_ratio, 4),
        "phrase_boundary_alignment": round(phrase_alignment, 4),
        "chorus_lift_score": round(min(2.0, chorus_lift_score), 4),
        "section_contrast_score": round(section_contrast, 4),
        "chart_source_consistency": round(min(1.0, selection_ratio), 4),
        "rest_space_preservation": round(rest_space_preservation, 4),
        "readability_proxy": round(1.0 - clamp(velocity_mean * 2.4, 0.0, 0.95), 4),
        "pattern_diversity_score": round(pattern_diversity, 4),
    }
    overall = (
        (1.0 - metrics["rhythm_awkwardness"]) * 0.14
        + (1.0 - metrics["repetition_monotony"]) * 0.11
        + (1.0 - min(1.0, metrics["cursor_velocity_spike_severity"])) * 0.1
        + metrics["continuity_stability"] * 0.12
        + metrics["phrase_boundary_alignment"] * 0.1
        + min(1.0, metrics["chorus_lift_score"] / 1.2) * 0.09
        + min(1.0, metrics["section_contrast_score"]) * 0.07
        + metrics["rest_space_preservation"] * 0.09
        + metrics["readability_proxy"] * 0.1
        + min(1.0, metrics["pattern_diversity_score"] * 3.0) * 0.08
    )
    warnings = []
    hints = []
    if metrics["slider_abuse_ratio"] > 0.35:
        warnings.append("slider usage is high for the current selection")
        hints.append("reduce slider ratio or simplify connector policy")
    if metrics["cursor_velocity_spike_severity"] > 0.8:
        warnings.append("large cursor velocity spikes detected")
        hints.append("reduce spacing or improve phrase continuity")
    if metrics["repetition_monotony"] > 0.65:
        warnings.append("rhythm repetition is too uniform")
        hints.append("increase phrase variation or diversify note selection")
    if metrics["rest_space_preservation"] < 0.4:
        warnings.append("map does not leave enough breathing space")
        hints.append("preserve more rest windows in note selection")
    section_scores = [
        {
            "section_label": phrase.section_label,
            "phrase_index": phrase.phrase_index,
            "expected_density": phrase.expected_density,
            "energy": phrase.energy,
            "movement_kind": phrase.movement_kind,
        }
        for phrase in phrase_plan or []
    ]
    return MapQualityReport(
        overall_score=round(clamp(overall, 0.0, 1.0), 4),
        metrics=metrics,
        warnings=warnings,
        regeneration_hints=hints,
        section_scores=section_scores,
    )
