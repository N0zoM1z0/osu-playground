from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from osu_lab.core.utils import dataclass_to_dict


@dataclass(slots=True)
class Segment:
    start_ms: int
    end_ms: int
    label: str
    confidence: float


@dataclass(slots=True)
class AudioAnalysis:
    path: str
    duration_ms: int
    bpm: float
    bpm_candidates: list[float] = field(default_factory=list)
    beats_ms: list[int] = field(default_factory=list)
    downbeats_ms: list[int] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    onset_envelope: list[float] = field(default_factory=list)
    band_energy_summary: dict[str, float] = field(default_factory=dict)
    optional_stem_energy: dict[str, float] = field(default_factory=dict)
    backend: str = "fallback"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(slots=True)
class TimingPoint:
    offset_ms: float
    beat_length_ms: float
    meter: int = 4
    sample_set: int = 1
    sample_index: int = 0
    volume: int = 100
    uninherited: bool = True
    effects: int = 0


@dataclass(slots=True)
class TimingGrid:
    uninherited_points: list[TimingPoint] = field(default_factory=list)
    inherited_points: list[TimingPoint] = field(default_factory=list)
    meter_sections: list[dict[str, int]] = field(default_factory=list)
    kiai_ranges: list[dict[str, int]] = field(default_factory=list)
    snap_divisors: list[int] = field(default_factory=lambda: [1, 2, 3, 4, 6, 8])
    offset_ms: float = 0.0


@dataclass(slots=True)
class StyleTarget:
    prompt_tags: list[str] = field(default_factory=list)
    target_star: float | None = None
    target_pp: float | None = None
    mods_profile: list[str] = field(default_factory=list)
    difficulty_bias: float = 0.0
    reference_maps: list[str] = field(default_factory=list)
    section_density_plan: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class StyleProfile:
    spacing_histogram: dict[str, int] = field(default_factory=dict)
    angle_histogram: dict[str, int] = field(default_factory=dict)
    slider_ratio: float = 0.0
    burst_profile: dict[str, float] = field(default_factory=dict)
    jump_stream_tech_scores: dict[str, float] = field(default_factory=dict)
    section_density_curve: list[float] = field(default_factory=list)
    source_maps: list[str] = field(default_factory=list)


@dataclass(slots=True)
class NoteSelectionConfig:
    chart_source_bias: str = "mixed-following"
    onset_gate: float = 0.35
    anchor_downbeat_bonus: float = 0.25
    phrase_peak_bonus: float = 0.35
    rest_gate: float = 0.18
    repetition_window_ms: int = 750
    max_density_multiplier: float = 1.5


@dataclass(slots=True)
class SelectedEvent:
    time_ms: int
    role: str
    confidence: float
    selected: bool = True
    source: str = "beat"
    section_label: str = "main"
    phrase_index: int = 0
    reason: str = ""
    features: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class TimingDraft:
    bpm: float
    offset_ms: int
    uninherited_points: list[dict[str, Any]] = field(default_factory=list)
    inherited_points: list[dict[str, Any]] = field(default_factory=list)
    breaks: list[dict[str, int]] = field(default_factory=list)
    kiai_ranges: list[dict[str, int]] = field(default_factory=list)
    preview_time_ms: int = 0
    report: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StylePolicyPack:
    name: str
    density_policy: float = 1.0
    rhythm_simplification: float = 0.0
    note_selection_bias: dict[str, float] = field(default_factory=dict)
    spacing_schedule: dict[str, float] = field(default_factory=dict)
    angle_policy: dict[str, float] = field(default_factory=dict)
    slider_policy: dict[str, float] = field(default_factory=dict)
    phrase_continuity: float = 1.0
    chorus_lift: float = 0.0
    strain_choreography: dict[str, float] = field(default_factory=dict)
    repetition_policy: float = 1.0
    rest_policy: float = 1.0
    hitsound_policy: dict[str, float] = field(default_factory=dict)
    sv_policy: dict[str, float] = field(default_factory=dict)
    ranking_weights: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class PhrasePlan:
    section_label: str
    phrase_index: int
    start_ms: int
    end_ms: int
    energy: float
    movement_kind: str
    expected_density: float
    event_count: int
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MapQualityReport:
    overall_score: float
    metrics: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    regeneration_hints: list[str] = field(default_factory=list)
    section_scores: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class HitObjectIR:
    type: str
    start_ms: int
    end_ms: int
    x: int
    y: int
    curve: list[tuple[int, int]] = field(default_factory=list)
    repeats: int = 1
    length: float = 0.0
    hitsounds: int = 0
    combo_flags: int = 0
    semantic_role: str = "main"


@dataclass(slots=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    object_index: int | None = None


@dataclass(slots=True)
class BeatmapIR:
    metadata: dict[str, Any]
    difficulty_settings: dict[str, Any]
    audio_ref: str = ""
    background_ref: str = ""
    timing_grid: TimingGrid = field(default_factory=TimingGrid)
    objects: list[HitObjectIR] = field(default_factory=list)
    validation_report: list[ValidationIssue] = field(default_factory=list)
    general_settings: dict[str, Any] = field(default_factory=dict)
    editor_settings: dict[str, Any] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)
    colours: dict[str, str] = field(default_factory=dict)
    raw_sections: dict[str, list[str]] = field(default_factory=dict)
    source_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(slots=True)
class ReplayFrame:
    dt_ms: int
    x: float
    y: float
    keys: int


@dataclass(slots=True)
class ReplayPlan:
    profile: str
    seed: int
    frames: list[ReplayFrame] = field(default_factory=list)
    expected_score_stats: dict[str, Any] = field(default_factory=dict)
    source_map: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(slots=True)
class LiveEvent:
    at_ms: int
    action: str
    x: float | None = None
    y: float | None = None
    keys: int | None = None


@dataclass(slots=True)
class LivePlan:
    provider: str
    map_path: str
    playfield: dict[str, float]
    events: list[LiveEvent]
    dry_run: bool = True


def default_metadata(audio_filename: str, title: str = "Generated", version: str = "Normal") -> dict[str, Any]:
    return {
        "Title": title,
        "TitleUnicode": title,
        "Artist": "osu-lab",
        "ArtistUnicode": "osu-lab",
        "Creator": "osu-lab",
        "Version": version,
        "Source": "local",
        "Tags": "generated local",
        "BeatmapID": 0,
        "BeatmapSetID": -1,
        "AudioFilename": audio_filename,
    }
