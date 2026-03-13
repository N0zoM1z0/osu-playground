# Architecture

## Overview

`osu-lab` is a single Python package with a file-first pipeline:

1. ingest `.osu` / audio files
2. normalize them into validated IR
3. run replay generation, scoring, profiling, or mapping logic against IR
4. compile back to `.osu` / `.osz` / `.osr`

The main rule is that agent-facing tools operate on structured objects, not on raw `.osu` text.

## Modules

- `core`: shared dataclasses, schema bundle, JSON helpers
- `beatmap`: `.osu` parsing, compilation, `.osz` packaging, validation
- `replay`: deterministic replay planning and `.osr` writing
- `live`: replay-to-live event planning, dry-run arming
- `audio`: WAV normalization and beat/segment analysis
- `style`: spacing, angle, density, and heuristic classification profiles
- `generate`: rule-based skeleton drafting and object arrangement
- `ai`: optional backend adapters with explicit local-failure reporting
- `integration`: scoring and agent-callable tool wrappers
- `eval`: benchmark placeholders and acceptance harness entry points

## Data Flow

### Beatmap

`.osu` -> `BeatmapIR` -> validation -> `.osu` / `.osz`

The parser extracts:

- metadata and difficulty settings
- timing points split into uninherited and inherited groups
- hit objects normalized into `HitObjectIR`

The compiler emits deterministic section ordering and keeps the writer stateless.

### Replay

`.osu` -> `BeatmapIR` -> `ReplayPlan` -> `.osr`

Replay synthesis uses object-level planning:

- circles: pre-aim, press, release
- sliders: press, hold, sample curve anchors, release
- spinners: center hold or circular spinner path

Profiles:

- `auto_perfect`
- `autopilot_only`
- `humanized_aim`

### Audio

audio file -> normalized WAV -> `AudioAnalysis`

Primary backend:

- `allin1` when installed locally

Fallback backend:

- deterministic energy/onset/autocorrelation analysis using the standard library

### Generation

`AudioAnalysis` + `StyleTarget` -> draft timing grid -> arranged `BeatmapIR`

The current generator is intentionally simple and deterministic. It maps prompt tags into spacing, density, and path heuristics:

- `flow aim`: arc-like movement and occasional sliders
- `jump`: large spacing with simpler rhythms
- `farm jump`: extra-large jump spacing
- `stream`: dense lower-spacing streams
- `deathstream`: even denser stream layout
- `mixed/control`: conservative baseline

## Agent Boundary

Recommended agent tools:

- `analyze_audio(path)`
- `build_style_profile(ref_maps)`
- `draft_skeleton(audio_analysis, style_target)`
- `arrange_objects(beatmap_ir, style_profile)`
- `score_map(path, mods, acc)`
- `classify_map(path)`
- `verify_map(path)`
- `compile_map(beatmap_ir)`
- `synthesize_replay(map_path, profile)`
- `plan_live_play(map_path_or_tosu_context, profile)`

Agents should patch IR JSON, then invoke validation and compilation.

## Constraints

- offline-only workflow
- no multiplayer or online score automation
- no client patching, DLL injection, packet manipulation, or ban-evasion logic
- Windows live execution remains dry-run-first
