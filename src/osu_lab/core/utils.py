from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from typing import Any, Iterable


def dataclass_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: dataclass_to_dict(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): dataclass_to_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [dataclass_to_dict(item) for item in value]
    return value


def json_dump(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataclass_to_dict(data), indent=2, sort_keys=True), encoding="utf-8")


def json_print(data: Any) -> None:
    print(json.dumps(dataclass_to_dict(data), indent=2, sort_keys=True))


def md5_bytes(payload: bytes) -> str:
    return hashlib.md5(payload).hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def mean(values: Iterable[float], default: float = 0.0) -> float:
    materialized = list(values)
    if not materialized:
        return default
    return sum(materialized) / len(materialized)

