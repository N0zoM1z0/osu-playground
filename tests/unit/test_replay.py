from pathlib import Path

from osrparse import Replay

from osu_lab.replay.synth import inspect_replay, synthesize_replay_plan, write_replay


def test_replay_plan_is_deterministic():
    first = synthesize_replay_plan("tests/fixtures/sample_map.osu", seed=7)
    second = synthesize_replay_plan("tests/fixtures/sample_map.osu", seed=7)
    assert first.to_dict() == second.to_dict()


def test_replay_file_is_parseable(tmp_path: Path):
    replay_path = tmp_path / "sample.osr"
    output, plan = write_replay("tests/fixtures/sample_map.osu", replay_path, seed=3)
    parsed = Replay.from_path(str(output))
    assert parsed.count_300 == plan.expected_score_stats["count_300"]
    inspected = inspect_replay(output)
    assert inspected["frame_count"] > 0

