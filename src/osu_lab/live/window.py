from __future__ import annotations

import ctypes
import platform
from ctypes import wintypes


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


def detect_active_osu_client_rect() -> dict[str, int] | None:
    if platform.system() != "Windows":
        return None
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, title, len(title))
    lowered = title.value.lower()
    if "osu!" not in lowered and "osu" not in lowered:
        return None
    rect = RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    origin = wintypes.POINT(0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
        return None
    return {
        "left": int(origin.x),
        "top": int(origin.y),
        "right": int(origin.x + rect.right),
        "bottom": int(origin.y + rect.bottom),
        "width": int(rect.right),
        "height": int(rect.bottom),
        "window_title": title.value,
    }
