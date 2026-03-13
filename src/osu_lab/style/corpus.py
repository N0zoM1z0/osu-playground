from __future__ import annotations

import json
from pathlib import Path

from osu_lab.core.utils import dataclass_to_dict, json_dump
from osu_lab.style.profile import build_style_profile, extract_map_style_metrics, merge_style_profiles


def build_style_index(paths: list[str | Path]) -> dict[str, object]:
    map_paths: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            map_paths.extend(sorted(path.rglob("*.osu")))
        elif path.suffix.lower() == ".osu":
            map_paths.append(path)
    unique_maps = [Path(path) for path in dict.fromkeys(str(path) for path in map_paths)]
    profiles = [extract_map_style_metrics(path) for path in unique_maps]
    aggregate = merge_style_profiles(profiles)
    return {
        "map_count": len(profiles),
        "maps": [dataclass_to_dict(profile) for profile in profiles],
        "aggregate": dataclass_to_dict(aggregate),
    }


def write_style_index(index: dict[str, object], output_path: str | Path) -> Path:
    target = Path(output_path)
    json_dump(index, target)
    return target


def load_style_index(path: str | Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
