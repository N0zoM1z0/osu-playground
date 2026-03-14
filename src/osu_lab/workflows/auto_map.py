from __future__ import annotations

import shutil
from pathlib import Path

from osu_lab.audio.analyze import analyze_audio
from osu_lab.core.utils import dataclass_to_dict, json_dump
from osu_lab.generate.candidate_search import search_candidate_maps
from osu_lab.generate.mapforge import build_section_density_plan
from osu_lab.generate.note_selection import NoteSelectionConfig, note_selection_report
from osu_lab.generate.phrase_planner import build_phrase_plan
from osu_lab.generate.timing_author import author_timing
from osu_lab.style.corpus import build_style_index
from osu_lab.style.profile import build_style_profile
from osu_lab.style.prompt_parser import resolve_style_prompt


def _resolve_reference_maps(refs: list[str | Path] | None) -> list[Path]:
    resolved: list[Path] = []
    for raw in refs or []:
        path = Path(raw)
        if path.is_dir():
            resolved.extend(sorted(path.rglob("*.osu")))
        elif path.suffix.lower() == ".osu":
            resolved.append(path)
    deduped = []
    seen = set()
    for path in resolved:
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return deduped


def _write_markdown_summary(output_dir: Path, payload: dict[str, object]) -> Path:
    best = payload.get("best_candidate") or {}
    lines = [
        "# osu-lab Auto Map Run",
        "",
        f"- Audio: `{payload['audio']}`",
        f"- Prompt: `{payload['prompt']}`",
        f"- Policy: `{payload['policy']['name']}`",
        f"- Selected events: `{payload['note_selection']['summary']['selected_count']}`",
        f"- Candidates: `{payload['candidate_search']['candidate_count']}`",
    ]
    if best:
        lines.extend(
            [
                f"- Best candidate: `{best.get('osu')}`",
                f"- Rank score: `{best.get('rank_score')}`",
                f"- Quality score: `{best.get('quality', {}).get('overall_score')}`",
                f"- Dominant class: `{best.get('dominant_class')}`",
            ]
        )
    target = output_dir / "summary.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def run_auto_map(
    audio_path: str | Path,
    output_dir: str | Path,
    prompt: str,
    refs: list[str | Path] | None = None,
    target_star: float | None = None,
    target_pp: float | None = None,
    candidate_count: int = 4,
    seed: int = 1,
    keep_intermediate: bool = True,
) -> dict[str, object]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    reference_maps = _resolve_reference_maps(refs)
    analysis = analyze_audio(audio_path)
    json_dump(analysis, output_root / "analysis.json")
    reference_profile = build_style_profile(reference_maps) if reference_maps else None
    style_index = build_style_index([str(path.parent) for path in reference_maps]) if reference_maps else None
    style_target, policy, constraints = resolve_style_prompt(prompt, target_star=target_star, target_pp=target_pp)
    if reference_profile is not None:
        from osu_lab.style.policies import merge_policy_packs

        policy = merge_policy_packs([policy], reference_profile=reference_profile)
    style_target.section_density_plan = build_section_density_plan(analysis, style_target, style_profile=reference_profile)
    timing_draft = author_timing(analysis, style_pack=policy.sv_policy)
    json_dump(timing_draft, output_root / "timing_draft.json")
    selection = note_selection_report(
        analysis,
        config=NoteSelectionConfig(chart_source_bias="mixed-following"),
        density_plan=style_target.section_density_plan,
        policy=policy,
    )
    json_dump(selection, output_root / "note_selection.json")
    phrase_plan = build_phrase_plan(selection["selected"], analysis.segments, policy)
    json_dump(phrase_plan, output_root / "phrase_plan.json")
    candidate_search = search_candidate_maps(
        analysis=analysis,
        output_dir=output_root / "candidates",
        style_target=style_target,
        policy=policy,
        timing_draft=timing_draft,
        selected_events=selection["selected"],
        phrase_plan=phrase_plan,
        candidate_count=candidate_count,
        seed=seed,
        reference_maps=reference_maps,
        style_profile=reference_profile,
        style_index=style_index,
    )
    best = candidate_search["best"]
    final_artifacts = {}
    if best:
        final_osu = output_root / "final.osu"
        final_osz = output_root / "final.osz"
        final_ir = output_root / "final.ir.json"
        shutil.copy2(best["osu"], final_osu)
        shutil.copy2(best["osz"], final_osz)
        shutil.copy2(best["ir"], final_ir)
        final_artifacts = {"osu": str(final_osu), "osz": str(final_osz), "ir": str(final_ir)}
    payload = {
        "audio": str(audio_path),
        "prompt": prompt,
        "refs": [str(path) for path in reference_maps],
        "policy": dataclass_to_dict(policy),
        "constraints": constraints,
        "timing_draft": dataclass_to_dict(timing_draft),
        "note_selection": dataclass_to_dict(selection),
        "phrase_plan": dataclass_to_dict(phrase_plan),
        "candidate_search": candidate_search,
        "best_candidate": best,
        "final_artifacts": final_artifacts,
        "artifacts": {
            "analysis": str(output_root / "analysis.json"),
            "timing_draft": str(output_root / "timing_draft.json"),
            "note_selection": str(output_root / "note_selection.json"),
            "phrase_plan": str(output_root / "phrase_plan.json"),
        },
        "status": "ok" if best else "empty",
    }
    json_dump(payload, output_root / "run_manifest.json")
    payload["summary_markdown"] = str(_write_markdown_summary(output_root, payload))
    if not keep_intermediate and best:
        keep_osu = Path(best["osu"]).resolve()
        for candidate_dir in sorted((output_root / "candidates").glob("candidate_*")):
            candidate_osu = candidate_dir / "candidate.osu"
            if candidate_osu.exists() and candidate_osu.resolve() != keep_osu:
                for artifact in candidate_dir.iterdir():
                    artifact.unlink(missing_ok=True)
                candidate_dir.rmdir()
    return payload
