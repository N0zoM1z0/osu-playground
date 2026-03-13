from pathlib import Path

from osu_lab.style.corpus import build_style_index, load_style_index, write_style_index


def test_style_index_roundtrip(tmp_path: Path):
    index = build_style_index(["tests/fixtures"])
    target = tmp_path / "style-index.json"
    write_style_index(index, target)
    loaded = load_style_index(target)
    assert loaded["map_count"] == 1
    assert loaded["aggregate"]["source_maps"] == ["tests/fixtures/sample_map.osu"]
    assert loaded["patterns"]["jump"]
