"""Validate the JSON contract shared by scene generation and ManimGL."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, NoReturn

SCHEMA: int = 1
_REGENERATE = "Re-run `python survey.py <name> solve` to regenerate it."


def _invalid(source: str, field: str, reason: str) -> NoReturn:
    raise ValueError(f"{source}: scene field {field} {reason}. {_REGENERATE}")


def _required(
    value: dict[str, Any], key: str, field: str, source: str
) -> Any:
    if key not in value:
        _invalid(source, field, "is required")
    return value[key]


def _object(value: Any, field: str, source: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _invalid(source, field, "must be an object")
    return value


def _number(value: Any, field: str, source: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _invalid(source, field, "must be a finite number")
    try:
        finite = math.isfinite(float(value))
    except OverflowError:
        finite = False
    if not finite:
        _invalid(source, field, "must be a finite number")


def _vector(value: Any, field: str, source: str) -> None:
    if not isinstance(value, list) or len(value) != 2:
        _invalid(source, field, "must be a two-number array")
    for index, component in enumerate(value):
        _number(component, f"{field}[{index}]", source)


def validate_scene(data: Any, *, source: str = "scene data") -> dict[str, Any]:
    """Return a schema-1 scene object after validating every consumed field."""
    scene = _object(data, "<root>", source)
    found = scene.get("schema")
    if type(found) is not int or found != SCHEMA:
        raise ValueError(
            f"{source} has scene schema {found!r}, expected {SCHEMA}. {_REGENERATE}"
        )

    survey = _required(scene, "survey", "survey", source)
    if not isinstance(survey, str):
        _invalid(source, "survey", "must be a string")

    origin = _object(
        _required(scene, "origin", "origin", source), "origin", source
    )
    for key in ("lat", "lon", "alt_m"):
        _number(
            _required(origin, key, f"origin.{key}", source),
            f"origin.{key}",
            source,
        )

    points = _required(scene, "points", "points", source)
    if not isinstance(points, list):
        _invalid(source, "points", "must be an array")
    if not points:
        _invalid(source, "points", "must contain at least one point")
    for index, raw_point in enumerate(points):
        prefix = f"points[{index}]"
        point = _object(raw_point, prefix, source)
        label = _required(point, "label", f"{prefix}.label", source)
        if not isinstance(label, str):
            _invalid(source, f"{prefix}.label", "must be a string")
        for key in ("e", "n", "dist_m", "elev_deg"):
            _number(
                _required(point, key, f"{prefix}.{key}", source),
                f"{prefix}.{key}",
                source,
            )

    _vector(
        _required(scene, "gnb_en", "gnb_en", source), "gnb_en", source
    )
    seed = _required(scene, "srls_seed_en", "srls_seed_en", source)
    if seed is not None:
        _vector(seed, "srls_seed_en", source)

    ellipse = _object(
        _required(scene, "ellipse", "ellipse", source), "ellipse", source
    )
    for key in ("major_m", "minor_m"):
        _number(
            _required(ellipse, key, f"ellipse.{key}", source),
            f"ellipse.{key}",
            source,
        )
    azimuth = _required(
        ellipse, "azimuth_deg", "ellipse.azimuth_deg", source
    )
    if azimuth is not None:
        _number(azimuth, "ellipse.azimuth_deg", source)

    result_lines = _required(scene, "result_lines", "result_lines", source)
    if not isinstance(result_lines, list):
        _invalid(source, "result_lines", "must be an array of strings")
    for index, line in enumerate(result_lines):
        if not isinstance(line, str):
            _invalid(source, f"result_lines[{index}]", "must be a string")

    return scene


def load_scene(path: Path) -> dict[str, Any]:
    """Read and validate one scene JSON file."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path}: invalid scene JSON: {exc.msg}. {_REGENERATE}"
        ) from exc
    return validate_scene(data, source=str(path))
