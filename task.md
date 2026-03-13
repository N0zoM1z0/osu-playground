Use the following as the task brief for Codex.

# Task Brief — OSU-Lab for osu!standard on Windows

This project is a **local-only R&D toolkit** for **osu!standard on Windows**, with **osu!stable as the required v1 target client** and a clean adapter boundary for future lazer support. The design must be **file-first**, not editor-UI-first, because osu! already documents the relevant file formats: `.osu` beatmaps, `.osr` replays, and `.osz` beatmap archives. `.osr` replay data is explicitly stored as `w|x|y|z` cursor/button frames over a `512 x 384` playfield, and `.osz` archives are extracted by osu! into `Songs`, which makes deterministic compilation and replay synthesis much more robust than trying to automate the editor UI. ([osu!][1])

## 1. Task

Build a modular toolkit that supports all of the following for **osu!standard on Windows**:

1. **Replay synthesis**: generate valid `.osr` replays from `.osu` beatmaps.
2. **Optional real-time autoplay/autopilot**: drive the running osu! client locally for offline experimentation.
3. **Audio-to-beatmap generation**: analyze song audio and generate `.osu` / `.osz` output without controlling the beatmap editor UI.
4. **Style-targeted mapping**: support prompts such as `flow aim`, `jump map`, `farm jump`, `stream`, and `deathstream`, and support reference-map style transfer.
5. **Agent-ready tooling**: expose structured tools/APIs so an LLM/agent can plan, edit, and refine a map through a validated IR instead of freehand-editing raw `.osu` text.

## 2. Goals

The implementation must optimize for these goals:

* **Determinism first**: given the same input files, config, and seed, outputs should be reproducible.
* **File-first correctness**: treat `.osu`, `.osr`, and `.osz` as the source of truth, not UI automation.
* **Modularity**: rule-based generation must work even if AI backends are unavailable.
* **Style controllability**: prompt-driven generation must translate into measurable pattern changes.
* **Offline safety**: the project must remain local-only and must not automate score submission, multiplayer, or any anti-detection workflow.
* **Codex efficiency**: use mature ecosystem libraries wherever possible instead of reimplementing parsers, pp calculators, and validators from scratch.

## 3. Non-negotiable facts and constraints

* `.osu` beatmaps contain structured sections such as `[TimingPoints]` and `[HitObjects]`, and sliders use the documented timing formula based on `length / (SliderMultiplier * 100 * SV) * beatLength`. `.osr` replay files encode explicit cursor coordinates and key states, and `.osz` is the archive format osu! opens directly. ([osu!][1])
* Replay-first development is the required first milestone because osu! already supports exporting local replays with `F2`, importing `.osr` files into the local leaderboard, and Auto behaves like a replay-based perfect play. Auto replays are also exportable. ([osu!][2])
* Generated beatmaps must be treated as **local/unranked experiments**. Official ranking criteria require hit objects, hitsounds, and timing to be created exclusively by direct human input for ranked content. The same criteria also enforce no same-tick object overlap, at least 10 ms between a hit circle and the next object, at least 20 ms between a slider end and the next object, and snap accuracy within less than 2 ms of a timeline tick. Official criteria recommend **Mapset Verifier** and note that old **AiMod** is outdated. ([osu!][3])
* For live play, prefer `tosu` as the state provider because it exposes WebSocket/API data for gameplay/beatmap state and direct endpoints for the current beatmap’s background, audio, and `.osu` file. Windows input injection should use Win32 `SendInput`, which is subject to UIPI and therefore only works reliably when the bot process and osu! run at the same or lower integrity relationship. ([GitHub][4])
* Audio analysis must standardize to WAV internally before precise timing analysis. `allin1` explicitly warns that MP3 decoder differences can introduce roughly `20–40 ms` of offset variation, which is unacceptable for beat tracking. `allin1` also provides BPM, beats, downbeats, segment boundaries, and segment labels, while `librosa`, `madmom`, and Essentia provide strong fallback primitives for beat/rhythm analysis. ([GitHub][5])

## 4. Assumptions and design decisions

* **Required mode**: osu!standard only.
* **Required platform**: Windows only.
* **Required client for acceptance**: osu!stable.
* **Primary implementation language**: Python.
* **Primary UX**: CLI-first, JSON-first, library-second. GUI is not required for v1.
* **Default stable root path** should be configurable, with `%localappdata%\osu!` used as the default assumption on Windows. Do not hardcode logic to a single `osu!.db` version. ([GitHub][6])

## 5. In scope

The following are in scope for v1:

* Parsing and compiling `.osu` beatmaps.
* Packaging generated beatmaps into `.osz`.
* Generating valid `.osr` replays for osu!standard.
* Real-time local autoplay/autopilot using Windows input injection.
* Audio analysis for BPM, beats, downbeats, segments, onset strength, and spectral summaries.
* Rule-based beatmap generation from audio plus prompt/style targets.
* Style profiling from reference maps and local map corpora.
* Difficulty and pp tuning loops.
* Offline validation and benchmark tooling.
* Adapters for optional AI generators.
* Agent-facing structured tools over a validated IR.
* Manual smoke-test procedures for in-game offline validation.

## 6. Out of scope

The following are explicitly out of scope:

* osu!taiko, osu!catch, osu!mania.
* macOS or Linux support.
* Ranked-map production workflows.
* Beatmap editor UI automation for map creation.
* Multiplayer, spectator, or online score submission automation.
* Anti-detection, anti-ban, obfuscation, or any workflow intended to hide automation.
* Memory patching, DLL injection, packet manipulation, or client modification.
* Full desktop GUI as a required deliverable.
* Training large foundation models from scratch as a required deliverable.
* Bundling copyrighted third-party beatmaps or audio into the repository.
* Hardcoded imitation of a specific named mapper as a baked-in mode; named styles should be expressed through reference maps and style profiles, not special-case codepaths.

## 7. Recommended stack

### Required runtime dependencies

* **`slider`** — Python utilities for `.osu` / `.osz` parsing/manipulation and `.osr` replay parsing. Use this as a primary Python beatmap IO dependency. ([GitHub][7])
* **`osrparse`** — Python `.osr` library with documented support for creating, editing, and writing replays. Use this as the primary replay writer in Python. ([GitHub][8])
* **`rosu-pp-py`** — Python bindings for `rosu-pp`, for star rating, strains, and performance calculations. Use this for difficulty/pp tuning loops. ([GitHub][9])
* **`allin1`** — primary high-level MIR backend for BPM, beats, downbeats, structure boundaries, and section labels. ([GitHub][5])
* **`tosu`** — primary live state provider for current beatmap/gameplay context and direct beatmap/audio file endpoints. ([GitHub][4])
* **`MapsetVerifier`** — primary offline validator. Official criteria recommend it, and it checks quantifiable beatmap issues such as unsnapped objects and unused files. ([GitHub][10])

### Recommended fallback / support libraries

* **`librosa`** — dynamic-programming beat tracker and core DSP utilities. Use as a lightweight fallback and for spectral features. ([Librosa][11])
* **`madmom`** — RNN-based beat processing. Use as a stronger fallback or ensemble source for beat/downbeat estimates. ([GitHub][12])
* **Essentia** — rhythm extraction and beat-position estimation. Use for alternative beat confidence or batch analysis tools. ([Essentia][13])

### Optional native / ecosystem references

* **`rosu-map`** — Rust library to decode and encode `.osu` files; useful as a reference or future native sidecar. ([GitHub][14])
* **`rosu-replay`** — Rust library for parsing and writing `.osr` files. Optional future native replay sidecar. ([GitHub][15])
* **`rosu-pp`** — Rust source of truth for performant pp/star calculation. ([GitHub][16])
* **`osu-map-analyzer-lib`** — Rust classifier for stream/jump/tech-like beatmap characteristics. Use for style evaluation. ([GitHub][17])
* **`Mapperator`** — .NET library for efficient osu!standard pattern search and beatmap construction; useful for pattern-bank ideas and retrieval-based generation. ([GitHub][18])
* **`Mapping_Tools`** — large collection of existing mapping utilities. Use as ecosystem reference, not as a required runtime dependency. ([GitHub][19])
* **`OsuParsers`** and **`Coosu`** — .NET alternatives for parsing/writing beatmaps, replays, and client data if a native Windows sidecar becomes necessary. ([GitHub][20])

### Optional AI backends

* **`Mapperatorinator`** — multi-model framework for generating/modding osu! beatmaps from spectrogram inputs; built on `osuT5` and `osu-diffusion`, and already includes post-processing such as resnapping and timing refinement. ([GitHub][21])
* **`osuT5`** — seq2seq audio-to-event model; inference explicitly expects BPM and offset, so it fits well as a controllable draft generator after MIR analysis. ([GitHub][22])
* **`osu-diffusion`** — standard-mode object-coordinate generator that turns partial rhythm/spacing drafts into more playable maps. ([GitHub][23])
* **`osu-dreamer`** — raw-audio diffusion baseline for automatic map generation. ([GitHub][24])

### Behavior / heuristic references

* **`osu-pilot`** — parses `.osu` directly and avoids reading game memory; useful as a reference for file-first live bot architecture. ([GitHub][25])
* **`OsuBot`** — Windows-only reference bot that already implements auto/relax/autopilot behavior. Use only as heuristic inspiration. ([GitHub][26])
* **`OsuAutoPlay`** — another file-first autoplay experiment with explicit offline-only intent. Use only as inspiration. ([GitHub][27])

## 8. Target architecture

### 8.1 Repository shape

Use a single Python monorepo with this approximate structure:

* `src/osu_lab/core/`
* `src/osu_lab/beatmap/`
* `src/osu_lab/replay/`
* `src/osu_lab/live/`
* `src/osu_lab/audio/`
* `src/osu_lab/style/`
* `src/osu_lab/generate/`
* `src/osu_lab/ai/`
* `src/osu_lab/integration/`
* `src/osu_lab/eval/`
* `tests/unit/`
* `tests/integration/`
* `tests/fixtures/`
* `configs/`
* `docs/`

### 8.2 Primary data contracts

Define a validated intermediate representation. Agents must edit this IR, not raw `.osu` text.

Required models:

* `AudioAnalysis`

  * `path`
  * `duration_ms`
  * `bpm`
  * `bpm_candidates`
  * `beats_ms`
  * `downbeats_ms`
  * `segments[{start_ms,end_ms,label,confidence}]`
  * `onset_envelope`
  * `band_energy_summary`
  * `optional_stem_energy`

* `TimingGrid`

  * `uninherited_points`
  * `inherited_points`
  * `meter_sections`
  * `kiai_ranges`
  * `snap_divisors`
  * `offset_ms`

* `StyleTarget`

  * `prompt_tags`
  * `target_star`
  * `target_pp`
  * `mods_profile`
  * `difficulty_bias`
  * `reference_maps`
  * `section_density_plan`

* `StyleProfile`

  * `spacing_histogram`
  * `angle_histogram`
  * `slider_ratio`
  * `burst_profile`
  * `jump_stream_tech_scores`
  * `section_density_curve`

* `HitObjectIR`

  * `type`
  * `start_ms`
  * `end_ms`
  * `x`
  * `y`
  * `curve`
  * `repeats`
  * `length`
  * `hitsounds`
  * `combo_flags`
  * `semantic_role`

* `BeatmapIR`

  * `metadata`
  * `difficulty_settings`
  * `audio_ref`
  * `background_ref`
  * `timing_grid`
  * `objects`
  * `validation_report`

* `ReplayPlan`

  * `profile`
  * `seed`
  * `frames[{dt_ms,x,y,keys}]`
  * `expected_score_stats`
  * `source_map`

### 8.3 Agent tool boundary

Expose a structured tool layer for agents:

* `analyze_audio(path)`
* `build_style_profile(ref_maps)`
* `draft_skeleton(audio_analysis, style_target)`
* `arrange_objects(beatmap_ir, style_profile)`
* `score_map(path, mods, acc)`
* `classify_map(path)`
* `verify_map(folder)`
* `compile_map(beatmap_ir)`
* `synthesize_replay(map_path, profile)`
* `plan_live_play(map_path_or_tosu_context, profile)`

An agent must never directly emit final `.osu` text. It may only request IR creation or IR patch operations that then pass through validation and compilation.

## 9. Work packages

## WP1 — Core file tooling and IR compiler

**Required tasks**

* Wrap `slider` for `.osu`/`.osz` read support.
* Wrap `osrparse` for `.osr` write support.
* Build the internal IR models.
* Implement `.osu` compiler from IR.
* Implement `.osz` packager.
* Implement normalization utilities for round-trip tests.
* Implement slider timing and inherited timing logic according to the documented `.osu` rules. ([osu!][1])

**Definition of done**

* Codex can parse existing `.osu` files into IR.
* Codex can compile IR back into `.osu`.
* Generated `.osu` re-parses successfully.
* `.osz` packages open in osu!stable.

## WP2 — ReplaySynth (`.osu` -> `.osr`)

**Required tasks**

* Parse hit objects and timing sections from `.osu`.
* Create a cursor planner for circles, sliders, and spinners.
* Implement replay profiles:

  * `auto_perfect`
  * `autopilot_only`
  * `humanized_aim`
* Use official Auto and Autopilot behavior as reference baselines where applicable:

  * Autopilot = move cursor to the exact centre of the next object.
  * Auto spinner baseline = 477 SPM. ([osu!][28])
* Write `.osr` frames using the documented replay format.
* Add replay validators and replay inspection CLI commands.

**Definition of done**

* A generated `.osr` is readable by `osrparse`.
* Fixed-seed generation is deterministic.
* The replay can be imported into local osu!stable and watched offline.

## WP3 — LivePlay (real-time local autoplay/autopilot)

**Required tasks**

* Build a provider abstraction:

  * `tosu` provider
  * direct-file/manual provider
* Implement active window detection and client rectangle capture.
* Implement osu! playfield coordinate mapping from the 512x384 logical playfield to client-space.
* Implement high-resolution event scheduler.
* Implement mouse/keyboard injection via `SendInput`.
* Add privilege checks and warning messages for UIPI-related failures.
* Add dry-run and log-only modes.
* Add arm/disarm hotkeys and emergency stop.

**Definition of done**

* The system can produce a live event plan from the current beatmap context.
* Dry-run shows expected cursor/key schedules without sending inputs.
* Real input injection works locally when integrity levels are compatible. ([Microsoft Learn][29])

## WP4 — Audio analysis

**Required tasks**

* Normalize audio to WAV for timing-critical analysis.
* Implement MIR pipeline:

  * BPM
  * beats
  * downbeats
  * segment boundaries
  * segment labels
  * onset strength
  * RMS / spectral band summaries
  * optional stem-level energy summaries
* Primary backend: `allin1`.
* Fallback/ensemble sources: `librosa`, `madmom`, Essentia.
* Export all audio analysis results as JSON.

**Definition of done**

* Codex can analyze a song file and produce a structured timing/segment report.
* WAV normalization is automatic unless disabled by config.
* Outputs are reusable by both rule-based generation and AI adapters.

## WP5 — Rule-based MapForge

**Required tasks**

* Build timing grid from audio analysis.
* Build section density plan from segment labels.
* Implement object arrangement logic for these prompt families:

  * `flow aim`
  * `jump`
  * `farm jump`
  * `stream`
  * `deathstream`
  * `mixed/control`
* Implement pattern generators:

  * arcs
  * simple jumps
  * triangles
  * wiggles
  * bursts
  * streams
  * slider connectors
  * spinner placement
* Implement hitsound assignment.
* Implement star/pp optimization loop using `rosu-pp-py`.
* Compile results to `.osu` / `.osz`.
* Verify all output with the validation stack before finalizing.

**Definition of done**

* Codex can generate a playable `.osu` from audio plus prompt plus target difficulty settings.
* Output passes parser validation and external validation.

## WP6 — Style engine

**Required tasks**

* Scan local reference maps from user-specified folders.
* Extract style features:

  * spacing
  * angles
  * slider ratio
  * section density
  * burst/stream ratios
  * jump/stream/tech classifier signals
* Build prompt parser mapping natural language to canonical style tags and numeric targets.
* Support style transfer from user-supplied reference maps.
* Implement style optimizer that adjusts pattern-bank weights and section density toward the requested profile.
* Output a human-readable style report for each generated map.

**Definition of done**

* A prompt or reference-map set measurably changes generation behavior.
* Style reports show why the map is considered jump-heavy, stream-heavy, or flow-oriented.

## WP7 — AI adapters

**Required tasks**

* Build optional adapters for:

  * `Mapperatorinator`
  * `osuT5`
  * `osu-diffusion`
  * `osu-dreamer`
* Normalize all AI outputs into `BeatmapIR`.
* Allow rule-based post-processing after AI draft generation.
* Implement graceful fallback when a backend is not installed.
* Support agent/tool usage without forcing network calls or cloud dependency.

**Definition of done**

* Each adapter can either produce a draft or return a clear actionable error.
* AI-generated drafts still pass through the same validation and optimization pipeline as rule-based drafts.

## WP8 — Evaluation, docs, and tooling

**Required tasks**

* Build automated unit/integration tests.
* Build benchmark harnesses for:

  * beat tracking
  * replay synthesis
  * map validity
  * style controllability
  * difficulty/pp targeting
* Add JSON log output for every CLI command.
* Add reproducible seeds.
* Write setup docs, architecture docs, and offline smoke-test docs.
* Add configuration examples for stable path discovery and `tosu` integration.

**Definition of done**

* A new contributor can clone the repo, install dependencies, and run the core CLI workflows from the README.

## 10. Deliverables

Codex must deliver all of the following:

* A working Python package.
* A CLI with at least these commands:

  * `osu-lab audio analyze`
  * `osu-lab replay synth`
  * `osu-lab replay inspect`
  * `osu-lab live plan`
  * `osu-lab live arm`
  * `osu-lab map generate`
  * `osu-lab map verify`
  * `osu-lab map score`
  * `osu-lab style build-index`
  * `osu-lab style profile`
  * `osu-lab ai draft`
* JSON schemas or dataclass docs for the main IR types.
* Test suite.
* Benchmark harness.
* Example configuration files.
* README quickstart.
* Architecture document.
* Manual smoke-test checklist for osu!stable offline runs.

## 11. Success metrics

## 11.1 Automated acceptance

* **Core formats**

  * At least 50 fixture `.osu` files parse into IR and compile back without crashes.
  * Object counts, timing-point counts, and key metadata fields remain stable under normalized round-trip.

* **ReplaySynth**

  * Generated `.osr` files are parseable by `osrparse`.
  * Replay generation is deterministic under fixed seeds.
  * Replay inspection reports valid frame streams and expected metadata.

* **Audio analysis**

  * Median BPM absolute error on the benchmark set is `< 1 BPM`.
  * Median beat timing error after WAV normalization is `< 35 ms`.

* **Map validity**

  * Generated maps satisfy the official timing/snap constraints from section 3.
  * `MapsetVerifier` reports no critical issues on benchmark outputs. ([osu!][3])

* **Difficulty / pp targeting**

  * Target star rating is reached within `±0.25★` on at least 80% of benchmark outputs.
  * Target pp is reached within `±15%` on at least 80% of benchmark outputs.

* **Style controllability**

  * For `jump`, `stream`, and `tech-like` prompts, the requested class must become the dominant class signal according to the analyzer or internal style metrics.
  * Reference-style generations must reduce fingerprint distance to the reference profile by at least 20% versus a neutral baseline.

* **AI adapters**

  * Each configured AI backend produces a normalized draft or a clear actionable failure report.

## 11.2 Manual offline smoke tests

* **ReplaySynth**

  * Import and watch generated `.osr` files in local osu!stable on at least 15 fixture maps.

* **LivePlay**

  * Offline autopilot/autoplay smoke test on:

    * tutorial
    * 5 easy maps
    * 10 medium maps
  * The objective is stable offline playback, not ranked viability.

## 12. Coding rules for Codex

* Do **not** reimplement binary file formats from scratch unless a required dependency is blocked.
* Do **not** let the LLM/agent write raw `.osu` text directly.
* Do **not** start with live automation. Build order must be:

  1. core formats
  2. replay synthesis
  3. live input
  4. audio analysis
  5. rule-based mapping
  6. style engine
  7. AI adapters
  8. benchmarking/docs
* Do **not** implement any online score submission or ban-evasion behavior.
* Do **not** use beatmap editor UI automation for map creation.
* Keep every stage config-driven and seedable.
* Every CLI command must support machine-readable JSON output.
* Review third-party licenses before vendoring code.
* Never commit third-party beatmaps/audio unless they are synthetic, tiny, or explicitly permitted for redistribution.
* Named style prompts must resolve into reference profiles or canonical tags, not hardcoded person-specific logic.

## 13. Suggested implementation order

1. Build IR + `.osu` compile/parse + `.osz` pack.
2. Build `.osr` synthesis and replay inspection tools.
3. Add live planner, then `SendInput` backend, then `tosu` integration.
4. Add WAV normalization and MIR pipeline.
5. Add rule-based object generation and difficulty/pp optimizer.
6. Add style profiling and reference-map transfer.
7. Add optional AI adapters.
8. Add benchmark harness, docs, and smoke-test guides.

## 14. Short rationale for the chosen roadmap

This roadmap is deliberate. Replay-first is the fastest stable entry point because osu! already treats replay import/export as a first-class local workflow, and Auto/Autopilot behavior gives usable baselines for cursor planning. Beatmap generation should be file-first because `.osu` is documented and programmatically writable, while official ranking criteria explicitly forbid generative tooling for ranked maps anyway. Validation must center on official timing/snap constraints and Mapset Verifier, and audio analysis should start with WAV-normalized MIR because MP3 decoder offsets are large enough to corrupt timing-sensitive generation. ([osu!][2])

A good next artifact is a **repo-bootstrap prompt for Codex** with the exact file tree, first 10 commits, and starter interfaces.

[1]: https://osu.ppy.sh/wiki/en/Client/File_formats/osu_%28file_format%29 "https://osu.ppy.sh/wiki/en/Client/File_formats/osu_%28file_format%29"
[2]: https://osu.ppy.sh/wiki/en/Gameplay/Replay "https://osu.ppy.sh/wiki/en/Gameplay/Replay"
[3]: https://osu.ppy.sh/wiki/en/Ranking_criteria "https://osu.ppy.sh/wiki/en/Ranking_criteria"
[4]: https://github.com/tosuapp/tosu/blob/master/README.md "https://github.com/tosuapp/tosu/blob/master/README.md"
[5]: https://github.com/mir-aidj/all-in-one "https://github.com/mir-aidj/all-in-one"
[6]: https://github.com/ppy/osu/wiki/Legacy-database-file-structure "https://github.com/ppy/osu/wiki/Legacy-database-file-structure"
[7]: https://github.com/llllllllll/slider "https://github.com/llllllllll/slider"
[8]: https://github.com/kszlim/osu-replay-parser "https://github.com/kszlim/osu-replay-parser"
[9]: https://github.com/MaxOhn/rosu-pp-py "https://github.com/MaxOhn/rosu-pp-py"
[10]: https://github.com/Naxesss/MapsetVerifier "https://github.com/Naxesss/MapsetVerifier"
[11]: https://librosa.org/doc/main/generated/librosa.beat.beat_track.html "https://librosa.org/doc/main/generated/librosa.beat.beat_track.html"
[12]: https://github.com/CPJKU/madmom/blob/master/madmom/features/beats.py "https://github.com/CPJKU/madmom/blob/master/madmom/features/beats.py"
[13]: https://essentia.upf.edu/reference/streaming_RhythmExtractor2013.html "https://essentia.upf.edu/reference/streaming_RhythmExtractor2013.html"
[14]: https://github.com/MaxOhn/rosu-map "https://github.com/MaxOhn/rosu-map"
[15]: https://github.com/Glubus/rosu-replay "https://github.com/Glubus/rosu-replay"
[16]: https://github.com/MaxOhn/rosu-pp "https://github.com/MaxOhn/rosu-pp"
[17]: https://github.com/yorunoken/osu-map-analyzer-lib "https://github.com/yorunoken/osu-map-analyzer-lib"
[18]: https://github.com/mappingtools/Mapperator "https://github.com/mappingtools/Mapperator"
[19]: https://github.com/OliBomby/Mapping_Tools "https://github.com/OliBomby/Mapping_Tools"
[20]: https://github.com/mrflashstudio/OsuParsers "https://github.com/mrflashstudio/OsuParsers"
[21]: https://github.com/OliBomby/Mapperatorinator "https://github.com/OliBomby/Mapperatorinator"
[22]: https://github.com/gyataro/osuT5 "https://github.com/gyataro/osuT5"
[23]: https://github.com/OliBomby/osu-diffusion "https://github.com/OliBomby/osu-diffusion"
[24]: https://github.com/jaswon/osu-dreamer "https://github.com/jaswon/osu-dreamer"
[25]: https://github.com/Wakype/osu-pilot "https://github.com/Wakype/osu-pilot"
[26]: https://github.com/CookieHoodie/OsuBot "https://github.com/CookieHoodie/OsuBot"
[27]: https://github.com/RayhaanA/OsuAutoPlay "https://github.com/RayhaanA/OsuAutoPlay"
[28]: https://osu.ppy.sh/wiki/en/Gameplay/Game_modifier/Autopilot "https://osu.ppy.sh/wiki/en/Gameplay/Game_modifier/Autopilot"
[29]: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput "https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput"
