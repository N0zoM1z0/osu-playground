from __future__ import annotations

import tempfile
from pathlib import Path

from osu_lab.beatmap.io import compile_osu, parse_osu
from osu_lab.beatmap.validate import verify_beatmap
from osu_lab.beatmap.verify_external import run_external_verifier
from osu_lab.eval.bench import benchmark_audio_tracking, benchmark_auto_workflow, benchmark_style_control
from osu_lab.generate.mapforge import generate_map
from osu_lab.replay.synth import inspect_replay, synthesize_replay_plan, write_replay


def _stable_metadata(source, reparsed) -> bool:
    fields = ("Title", "Artist", "Version", "Creator", "AudioFilename")
    return all(source.metadata.get(field) == reparsed.metadata.get(field) for field in fields)


def roundtrip_acceptance(fixtures_dir: str | Path, min_fixture_count: int = 50) -> dict[str, object]:
    fixtures = sorted(Path(fixtures_dir).rglob("*.osu"))
    stable = 0
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="osu-lab-roundtrip-") as tmpdir:
        temp_root = Path(tmpdir)
        for index, fixture in enumerate(fixtures):
            beatmap = parse_osu(fixture)
            compiled = compile_osu(beatmap)
            roundtrip_path = temp_root / f"{index}.osu"
            roundtrip_path.write_text(compiled, encoding="utf-8")
            reparsed = parse_osu(roundtrip_path)
            counts_stable = (
                len(beatmap.objects) == len(reparsed.objects)
                and len(beatmap.timing_grid.uninherited_points) == len(reparsed.timing_grid.uninherited_points)
                and len(beatmap.timing_grid.inherited_points) == len(reparsed.timing_grid.inherited_points)
            )
            metadata_stable = _stable_metadata(beatmap, reparsed)
            issues = verify_beatmap(reparsed)
            okay = counts_stable and metadata_stable and not [issue for issue in issues if issue.severity == "error"]
            stable += 1 if okay else 0
            results.append(
                {
                    "path": str(fixture),
                    "counts_stable": counts_stable,
                    "metadata_stable": metadata_stable,
                    "error_count": len([issue for issue in issues if issue.severity == "error"]),
                }
            )
    stable_rate = stable / max(1, len(fixtures))
    return {
        "fixtures_dir": str(fixtures_dir),
        "map_count": len(fixtures),
        "stable_roundtrips": stable,
        "stable_roundtrip_rate": stable_rate,
        "minimum_fixture_target": min_fixture_count,
        "meets_fixture_target": len(fixtures) >= min_fixture_count,
        "results": results,
        "status": "ok" if fixtures and stable == len(fixtures) and len(fixtures) >= min_fixture_count else "warn",
    }


def replay_acceptance(fixtures_dir: str | Path, profile: str = "auto_perfect", seed: int = 1) -> dict[str, object]:
    fixtures = sorted(Path(fixtures_dir).rglob("*.osu"))
    deterministic = 0
    parseable = 0
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="osu-lab-replays-") as tmpdir:
        temp_root = Path(tmpdir)
        for index, fixture in enumerate(fixtures):
            left = synthesize_replay_plan(fixture, profile=profile, seed=seed).to_dict()
            right = synthesize_replay_plan(fixture, profile=profile, seed=seed).to_dict()
            is_deterministic = left == right
            deterministic += 1 if is_deterministic else 0
            replay_path = temp_root / f"{index}.{profile}.osr"
            write_replay(fixture, replay_path, profile=profile, seed=seed)
            inspected = inspect_replay(replay_path)
            is_parseable = inspected["frame_count"] > 0 and inspected["rng_seed"] == seed
            parseable += 1 if is_parseable else 0
            results.append(
                {
                    "path": str(fixture),
                    "deterministic": is_deterministic,
                    "parseable": is_parseable,
                    "frame_count": inspected["frame_count"],
                }
            )
    total = max(1, len(fixtures))
    return {
        "fixtures_dir": str(fixtures_dir),
        "map_count": len(fixtures),
        "deterministic_rate": deterministic / total,
        "parseable_rate": parseable / total,
        "results": results,
        "status": "ok" if fixtures and deterministic == len(fixtures) and parseable == len(fixtures) else "warn",
    }


def generation_acceptance(
    audio_path: str | Path,
    output_dir: str | Path,
    prompts: list[str],
    seed: int = 1,
    reference_maps: list[str | Path] | None = None,
    target_star: float | None = None,
    target_pp: float | None = None,
    external_command: str | None = None,
) -> dict[str, object]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    star_hits = 0
    pp_hits = 0
    valid_maps = 0
    external_clean = 0
    for prompt in prompts:
        prompt_slug = prompt.replace(" ", "_").replace(",", "_")
        generation = generate_map(
            audio_path=audio_path,
            output_dir=output_root / prompt_slug,
            prompt=prompt,
            seed=seed,
            reference_maps=reference_maps,
            target_star=target_star,
            target_pp=target_pp,
        )
        internal_errors = [issue for issue in generation["validation_issues"] if issue["severity"] == "error"]
        star_delta = None if target_star is None else abs(float(generation["final_score"]["stars"]) - target_star)
        pp_delta_ratio = None
        if target_pp is not None:
            pp_delta_ratio = abs(float(generation["final_score"]["pp"]) - target_pp) / max(1.0, target_pp)
        external = run_external_verifier(generation["osu"], command=external_command)
        no_external_critical = external.get("status") in {"skipped", "ok"} and not external.get("stderr")
        valid_maps += 1 if not internal_errors else 0
        star_hits += 1 if star_delta is not None and star_delta <= 0.25 else 0
        pp_hits += 1 if pp_delta_ratio is not None and pp_delta_ratio <= 0.15 else 0
        external_clean += 1 if no_external_critical else 0
        results.append(
            {
                "prompt": prompt,
                "osu": generation["osu"],
                "internal_error_count": len(internal_errors),
                "external": external,
                "style_report": generation["style_report"],
                "stars": float(generation["final_score"]["stars"]),
                "pp": float(generation["final_score"]["pp"]),
                "star_delta": star_delta,
                "pp_delta_ratio": pp_delta_ratio,
            }
        )
    total = max(1, len(results))
    output = {
        "audio_path": str(audio_path),
        "prompt_count": len(results),
        "validity_pass_rate": valid_maps / total,
        "external_clean_rate": external_clean / total,
        "results": results,
        "status": "ok" if valid_maps == len(results) else "warn",
    }
    if target_star is not None:
        output["target_star"] = target_star
        output["star_hit_rate"] = star_hits / total
    if target_pp is not None:
        output["target_pp"] = target_pp
        output["pp_hit_rate"] = pp_hits / total
    return output


def run_acceptance(
    fixtures_dir: str | Path,
    audio_path: str | Path | None = None,
    audio_manifest: str | Path | None = None,
    output_dir: str | Path | None = None,
    prompts: list[str] | None = None,
    reference_maps: list[str | Path] | None = None,
    seed: int = 1,
    target_star: float | None = None,
    target_pp: float | None = None,
    external_command: str | None = None,
    min_fixture_count: int = 50,
) -> dict[str, object]:
    prompts = prompts or ["jump", "stream", "flow aim"]
    report = {
        "roundtrip": roundtrip_acceptance(fixtures_dir, min_fixture_count=min_fixture_count),
        "replay": replay_acceptance(fixtures_dir, seed=seed),
    }
    if audio_manifest:
        report["audio"] = benchmark_audio_tracking(audio_manifest)
    if audio_path and output_dir:
        report["generation"] = generation_acceptance(
            audio_path=audio_path,
            output_dir=output_dir,
            prompts=prompts,
            seed=seed,
            reference_maps=reference_maps,
            target_star=target_star,
            target_pp=target_pp,
            external_command=external_command,
        )
        report["style_control"] = benchmark_style_control(
            audio_path=audio_path,
            output_dir=Path(output_dir) / "style-control",
            prompts=prompts,
            reference_maps=reference_maps,
            seed=seed,
        )
        report["auto_workflow"] = benchmark_auto_workflow(
            audio_path=audio_path,
            output_dir=Path(output_dir) / "auto-workflow",
            prompt=prompts[0],
            refs=reference_maps,
            seed=seed,
            candidate_count=max(2, len(prompts)),
            target_star=target_star,
            target_pp=target_pp,
        )
    statuses = [section.get("status", "ok") for section in report.values() if isinstance(section, dict)]
    report["status"] = "ok" if statuses and all(status == "ok" for status in statuses) else "warn"
    return report
