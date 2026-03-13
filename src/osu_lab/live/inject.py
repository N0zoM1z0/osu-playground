from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from osu_lab.core.models import LivePlan


INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
KEYEVENTF_KEYUP = 0x0002

VK_Z = 0x5A
VK_X = 0x58


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _send_mouse(x: float, y: float) -> None:
    user32 = ctypes.windll.user32
    screen_w = user32.GetSystemMetrics(0) - 1
    screen_h = user32.GetSystemMetrics(1) - 1
    absolute_x = int(x * 65535 / max(1, screen_w))
    absolute_y = int(y * 65535 / max(1, screen_h))
    event = INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(absolute_x, absolute_y, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, None))
    if user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
        raise RuntimeError("SendInput mouse injection failed; this is commonly caused by incompatible integrity levels (UIPI)")


def _send_key(vk_code: int, down: bool) -> None:
    user32 = ctypes.windll.user32
    flags = 0 if down else KEYEVENTF_KEYUP
    event = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk_code, 0, flags, 0, None))
    if user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
        raise RuntimeError("SendInput keyboard injection failed; this is commonly caused by incompatible integrity levels (UIPI)")


def execute_live_plan(plan: LivePlan, lead_in_ms: int = 1000, stop_file: str | Path | None = None) -> dict[str, object]:
    active_keys = 0
    start = time.perf_counter() + lead_in_ms / 1000.0
    stop_path = Path(stop_file) if stop_file else None
    for event in plan.events:
        if stop_path and stop_path.exists():
            break
        while time.perf_counter() < start + event.at_ms / 1000.0:
            if stop_path and stop_path.exists():
                break
            time.sleep(0.001)
        if stop_path and stop_path.exists():
            break
        if event.x is not None and event.y is not None:
            _send_mouse(event.x, event.y)
        if event.keys is not None:
            desired = int(event.keys)
            previous = active_keys
            for mask, vk in ((4, VK_Z), (8, VK_X), (1, VK_Z), (2, VK_X)):
                if desired & mask and not previous & mask:
                    _send_key(vk, True)
                if previous & mask and not desired & mask:
                    _send_key(vk, False)
            active_keys = desired
    for mask, vk in ((4, VK_Z), (8, VK_X), (1, VK_Z), (2, VK_X)):
        if active_keys & mask:
            _send_key(vk, False)
    return {
        "status": "aborted" if stop_path and stop_path.exists() else "injected",
        "event_count": len(plan.events),
        "lead_in_ms": lead_in_ms,
        "stop_file": str(stop_path) if stop_path else None,
        "warning": "SendInput is subject to UIPI; osu! and the injector must run at compatible integrity levels",
    }
