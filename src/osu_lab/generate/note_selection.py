from __future__ import annotations

from dataclasses import replace

from osu_lab.core.models import AudioAnalysis, NoteSelectionConfig, SelectedEvent, Segment, StylePolicyPack
from osu_lab.core.utils import clamp


def _segment_for_time(segments: list[Segment], at_ms: int) -> Segment:
    for segment in segments:
        if segment.start_ms <= at_ms < segment.end_ms:
            return segment
    return segments[-1] if segments else Segment(start_ms=0, end_ms=at_ms + 1, label="main", confidence=0.0)


def _onset_value(analysis: AudioAnalysis, at_ms: int) -> float:
    if not analysis.onset_envelope:
        return 0.0
    ratio = clamp(at_ms / max(1, analysis.duration_ms), 0.0, 0.999)
    index = min(len(analysis.onset_envelope) - 1, int(ratio * len(analysis.onset_envelope)))
    return float(analysis.onset_envelope[index])


def _role_for_event(
    at_ms: int,
    segment: Segment,
    onset_strength: float,
    is_downbeat: bool,
    density_scale: float,
    policy: StylePolicyPack | None,
) -> str:
    label = segment.label.lower()
    stream_bias = (policy.note_selection_bias.get("stream_body", 0.0) if policy else 0.0)
    slider_bias = (policy.note_selection_bias.get("slider_opportunity", 0.0) if policy else 0.0)
    peak_bias = (policy.note_selection_bias.get("phrase_peak", 0.0) if policy else 0.0)
    if label in {"break", "outro", "bridge"} and onset_strength < 0.35:
        return "rest_window"
    if label in {"chorus", "drop", "climax"} and onset_strength + peak_bias > 0.6:
        return "phrase_peak"
    if onset_strength + slider_bias > 0.72:
        return "slider_opportunity"
    if density_scale >= 1.25 and onset_strength + stream_bias > 0.42:
        return "stream_body"
    if density_scale >= 1.1 and onset_strength > 0.38:
        return "burst_start"
    if is_downbeat:
        return "anchor"
    if label in {"bridge", "verse", "intro"} and onset_strength > 0.3:
        return "transition"
    return "filler"


def _confidence_for_role(role: str, onset_strength: float, segment: Segment) -> float:
    base = {
        "anchor": 0.72,
        "filler": 0.42,
        "phrase_peak": 0.84,
        "transition": 0.56,
        "slider_opportunity": 0.63,
        "burst_start": 0.66,
        "stream_body": 0.68,
        "rest_window": 0.58,
    }.get(role, 0.5)
    return clamp(base + onset_strength * 0.25 + segment.confidence * 0.1, 0.0, 1.0)


def _selection_threshold(role: str, config: NoteSelectionConfig, policy: StylePolicyPack | None) -> float:
    threshold = config.onset_gate
    if role == "anchor":
        threshold -= config.anchor_downbeat_bonus * 0.3
    if role == "phrase_peak":
        threshold -= config.phrase_peak_bonus * 0.35
    if role == "rest_window":
        threshold = config.rest_gate
    if policy is not None:
        threshold -= policy.note_selection_bias.get(role, 0.0) * 0.2
        threshold += policy.rhythm_simplification * 0.08 if role == "filler" else 0.0
    return clamp(threshold, 0.08, 0.8)


def build_candidate_event_timeline(
    analysis: AudioAnalysis,
    config: NoteSelectionConfig | None = None,
    density_plan: list[dict[str, float | str | int]] | None = None,
    policy: StylePolicyPack | None = None,
) -> dict[str, object]:
    config = config or NoteSelectionConfig()
    beats = analysis.beats_ms or list(range(0, analysis.duration_ms, int(round(60000.0 / max(1.0, analysis.bpm or 120.0)))))
    segments = analysis.segments or [Segment(start_ms=0, end_ms=analysis.duration_ms, label="main", confidence=0.5)]
    downbeats = set(analysis.downbeats_ms or beats[::4])
    selected: list[SelectedEvent] = []
    rejected: list[SelectedEvent] = []
    previous_selected = -10_000
    phrase_index = -1
    current_section = None

    for beat in beats:
        segment = _segment_for_time(segments, beat)
        if segment.label != current_section:
            phrase_index += 1
            current_section = segment.label
        density_scale = 1.0
        for section in density_plan or []:
            if int(section["start_ms"]) <= beat < int(section["end_ms"]):
                density_scale = float(section["density_multiplier"])
                break
        onset_strength = _onset_value(analysis, beat)
        role = _role_for_event(beat, segment, onset_strength, beat in downbeats, density_scale, policy)
        confidence = _confidence_for_role(role, onset_strength, segment)
        threshold = _selection_threshold(role, config, policy)
        selected_now = confidence >= threshold
        reasons = [f"segment={segment.label}", f"onset={onset_strength:.2f}", f"density={density_scale:.2f}", f"threshold={threshold:.2f}"]
        if beat - previous_selected < config.repetition_window_ms and role == "filler":
            selected_now = False
            reasons.append("repetition-pruned")
        if role == "rest_window":
            selected_now = False
            reasons.append("rest-preserved")
        event = SelectedEvent(
            time_ms=int(beat),
            role=role,
            confidence=round(confidence, 4),
            selected=selected_now,
            source="downbeat" if beat in downbeats else "beat",
            section_label=segment.label,
            phrase_index=phrase_index,
            reason="; ".join(reasons),
            features={
                "onset_strength": round(onset_strength, 4),
                "density_scale": round(density_scale, 4),
                "segment_confidence": round(segment.confidence, 4),
            },
        )
        if selected_now:
            selected.append(event)
            previous_selected = beat
        else:
            rejected.append(event)

    summary = {
        "selected_count": len(selected),
        "rejected_count": len(rejected),
        "role_histogram": {},
        "chart_source_bias": config.chart_source_bias,
    }
    for item in selected:
        summary["role_histogram"][item.role] = summary["role_histogram"].get(item.role, 0) + 1
    return {"selected": selected, "rejected": rejected, "summary": summary}


def note_selection_report(
    analysis: AudioAnalysis,
    config: NoteSelectionConfig | None = None,
    density_plan: list[dict[str, float | str | int]] | None = None,
    policy: StylePolicyPack | None = None,
) -> dict[str, object]:
    payload = build_candidate_event_timeline(analysis, config=config, density_plan=density_plan, policy=policy)
    return payload
