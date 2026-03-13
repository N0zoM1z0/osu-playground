from __future__ import annotations

import platform
from pathlib import Path

from osu_lab.core.models import LiveEvent, LivePlan
from osu_lab.replay.synth import synthesize_replay_plan


def _map_to_client(x: float, y: float, width: int, height: int) -> tuple[float, float]:
    scale = min(width / 512.0, height / 384.0)
    offset_x = (width - 512.0 * scale) / 2.0
    offset_y = (height - 384.0 * scale) / 2.0
    return offset_x + x * scale, offset_y + y * scale


def plan_live_play(
    map_path_or_tosu_context: str | Path,
    profile: str = "auto_perfect",
    provider: str = "direct-file/manual",
    client_width: int = 1280,
    client_height: int = 960,
) -> LivePlan:
    plan = synthesize_replay_plan(map_path_or_tosu_context, profile=profile)
    elapsed = 0
    events: list[LiveEvent] = []
    for frame in plan.frames:
        if frame.dt_ms < 0:
            continue
        elapsed += frame.dt_ms
        x, y = _map_to_client(frame.x, frame.y, client_width, client_height)
        events.append(LiveEvent(at_ms=elapsed, action="input", x=x, y=y, keys=frame.keys))
    return LivePlan(
        provider=provider,
        map_path=str(map_path_or_tosu_context),
        playfield={"width": client_width, "height": client_height},
        events=events,
        dry_run=True,
    )


def arm_live_plan(plan: LivePlan, dry_run: bool = True) -> dict[str, object]:
    if dry_run or platform.system() != "Windows":
        return {
            "status": "dry-run",
            "platform": platform.system(),
            "event_count": len(plan.events),
            "message": "live injection is only armed on Windows and remains disabled by default",
        }
    return {
        "status": "not-implemented",
        "platform": platform.system(),
        "event_count": len(plan.events),
        "message": "Win32 SendInput execution should be implemented in a Windows runtime",
    }
