from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from osu_lab.audio.analyze import analyze_audio
from osu_lab.generate.mapforge import generate_map


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

    if backend_key in {"claude", "claude-agent"}:
        extracted = _extract_payload(_run_claude(prompt_text), backend=backend)
    elif backend_key in {"droid", "droid-agent"}:
        extracted = _extract_payload(_run_droid(prompt_text), backend=backend)
    elif backend_key in {"kimi", "kimi-agent"}:
        extracted = _run_kimi(prompt_text, model=KIMI_DEFAULT_MODEL, dotenv_path=Path(dotenv_path) if dotenv_path else None)
    elif backend_key in {"kimi-thinking", "kimi-k2-thinking"}:
        extracted = _run_kimi(prompt_text, model=KIMI_THINKING_MODEL, dotenv_path=Path(dotenv_path) if dotenv_path else None)
    else:
        return {"status": "error", "backend": backend, "message": f"unsupported backend: {backend}"}

    if extracted["status"] != "ok":
        return extracted
    draft = _normalize_draft(extracted["draft"], fallback_prompt=prompt)
    merged_prompt = ",".join(dict.fromkeys([*(draft.get("prompt_tags", []) or []), *[part.strip() for part in prompt.split(",") if part.strip()]]))
    output_root = Path(output_path) if output_path else source.parent / "ai-drafts"
    if output_root.suffix:
        output_root = output_root.parent
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
