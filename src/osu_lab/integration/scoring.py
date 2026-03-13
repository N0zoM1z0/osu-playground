from __future__ import annotations

from pathlib import Path

import rosu_pp_py as rosu


def score_map(path: str | Path, mods: str = "", acc: float = 98.0) -> dict[str, object]:
    beatmap = rosu.Beatmap(path=str(path))
    difficulty = rosu.Difficulty()
    performance = rosu.Performance()
    if mods:
        difficulty.set_mods(mods)
        performance.set_mods(mods)
    attrs = difficulty.calculate(beatmap)
    performance.set_accuracy(acc)
    pp = performance.calculate(beatmap)
    return {
        "path": str(path),
        "mods": mods or "NM",
        "acc": acc,
        "stars": attrs.stars,
        "max_combo": attrs.max_combo,
        "pp": pp.pp,
        "aim": getattr(pp, "pp_aim", None),
        "speed": getattr(pp, "pp_speed", None),
        "accuracy": getattr(pp, "pp_accuracy", None),
    }

