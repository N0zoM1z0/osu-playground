from osu_lab.style.patterns import adapt_pattern_to_context, extract_pattern_bank, select_patterns, transform_pattern


def test_select_patterns_respects_mode_and_section():
    bank = extract_pattern_bank(["tests/fixtures/sample_map.osu"])
    jump_patterns = select_patterns(bank, "jump", section_label="chorus")
    mixed_patterns = select_patterns(bank, "mixed", section_label="break")
    assert jump_patterns
    assert mixed_patterns
    assert all("label" in pattern for pattern in jump_patterns)


def test_transform_pattern_rotates_and_mirrors_signature():
    pattern = {
        "points": [(100, 0), (50, 25)],
        "span": 100.0,
    }
    transformed = transform_pattern(pattern, scale=0.8, mirror_x=True, rotate_quadrants=1)
    assert transformed["points"][0] == (0, -80)
    assert transformed["transform"]["mirror_x"] is True


def test_adapt_pattern_to_context_prefers_in_bounds_variant():
    pattern = {
        "points": [(180, 0), (180, 0)],
        "span": 180.0,
        "gaps": [250, 250],
        "types": ["circle", "circle"],
    }
    adapted = adapt_pattern_to_context(pattern, origin_x=450, origin_y=192, section_spacing=120, previous_vector=(-80.0, 0.0))
    xs = [450]
    current_x = 450
    for dx, _ in adapted["points"]:
        current_x += dx
        xs.append(current_x)
    assert max(xs) <= 480
