from __future__ import annotations

from pathlib import Path

from osu_lab.core.models import BeatmapIR


def draft_with_backend(backend: str, audio_path: str | Path, output_path: str | Path | None = None) -> dict[str, object]:
    backend_key = backend.lower()
    module_names = {
        "mapperatorinator": "mapperatorinator",
        "osut5": "osuT5",
        "osu-diffusion": "osu_diffusion",
        "osu-dreamer": "osu_dreamer",
    }
    module_name = module_names.get(backend_key)
    if not module_name:
        return {"status": "error", "backend": backend, "message": f"unsupported backend: {backend}"}
    try:
        __import__(module_name)
    except Exception as exc:
        return {
            "status": "error",
            "backend": backend,
            "message": f"{backend} is not installed locally",
            "detail": str(exc),
            "next_step": f"install the {backend} backend and normalize its output into BeatmapIR",
        }
    return {
        "status": "error",
        "backend": backend,
        "message": f"{backend} adapter stub is present but normalization into BeatmapIR is not implemented yet",
        "audio_path": str(audio_path),
        "output_path": str(output_path) if output_path else None,
    }
