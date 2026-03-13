# IR Schema

The canonical schema bundle is available through:

```bash
osu-lab schema dump
```

Primary IR types:

## AudioAnalysis

- `path`
- `duration_ms`
- `bpm`
- `bpm_candidates`
- `beats_ms`
- `downbeats_ms`
- `segments`
- `onset_envelope`
- `band_energy_summary`
- `optional_stem_energy`
- `backend`

## TimingGrid

- `uninherited_points`
- `inherited_points`
- `meter_sections`
- `kiai_ranges`
- `snap_divisors`
- `offset_ms`

## StyleTarget

- `prompt_tags`
- `target_star`
- `target_pp`
- `mods_profile`
- `difficulty_bias`
- `reference_maps`
- `section_density_plan`

## StyleProfile

- `spacing_histogram`
- `angle_histogram`
- `slider_ratio`
- `burst_profile`
- `jump_stream_tech_scores`
- `section_density_curve`
- `source_maps`

## HitObjectIR

- `type`
- `start_ms`
- `end_ms`
- `x`
- `y`
- `curve`
- `repeats`
- `length`
- `hitsounds`
- `combo_flags`
- `semantic_role`

## BeatmapIR

- `metadata`
- `difficulty_settings`
- `audio_ref`
- `background_ref`
- `timing_grid`
- `objects`
- `validation_report`
- `general_settings`
- `editor_settings`
- `events`
- `colours`
- `raw_sections`
- `source_path`

## ReplayPlan

- `profile`
- `seed`
- `frames`
- `expected_score_stats`
- `source_map`

## Notes

- JSON serialization is deterministic and path-safe.
- `BeatmapIR` is the required edit surface for agents.
- Final `.osu` text should be produced only by the compiler.
