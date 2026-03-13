from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

from osrparse import GameMode, Key, Mod, Replay, ReplayEventOsu

from osu_lab.beatmap.io import parse_osu
from osu_lab.core.models import BeatmapIR, HitObjectIR, ReplayFrame, ReplayPlan
from osu_lab.core.utils import clamp, md5_bytes, md5_file


def _absolute_frame(at_ms: int, x: float, y: float, keys: Key | int) -> tuple[int, float, float, int]:
    return at_ms, round(x, 3), round(y, 3), int(keys)


def _object_target(item: HitObjectIR, rng: random.Random, profile: str) -> tuple[float, float]:
    x = float(item.x)
    y = float(item.y)
    if profile == "humanized_aim":
        x += rng.uniform(-5.0, 5.0)
        y += rng.uniform(-5.0, 5.0)
    return clamp(x, 0.0, 512.0), clamp(y, 0.0, 384.0)


def synthesize_replay_plan(map_path: str | Path, profile: str = "auto_perfect", seed: int = 1) -> ReplayPlan:
    beatmap = parse_osu(map_path)
    rng = random.Random(seed)
    timeline: list[tuple[int, float, float, int]] = [_absolute_frame(0, 256.0, 192.0, 0)]
    ordered = sorted(beatmap.objects, key=lambda item: item.start_ms)
    previous_x = 256.0
    previous_y = 192.0
    key_cycle = [int(Key.K1), int(Key.K2)]
    key_index = 0
    for item in ordered:
        target_x, target_y = _object_target(item, rng, profile)
        travel_start = max(0, item.start_ms - 80)
        timeline.append(_absolute_frame(travel_start, previous_x, previous_y, 0))
        timeline.append(_absolute_frame(item.start_ms - 8, target_x, target_y, 0))
        press_key = 0 if profile == "autopilot_only" else key_cycle[key_index % len(key_cycle)]
        key_index += 1
        timeline.append(_absolute_frame(item.start_ms, target_x, target_y, press_key))
        if item.type == "slider":
            nodes = item.curve or [(item.x, item.y)]
            samples = max(2, item.repeats * max(1, len(nodes)))
            duration = max(1, item.end_ms - item.start_ms)
            for sample in range(1, samples + 1):
                ratio = sample / samples
                anchor = nodes[min(len(nodes) - 1, int(ratio * len(nodes)) - 1)]
                timeline.append(
                    _absolute_frame(
                        item.start_ms + int(duration * ratio),
                        anchor[0],
                        anchor[1],
                        press_key,
                    )
                )
            timeline.append(_absolute_frame(item.end_ms + 10, target_x, target_y, 0))
        elif item.type == "spinner":
            if profile == "autopilot_only":
                timeline.append(_absolute_frame(item.end_ms + 10, 256.0, 192.0, 0))
            else:
                for tick in range(item.start_ms, item.end_ms, 16):
                    angle = (tick - item.start_ms) / 48.0
                    x = 256.0 + 96.0 * math_cos(angle)
                    y = 192.0 + 96.0 * math_sin(angle)
                    timeline.append(_absolute_frame(tick, x, y, press_key))
                timeline.append(_absolute_frame(item.end_ms + 10, 256.0, 192.0, 0))
        else:
            timeline.append(_absolute_frame(item.start_ms + 16, target_x, target_y, 0))
        previous_x = target_x
        previous_y = target_y

    timeline.sort(key=lambda item: item[0])
    frames: list[ReplayFrame] = []
    last_time = 0
    last_state = None
    for at_ms, x, y, keys in timeline:
        state = (at_ms, x, y, keys)
        if last_state == state:
            continue
        frames.append(ReplayFrame(dt_ms=at_ms - last_time, x=x, y=y, keys=keys))
        last_time = at_ms
        last_state = state
    frames.append(ReplayFrame(dt_ms=-12345, x=0.0, y=0.0, keys=0))
    return ReplayPlan(
        profile=profile,
        seed=seed,
        frames=frames,
        expected_score_stats={
            "count_300": len(ordered),
            "count_100": 0,
            "count_50": 0,
            "count_miss": 0,
            "max_combo": len(ordered),
            "score": len(ordered) * 300,
        },
        source_map=str(Path(map_path)),
    )


def _to_replay_events(plan: ReplayPlan) -> list[ReplayEventOsu]:
    return [ReplayEventOsu(time_delta=frame.dt_ms, x=frame.x, y=frame.y, keys=Key(frame.keys)) for frame in plan.frames]


def write_replay(map_path: str | Path, output_path: str | Path, profile: str = "auto_perfect", seed: int = 1, username: str = "osu-lab") -> tuple[Path, ReplayPlan]:
    beatmap_path = Path(map_path)
    plan = synthesize_replay_plan(beatmap_path, profile=profile, seed=seed)
    beatmap_hash = md5_file(beatmap_path)
    replay_hash = md5_bytes(f"{beatmap_hash}:{username}:{profile}:{seed}".encode("utf-8"))
    replay = Replay(
        mode=GameMode.STD,
        game_version=20260313,
        beatmap_hash=beatmap_hash,
        username=username,
        replay_hash=replay_hash,
        count_300=plan.expected_score_stats["count_300"],
        count_100=plan.expected_score_stats["count_100"],
        count_50=plan.expected_score_stats["count_50"],
        count_geki=0,
        count_katu=0,
        count_miss=plan.expected_score_stats["count_miss"],
        score=plan.expected_score_stats["score"],
        max_combo=plan.expected_score_stats["max_combo"],
        perfect=True,
        mods=Mod.NoMod,
        life_bar_graph=[],
        timestamp=dt.datetime.utcnow(),
        replay_data=_to_replay_events(plan),
        replay_id=0,
        rng_seed=seed,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    replay.write_path(str(output))
    return output, plan


def inspect_replay(path: str | Path) -> dict[str, object]:
    replay = Replay.from_path(str(path))
    return {
        "path": str(path),
        "mode": replay.mode.name,
        "username": replay.username,
        "mods": int(replay.mods),
        "score": replay.score,
        "max_combo": replay.max_combo,
        "counts": {
            "300": replay.count_300,
            "100": replay.count_100,
            "50": replay.count_50,
            "miss": replay.count_miss,
        },
        "frame_count": len(replay.replay_data),
        "rng_seed": replay.rng_seed,
    }


def dump_replay_plan(plan: ReplayPlan, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output


def math_sin(value: float) -> float:
    import math

    return math.sin(value)


def math_cos(value: float) -> float:
    import math

    return math.cos(value)
