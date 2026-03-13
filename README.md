# osu-lab

Local-only R&D toolkit for `osu!standard` with a file-first workflow centered on `.osu`, `.osr`, and `.osz`.

This repository implements a CLI-first Python package that prioritizes:

- deterministic beatmap parsing and compilation
- replay synthesis for offline `.osr` experimentation
- offline audio analysis and rule-based map drafting
- style profiling from local reference maps
- agent-safe IR editing instead of raw `.osu` text generation

## Status

The current implementation provides a working v0.1 foundation:

- `BeatmapIR`, `AudioAnalysis`, `StyleProfile`, `ReplayPlan`, and related models
- `.osu` parse -> IR -> compile round-trip
- `.osz` packaging
- deterministic `.osr` synthesis using `osrparse`
- fallback WAV audio analysis plus optional `allin1`
- basic rule-based generator for prompts such as `flow aim`, `jump`, `farm jump`, `stream`, `deathstream`
- style profiling and map classification heuristics
- `rosu-pp-py` based map scoring
- JSON-first CLI and automated tests

Windows live injection is intentionally left in dry-run mode by default. Online score submission, multiplayer automation, anti-detection workflows, and client modification remain out of scope.

## Quickstart

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev]
pytest -q
```

Core CLI examples:

```bash
osu-lab schema dump
osu-lab map verify tests/fixtures/sample_map.osu
osu-lab replay synth tests/fixtures/sample_map.osu --plan-json /tmp/sample.plan.json
osu-lab replay inspect tests/fixtures/sample_map.auto_perfect.osr
osu-lab style profile tests/fixtures/sample_map.osu
```

Generate a WAV analysis report:

```bash
osu-lab audio analyze /path/to/song.wav --out /tmp/song.analysis.json
```

Generate a draft beatmap package:

```bash
osu-lab map generate /path/to/song.wav --out-dir /tmp/out --prompt "flow aim,jump" --seed 7
```

Score a map with `rosu-pp-py`:

```bash
osu-lab map score /path/to/map.osu --mods HDDT --acc 98.5
```

## CLI Surface

Implemented commands:

- `osu-lab audio analyze`
- `osu-lab replay synth`
- `osu-lab replay inspect`
- `osu-lab live plan`
- `osu-lab live arm`
- `osu-lab map generate`
- `osu-lab map verify`
- `osu-lab map score`
- `osu-lab style build-index`
- `osu-lab style profile`
- `osu-lab ai draft`
- `osu-lab schema dump`
- `osu-lab bench`

All commands emit JSON to stdout.

## Repository Layout

```text
src/osu_lab/core/
src/osu_lab/beatmap/
src/osu_lab/replay/
src/osu_lab/live/
src/osu_lab/audio/
src/osu_lab/style/
src/osu_lab/generate/
src/osu_lab/ai/
src/osu_lab/integration/
src/osu_lab/eval/
tests/unit/
tests/integration/
tests/fixtures/
configs/
docs/
```

## Design Notes

- Agents should operate on IR JSON, not raw `.osu` text.
- The parser/compiler path is deterministic under fixed inputs.
- Replay generation is deterministic under fixed seeds.
- Audio analysis normalizes non-WAV input via `ffmpeg` when available.
- `allin1` is optional; a fallback analyzer is included for lightweight local use.

## Docs

- [Architecture](docs/architecture.md)
- [IR Schema](docs/ir-schema.md)
- [Offline Smoke Tests](docs/smoke-test.md)
- [Example Config](configs/example-config.json)
