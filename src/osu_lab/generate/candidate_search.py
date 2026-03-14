from __future__ import annotations

import copy
from pathlib import Path

from osu_lab.beatmap.io import package_osz, write_ir_json, write_osu
from osu_lab.core.models import AudioAnalysis, BeatmapIR, PhrasePlan, SelectedEvent, StylePolicyPack, StyleProfile, StyleTarget
from osu_lab.core.utils import dataclass_to_dict
from osu_lab.eval.map_quality import evaluate_map_quality
from osu_lab.generate.mapforge import _select_pattern_bank, arrange_objects, build_section_density_plan, draft_skeleton
from osu_lab.generate.timing_author import timing_draft_to_grid
from osu_lab.integration.scoring import score_map
from osu_lab.style.profile import build_style_profile, classify_map, style_distance


def _mutate_selection(events: list[SelectedEvent], candidate_index: int, policy: StylePolicyPack) -> list[SelectedEvent]:
    mutated = []
    for index, event in enumerate(events):
        keep = event.selected
        if event.role == "filler" and (index + candidate_index) % max(2, 4 - int(policy.rhythm_simplification * 2)) != 0:
            keep = False
        if event.role == "stream_body" and candidate_index % 2 == 1:
            keep = keep or event.confidence > 0.58
        mutated.append(copy.deepcopy(event))
        mutated[-1].selected = keep
    return mutated


def _selected_analysis(analysis: AudioAnalysis, events: list[SelectedEvent], timing_bpm: float) -> AudioAnalysis:
    selected = [event for event in events if event.selected]
    downbeats = [event.time_ms for event in selected if event.role in {"anchor", "phrase_peak"}]
    return AudioAnalysis(
        path=analysis.path,
        duration_ms=analysis.duration_ms,
        bpm=timing_bpm,
        bpm_candidates=analysis.bpm_candidates,
        beats_ms=[event.time_ms for event in selected],
        downbeats_ms=downbeats,
        segments=analysis.segments,
        onset_envelope=analysis.onset_envelope,
        band_energy_summary=analysis.band_energy_summary,
        optional_stem_energy=analysis.optional_stem_energy,
        backend=analysis.backend,
    )


def _style_fit_score(prompt_tags: list[str], dominant_class: str) -> float:
    if any(tag in {"deathstream", "stream"} for tag in prompt_tags):
        return 1.0 if dominant_class == "stream" else 0.5
    if any(tag in {"jump", "farm jump"} for tag in prompt_tags):
        return 1.0 if dominant_class == "jump" else 0.55
    if "flow aim" in prompt_tags:
        return 1.0 if dominant_class == "flow" else 0.6
    return 1.0 if dominant_class in {"tech", "flow"} else 0.6


def _target_fit(actual: float, target: float | None, tolerance: float) -> float:
    if target is None:
        return 1.0
    delta = abs(actual - target)
    return max(0.0, 1.0 - delta / max(tolerance, target if tolerance > 1 else 1.0))


def _candidate_report(
    beatmap: BeatmapIR,
    candidate_dir: Path,
    audio_path: str | Path,
    selected_events: list[SelectedEvent],
    phrase_plan: list[PhrasePlan],
    prompt_tags: list[str],
    policy: StylePolicyPack,
    reference_profile: StyleProfile | None,
    target_star: float | None,
    target_pp: float | None,
) -> dict[str, object]:
    osu_path = candidate_dir / "candidate.osu"
    ir_path = candidate_dir / "candidate.ir.json"
    osz_path = candidate_dir / "candidate.osz"
    write_osu(beatmap, osu_path)
    write_ir_json(beatmap, ir_path)
    package_osz(osu_path, osz_path, asset_paths=[audio_path])
    score = score_map(osu_path)
    generated_profile = build_style_profile([osu_path])
    quality = evaluate_map_quality(beatmap, selected_events=selected_events, phrase_plan=phrase_plan)
    classifications = classify_map(osu_path)
    dominant_class = max(classifications, key=classifications.get) if classifications else "unknown"
    reference_distance = style_distance(generated_profile, reference_profile) if reference_profile else None
    provenance = {
        "retrieved": sum(1 for item in beatmap.objects if "generated:pattern" in item.semantic_role and "native" in item.semantic_role),
        "transformed": sum(1 for item in beatmap.objects if "generated:pattern" in item.semantic_role and "transformed" in item.semantic_role),
        "procedural": sum(1 for item in beatmap.objects if "generated:pattern" not in item.semantic_role),
    }
    ranking_weights = policy.ranking_weights
    style_fit = _style_fit_score(prompt_tags, dominant_class)
    star_fit = _target_fit(float(score["stars"]), target_star, 0.25)
    pp_fit = _target_fit(float(score["pp"]), target_pp, 0.15 * max(1.0, target_pp or 1.0))
    reference_fit = 1.0 / (1.0 + reference_distance) if reference_distance is not None else 1.0
    validation_penalty = len([issue for issue in beatmap.validation_report if issue.severity == "error"])
    final_rank_score = (
        max(0.0, 1.0 - validation_penalty) * ranking_weights.get("validation", 1.0)
        + quality.overall_score * ranking_weights.get("quality", 1.0)
        + style_fit * ranking_weights.get("style", 1.0)
        + reference_fit * ranking_weights.get("reference", 1.0)
        + star_fit * ranking_weights.get("stars", 1.0)
        + pp_fit * ranking_weights.get("pp", 1.0)
    )
    return {
        "osu": str(osu_path),
        "osz": str(osz_path),
        "ir": str(ir_path),
        "score": score,
        "quality": dataclass_to_dict(quality),
        "classifications": classifications,
        "dominant_class": dominant_class,
        "style_fit": style_fit,
        "reference_distance": reference_distance,
        "reference_fit": reference_fit,
        "star_fit": star_fit,
        "pp_fit": pp_fit,
        "validation_errors": [dataclass_to_dict(issue) for issue in beatmap.validation_report if issue.severity == "error"],
        "provenance": provenance,
        "arrangement_report": {
            "phrase_plan": [dataclass_to_dict(phrase) for phrase in phrase_plan],
            "continuity_diagnostics": {
                "cursor_velocity_spikes": quality.metrics.get("cursor_velocity_spike_severity", 0.0),
                "angle_awkwardness": quality.metrics.get("angle_entropy_by_section", 0.0),
                "repetition_monotony": quality.metrics.get("repetition_monotony", 0.0),
            },
        },
        "rank_score": round(final_rank_score, 4),
    }


def search_candidate_maps(
    analysis: AudioAnalysis,
    output_dir: str | Path,
    style_target: StyleTarget,
    policy: StylePolicyPack,
    timing_draft,
    selected_events: list[SelectedEvent],
    phrase_plan: list[PhrasePlan],
    candidate_count: int = 4,
    seed: int = 1,
    reference_maps: list[str | Path] | None = None,
    style_profile: StyleProfile | None = None,
    style_index: dict[str, object] | None = None,
) -> dict[str, object]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    pattern_bank = _select_pattern_bank(reference_maps, style_index)
    style_target.section_density_plan = build_section_density_plan(analysis, style_target, style_profile=style_profile)
    reference_profile = style_profile if reference_maps else None
    candidates = []
    for candidate_index in range(candidate_count):
        mutated_events = _mutate_selection(selected_events, candidate_index, policy)
        event_analysis = _selected_analysis(analysis, mutated_events, timing_draft.bpm)
        beatmap = draft_skeleton(event_analysis, style_target)
        beatmap.timing_grid = timing_draft_to_grid(timing_draft)
        beatmap.metadata["Version"] = f"Auto Candidate {candidate_index + 1}"
        beatmap = arrange_objects(
            beatmap,
            audio_analysis=event_analysis,
            style_profile=style_profile,
            style_target=style_target,
            seed=seed + candidate_index,
            spacing_scale=(policy.spacing_schedule.get("base", 90.0) / 90.0) * (1.0 + candidate_index * 0.03),
            density_scale=policy.density_policy * (1.0 + (candidate_index % 3) * 0.04),
            slider_ratio_bias=max(0.5, policy.slider_policy.get("ratio", 0.1) / 0.12),
            pattern_bank=pattern_bank,
        )
        candidate_dir = output_root / f"candidate_{candidate_index + 1:02d}"
        report = _candidate_report(
            beatmap,
            candidate_dir,
            analysis.path,
            [event for event in mutated_events if event.selected],
            phrase_plan,
            style_target.prompt_tags,
            policy,
            reference_profile,
            style_target.target_star,
            style_target.target_pp,
        )
        report["seed"] = seed + candidate_index
        report["selected_event_count"] = len([event for event in mutated_events if event.selected])
        candidates.append(report)
    ranked = sorted(candidates, key=lambda item: (item["rank_score"], item["quality"]["overall_score"]), reverse=True)
    return {
        "candidate_count": len(ranked),
        "ranking": [
            {
                "path": item["osu"],
                "rank_score": item["rank_score"],
                "quality_score": item["quality"]["overall_score"],
                "style_fit": item["style_fit"],
                "reference_fit": item["reference_fit"],
                "star_fit": item["star_fit"],
                "pp_fit": item["pp_fit"],
            }
            for item in ranked
        ],
        "candidates": ranked,
        "best": ranked[0] if ranked else None,
    }
