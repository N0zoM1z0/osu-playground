from __future__ import annotations

import tempfile
import urllib.error
import urllib.request
from pathlib import Path


def fetch_tosu_current_beatmap(base_url: str = "http://127.0.0.1:24050", cache_dir: str | Path | None = None) -> Path:
    cache_root = Path(cache_dir or tempfile.gettempdir()) / "osu-lab-tosu"
    cache_root.mkdir(parents=True, exist_ok=True)
    beatmap_url = base_url.rstrip("/") + "/files/beatmap/file"
    destination = cache_root / "current.osu"
    try:
        with urllib.request.urlopen(beatmap_url, timeout=5) as response:
            destination.write_bytes(response.read())
    except urllib.error.URLError as exc:
        raise RuntimeError(f"failed to fetch current beatmap from tosu at {beatmap_url}: {exc}") from exc
    return destination
