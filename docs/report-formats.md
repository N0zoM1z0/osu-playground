# Report Formats

## Core Run Manifest

`run_manifest.json` contains:

- input audio path
- prompt
- resolved refs
- merged policy pack
- parsed constraints
- timing draft
- note-selection trace
- phrase plan
- candidate ranking table
- best candidate
- promoted final artifacts

## Note Selection

Each selected or rejected event records:

- `time_ms`
- `role`
- `confidence`
- `selected`
- `source`
- `section_label`
- `phrase_index`
- `reason`
- `features`

## Candidate Report

Each candidate records:

- quality report
- legality errors
- style fit
- reference fit
- star fit
- pp fit
- provenance counts
- continuity diagnostics
- final ranking score
