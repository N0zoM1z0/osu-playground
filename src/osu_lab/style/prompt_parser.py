from __future__ import annotations

import re

from osu_lab.core.models import StylePolicyPack, StyleTarget
from osu_lab.style.policies import merge_policy_packs, policy_pack_for_tag
from osu_lab.style.prompt import parse_style_prompt


def parse_prompt_constraints(prompt: str) -> dict[str, object]:
    normalized = prompt.lower().strip()
    negatives = re.findall(r"not too ([a-z ]+)", normalized)
    constraints = {
        "easy_reading": "easy reading" in normalized,
        "chorus_lift": "chorus lift" in normalized or "chorus jump lift" in normalized,
        "low_slider_spam": "low slider spam" in normalized or "low slider" in normalized,
        "melodic": "melodic" in normalized,
        "negative_constraints": [item.strip() for item in negatives],
    }
    return constraints


def resolve_style_prompt(prompt: str, target_star: float | None = None, target_pp: float | None = None) -> tuple[StyleTarget, StylePolicyPack, dict[str, object]]:
    target = parse_style_prompt(prompt, target_star=target_star, target_pp=target_pp)
    packs = [policy_pack_for_tag(tag) for tag in target.prompt_tags]
    policy = merge_policy_packs(packs)
    constraints = parse_prompt_constraints(prompt)
    if constraints["easy_reading"]:
        policy.rhythm_simplification = min(0.65, policy.rhythm_simplification + 0.18)
        policy.rest_policy *= 1.08
    if constraints["chorus_lift"]:
        policy.chorus_lift += 0.08
        policy.strain_choreography["chorus"] = policy.strain_choreography.get("chorus", 1.0) + 0.08
    if constraints["low_slider_spam"]:
        policy.slider_policy["ratio"] = max(0.02, policy.slider_policy.get("ratio", 0.1) * 0.6)
    if constraints["melodic"]:
        policy.note_selection_bias["phrase_peak"] = policy.note_selection_bias.get("phrase_peak", 0.0) + 0.12
        policy.note_selection_bias["slider_opportunity"] = policy.note_selection_bias.get("slider_opportunity", 0.0) + 0.1
    for negative in constraints["negative_constraints"]:
        if "tech" in negative:
            policy.angle_policy["volatility"] = max(0.12, policy.angle_policy.get("volatility", 0.4) * 0.65)
        if "stream" in negative:
            policy.density_policy *= 0.88
            policy.note_selection_bias["stream_body"] = policy.note_selection_bias.get("stream_body", 0.0) * 0.6
    return target, policy, constraints
