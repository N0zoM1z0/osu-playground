from __future__ import annotations

import argparse
from pathlib import Path

from osu_lab.ai.adapters import draft_with_backend
from osu_lab.audio.analyze import analyze_audio
from osu_lab.beatmap.io import parse_osu
from osu_lab.beatmap.validate import verify_beatmap
from osu_lab.beatmap.verify_external import run_external_verifier
from osu_lab.core.schema import schema_bundle
from osu_lab.core.models import StyleProfile
from osu_lab.core.utils import dataclass_to_dict, json_dump, json_print
from osu_lab.eval.bench import benchmark_summary
from osu_lab.generate.mapforge import generate_map
from osu_lab.integration.scoring import score_map
from osu_lab.live.planner import arm_live_plan, plan_live_play
from osu_lab.replay.synth import dump_replay_plan, inspect_replay, write_replay
from osu_lab.style.corpus import build_style_index, load_style_index
from osu_lab.style.profile import build_style_profile, classify_map


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="osu-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audio = subparsers.add_parser("audio")
    audio_sub = audio.add_subparsers(dest="audio_command", required=True)
    audio_analyze = audio_sub.add_parser("analyze")
    audio_analyze.add_argument("path")
    audio_analyze.add_argument("--out")
    audio_analyze.add_argument("--no-normalize", action="store_true")

    replay = subparsers.add_parser("replay")
    replay_sub = replay.add_subparsers(dest="replay_command", required=True)
    replay_synth = replay_sub.add_parser("synth")
    replay_synth.add_argument("map")
    replay_synth.add_argument("--out")
    replay_synth.add_argument("--profile", default="auto_perfect")
    replay_synth.add_argument("--seed", type=int, default=1)
    replay_synth.add_argument("--plan-json")
    replay_inspect = replay_sub.add_parser("inspect")
    replay_inspect.add_argument("path")

    live = subparsers.add_parser("live")
    live_sub = live.add_subparsers(dest="live_command", required=True)
    live_plan = live_sub.add_parser("plan")
    live_plan.add_argument("map", nargs="?", default="")
    live_plan.add_argument("--profile", default="auto_perfect")
    live_plan.add_argument("--provider", choices=["direct-file/manual", "tosu"], default="direct-file/manual")
    live_plan.add_argument("--tosu-base-url", default="http://127.0.0.1:24050")
    live_plan.add_argument("--cache-dir")
    live_plan.add_argument("--width", type=int, default=1280)
    live_plan.add_argument("--height", type=int, default=960)
    live_arm = live_sub.add_parser("arm")
    live_arm.add_argument("map", nargs="?", default="")
    live_arm.add_argument("--profile", default="auto_perfect")
    live_arm.add_argument("--provider", choices=["direct-file/manual", "tosu"], default="direct-file/manual")
    live_arm.add_argument("--tosu-base-url", default="http://127.0.0.1:24050")
    live_arm.add_argument("--cache-dir")
    live_arm.add_argument("--inject", action="store_true")
    live_arm.add_argument("--lead-in-ms", type=int, default=1000)

    map_parser = subparsers.add_parser("map")
    map_sub = map_parser.add_subparsers(dest="map_command", required=True)
    map_generate = map_sub.add_parser("generate")
    map_generate.add_argument("audio")
    map_generate.add_argument("--out-dir", required=True)
    map_generate.add_argument("--prompt", default="mixed")
    map_generate.add_argument("--seed", type=int, default=1)
    map_generate.add_argument("--target-star", type=float)
    map_generate.add_argument("--target-pp", type=float)
    map_generate.add_argument("--reference-map", action="append", default=[])
    map_generate.add_argument("--style-index")
    map_verify = map_sub.add_parser("verify")
    map_verify.add_argument("path")
    map_verify.add_argument("--external-command")
    map_score = map_sub.add_parser("score")
    map_score.add_argument("path")
    map_score.add_argument("--mods", default="")
    map_score.add_argument("--acc", type=float, default=98.0)

    style = subparsers.add_parser("style")
    style_sub = style.add_subparsers(dest="style_command", required=True)
    style_index = style_sub.add_parser("build-index")
    style_index.add_argument("paths", nargs="+")
    style_index.add_argument("--out", required=True)
    style_profile_cmd = style_sub.add_parser("profile")
    style_profile_cmd.add_argument("maps", nargs="+")

    ai = subparsers.add_parser("ai")
    ai_sub = ai.add_subparsers(dest="ai_command", required=True)
    ai_draft = ai_sub.add_parser("draft")
    ai_draft.add_argument("backend")
    ai_draft.add_argument("audio")
    ai_draft.add_argument("--prompt", default="mixed")
    ai_draft.add_argument("--out")
    ai_draft.add_argument("--seed", type=int, default=1)
    ai_draft.add_argument("--target-star", type=float)
    ai_draft.add_argument("--target-pp", type=float)
    ai_draft.add_argument("--reference-map", action="append", default=[])

    schema = subparsers.add_parser("schema")
    schema_sub = schema.add_subparsers(dest="schema_command", required=True)
    schema_dump = schema_sub.add_parser("dump")
    schema_dump.add_argument("--out")

    bench = subparsers.add_parser("bench")
    bench.add_argument("fixtures_dir")
    return parser


def _verify_path(path: Path, external_command: str | None = None) -> dict[str, object]:
    beatmap = parse_osu(path)
    issues = verify_beatmap(beatmap)
    return {
        "path": str(path),
        "issue_count": len(issues),
        "issues": [dataclass_to_dict(issue) for issue in issues],
        "external": run_external_verifier(path, command=external_command),
    }


def _style_index_bundle(path: str | Path | None):
    if not path:
        return None, None
    index = load_style_index(path)
    aggregate = index.get("aggregate")
    if not isinstance(aggregate, dict):
        return None, index
    profile = StyleProfile(
        spacing_histogram=aggregate.get("spacing_histogram", {}),
        angle_histogram=aggregate.get("angle_histogram", {}),
        slider_ratio=aggregate.get("slider_ratio", 0.0),
        burst_profile=aggregate.get("burst_profile", {}),
        jump_stream_tech_scores=aggregate.get("jump_stream_tech_scores", {}),
        section_density_curve=aggregate.get("section_density_curve", []),
        source_maps=aggregate.get("source_maps", []),
    )
    return profile, index


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "audio" and args.audio_command == "analyze":
        analysis = analyze_audio(args.path, normalize=not args.no_normalize)
        if args.out:
            json_dump(analysis, Path(args.out))
        json_print(analysis)
        return 0

    if args.command == "replay" and args.replay_command == "synth":
        out = Path(args.out) if args.out else Path(args.map).with_suffix(f".{args.profile}.osr")
        replay_path, plan = write_replay(args.map, out, profile=args.profile, seed=args.seed)
        if args.plan_json:
            dump_replay_plan(plan, args.plan_json)
        json_print({"replay_path": str(replay_path), "plan": plan})
        return 0

    if args.command == "replay" and args.replay_command == "inspect":
        json_print(inspect_replay(args.path))
        return 0

    if args.command == "live" and args.live_command == "plan":
        try:
            plan = plan_live_play(
                args.map,
                profile=args.profile,
                provider=args.provider,
                client_width=args.width,
                client_height=args.height,
                tosu_base_url=args.tosu_base_url,
                cache_dir=args.cache_dir,
            )
        except Exception as exc:
            json_print({"status": "error", "provider": args.provider, "message": str(exc)})
            return 1
        json_print(plan)
        return 0

    if args.command == "live" and args.live_command == "arm":
        try:
            plan = plan_live_play(
                args.map,
                profile=args.profile,
                provider=args.provider,
                tosu_base_url=args.tosu_base_url,
                cache_dir=args.cache_dir,
            )
        except Exception as exc:
            json_print({"status": "error", "provider": args.provider, "message": str(exc)})
            return 1
        json_print(arm_live_plan(plan, dry_run=not args.inject, lead_in_ms=args.lead_in_ms))
        return 0

    if args.command == "map" and args.map_command == "generate":
        style_profile, style_index = _style_index_bundle(args.style_index)
        json_print(
            generate_map(
                audio_path=args.audio,
                output_dir=args.out_dir,
                prompt=args.prompt,
                seed=args.seed,
                target_star=args.target_star,
                target_pp=args.target_pp,
                profile=style_profile,
                reference_maps=args.reference_map,
                style_index=style_index,
            )
        )
        return 0

    if args.command == "map" and args.map_command == "verify":
        path = Path(args.path)
        if path.is_dir():
            results = [_verify_path(item, external_command=args.external_command) for item in sorted(path.rglob("*.osu"))]
            json_print({"path": str(path), "maps": results})
            return 0
        json_print(_verify_path(path, external_command=args.external_command))
        return 0

    if args.command == "map" and args.map_command == "score":
        json_print(score_map(args.path, mods=args.mods, acc=args.acc))
        return 0

    if args.command == "style" and args.style_command == "build-index":
        index = build_style_index(args.paths)
        json_dump(index, Path(args.out))
        json_print(index)
        return 0

    if args.command == "style" and args.style_command == "profile":
        profile = build_style_profile(args.maps)
        json_print({"profile": profile, "classifications": {path: classify_map(path) for path in args.maps}})
        return 0

    if args.command == "ai" and args.ai_command == "draft":
        json_print(
            draft_with_backend(
                args.backend,
                args.audio,
                output_path=args.out,
                prompt=args.prompt,
                seed=args.seed,
                target_star=args.target_star,
                target_pp=args.target_pp,
                reference_maps=args.reference_map,
            )
        )
        return 0

    if args.command == "schema" and args.schema_command == "dump":
        payload = schema_bundle()
        if args.out:
            json_dump(payload, Path(args.out))
        json_print(payload)
        return 0

    if args.command == "bench":
        json_print(benchmark_summary(args.fixtures_dir))
        return 0

    parser.error("unsupported command")
    return 2
