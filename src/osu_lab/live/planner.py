from __future__ import annotations

import platform
from pathlib import Path

from osu_lab.core.models import LiveEvent, LivePlan
from osu_lab.live.inject import execute_live_plan
from osu_lab.live.providers import fetch_tosu_current_beatmap
from osu_lab.live.window import detect_active_osu_client_rect
from osu_lab.replay.synth import synthesize_replay_plan


def _map_to_client(x: float, y: float, width: int, height: int) -> tuple[float, float]:
    scale = min(width / 512.0, height / 384.0)
    offset_x = (width - 512.0 * scale) / 2.0
    offset_y = (height - 384.0 * scale) / 2.0
    return offset_x + x * scale, offset_y + y * scale


def _resolve_map_path(map_path_or_tosu_context: str | Path, provider: str, tosu_base_url: str, cache_dir: str | Path | None) -> Path:
    if provider == "tosu":
        return fetch_tosu_current_beatmap(base_url=tosu_base_url, cache_dir=cache_dir)
    return Path(map_path_or_tosu_context)


def plan_live_play(
    map_path_or_tosu_context: str | Path,
    profile: str = "auto_perfect",
    provider: str = "direct-file/manual",
    client_width: int = 1280,
    client_height: int = 960,
    window_auto: bool = False,
    tosu_base_url: str = "http://127.0.0.1:24050",
    cache_dir: str | Path | None = None,
) -> LivePlan:
    map_path = _resolve_map_path(map_path_or_tosu_context, provider=provider, tosu_base_url=tosu_base_url, cache_dir=cache_dir)
    client_rect = detect_active_osu_client_rect() if window_auto else None
    if client_rect:
        client_width = int(client_rect["width"])
        client_height = int(client_rect["height"])
    plan = synthesize_replay_plan(map_path, profile=profile)
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
        map_path=str(map_path),
        playfield={
            "width": client_width,
            "height": client_height,
            "left": client_rect["left"] if client_rect else 0,
            "top": client_rect["top"] if client_rect else 0,
            "window_title": client_rect.get("window_title") if client_rect else None,
            "source": "active-window" if client_rect else "manual",
            "tosu_base_url": tosu_base_url if provider == "tosu" else None,
        },
        events=events,
        dry_run=True,
    )


def arm_live_plan(plan: LivePlan, dry_run: bool = True, lead_in_ms: int = 1000, stop_file: str | Path | None = None) -> dict[str, object]:
    if dry_run or platform.system() != "Windows":
        return {
            "status": "dry-run",
            "platform": platform.system(),
            "event_count": len(plan.events),
            "message": "live injection remains disabled unless --inject is used on Windows",
            "warning": "SendInput is subject to UIPI; osu! and the injector must run at compatible integrity levels",
            "hotkeys": {
                "arming": "CLI invocation only",
                "emergency_stop": f"create {Path(stop_file)}" if stop_file else "Ctrl+C or provide --stop-file for a file-based emergency stop",
            },
            "stop_file": str(Path(stop_file)) if stop_file else None,
        }
    return execute_live_plan(plan, lead_in_ms=lead_in_ms, stop_file=stop_file)
