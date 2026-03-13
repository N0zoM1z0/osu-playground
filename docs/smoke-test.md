# Offline Smoke Test Checklist

## Environment

- Windows machine
- `osu!stable` installed locally
- `osu-lab` virtual environment installed
- optional: `ffmpeg`, `allin1`, `tosu`

## ReplaySynth

1. Generate a replay:

   ```bash
   osu-lab replay synth C:\\path\\to\\map.osu --profile auto_perfect --out C:\\temp\\sample.osr
   ```

2. Import the replay into osu!stable.

3. Confirm:

- the replay imports without corruption
- playback starts and cursor movement tracks hit objects
- deterministic seeds reproduce identical `.osr` payloads

## LivePlan

1. Generate a dry-run plan:

   ```bash
   osu-lab live plan C:\\path\\to\\map.osu > C:\\temp\\live-plan.json
   ```

   Or fetch from a running `tosu` instance:

   ```bash
   osu-lab live plan --provider tosu --tosu-base-url http://127.0.0.1:24050 > C:\\temp\\live-plan.json
   ```

2. Arm in dry-run mode:

   ```bash
   osu-lab live arm C:\\path\\to\\map.osu
   ```

3. Confirm:

- event timings are plausible
- mapped coordinates stay inside the osu! client rect
- no input is injected unless `--inject` is explicitly requested in a Windows runtime
- if `tosu` is used, the current beatmap file is fetched successfully

## Audio Analysis

1. Analyze a local song:

   ```bash
   osu-lab audio analyze C:\\path\\to\\song.wav --out C:\\temp\\song.analysis.json
   ```

2. Confirm:

- BPM is plausible
- beat markers align within expected tolerance
- segment labels and onset envelope are emitted

## Rule-Based Mapping

1. Generate a local map:

   ```bash
   osu-lab map generate C:\\path\\to\\song.wav --out-dir C:\\temp\\map --prompt "flow aim,jump"
   ```

2. Confirm:

- `.osu`, `.osz`, and IR JSON are produced
- `osu-lab map verify` reports no critical object-gap or bounds errors
- optional external verifier output is captured when `MapsetVerifier` is configured
- generated package opens as an unranked local experiment in osu!stable

## AI Draft

1. Run a non-interactive AI draft:

   ```bash
   osu-lab ai draft claude C:\\path\\to\\song.wav --prompt "jump,flow aim" --target-star 5.0
   ```

2. Confirm:

- the AI backend returns a structured recipe, not raw `.osu` text
- the generated map package is still produced by the local compiler
- failures are explicit if the backend CLI is missing or unauthenticated

## Style

1. Build a local index over a folder of reference maps.
2. Inspect the profile output.
3. Confirm that jump-heavy, stream-heavy, and flow-heavy folders produce meaningfully different histograms and class scores.
