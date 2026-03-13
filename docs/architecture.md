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
- `live`: replay-to-live event planning, `tosu` provider fetch, Windows injection
- `audio`: WAV normalization and beat/segment analysis
- `style`: spacing, angle, density, corpus indexing, and heuristic classification profiles
- `generate`: rule-based skeleton drafting and object arrangement
- `ai`: optional external CLI adapters with structured recipe normalization
- `integration`: scoring and agent-callable tool wrappers
- `eval`: benchmark placeholders and acceptance harness entry points
- `eval.acceptance`: round-trip, replay, generation, and style-control acceptance aggregation

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

The current generator is deterministic and target-aware. It maps prompt tags into spacing, density, and path heuristics, then runs a short local tuning loop against `rosu-pp-py`:

- `flow aim`: arc-like movement and occasional sliders
- `jump`: large spacing with simpler rhythms
- `farm jump`: extra-large jump spacing
- `stream`: dense lower-spacing streams
- `deathstream`: even denser stream layout
- `mixed/control`: conservative baseline

The tuning loop adjusts:

- spacing scale
- density scale
- slider ratio bias

and keeps the best candidate against requested star and pp targets.

The generator is now section-aware:

- it derives a section density plan from audio segments
- it can blend in density tendencies from a local reference corpus
- it can consume explicit reference maps supplied by the user at generation time
- it assigns simple hitsounds and adjusts object mix by section label
- it adapts retrieved reference patterns with continuity-aware mirroring, rotation, and rescaling before stitching them into the arranged output

### Style Corpus

local `.osu` folders -> per-map profiles -> aggregate style index

The repository does not ship third-party beatmaps. Instead, the workflow expects user-supplied local folders and builds:

- per-map style metrics
- aggregate histograms
- section density curves
- heuristic class signals
- lightweight pattern banks for retrieval-driven arrangement

This keeps the project local-only while still enabling prompt and reference driven generation.
Generated outputs also include a short human-readable style report so agent and CLI consumers can inspect why a map reads as jump-heavy, stream-heavy, or flow-oriented.

### Live

`ReplayPlan` -> `LivePlan` -> optional Windows injection

Providers:

- `direct-file/manual`: read a local `.osu`
- `tosu`: fetch the current beatmap file from the local `tosu` HTTP endpoint

Execution:

- dry-run on any platform
- `SendInput` injection on Windows only, with an explicit UIPI warning

### AI

audio + analysis summary -> external AI backend -> structured recipe -> local generator

Supported adapters:

- `claude`
- `droid`
- `kimi`
- `kimi-thinking`

The AI output is constrained to a small JSON recipe and never writes raw `.osu` text directly.

For Kimi, the implementation targets Moonshot's international OpenAI-compatible API:

- base URL: `https://api.moonshot.ai/v1`
- recommended general model: `kimi-k2.5`
- dedicated reasoning model: `kimi-k2-thinking`

The adapter normalizes freer Kimi responses back into the repository's internal recipe schema before generation.

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
