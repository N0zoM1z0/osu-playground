from __future__ import annotations

from osu_lab.core.models import AudioAnalysis, BeatmapIR, ReplayPlan, StyleProfile, StyleTarget, TimingGrid


def schema_bundle() -> dict[str, object]:
    return {
        "AudioAnalysis": {
            "type": "object",
            "required": ["path", "duration_ms", "bpm", "beats_ms"],
            "properties": {
                "path": {"type": "string"},
                "duration_ms": {"type": "integer"},
                "bpm": {"type": "number"},
                "bpm_candidates": {"type": "array", "items": {"type": "number"}},
                "beats_ms": {"type": "array", "items": {"type": "integer"}},
                "downbeats_ms": {"type": "array", "items": {"type": "integer"}},
                "segments": {"type": "array"},
                "onset_envelope": {"type": "array", "items": {"type": "number"}},
                "band_energy_summary": {"type": "object"},
                "optional_stem_energy": {"type": "object"},
            },
        },
        "TimingGrid": {
            "type": "object",
            "required": ["uninherited_points", "inherited_points", "snap_divisors", "offset_ms"],
            "properties": {
                "uninherited_points": {"type": "array"},
                "inherited_points": {"type": "array"},
                "meter_sections": {"type": "array"},
                "kiai_ranges": {"type": "array"},
                "snap_divisors": {"type": "array", "items": {"type": "integer"}},
                "offset_ms": {"type": "number"},
            },
        },
        "StyleTarget": {
            "type": "object",
            "properties": {
                "prompt_tags": {"type": "array", "items": {"type": "string"}},
                "target_star": {"type": ["number", "null"]},
                "target_pp": {"type": ["number", "null"]},
                "mods_profile": {"type": "array", "items": {"type": "string"}},
                "difficulty_bias": {"type": "number"},
                "reference_maps": {"type": "array", "items": {"type": "string"}},
                "section_density_plan": {"type": "array"},
            },
        },
        "StyleProfile": {
            "type": "object",
            "properties": {
                "spacing_histogram": {"type": "object"},
                "angle_histogram": {"type": "object"},
                "slider_ratio": {"type": "number"},
                "burst_profile": {"type": "object"},
                "jump_stream_tech_scores": {"type": "object"},
                "section_density_curve": {"type": "array", "items": {"type": "number"}},
            },
        },
        "BeatmapIR": {
            "type": "object",
            "required": ["metadata", "difficulty_settings", "timing_grid", "objects"],
            "properties": {
                "metadata": {"type": "object"},
                "difficulty_settings": {"type": "object"},
                "audio_ref": {"type": "string"},
                "background_ref": {"type": "string"},
                "timing_grid": {"type": "object"},
                "objects": {"type": "array"},
                "validation_report": {"type": "array"},
            },
        },
        "ReplayPlan": {
            "type": "object",
            "required": ["profile", "seed", "frames"],
            "properties": {
                "profile": {"type": "string"},
                "seed": {"type": "integer"},
                "frames": {"type": "array"},
                "expected_score_stats": {"type": "object"},
                "source_map": {"type": "string"},
            },
        },
        "_types": [
            AudioAnalysis.__name__,
            TimingGrid.__name__,
            StyleTarget.__name__,
            StyleProfile.__name__,
            BeatmapIR.__name__,
            ReplayPlan.__name__,
        ],
    }
