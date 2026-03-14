# Pipeline Refactor Note

## Old Ownership

Previously the repository center of gravity was:

- parser / compiler
- arrangement heuristics
- style biasing
- replay / live side modules

## New Ownership

The dominant path is now:

1. audio analysis
2. timing authoring
3. note selection
4. style policy resolution
5. phrase planning
6. candidate search
7. quality-based ranking
8. final promotion

## Compatibility Matrix

Still supported:

- `map generate`
- `map verify`
- `map score`
- `style build-index`
- `style profile`
- `ai draft`
- `bench`
- `replay synth`
- `replay inspect`
- `live plan`
- `live arm`

New primary path:

- `map auto`
- `map quality`
- `bench --auto-workflow`

The older `map generate` path remains as a lightweight baseline and regression target. The new `map auto` path layers explicit selection, timing, policy, quality, and candidate ranking on top of the existing file-first generator.
