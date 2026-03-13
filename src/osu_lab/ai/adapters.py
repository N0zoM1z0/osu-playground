from __future__ import annotations

import json
import shutil
import subprocess
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


def _ai_prompt(audio_path: Path, analysis: dict[str, object], prompt: str) -> str:
    return "\n".join(
        [
            "You are drafting a structured plan for an osu!standard beatmap generator.",
            "Do not output .osu text.",
            "Return only JSON matching the provided schema.",
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
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "backend": backend,
            "message": f"{backend} did not return valid JSON",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    if isinstance(payload, dict) and "result" in payload and isinstance(payload["result"], str):
        try:
            payload = json.loads(payload["result"])
        except json.JSONDecodeError:
            pass
    if isinstance(payload, dict) and "content" in payload and isinstance(payload["content"], list):
        joined = "".join(
            item.get("text", "")
            for item in payload["content"]
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
        )
        try:
            payload = json.loads(joined)
        except json.JSONDecodeError:
            return {
                "status": "error",
                "backend": backend,
                "message": f"{backend} returned content that could not be decoded as JSON",
                "stdout": result.stdout,
            }
    if not isinstance(payload, dict):
        return {"status": "error", "backend": backend, "message": f"{backend} returned an unexpected payload", "stdout": result.stdout}
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
) -> dict[str, object]:
    backend_key = backend.lower()
    source = Path(audio_path)
    analysis = analyze_audio(source).to_dict()
    prompt_text = _ai_prompt(source, analysis, prompt=prompt)
    if backend_key in {"claude", "claude-agent"}:
        result = _run_claude(prompt_text)
    elif backend_key in {"droid", "droid-agent"}:
        result = _run_droid(prompt_text)
    else:
        return {"status": "error", "backend": backend, "message": f"unsupported backend: {backend}"}
    extracted = _extract_payload(result, backend=backend)
    if extracted["status"] != "ok":
        return extracted
    draft = extracted["draft"]
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
    )
    return {
        "status": "ok",
        "backend": backend,
        "draft": draft,
        "generation": generation,
    }
