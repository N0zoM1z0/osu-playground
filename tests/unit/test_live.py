from pathlib import Path

from osu_lab.live.planner import plan_live_play


class _FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_plan_live_play_with_tosu_provider(monkeypatch, tmp_path: Path):
    payload = Path("tests/fixtures/sample_map.osu").read_bytes()

    def _fake_urlopen(url: str, timeout: int = 5):
        assert url.endswith("/files/beatmap/file")
        return _FakeResponse(payload)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    plan = plan_live_play("", provider="tosu", cache_dir=tmp_path)
    assert plan.provider == "tosu"
    assert plan.events
    assert Path(plan.map_path).exists()

