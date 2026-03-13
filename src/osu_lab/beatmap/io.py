from __future__ import annotations

import json
import zipfile
from pathlib import Path

from osu_lab.core.models import BeatmapIR, HitObjectIR, TimingGrid, TimingPoint, ValidationIssue
from osu_lab.core.utils import json_dump


def _coerce_value(raw: str) -> object:
    text = raw.strip()
    if text == "":
        return ""
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def _parse_key_value_section(lines: list[str]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = _coerce_value(value)
    return parsed


def _parse_sections(text: str) -> tuple[str, dict[str, list[str]]]:
    version_line = "osu file format v14"
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        if line.startswith("osu file format"):
            version_line = line
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line.strip("[]")
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return version_line, sections


def _timing_at(points: list[TimingPoint], start_ms: int) -> TimingPoint | None:
    selected = None
    for point in points:
        if point.offset_ms <= start_ms:
            selected = point
        else:
            break
    return selected


def slider_duration_ms(start_ms: int, length: float, repeats: int, timing_grid: TimingGrid, difficulty_settings: dict[str, object]) -> float:
    slider_multiplier = float(difficulty_settings.get("SliderMultiplier", 1.4))
    uninherited = _timing_at(timing_grid.uninherited_points, start_ms)
    inherited = _timing_at(timing_grid.inherited_points, start_ms)
    beat_length = uninherited.beat_length_ms if uninherited else 500.0
    velocity = 1.0
    if inherited and inherited.beat_length_ms < 0:
        velocity = -100.0 / inherited.beat_length_ms
    return (length / (slider_multiplier * 100.0 * velocity)) * beat_length * repeats


def parse_osu(path: str | Path) -> BeatmapIR:
    source = Path(path)
    version_line, sections = _parse_sections(source.read_text(encoding="utf-8"))
    general = _parse_key_value_section(sections.get("General", []))
    metadata = _parse_key_value_section(sections.get("Metadata", []))
    difficulty = _parse_key_value_section(sections.get("Difficulty", []))
    editor = _parse_key_value_section(sections.get("Editor", []))
    colours = _parse_key_value_section(sections.get("Colours", []))
    events = [line for line in sections.get("Events", []) if line and not line.startswith("//")]

    background = ""
    for event_line in events:
        if event_line.startswith("0,0,") or event_line.startswith("Video,"):
            chunks = [chunk.strip().strip('"') for chunk in event_line.split(",")]
            if len(chunks) >= 3:
                background = chunks[2]
                break

    uninherited_points: list[TimingPoint] = []
    inherited_points: list[TimingPoint] = []
    meter_sections: list[dict[str, int]] = []
    kiai_ranges: list[dict[str, int]] = []
    for raw in sections.get("TimingPoints", []):
        if not raw or raw.startswith("//"):
            continue
        parts = raw.split(",")
        if len(parts) < 8:
            continue
        point = TimingPoint(
            offset_ms=float(parts[0]),
            beat_length_ms=float(parts[1]),
            meter=int(parts[2]),
            sample_set=int(parts[3]),
            sample_index=int(parts[4]),
            volume=int(parts[5]),
            uninherited=parts[6] == "1",
            effects=int(parts[7]),
        )
        if point.uninherited:
            uninherited_points.append(point)
            meter_sections.append({"start_ms": int(point.offset_ms), "meter": point.meter})
        else:
            inherited_points.append(point)
        if point.effects & 1:
            kiai_ranges.append({"start_ms": int(point.offset_ms)})

    timing_grid = TimingGrid(
        uninherited_points=sorted(uninherited_points, key=lambda item: item.offset_ms),
        inherited_points=sorted(inherited_points, key=lambda item: item.offset_ms),
        meter_sections=meter_sections,
        kiai_ranges=kiai_ranges,
        offset_ms=float(uninherited_points[0].offset_ms if uninherited_points else 0.0),
    )

    objects: list[HitObjectIR] = []
    for raw in sections.get("HitObjects", []):
        if not raw or raw.startswith("//"):
            continue
        parts = raw.split(",")
        if len(parts) < 5:
            continue
        x = int(parts[0])
        y = int(parts[1])
        start_ms = int(parts[2])
        type_mask = int(parts[3])
        hitsounds = int(parts[4])
        combo_flags = type_mask & 0b11110000
        if type_mask & 8:
            end_ms = int(parts[5]) if len(parts) > 5 else start_ms
            objects.append(
                HitObjectIR(
                    type="spinner",
                    start_ms=start_ms,
                    end_ms=end_ms,
                    x=x,
                    y=y,
                    hitsounds=hitsounds,
                    combo_flags=combo_flags,
                    semantic_role="spinner",
                )
            )
            continue
        if type_mask & 2:
            curve_spec = parts[5] if len(parts) > 5 else "B"
            nodes = []
            for node in curve_spec.split("|")[1:]:
                if ":" not in node:
                    continue
                nx, ny = node.split(":", 1)
                nodes.append((int(nx), int(ny)))
            repeats = int(parts[6]) if len(parts) > 6 else 1
            length = float(parts[7]) if len(parts) > 7 else 0.0
            duration = slider_duration_ms(start_ms, length, repeats, timing_grid, difficulty)
            objects.append(
                HitObjectIR(
                    type="slider",
                    start_ms=start_ms,
                    end_ms=int(round(start_ms + duration)),
                    x=x,
                    y=y,
                    curve=nodes,
                    repeats=repeats,
                    length=length,
                    hitsounds=hitsounds,
                    combo_flags=combo_flags,
                    semantic_role="slider",
                )
            )
            continue
        objects.append(
            HitObjectIR(
                type="circle",
                start_ms=start_ms,
                end_ms=start_ms,
                x=x,
                y=y,
                hitsounds=hitsounds,
                combo_flags=combo_flags,
                semantic_role="circle",
            )
        )

    beatmap = BeatmapIR(
        metadata=metadata,
        difficulty_settings=difficulty,
        audio_ref=str(general.get("AudioFilename", metadata.get("AudioFilename", ""))),
        background_ref=background,
        timing_grid=timing_grid,
        objects=objects,
        general_settings=general,
        editor_settings=editor,
        events=events,
        colours={str(key): str(value) for key, value in colours.items()},
        raw_sections=sections,
        source_path=str(source),
    )
    beatmap.general_settings["FormatVersion"] = version_line
    return beatmap


def compile_osu(beatmap: BeatmapIR) -> str:
    general = {
        "AudioFilename": beatmap.audio_ref or beatmap.metadata.get("AudioFilename", ""),
        "AudioLeadIn": 0,
        "PreviewTime": -1,
        "Countdown": 0,
        "SampleSet": "Soft",
        "StackLeniency": 0.7,
        "Mode": 0,
        "LetterboxInBreaks": 0,
        "WidescreenStoryboard": 1,
    }
    general.update(beatmap.general_settings)
    general.pop("FormatVersion", None)

    metadata = dict(beatmap.metadata)
    difficulty = {
        "HPDrainRate": 5,
        "CircleSize": 4,
        "OverallDifficulty": 7,
        "ApproachRate": 8,
        "SliderMultiplier": 1.4,
        "SliderTickRate": 1,
    }
    difficulty.update(beatmap.difficulty_settings)

    lines = [beatmap.general_settings.get("FormatVersion", "osu file format v14"), ""]
    lines.append("[General]")
    for key, value in general.items():
        lines.append(f"{key}: {value}")
    lines.append("")
    lines.append("[Editor]")
    for key, value in beatmap.editor_settings.items():
        lines.append(f"{key}: {value}")
    lines.append("")
    lines.append("[Metadata]")
    for key, value in metadata.items():
        lines.append(f"{key}: {value}")
    lines.append("")
    lines.append("[Difficulty]")
    for key, value in difficulty.items():
        lines.append(f"{key}: {value}")
    lines.append("")
    lines.append("[Events]")
    if beatmap.background_ref:
        lines.append(f'0,0,"{beatmap.background_ref}",0,0')
    lines.extend(beatmap.events)
    lines.append("")
    lines.append("[TimingPoints]")
    for point in beatmap.timing_grid.uninherited_points + beatmap.timing_grid.inherited_points:
        uninherited = 1 if point.uninherited else 0
        lines.append(
            ",".join(
                [
                    _floatish(point.offset_ms),
                    _floatish(point.beat_length_ms),
                    str(point.meter),
                    str(point.sample_set),
                    str(point.sample_index),
                    str(point.volume),
                    str(uninherited),
                    str(point.effects),
                ]
            )
        )
    lines.append("")
    lines.append("[Colours]")
    for key, value in beatmap.colours.items():
        lines.append(f"{key} : {value}")
    lines.append("")
    lines.append("[HitObjects]")
    for item in beatmap.objects:
        if item.type == "spinner":
            lines.append(f"{item.x},{item.y},{item.start_ms},12,{item.hitsounds},{item.end_ms},0:0:0:0:")
            continue
        if item.type == "slider":
            nodes = "|".join(f"{x}:{y}" for x, y in item.curve) if item.curve else f"{item.x}:{item.y}"
            curve = f"B|{nodes}"
            type_mask = 2 | item.combo_flags
            lines.append(
                f"{item.x},{item.y},{item.start_ms},{type_mask},{item.hitsounds},{curve},{item.repeats},{_floatish(item.length)},0:0|0:0,0:0:0:0:"
            )
            continue
        type_mask = 1 | item.combo_flags
        lines.append(f"{item.x},{item.y},{item.start_ms},{type_mask},{item.hitsounds},0:0:0:0:")
    return "\n".join(lines).rstrip() + "\n"


def _floatish(value: float) -> str:
    text = f"{value:.15f}".rstrip("0").rstrip(".")
    return text if text else "0"


def write_osu(beatmap: BeatmapIR, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(compile_osu(beatmap), encoding="utf-8")
    return target


def write_ir_json(beatmap: BeatmapIR, path: str | Path) -> Path:
    target = Path(path)
    json_dump(beatmap, target)
    return target


def load_ir_json(path: str | Path) -> BeatmapIR:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    timing_grid_raw = payload["timing_grid"]
    timing_grid = TimingGrid(
        uninherited_points=[TimingPoint(**point) for point in timing_grid_raw.get("uninherited_points", [])],
        inherited_points=[TimingPoint(**point) for point in timing_grid_raw.get("inherited_points", [])],
        meter_sections=timing_grid_raw.get("meter_sections", []),
        kiai_ranges=timing_grid_raw.get("kiai_ranges", []),
        snap_divisors=timing_grid_raw.get("snap_divisors", [1, 2, 4, 8]),
        offset_ms=timing_grid_raw.get("offset_ms", 0.0),
    )
    return BeatmapIR(
        metadata=payload["metadata"],
        difficulty_settings=payload["difficulty_settings"],
        audio_ref=payload.get("audio_ref", ""),
        background_ref=payload.get("background_ref", ""),
        timing_grid=timing_grid,
        objects=[HitObjectIR(**item) for item in payload.get("objects", [])],
        validation_report=[ValidationIssue(**item) for item in payload.get("validation_report", [])],
        general_settings=payload.get("general_settings", {}),
        editor_settings=payload.get("editor_settings", {}),
        events=payload.get("events", []),
        colours=payload.get("colours", {}),
        raw_sections=payload.get("raw_sections", {}),
        source_path=payload.get("source_path", ""),
    )


def package_osz(beatmap_path: str | Path, output_path: str | Path, asset_paths: list[str | Path] | None = None) -> Path:
    beatmap_path = Path(beatmap_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    asset_paths = [Path(path) for path in asset_paths or []]
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(beatmap_path, arcname=beatmap_path.name)
        for asset in asset_paths:
            if asset.exists():
                archive.write(asset, arcname=asset.name)
    return output_path
