from pathlib import Path

from osu_lab.beatmap.io import compile_osu, parse_osu
from osu_lab.beatmap.validate import verify_beatmap


def test_parse_compile_roundtrip():
    fixture = Path("tests/fixtures/sample_map.osu")
    beatmap = parse_osu(fixture)
    compiled = compile_osu(beatmap)
    roundtrip_path = Path("tests/fixtures/.roundtrip.osu")
    roundtrip_path.write_text(compiled, encoding="utf-8")
    try:
        reparsed = parse_osu(roundtrip_path)
    finally:
        roundtrip_path.unlink(missing_ok=True)
    assert len(beatmap.objects) == len(reparsed.objects)
    assert len(beatmap.timing_grid.uninherited_points) == len(reparsed.timing_grid.uninherited_points)
    assert beatmap.metadata["Title"] == reparsed.metadata["Title"]


def test_verify_fixture_has_no_errors():
    beatmap = parse_osu("tests/fixtures/sample_map.osu")
    issues = verify_beatmap(beatmap)
    assert [issue for issue in issues if issue.severity == "error"] == []

