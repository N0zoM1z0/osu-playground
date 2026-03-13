from __future__ import annotations

import re

from osu_lab.core.models import StyleTarget


CANONICAL_TAGS = [
    "flow aim",
    "jump",
    "farm jump",
    "stream",
    "deathstream",
    "mixed",
    "control",
]


def parse_style_prompt(prompt: str, target_star: float | None = None, target_pp: float | None = None) -> StyleTarget:
    normalized = prompt.lower().strip()
    tags: list[str] = []
    if "farm" in normalized and "jump" in normalized:
        tags.append("farm jump")
    if "deathstream" in normalized:
        tags.append("deathstream")
    if "flow" in normalized or "aim" in normalized:
        tags.append("flow aim")
    if "jump" in normalized:
        tags.append("jump")
    if "stream" in normalized:
        tags.append("stream")
    if "mixed" in normalized:
        tags.append("mixed")
    if "control" in normalized or "tech" in normalized:
        tags.append("control")
    if not tags:
        tags = ["mixed"]
    tags = list(dict.fromkeys(tags))

    difficulty_bias = 0.0
    if re.search(r"\binsane\b|\bexpert\b|\bhard\b", normalized):
        difficulty_bias = 0.2
    if re.search(r"\beasy\b|\bnormal\b", normalized):
        difficulty_bias = -0.2
    return StyleTarget(
        prompt_tags=tags,
        target_star=target_star,
        target_pp=target_pp,
        difficulty_bias=difficulty_bias,
    )
