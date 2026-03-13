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

    def _fake_generate_map(audio_path, output_dir, prompt, seed=1, target_star=None, target_pp=None, ai_recipe=None, reference_maps=None, style_index=None):
        return {"osu": str(Path(output_dir) / "a.osu"), "ai_recipe": ai_recipe, "prompt": prompt, "reference_maps": reference_maps, "style_index": style_index}

    monkeypatch.setattr("osu_lab.ai.adapters.analyze_audio", _fake_analyze)
    monkeypatch.setattr("osu_lab.ai.adapters._run_claude", lambda prompt: _fake_run([], text=True))
    monkeypatch.setattr("osu_lab.ai.adapters.generate_map", _fake_generate_map)
    result = draft_with_backend("claude", wav_path, output_path=tmp_path, prompt="flow aim")
    assert result["status"] == "ok"
    assert "jump" in result["generation"]["prompt"]


def test_kimi_adapter_uses_native_result(monkeypatch, tmp_path: Path):
    wav_path = tmp_path / "song.wav"
    wav_path.write_bytes(Path("tests/fixtures/sample_map.osu").read_bytes())

    class _Analysis:
        def to_dict(self):
            return {"bpm": 180.0, "beats_ms": [0, 333, 666], "path": str(wav_path), "duration_ms": 1000}

    monkeypatch.setattr("osu_lab.ai.adapters.analyze_audio", lambda path: _Analysis())
    monkeypatch.setattr(
        "osu_lab.ai.adapters._run_kimi",
        lambda prompt, model, dotenv_path=None: {
            "status": "ok",
            "backend": "kimi",
            "draft": {
                "title": "Kimi Draft",
                "version": "Hard",
                "prompt_tags": ["stream"],
                "density_bias": 1.2,
                "spacing_bias": 0.9,
                "slider_ratio_bias": 0.8,
                "difficulty_bias": 1.0,
                "notes": ["native"],
            },
            "model": model,
            "usage": {"total_tokens": 42},
        },
    )
    monkeypatch.setattr(
        "osu_lab.ai.adapters.generate_map",
        lambda audio_path, output_dir, prompt, seed=1, target_star=None, target_pp=None, ai_recipe=None, reference_maps=None, style_index=None: {
            "osu": str(Path(output_dir) / "a.osu"),
            "prompt": prompt,
            "ai_recipe": ai_recipe,
            "style_index": style_index,
        },
    )
    result = draft_with_backend("kimi", wav_path, output_path=tmp_path, prompt="jump")
    assert result["status"] == "ok"
    assert result["model"] == "kimi-k2.5"
    assert "stream" in result["generation"]["prompt"]
    assert result["draft"]["version"] == "Hard"
    assert result["draft"]["notes"]


def test_kimi_normalization_reads_nested_style_blocks(monkeypatch, tmp_path: Path):
    wav_path = tmp_path / "song.wav"
    wav_path.write_bytes(Path("tests/fixtures/sample_map.osu").read_bytes())

    class _Analysis:
        def to_dict(self):
            return {"bpm": 150.0, "beats_ms": [0, 400, 800], "path": str(wav_path), "duration_ms": 1000}

    monkeypatch.setattr("osu_lab.ai.adapters.analyze_audio", lambda path: _Analysis())
    monkeypatch.setattr(
        "osu_lab.ai.adapters._run_kimi",
        lambda prompt, model, dotenv_path=None: {
            "status": "ok",
            "backend": "kimi",
            "draft": {
                "audio_path": str(wav_path),
                "timing": {"bpm": 150.0, "offset_ms": 0},
                "style": {
                    "prompt_tags": ["jump", "flow aim"],
                    "density_bias": 1.1,
                    "spacing_bias": 1.3,
                    "slider_ratio_bias": 0.7,
                    "difficulty_bias": 1.2,
                },
            },
            "model": model,
        },
    )
    monkeypatch.setattr(
        "osu_lab.ai.adapters.generate_map",
        lambda audio_path, output_dir, prompt, seed=1, target_star=None, target_pp=None, ai_recipe=None, reference_maps=None, style_index=None: {
            "prompt": prompt,
            "ai_recipe": ai_recipe,
        },
    )
    result = draft_with_backend("kimi", wav_path, output_path=tmp_path, prompt="mixed")
    assert result["draft"]["spacing_bias"] == 1.3
    assert result["draft"]["difficulty_bias"] == 1.2
    assert "jump" in result["draft"]["prompt_tags"]
