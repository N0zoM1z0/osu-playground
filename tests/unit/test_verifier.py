from pathlib import Path

from osu_lab.beatmap.verify_external import run_external_verifier


def test_external_verifier_command_template():
    payload = run_external_verifier("tests/fixtures/sample_map.osu", command="python3 -c print('ok')")
    assert payload["status"] == "ok"
    assert "ok" in payload["stdout"]

