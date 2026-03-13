from __future__ import annotations

import tempfile
from pathlib import Path

from osu_lab.generate.mapforge import generate_map
from osu_lab.integration.scoring import score_map
from osu_lab.style.profile import build_style_profile, classify_map, style_distance


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


def _expected_class(prompt: str) -> str:
    normalized = prompt.lower()
    if "stream" in normalized:
        return "stream"
    if "jump" in normalized:
        return "jump"
    if "flow" in normalized or "aim" in normalized:
        return "flow"
    return "tech" if "control" in normalized or "tech" in normalized else "jump"


def benchmark_style_control(
    audio_path: str | Path,
    output_dir: str | Path,
    prompts: list[str],
    reference_maps: list[str | Path] | None = None,
    seed: int = 1,
) -> dict[str, object]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    prompt_results = []
    reference_profile = build_style_profile(reference_maps) if reference_maps else None

    for prompt in prompts:
        prompt_slug = prompt.replace(" ", "_").replace(",", "_")
        prompt_out = output_root / prompt_slug
        neutral = generate_map(audio_path, prompt_out / "neutral", prompt=prompt, seed=seed)
        styled = generate_map(
            audio_path,
            prompt_out / "styled",
            prompt=prompt,
            seed=seed,
            reference_maps=reference_maps,
        )
        neutral_map = neutral["osu"]
        styled_map = styled["osu"]
        neutral_class = classify_map(neutral_map)
        styled_class = classify_map(styled_map)
        neutral_dominant = max(neutral_class, key=neutral_class.get) if neutral_class else "unknown"
        styled_dominant = max(styled_class, key=styled_class.get) if styled_class else "unknown"
        expected = _expected_class(prompt)
        entry = {
            "prompt": prompt,
            "expected_class": expected,
            "neutral_map": neutral_map,
            "styled_map": styled_map,
            "neutral_dominant": neutral_dominant,
            "styled_dominant": styled_dominant,
            "neutral_match": neutral_dominant == expected,
            "styled_match": styled_dominant == expected,
        }
        if reference_profile is not None:
            neutral_profile = build_style_profile([neutral_map])
            styled_profile = build_style_profile([styled_map])
            neutral_distance = style_distance(neutral_profile, reference_profile)
            styled_distance = style_distance(styled_profile, reference_profile)
            improvement = 0.0
            if neutral_distance > 0:
                improvement = (neutral_distance - styled_distance) / neutral_distance
            entry.update(
                {
                    "reference_distance_neutral": neutral_distance,
                    "reference_distance_styled": styled_distance,
                    "reference_improvement_ratio": improvement,
                }
            )
        prompt_results.append(entry)

    styled_match_rate = sum(1 for item in prompt_results if item["styled_match"]) / max(1, len(prompt_results))
    neutral_match_rate = sum(1 for item in prompt_results if item["neutral_match"]) / max(1, len(prompt_results))
    result = {
        "audio_path": str(audio_path),
        "prompt_count": len(prompts),
        "neutral_match_rate": neutral_match_rate,
        "styled_match_rate": styled_match_rate,
        "results": prompt_results,
    }
    if reference_profile is not None:
        improvements = [item.get("reference_improvement_ratio", 0.0) for item in prompt_results]
        result["mean_reference_improvement_ratio"] = sum(improvements) / max(1, len(improvements))
        result["reference_maps"] = [str(Path(path)) for path in reference_maps or []]
    return result
