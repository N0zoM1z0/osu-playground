from osu_lab.style.patterns import extract_pattern_bank, select_patterns


def test_select_patterns_respects_mode_and_section():
    bank = extract_pattern_bank(["tests/fixtures/sample_map.osu"])
    jump_patterns = select_patterns(bank, "jump", section_label="chorus")
    mixed_patterns = select_patterns(bank, "mixed", section_label="break")
    assert jump_patterns
    assert mixed_patterns
    assert all("label" in pattern for pattern in jump_patterns)
