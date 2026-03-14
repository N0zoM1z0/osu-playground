from __future__ import annotations

from osu_lab.core.models import PhrasePlan, SelectedEvent, Segment, StylePolicyPack
from osu_lab.core.utils import mean


def _movement_kind(section_label: str, policy: StylePolicyPack) -> str:
    label = section_label.lower()
    if label in {"chorus", "drop", "climax"}:
        return "lift"
    if label in {"break", "outro"}:
        return "relief"
    if policy.slider_policy.get("ratio", 0.0) >= 0.2:
        return "flow"
    if policy.note_selection_bias.get("stream_body", 0.0) >= 0.4:
        return "stream"
    return "control"


def build_phrase_plan(selected_events: list[SelectedEvent], segments: list[Segment], policy: StylePolicyPack) -> list[PhrasePlan]:
    phrases: list[PhrasePlan] = []
    if not selected_events:
        return phrases
    grouped: dict[tuple[str, int], list[SelectedEvent]] = {}
    for event in selected_events:
        grouped.setdefault((event.section_label, event.phrase_index), []).append(event)
    for segment in segments:
        segment_events = [
            event
            for key, events in grouped.items()
            if key[0] == segment.label
            for event in events
        ]
        if not segment_events:
            continue
        phrase_groups: dict[int, list[SelectedEvent]] = {}
        for event in segment_events:
            phrase_groups.setdefault(event.phrase_index, []).append(event)
        for phrase_index, events in sorted(phrase_groups.items()):
            density = len(events) / max(1.0, (segment.end_ms - segment.start_ms) / 1000.0)
            phrases.append(
                PhrasePlan(
                    section_label=segment.label,
                    phrase_index=phrase_index,
                    start_ms=min(event.time_ms for event in events),
                    end_ms=max(event.time_ms for event in events),
                    energy=round(mean(event.confidence for event in events), 4),
                    movement_kind=_movement_kind(segment.label, policy),
                    expected_density=round(density * policy.density_policy, 4),
                    event_count=len(events),
                    notes=[f"roles={','.join(sorted({event.role for event in events}))}"],
                )
            )
    return phrases
