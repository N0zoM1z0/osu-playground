from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from osu_lab.audio.analyze import analyze_audio
from osu_lab.beatmap.io import parse_osu
from osu_lab.beatmap.validate import verify_beatmap
from osu_lab.core.utils import dataclass_to_dict
from osu_lab.generate.mapforge import generate_map
from osu_lab.integration.scoring import score_map
from osu_lab.style.profile import build_style_profile, render_style_report


AI_DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "version": {"type": "string"},
        "prompt_tags": {"type": "array", "items": {"type": "string"}},
        "density_bias": {"type": "number"},
        "spacing_bias": {"type": "number"},
        "slider_ratio_bias": {"type": "number"},
        "difficulty_bias": {"type": "number"},
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "version", "prompt_tags", "density_bias", "spacing_bias", "slider_ratio_bias", "difficulty_bias", "notes"],
}

KIMI_BASE_URL = "https://api.moonshot.ai/v1"
KIMI_DEFAULT_MODEL = "kimi-k2.5"
KIMI_THINKING_MODEL = "kimi-k2-thinking"
FILE_BACKENDS = {"mapperatorinator", "osut5", "osu-diffusion", "osu-dreamer"}


def _load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _secret_from_env(key: str, dotenv_path: Path | None = None) -> str | None:
    if os.environ.get(key):
        return os.environ[key]
    dotenv_candidates = []
    if dotenv_path is not None:
        dotenv_candidates.append(dotenv_path)
    dotenv_candidates.extend([Path.cwd() / ".env", Path(__file__).resolve().parents[3] / ".env"])
    for candidate in dotenv_candidates:
        values = _load_dotenv(candidate)
        if key in values:
            return values[key]
    return None


def _ai_prompt(audio_path: Path, analysis: dict[str, object], prompt: str) -> str:
    return "\n".join(
        [
            "You are drafting a structured plan for an osu!standard beatmap generator.",
            "Do not output .osu text.",
            "Return only compact JSON matching the required schema.",
            f"Audio path: {audio_path}",
            f"User prompt tags: {prompt}",
            f"Audio analysis summary: {json.dumps(analysis, ensure_ascii=True)}",
            "Choose sensible density_bias, spacing_bias, slider_ratio_bias, and difficulty_bias values between 0.5 and 1.5.",
            "Use prompt_tags to refine the requested style.",
        ]
    )


def _run_claude(prompt: str) -> subprocess.CompletedProcess[str]:
    command = [
        "bash",
        "-lc",
        "source ~/claude.sh; claude -p --output-format json --permission-mode bypassPermissions "
        f"--json-schema '{json.dumps(AI_DRAFT_SCHEMA)}' {json.dumps(prompt)}",
    ]
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _run_droid(prompt: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("droid")
    if not executable:
        raise FileNotFoundError("droid executable was not found")
    command = [executable, "exec", "--output-format", "json", prompt]
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _extract_json_object(text: str) -> dict[str, object] | None:
    stripped = text.strip()
    try:
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = stripped[start : end + 1]
        try:
            payload = json.loads(snippet)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            return None
    return None


def _run_kimi(prompt: str, model: str, dotenv_path: Path | None = None) -> dict[str, object]:
    api_key = _secret_from_env("KIMI_API_KEY", dotenv_path=dotenv_path)
    if not api_key:
        return {"status": "error", "backend": "kimi", "message": "KIMI_API_KEY was not found in environment or .env"}
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are Kimi. Return only valid JSON for the requested schema and never emit .osu text.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 1.0,
    }
    request = urllib.request.Request(
        f"{KIMI_BASE_URL}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return {
            "status": "error",
            "backend": "kimi",
            "message": "kimi API request failed",
            "http_status": exc.code,
            "response": error_body,
        }
    except urllib.error.URLError as exc:
        return {"status": "error", "backend": "kimi", "message": f"kimi API connection failed: {exc}"}
    choice = (((payload.get("choices") or [{}])[0]).get("message") or {})
    content = choice.get("content", "")
    extracted = _extract_json_object(content)
    if not extracted:
        return {
            "status": "error",
            "backend": "kimi",
            "message": "kimi did not return parseable JSON content",
            "content": content,
        }
    return {
        "status": "ok",
        "backend": "kimi",
        "draft": extracted,
        "model": model,
        "usage": payload.get("usage", {}),
        "reasoning_content": choice.get("reasoning_content"),
    }


def _normalize_prompt_tags(tags: list[object] | None) -> list[str]:
    normalized = []
    for raw in tags or []:
        text = str(raw).replace("_", " ").strip().lower()
        if text == "flow aim":
            normalized.append("flow aim")
        elif text:
            normalized.append(text)
    return list(dict.fromkeys(normalized or ["mixed"]))


def _normalize_draft(draft: dict[str, object], fallback_prompt: str) -> dict[str, object]:
    style_block = draft.get("style") if isinstance(draft.get("style"), dict) else {}
    params_block = draft.get("generation_params") if isinstance(draft.get("generation_params"), dict) else {}
    prompt_tags = _normalize_prompt_tags(
        draft.get("prompt_tags") if isinstance(draft.get("prompt_tags"), list) else style_block.get("prompt_tags") if isinstance(style_block.get("prompt_tags"), list) else params_block.get("prompt_tags") if isinstance(params_block.get("prompt_tags"), list) else []
    )
    if not prompt_tags:
        prompt_tags = _normalize_prompt_tags([part.strip() for part in fallback_prompt.split(",") if part.strip()])
    notes = []
    if isinstance(draft.get("notes"), list):
        notes.extend(str(item) for item in draft["notes"])
    if isinstance(draft.get("structure"), list):
        notes.extend(json.dumps(item, ensure_ascii=True) for item in draft["structure"][:8])
    if isinstance(draft.get("timing"), dict):
        notes.append(json.dumps(draft["timing"], ensure_ascii=True))
    if isinstance(draft.get("beatmap_plan"), dict):
        notes.append(json.dumps(draft["beatmap_plan"], ensure_ascii=True))

    def _pick_number(*values: object, default: float = 1.0) -> float:
        for value in values:
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return default

    return {
        "title": str(draft.get("title") or Path(str(draft.get("audio_path") or "Generated")).stem or "Generated"),
        "version": str(draft.get("version") or "AI Draft"),
        "prompt_tags": prompt_tags,
        "density_bias": _pick_number(draft.get("density_bias"), style_block.get("density_bias"), params_block.get("density_bias"), default=1.0),
        "spacing_bias": _pick_number(draft.get("spacing_bias"), style_block.get("spacing_bias"), params_block.get("spacing_bias"), default=1.0),
        "slider_ratio_bias": _pick_number(draft.get("slider_ratio_bias"), style_block.get("slider_ratio_bias"), params_block.get("slider_ratio_bias"), default=1.0),
        "difficulty_bias": _pick_number(draft.get("difficulty_bias"), style_block.get("difficulty_bias"), params_block.get("difficulty_bias"), default=1.0),
        "notes": notes or ["normalized-ai-draft"],
    }


def _ai_context(
    audio_path: Path,
    analysis: dict[str, object],
    prompt: str,
    output_root: Path,
    reference_maps: list[str | Path] | None = None,
    target_star: float | None = None,
) -> dict[str, str]:
    title = audio_path.stem or "Generated"
    reference_map = str(Path(reference_maps[0])) if reference_maps else ""
    prompt_tags = ",".join(_normalize_prompt_tags([part.strip() for part in prompt.split(",") if part.strip()]))
    return {
        "audio_path": str(audio_path),
        "output_path": str(output_root),
        "beatmap_path": reference_map,
        "reference_map": reference_map,
        "bpm": str(analysis.get("bpm", 120.0)),
        "offset": str((analysis.get("beats_ms") or [0])[0] if isinstance(analysis.get("beats_ms"), list) else 0),
        "title": title,
        "artist": "osu-lab",
        "difficulty": str(target_star or 5.0),
        "prompt_tags": prompt_tags or "mixed",
        "descriptors": json.dumps(prompt_tags.split(",") if prompt_tags else ["mixed"]),
        "model_path": os.environ.get("OSU_LAB_AI_MODEL_PATH", ""),
        "ckpt_path": os.environ.get("OSU_LAB_AI_CKPT_PATH", ""),
        "beatmap_idx": os.environ.get("OSU_LAB_OSU_DIFFUSION_BEATMAP_IDX", ""),
        "num_classes": os.environ.get("OSU_LAB_OSU_DIFFUSION_NUM_CLASSES", ""),
        "style_id": os.environ.get("OSU_LAB_OSU_DIFFUSION_STYLE_ID", ""),
    }


def _command_from_template(template: str, context: dict[str, str]) -> list[str]:
    formatted = template.format(**context)
    return shlex.split(formatted)


def _backend_error(backend: str, message: str, **extra: object) -> dict[str, object]:
    payload = {"status": "error", "backend": backend, "message": message}
    payload.update(extra)
    return payload


def _python_command(root: Path, env_key: str) -> str:
    explicit = os.environ.get(env_key)
    if explicit:
        return explicit
    venv_python = root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    windows_python = root / ".venv" / "Scripts" / "python.exe"
    if windows_python.exists():
        return str(windows_python)
    return shutil.which("python") or "python"


def _default_file_backend_command(backend: str, root: Path, context: dict[str, str]) -> tuple[list[str], Path]:
    if backend == "mapperatorinator":
        command = [
            _python_command(root, "OSU_LAB_MAPPERATORINATOR_PYTHON"),
            "inference.py",
            f"audio_path={context['audio_path']}",
            f"output_path={context['output_path']}",
            "gamemode=0",
            f"difficulty={context['difficulty']}",
            "year=2023",
            f"descriptors={context['descriptors']}",
            "seed=1",
        ]
        if context["beatmap_path"]:
            command.append(f"beatmap_path={context['beatmap_path']}")
        return command, root
    if backend == "osut5":
        model_path = os.environ.get("OSU_LAB_OSUT5_MODEL_PATH", "")
        if not model_path:
            raise FileNotFoundError("OSU_LAB_OSUT5_MODEL_PATH is required for the osut5 adapter")
        return (
            [
                _python_command(root, "OSU_LAB_OSUT5_PYTHON"),
                "-m",
                "inference",
                f"model_path={model_path}",
                f"audio_path={context['audio_path']}",
                f"output_path={context['output_path']}",
                f"bpm={context['bpm']}",
                f"offset={context['offset']}",
                f"title={context['title']}",
                f"artist={context['artist']}",
            ],
            root,
        )
    if backend == "osu-dreamer":
        model_path = os.environ.get("OSU_LAB_OSU_DREAMER_MODEL_PATH", "")
        if not model_path:
            raise FileNotFoundError("OSU_LAB_OSU_DREAMER_MODEL_PATH is required for the osu-dreamer adapter")
        uv = shutil.which("uv") or "uv"
        return (
            [
                uv,
                "run",
                "python",
                "-m",
                "osu_dreamer.model",
                "predict",
                "--model_path",
                model_path,
                "--audio_file",
                context["audio_path"],
                "--num_samples",
                "1",
                "--title",
                context["title"],
                "--artist",
                context["artist"],
            ],
            Path(context["output_path"]),
        )
    if backend == "osu-diffusion":
        if not context["beatmap_path"]:
            raise FileNotFoundError("osu-diffusion requires at least one --reference-map to supply rhythm and spacing")
        ckpt_path = os.environ.get("OSU_LAB_OSU_DIFFUSION_CKPT", "")
        if not ckpt_path:
            raise FileNotFoundError("OSU_LAB_OSU_DIFFUSION_CKPT is required for the osu-diffusion adapter")
        beatmap_idx = os.environ.get("OSU_LAB_OSU_DIFFUSION_BEATMAP_IDX", "")
        num_classes = os.environ.get("OSU_LAB_OSU_DIFFUSION_NUM_CLASSES", "")
        if not beatmap_idx or not num_classes:
            raise FileNotFoundError("OSU_LAB_OSU_DIFFUSION_BEATMAP_IDX and OSU_LAB_OSU_DIFFUSION_NUM_CLASSES are required for the osu-diffusion adapter")
        return (
            [
                _python_command(root, "OSU_LAB_OSU_DIFFUSION_PYTHON"),
                "sample.py",
                "--beatmap",
                context["beatmap_path"],
                "--ckpt",
                ckpt_path,
                "--beatmap_idx",
                beatmap_idx,
                "--num-classes",
                num_classes,
            ],
            Path(context["output_path"]),
        )
    raise FileNotFoundError(f"unsupported file backend: {backend}")


def _discover_generated_map(output_root: Path, fallback_root: Path | None = None) -> Path | None:
    candidates = sorted(output_root.rglob("*.osu"), key=lambda path: path.stat().st_mtime, reverse=True) if output_root.exists() else []
    if not candidates and fallback_root is not None and fallback_root.exists():
        candidates = sorted(fallback_root.rglob("*.osu"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _summarize_generated_map(path: Path) -> dict[str, object]:
    issues = verify_beatmap(parse_osu(path))
    profile = build_style_profile([path])
    return {
        "path": str(path),
        "score": score_map(path),
        "issue_count": len([issue for issue in issues if issue.severity == "error"]),
        "warning_count": len([issue for issue in issues if issue.severity == "warning"]),
        "issues": [dataclass_to_dict(issue) for issue in issues],
        "style_report": render_style_report(profile),
    }


def _run_file_backend(
    backend: str,
    audio_path: Path,
    output_root: Path,
    analysis: dict[str, object],
    prompt: str,
    reference_maps: list[str | Path] | None = None,
    target_star: float | None = None,
) -> dict[str, object]:
    env_prefix = backend.upper().replace("-", "_")
    template = os.environ.get(f"OSU_LAB_{env_prefix}_COMMAND_TEMPLATE", "")
    root_value = os.environ.get(f"OSU_LAB_{env_prefix}_ROOT", "")
    if not template and not root_value:
        return _backend_error(
            backend,
            f"set OSU_LAB_{env_prefix}_ROOT or OSU_LAB_{env_prefix}_COMMAND_TEMPLATE to enable this adapter",
        )
    output_root.mkdir(parents=True, exist_ok=True)
    context = _ai_context(audio_path, analysis, prompt, output_root, reference_maps=reference_maps, target_star=target_star)
    try:
        if template:
            command = _command_from_template(template, context)
            cwd = output_root
            fallback_root = Path(root_value) if root_value else output_root
        else:
            root = Path(root_value)
            if not root.exists():
                return _backend_error(backend, f"configured root does not exist: {root}")
            command, cwd = _default_file_backend_command(backend, root, context)
            fallback_root = root
    except FileNotFoundError as exc:
        return _backend_error(backend, str(exc))
    result = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return _backend_error(
            backend,
            f"{backend} command failed",
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            command=command,
        )
    generated_map = _discover_generated_map(output_root, fallback_root=fallback_root)
    if generated_map is None:
        return _backend_error(
            backend,
            f"{backend} completed but no .osu output was found",
            stdout=result.stdout,
            stderr=result.stderr,
            command=command,
        )
    return {
        "status": "ok",
        "backend": backend,
        "draft_map": str(generated_map),
        "stdout": result.stdout,
        "stderr": result.stderr,
        "command": command,
    }


def _extract_payload(result: subprocess.CompletedProcess[str], backend: str) -> dict[str, object]:
    if result.returncode != 0:
        return {
            "status": "error",
            "backend": backend,
            "message": f"{backend} command failed",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    payload = _extract_json_object(result.stdout)
    if payload is None:
        return {
            "status": "error",
            "backend": backend,
            "message": f"{backend} did not return valid JSON",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    if "result" in payload and isinstance(payload["result"], str):
        nested = _extract_json_object(payload["result"])
        if nested is not None:
            payload = nested
    if "content" in payload and isinstance(payload["content"], list):
        joined = "".join(
            item.get("text", "")
            for item in payload["content"]
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
        )
        nested = _extract_json_object(joined)
        if nested is not None:
            payload = nested
    return {"status": "ok", "backend": backend, "draft": payload}


def draft_with_backend(
    backend: str,
    audio_path: str | Path,
    output_path: str | Path | None = None,
    prompt: str = "mixed",
    seed: int = 1,
    target_star: float | None = None,
    target_pp: float | None = None,
    reference_maps: list[str | Path] | None = None,
    style_index: dict[str, object] | None = None,
    dotenv_path: str | Path | None = None,
) -> dict[str, object]:
    backend_key = backend.lower()
    source = Path(audio_path)
    analysis = analyze_audio(source).to_dict()
    prompt_text = _ai_prompt(source, analysis, prompt=prompt)
    output_root = Path(output_path) if output_path else source.parent / "ai-drafts"
    if output_root.suffix:
        output_root = output_root.parent

    if backend_key in {"claude", "claude-agent"}:
        extracted = _extract_payload(_run_claude(prompt_text), backend=backend)
    elif backend_key in {"droid", "droid-agent"}:
        extracted = _extract_payload(_run_droid(prompt_text), backend=backend)
    elif backend_key in {"kimi", "kimi-agent"}:
        extracted = _run_kimi(prompt_text, model=KIMI_DEFAULT_MODEL, dotenv_path=Path(dotenv_path) if dotenv_path else None)
    elif backend_key in {"kimi-thinking", "kimi-k2-thinking"}:
        extracted = _run_kimi(prompt_text, model=KIMI_THINKING_MODEL, dotenv_path=Path(dotenv_path) if dotenv_path else None)
    elif backend_key in FILE_BACKENDS:
        extracted = _run_file_backend(
            backend_key,
            source,
            output_root / backend_key / "raw",
            analysis,
            prompt,
            reference_maps=reference_maps,
            target_star=target_star,
        )
    else:
        return {"status": "error", "backend": backend, "message": f"unsupported backend: {backend}"}

    if extracted["status"] != "ok":
        return extracted
    if backend_key in FILE_BACKENDS:
        draft_summary = _summarize_generated_map(Path(extracted["draft_map"]))
        chained_reference_maps = [Path(extracted["draft_map"]), *(reference_maps or [])]
        generation = generate_map(
            audio_path=source,
            output_dir=output_root / backend_key / "postprocessed",
            prompt=prompt,
            seed=seed,
            target_star=target_star,
            target_pp=target_pp,
            reference_maps=chained_reference_maps,
            style_index=style_index,
        )
        return {
            "status": "ok",
            "backend": backend,
            "draft_source": "external-map",
            "draft_map": draft_summary,
            "generation": generation,
            "command": extracted.get("command"),
            "stdout": extracted.get("stdout"),
            "stderr": extracted.get("stderr"),
        }
    draft = _normalize_draft(extracted["draft"], fallback_prompt=prompt)
    merged_prompt = ",".join(dict.fromkeys([*(draft.get("prompt_tags", []) or []), *[part.strip() for part in prompt.split(",") if part.strip()]]))
    generation = generate_map(
        audio_path=source,
        output_dir=output_root,
        prompt=merged_prompt or prompt,
        seed=seed,
        target_star=target_star,
        target_pp=target_pp,
        ai_recipe=draft,
        reference_maps=reference_maps,
        style_index=style_index,
    )
    return {
        "status": "ok",
        "backend": backend,
        "draft": draft,
        "generation": generation,
        "model": extracted.get("model"),
        "usage": extracted.get("usage"),
        "reasoning_content": extracted.get("reasoning_content"),
    }
