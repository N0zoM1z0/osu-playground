from __future__ import annotations

from pathlib import Path

from osu_lab.integration.scoring import score_map
from osu_lab.style.profile import classify_map


def benchmark_summary(fixtures_dir: str | Path) -> dict[str, object]:
    fixtures = sorted(Path(fixtures_dir).rglob("*.osu"))
    star_values = []
    classifications = {"jump": 0, "stream": 0, "tech": 0, "flow": 0}
    per_map: list[dict[str, object]] = []
    for fixture in fixtures:
        score = score_map(fixture)
        labels = classify_map(fixture)
        dominant = max(labels, key=labels.get) if labels else "unknown"
        if dominant in classifications:
            classifications[dominant] += 1
        star_values.append(float(score["stars"]))
        per_map.append({"path": str(fixture), "stars": score["stars"], "dominant_class": dominant})
    average_stars = sum(star_values) / len(star_values) if star_values else 0.0
    return {
        "fixtures_dir": str(fixtures_dir),
        "map_count": len(fixtures),
        "average_stars": average_stars,
        "dominant_class_histogram": classifications,
        "maps": per_map,
        "status": "ok" if fixtures else "empty",
    }
