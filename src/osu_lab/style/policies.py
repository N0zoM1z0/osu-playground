from __future__ import annotations

from copy import deepcopy

from osu_lab.core.models import StylePolicyPack, StyleProfile
from osu_lab.core.utils import clamp


_BASE_RANKING = {
    "validation": 1.2,
    "quality": 1.4,
    "style": 1.1,
    "reference": 1.0,
    "stars": 0.9,
    "pp": 0.8,
}


BUILTIN_POLICY_PACKS: dict[str, StylePolicyPack] = {
    "flow_aim": StylePolicyPack(
        name="flow_aim",
        density_policy=1.05,
        rhythm_simplification=0.2,
        note_selection_bias={"slider_opportunity": 0.45, "phrase_peak": 0.25},
        spacing_schedule={"base": 140.0, "chorus": 1.1, "break": 0.8},
        angle_policy={"smoothness": 0.85, "volatility": 0.35},
        slider_policy={"ratio": 0.28, "connector_bias": 0.4},
        phrase_continuity=1.2,
        chorus_lift=0.22,
        strain_choreography={"chorus": 1.15, "break": 0.82},
        repetition_policy=0.85,
        rest_policy=1.05,
        hitsound_policy={"chorus_finish": 0.5},
        sv_policy={"chorus": 1.05},
        ranking_weights={**_BASE_RANKING, "quality": 1.5},
    ),
    "jump_control": StylePolicyPack(
        name="jump_control",
        density_policy=0.9,
        rhythm_simplification=0.3,
        note_selection_bias={"anchor": 0.35, "rest_window": 0.25},
        spacing_schedule={"base": 175.0, "chorus": 1.18, "break": 0.78},
        angle_policy={"smoothness": 0.5, "volatility": 0.45},
        slider_policy={"ratio": 0.08, "connector_bias": 0.1},
        phrase_continuity=0.95,
        chorus_lift=0.28,
        strain_choreography={"chorus": 1.2, "intro": 0.8},
        repetition_policy=1.0,
        rest_policy=1.1,
        hitsound_policy={"chorus_finish": 0.65},
        sv_policy={},
        ranking_weights={**_BASE_RANKING, "stars": 1.0},
    ),
    "farm_jump": StylePolicyPack(
        name="farm_jump",
        density_policy=0.88,
        rhythm_simplification=0.45,
        note_selection_bias={"anchor": 0.5, "phrase_peak": 0.3},
        spacing_schedule={"base": 215.0, "chorus": 1.22, "break": 0.76},
        angle_policy={"smoothness": 0.68, "volatility": 0.22},
        slider_policy={"ratio": 0.04, "connector_bias": 0.06},
        phrase_continuity=1.05,
        chorus_lift=0.34,
        strain_choreography={"chorus": 1.25, "verse": 0.92},
        repetition_policy=0.92,
        rest_policy=1.15,
        hitsound_policy={"chorus_finish": 0.72},
        sv_policy={},
        ranking_weights={**_BASE_RANKING, "pp": 1.0},
    ),
    "stream_focus": StylePolicyPack(
        name="stream_focus",
        density_policy=1.32,
        rhythm_simplification=0.1,
        note_selection_bias={"burst_start": 0.38, "stream_body": 0.55},
        spacing_schedule={"base": 74.0, "chorus": 1.05, "break": 0.85},
        angle_policy={"smoothness": 0.72, "volatility": 0.28},
        slider_policy={"ratio": 0.06, "connector_bias": 0.12},
        phrase_continuity=1.15,
        chorus_lift=0.16,
        strain_choreography={"chorus": 1.08, "break": 0.82},
        repetition_policy=0.88,
        rest_policy=0.82,
        hitsound_policy={"stream_clap": 0.55},
        sv_policy={"break": 0.96},
        ranking_weights={**_BASE_RANKING, "style": 1.2},
    ),
    "deathstream": StylePolicyPack(
        name="deathstream",
        density_policy=1.55,
        rhythm_simplification=0.05,
        note_selection_bias={"burst_start": 0.42, "stream_body": 0.72},
        spacing_schedule={"base": 56.0, "chorus": 1.02, "break": 0.92},
        angle_policy={"smoothness": 0.78, "volatility": 0.18},
        slider_policy={"ratio": 0.02, "connector_bias": 0.05},
        phrase_continuity=1.25,
        chorus_lift=0.08,
        strain_choreography={"chorus": 1.06, "break": 0.9},
        repetition_policy=0.8,
        rest_policy=0.62,
        hitsound_policy={"stream_clap": 0.65},
        sv_policy={"chorus": 1.02},
        ranking_weights={**_BASE_RANKING, "quality": 1.6},
    ),
    "hybrid_tech_light": StylePolicyPack(
        name="hybrid_tech_light",
        density_policy=1.0,
        rhythm_simplification=0.18,
        note_selection_bias={"slider_opportunity": 0.3, "transition": 0.28},
        spacing_schedule={"base": 110.0, "chorus": 1.06, "break": 0.82},
        angle_policy={"smoothness": 0.42, "volatility": 0.65},
        slider_policy={"ratio": 0.18, "connector_bias": 0.22},
        phrase_continuity=1.0,
        chorus_lift=0.18,
        strain_choreography={"chorus": 1.1, "bridge": 0.86},
        repetition_policy=0.76,
        rest_policy=0.96,
        hitsound_policy={"chorus_finish": 0.45, "stream_clap": 0.24},
        sv_policy={"bridge": 0.94},
        ranking_weights={**_BASE_RANKING, "reference": 1.15},
    ),
}


_PROMPT_TO_PACK = {
    "flow aim": "flow_aim",
    "jump": "jump_control",
    "farm jump": "farm_jump",
    "stream": "stream_focus",
    "deathstream": "deathstream",
    "control": "hybrid_tech_light",
    "mixed": "hybrid_tech_light",
}


def policy_pack_for_tag(tag: str) -> StylePolicyPack:
    key = _PROMPT_TO_PACK.get(tag.lower().strip(), "hybrid_tech_light")
    return deepcopy(BUILTIN_POLICY_PACKS[key])


def merge_policy_packs(packs: list[StylePolicyPack], reference_profile: StyleProfile | None = None) -> StylePolicyPack:
    if not packs:
        packs = [policy_pack_for_tag("mixed")]
    count = float(len(packs))
    merged = deepcopy(packs[0])
    if len(packs) > 1:
        merged.name = "+".join(pack.name for pack in packs)
        merged.density_policy = sum(pack.density_policy for pack in packs) / count
        merged.rhythm_simplification = sum(pack.rhythm_simplification for pack in packs) / count
        merged.phrase_continuity = sum(pack.phrase_continuity for pack in packs) / count
        merged.chorus_lift = sum(pack.chorus_lift for pack in packs) / count
        merged.repetition_policy = sum(pack.repetition_policy for pack in packs) / count
        merged.rest_policy = sum(pack.rest_policy for pack in packs) / count
        for field_name in ("note_selection_bias", "spacing_schedule", "angle_policy", "slider_policy", "strain_choreography", "hitsound_policy", "sv_policy", "ranking_weights"):
            merged_field: dict[str, float] = {}
            for pack in packs:
                field = getattr(pack, field_name)
                for key, value in field.items():
                    merged_field[key] = merged_field.get(key, 0.0) + float(value) / count
            setattr(merged, field_name, merged_field)
    if reference_profile is not None:
        jump_bias = reference_profile.jump_stream_tech_scores.get("jump", 0.0)
        flow_bias = reference_profile.jump_stream_tech_scores.get("flow", 0.0)
        stream_bias = reference_profile.jump_stream_tech_scores.get("stream", 0.0)
        merged.density_policy = clamp(merged.density_policy * (1.0 + stream_bias * 0.1 - jump_bias * 0.04), 0.65, 1.8)
        merged.slider_policy["ratio"] = clamp(merged.slider_policy.get("ratio", 0.1) * (1.0 + flow_bias * 0.15), 0.02, 0.4)
        merged.spacing_schedule["base"] = clamp(merged.spacing_schedule.get("base", 100.0) * (1.0 + jump_bias * 0.22 - stream_bias * 0.12), 52.0, 240.0)
    return merged
