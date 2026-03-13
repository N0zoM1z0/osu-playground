from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _candidate_commands(path: Path) -> list[list[str]]:
    commands: list[list[str]] = []
    executable = shutil.which("MapsetVerifier")
    if executable:
        commands.append([executable, str(path)])
    executable = shutil.which("MapsetVerifier.exe")
    if executable:
        commands.append([executable, str(path)])
    configured = os.environ.get("OSU_LAB_MAPSET_VERIFIER")
    if configured:
        commands.append([token.format(path=str(path)) for token in configured.split()])
    return commands


def run_external_verifier(path: str | Path, command: str | None = None) -> dict[str, object]:
    target = Path(path)
    attempts = [command.split()] if command else _candidate_commands(target)
    if not attempts:
        return {
            "status": "unavailable",
            "path": str(target),
            "message": "no external verifier configured; set OSU_LAB_MAPSET_VERIFIER or install MapsetVerifier",
        }
    for args in attempts:
        prepared = [token.format(path=str(target)) for token in args]
        try:
            result = subprocess.run(prepared, check=False, capture_output=True, text=True)
        except FileNotFoundError:
            continue
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "path": str(target),
            "command": prepared,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    return {
        "status": "unavailable",
        "path": str(target),
        "message": "configured external verifier executable was not found",
    }
