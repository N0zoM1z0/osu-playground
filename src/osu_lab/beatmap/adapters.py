from __future__ import annotations

from pathlib import Path


def load_with_slider(path: str | Path):
    import slider

    source = Path(path)
    if source.suffix.lower() == ".osz":
        return slider.Beatmap.from_osz_path(str(source))
    return slider.Beatmap.from_path(str(source))
