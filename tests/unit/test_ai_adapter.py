import subprocess
from pathlib import Path

from osu_lab.ai.adapters import draft_with_backend


def test_claude_adapter_normalizes_recipe(monkeypatch, tmp_path: Path):
    wav_path = tmp_path / "song.wav"
    wav_path.write_bytes(Path("tests/fixtures/sample_map.osu").read_bytes())

    class _Analysis:
        def to_dict(self):
            return {"bpm": 180.0, "beats_ms": [0, 333, 666], "path": str(wav_path), "duration_ms": 1000}

    def _fake_analyze(path):
        return _Analysis()

    def _fake_run(command, check=False, capture_output=True, text=True):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"title":"AI Draft","version":"Insane","prompt_tags":["jump"],"density_bias":1.1,"spacing_bias":1.2,"slider_ratio_bias":0.9,"difficulty_bias":1.0,"notes":["ok"]}',
            stderr="",
        )

    def _fake_generate_map(audio_path, output_dir, prompt, seed=1, target_star=None, target_pp=None, ai_recipe=None, reference_maps=None):
        return {"osu": str(Path(output_dir) / "a.osu"), "ai_recipe": ai_recipe, "prompt": prompt, "reference_maps": reference_maps}

    monkeypatch.setattr("osu_lab.ai.adapters.analyze_audio", _fake_analyze)
    monkeypatch.setattr("osu_lab.ai.adapters._run_claude", lambda prompt: _fake_run([], text=True))
    monkeypatch.setattr("osu_lab.ai.adapters.generate_map", _fake_generate_map)
    result = draft_with_backend("claude", wav_path, output_path=tmp_path, prompt="flow aim")
    assert result["status"] == "ok"
    assert "jump" in result["generation"]["prompt"]
