from __future__ import annotations

from osu_lab.core.models import StylePolicyPack, StyleProfile
from osu_lab.style.policies import merge_policy_packs, policy_pack_for_tag


def chart_policy_from_tags(tags: list[str], reference_profile: StyleProfile | None = None) -> StylePolicyPack:
    packs = [policy_pack_for_tag(tag) for tag in tags] or [policy_pack_for_tag("mixed")]
    return merge_policy_packs(packs, reference_profile=reference_profile)
