# Auto-Mapping Workflow

## Goal

`osu-lab map auto` is now the primary end-to-end workflow.

Input:

- audio file (`.mp3` or `.wav`)
- prompt
- optional reference maps or directories

Output:

- analysis report
- timing draft
- note-selection report
- phrase plan
- multiple ranked candidates
- promoted final `.osu`
- promoted final `.osz`
- machine-readable run manifest
- markdown summary

## Pipeline

1. Normalize and analyze audio.
2. Resolve prompt into canonical tags, policy pack, and constraints.
3. Build a timing draft.
4. Run explicit note selection with selected and rejected events.
5. Build a phrase plan from selected events and section labels.
6. Generate multiple candidates with varied seeds and density realizations.
7. Score candidates by legality, quality, style fit, reference fit, stars, and pp.
8. Promote the best candidate to `final.osu` / `final.osz`.

## CLI

```bash
osu-lab map auto \
  --audio path/to/song.mp3 \
  --prompt "flow aim with chorus jump lift" \
  --refs path/to/reference_dir \
  --target-stars 6.3 \
  --target-pp 280 \
  --candidate-count 4 \
  --out out_dir
```

## Artifact Layout

```text
out_dir/
  analysis.json
  timing_draft.json
  note_selection.json
  phrase_plan.json
  run_manifest.json
  summary.md
  final.osu
  final.osz
  final.ir.json
  candidates/
    candidate_01/
    candidate_02/
    ...
```
