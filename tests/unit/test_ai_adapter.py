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


def test_mapperatorinator_adapter_wraps_external_map(monkeypatch, tmp_path: Path):
    wav_path = tmp_path / "song.wav"
    wav_path.write_bytes(Path("tests/fixtures/sample_map.osu").read_bytes())
    backend_root = tmp_path / "mapperatorinator"
    backend_root.mkdir()

    class _Analysis:
        def to_dict(self):
            return {"bpm": 180.0, "beats_ms": [0, 333, 666], "path": str(wav_path), "duration_ms": 1000}

    def _fake_run(command, cwd=None, check=False, capture_output=True, text=True):
        output_arg = next(item for item in command if str(item).startswith("output_path="))
        output_dir = Path(str(output_arg).split("=", 1)[1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "draft.osu").write_bytes(Path("tests/fixtures/sample_map.osu").read_bytes())
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr("osu_lab.ai.adapters.analyze_audio", lambda path: _Analysis())
    monkeypatch.setattr("osu_lab.ai.adapters.subprocess.run", _fake_run)
    monkeypatch.setenv("OSU_LAB_MAPPERATORINATOR_ROOT", str(backend_root))
    monkeypatch.setattr(
        "osu_lab.ai.adapters.generate_map",
        lambda audio_path, output_dir, prompt, seed=1, target_star=None, target_pp=None, ai_recipe=None, reference_maps=None, style_index=None: {
            "osu": str(Path(output_dir) / "post.osu"),
            "prompt": prompt,
            "reference_maps": [str(item) for item in reference_maps or []],
        },
    )
    result = draft_with_backend("mapperatorinator", wav_path, output_path=tmp_path / "out", prompt="jump")
    assert result["status"] == "ok"
    assert result["draft_map"]["path"].endswith("draft.osu")
    assert result["generation"]["reference_maps"][0].endswith("draft.osu")


def test_osut5_adapter_returns_actionable_error_when_model_missing(monkeypatch, tmp_path: Path):
    wav_path = tmp_path / "song.wav"
    wav_path.write_bytes(Path("tests/fixtures/sample_map.osu").read_bytes())
    backend_root = tmp_path / "osut5"
    backend_root.mkdir()

    class _Analysis:
        def to_dict(self):
            return {"bpm": 180.0, "beats_ms": [0, 333, 666], "path": str(wav_path), "duration_ms": 1000}

    monkeypatch.setattr("osu_lab.ai.adapters.analyze_audio", lambda path: _Analysis())
    monkeypatch.setenv("OSU_LAB_OSUT5_ROOT", str(backend_root))
    monkeypatch.delenv("OSU_LAB_OSUT5_MODEL_PATH", raising=False)
    result = draft_with_backend("osut5", wav_path, output_path=tmp_path / "out", prompt="stream")
    assert result["status"] == "error"
    assert "OSU_LAB_OSUT5_MODEL_PATH" in result["message"]
