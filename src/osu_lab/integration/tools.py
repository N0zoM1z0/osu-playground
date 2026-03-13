from __future__ import annotations

from pathlib import Path

from osu_lab.ai.adapters import draft_with_backend
from osu_lab.audio.analyze import analyze_audio
from osu_lab.beatmap.io import load_ir_json, parse_osu, write_osu
from osu_lab.beatmap.verify_external import run_external_verifier
from osu_lab.beatmap.validate import verify_beatmap
from osu_lab.core.models import StyleTarget
from osu_lab.core.utils import dataclass_to_dict
from osu_lab.generate.mapforge import arrange_objects, draft_skeleton
from osu_lab.integration.scoring import score_map
from osu_lab.live.planner import plan_live_play
from osu_lab.replay.synth import synthesize_replay_plan
from osu_lab.style.profile import build_style_profile, classify_map


def analyze_audio_tool(path: str) -> dict[str, object]:
    return analyze_audio(path).to_dict()


def build_style_profile_tool(ref_maps: list[str]) -> dict[str, object]:
    return dataclass_to_dict(build_style_profile(ref_maps))


def draft_skeleton_tool(audio_analysis_path: str, style_tags: list[str]) -> dict[str, object]:
    analysis = analyze_audio(audio_analysis_path)
    return draft_skeleton(analysis, StyleTarget(prompt_tags=style_tags)).to_dict()


def arrange_objects_tool(beatmap_ir_path: str, style_tags: list[str]) -> dict[str, object]:
    beatmap = load_ir_json(beatmap_ir_path)
    arranged = arrange_objects(beatmap, style_target=StyleTarget(prompt_tags=style_tags))
    return arranged.to_dict()


def score_map_tool(path: str, mods: str, acc: float) -> dict[str, object]:
    return score_map(path, mods=mods, acc=acc)


def classify_map_tool(path: str) -> dict[str, object]:
    return classify_map(path)


def verify_map_tool(path: str) -> dict[str, object]:
    beatmap = parse_osu(path)
    issues = verify_beatmap(beatmap)
    return {
        "path": str(path),
        "issue_count": len(issues),
        "issues": [dataclass_to_dict(issue) for issue in issues],
        "external": run_external_verifier(path),
    }


def compile_map_tool(beatmap_ir_path: str, output_path: str) -> dict[str, object]:
    beatmap = load_ir_json(beatmap_ir_path)
    write_osu(beatmap, output_path)
    return {"status": "ok", "output_path": str(output_path)}


def synthesize_replay_tool(map_path: str, profile: str) -> dict[str, object]:
    return synthesize_replay_plan(map_path, profile=profile).to_dict()


def plan_live_play_tool(map_path_or_tosu_context: str, profile: str, provider: str = "direct-file/manual") -> dict[str, object]:
    return dataclass_to_dict(plan_live_play(map_path_or_tosu_context, profile=profile, provider=provider))


def ai_draft_tool(backend: str, audio_path: str, prompt: str = "mixed") -> dict[str, object]:
    return draft_with_backend(backend, audio_path, prompt=prompt)
