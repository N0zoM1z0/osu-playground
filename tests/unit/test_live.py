from pathlib import Path

from osu_lab.live.planner import arm_live_plan, plan_live_play


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


def test_plan_live_play_can_use_active_window_rect(monkeypatch):
    monkeypatch.setattr(
        "osu_lab.live.planner.detect_active_osu_client_rect",
        lambda: {"left": 100, "top": 50, "right": 1380, "bottom": 1010, "width": 1280, "height": 960, "window_title": "osu!"},
    )
    plan = plan_live_play("tests/fixtures/sample_map.osu", window_auto=True)
    assert plan.playfield["source"] == "active-window"
    assert plan.playfield["left"] == 100
    assert plan.playfield["window_title"] == "osu!"


def test_arm_live_plan_dry_run_reports_stop_file():
    plan = plan_live_play("tests/fixtures/sample_map.osu")
    result = arm_live_plan(plan, dry_run=True, stop_file="/tmp/osu-lab.stop")
    assert result["status"] == "dry-run"
    assert result["stop_file"] == "/tmp/osu-lab.stop"
    assert "emergency_stop" in result["hotkeys"]
