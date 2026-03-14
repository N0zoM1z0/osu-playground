# Benchmarking Guide

## Benchmark Families

The repository now has benchmark coverage for:

- audio BPM and beat timing via `--audio-manifest`
- style controllability
- acceptance aggregation
- auto-workflow ranking stability

## Audio Benchmark Manifest

```json
{
  "cases": [
    {
      "audio_path": "/path/to/song.wav",
      "expected_bpm": 120.0,
      "expected_beats_ms": [500, 1000, 1500, 2000]
    }
  ]
}
```

Run:

```bash
osu-lab bench --audio-manifest /path/to/audio-benchmark.json
```

## Auto Workflow Stability

Run:

```bash
osu-lab bench \
  --auto-workflow \
  --audio /path/to/song.wav \
  --prompt "flow aim" \
  --reference-map /path/to/reference_dir \
  --out-dir /tmp/osu-lab-bench
```

This repeats `map auto` with the same seed and checks whether ranking scores remain stable.

## Acceptance Harness

Run:

```bash
osu-lab bench fixtures_dir \
  --acceptance \
  --audio /path/to/song.wav \
  --audio-manifest /path/to/audio-benchmark.json \
  --out-dir /tmp/osu-lab-acceptance \
  --prompt jump \
  --prompt "flow aim"
```
