from __future__ import annotations

from statistics import median

from osu_lab.core.models import AudioAnalysis, Segment, TimingDraft, TimingGrid, TimingPoint


def _beat_intervals(beats_ms: list[int]) -> list[int]:
    return [current - previous for previous, current in zip(beats_ms[:-1], beats_ms[1:]) if current > previous]


def _segment_bpm(beats_ms: list[int], start_ms: int, end_ms: int, fallback_bpm: float) -> float:
    local = [beat for beat in beats_ms if start_ms <= beat < end_ms]
    intervals = _beat_intervals(local)
    if not intervals:
        return fallback_bpm
    return round(60000.0 / median(intervals), 3)


def author_timing(
    analysis: AudioAnalysis,
    style_pack: dict[str, object] | None = None,
) -> TimingDraft:
    beats = analysis.beats_ms or [0]
    offset_ms = int(beats[0]) if beats else 0
    global_bpm = round(float(analysis.bpm or 120.0), 3)
    segments = analysis.segments or [Segment(start_ms=0, end_ms=analysis.duration_ms, label="main", confidence=0.5)]
    uninherited_points = []
    inherited_points = []
    breaks = []
    kiai_ranges = []
    report_sections = []
    previous_bpm = None

    for segment in segments:
        bpm = _segment_bpm(beats, segment.start_ms, segment.end_ms, global_bpm)
        if previous_bpm is None or abs(previous_bpm - bpm) >= 3.0:
            uninherited_points.append(
                {
                    "offset_ms": int(segment.start_ms),
                    "beat_length_ms": round(60000.0 / max(1.0, bpm), 3),
                    "meter": 4,
                }
            )
            previous_bpm = bpm
        label = segment.label.lower()
        if label in {"break", "outro"} or (segment.end_ms - segment.start_ms >= 6000 and segment.confidence < 0.5):
            breaks.append({"start_ms": int(segment.start_ms), "end_ms": int(segment.end_ms)})
        if label in {"chorus", "drop", "climax"}:
            kiai_ranges.append({"start_ms": int(segment.start_ms), "end_ms": int(segment.end_ms)})
            sv_multiplier = 1.0 + float((style_pack or {}).get("chorus", 0.0)) * 0.05
            inherited_points.append(
                {
                    "offset_ms": int(segment.start_ms),
                    "beat_length_ms": round(-100.0 / max(0.5, sv_multiplier), 3),
                    "meter": 4,
                }
            )
        report_sections.append(
            {
                "label": segment.label,
                "start_ms": int(segment.start_ms),
                "end_ms": int(segment.end_ms),
                "bpm": bpm,
                "timing_confidence": round(segment.confidence, 3),
            }
        )

    preview_time_ms = next((segment.start_ms for segment in segments if segment.label.lower() in {"chorus", "drop"}), offset_ms)
    return TimingDraft(
        bpm=global_bpm,
        offset_ms=offset_ms,
        uninherited_points=uninherited_points or [{"offset_ms": offset_ms, "beat_length_ms": round(60000.0 / max(1.0, global_bpm), 3), "meter": 4}],
        inherited_points=inherited_points,
        breaks=breaks,
        kiai_ranges=kiai_ranges,
        preview_time_ms=int(preview_time_ms),
        report={
            "raw_beat_count": len(beats),
            "segment_count": len(segments),
            "timing_sections": report_sections,
            "fallback_used": not bool(analysis.beats_ms),
        },
    )


def timing_draft_to_grid(draft: TimingDraft) -> TimingGrid:
    return TimingGrid(
        uninherited_points=[
            TimingPoint(offset_ms=float(item["offset_ms"]), beat_length_ms=float(item["beat_length_ms"]), meter=int(item.get("meter", 4)))
            for item in draft.uninherited_points
        ],
        inherited_points=[
            TimingPoint(offset_ms=float(item["offset_ms"]), beat_length_ms=float(item["beat_length_ms"]), meter=int(item.get("meter", 4)), uninherited=False)
            for item in draft.inherited_points
        ],
        meter_sections=[{"start_ms": int(item["offset_ms"]), "meter": int(item.get("meter", 4))} for item in draft.uninherited_points],
        kiai_ranges=draft.kiai_ranges,
        snap_divisors=[1, 2, 3, 4, 6, 8],
        offset_ms=float(draft.offset_ms),
    )
