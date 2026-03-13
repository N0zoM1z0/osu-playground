import json
import os
import subprocess
import sys
from pathlib import Path


def _run_cli(*args: str) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    result = subprocess.run([sys.executable, "-m", "osu_lab", *args], check=True, capture_output=True, text=True, env=env)
    return json.loads(result.stdout)


def test_schema_dump_cli():
    payload = _run_cli("schema", "dump")
    assert "BeatmapIR" in payload


def test_map_verify_cli():
    payload = _run_cli("map", "verify", "tests/fixtures/sample_map.osu")
    assert payload["issue_count"] == 0
