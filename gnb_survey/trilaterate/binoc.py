"""Read the handheld-binocular workbook: one distance/angle sighting per point.

The binoculars are a separate instrument from the GNSS pole. They record the
slant distance and elevation angle to the gNB, and -- critically -- the height
the observer held them at, which differs from the 2.066 m pole and differs
between points. Positions come from the MapPro export; only the sighting comes
from here.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import openpyxl

from .errors import SurveyDataError
from .models import BinocReading

# Header text varies ("viewfiner" is a real typo in the sheet), so columns are
# matched on a keyword rather than an exact string.
_DISTANCE_KEY = "distance"
_ANGLE_KEY = "angle"
_HEIGHT_KEY = "height"
_NAME_KEY = "point name"

_MAX_ANGLE_DEG = 90.0
_MAX_INSTRUMENT_HEIGHT_M = 3.0


def _column_index(headers: list[str], keyword: str, path: Path) -> int:
    matches = [i for i, h in enumerate(headers) if keyword in h]
    if not matches:
        raise SurveyDataError(
            f"{path.name}: no column mentioning '{keyword}'. Found: "
            f"{', '.join(h or '<blank>' for h in headers)}"
        )
    return matches[0]


def _number(value: object, field: str, point: str, path: Path) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise SurveyDataError(
            f"{path.name}: {point} has a non-numeric {field}: {value!r}"
        ) from None


def read_binoc_readings(xlsx_path: str | Path) -> tuple[BinocReading, ...]:
    """Read every sighting, rejecting duplicates and out-of-range values."""
    path = Path(xlsx_path)
    try:
        workbook = openpyxl.load_workbook(path, data_only=True)
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        # A half-copied or non-.xlsx file off a field laptop isn't a valid
        # zip at all; openpyxl's own errors (and a plain OSError, e.g. a
        # missing file) are just as unreadable to a non-Python user as the
        # zipfile traceback underneath them. Name the file, not the library.
        raise SurveyDataError(f"{path.name}: cannot read workbook: {exc}") from exc
    rows = [r for r in workbook.worksheets[0].iter_rows(values_only=True) if any(r)]
    if not rows:
        raise SurveyDataError(f"{path.name}: sheet is empty")

    headers = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    name_col = _column_index(headers, _NAME_KEY, path)
    dist_col = _column_index(headers, _DISTANCE_KEY, path)
    angle_col = _column_index(headers, _ANGLE_KEY, path)
    height_col = _column_index(headers, _HEIGHT_KEY, path)

    readings: list[BinocReading] = []
    seen: dict[str, int] = {}
    for line_no, row in enumerate(rows[1:], start=2):
        raw_name = row[name_col] if len(row) > name_col else None
        if raw_name is None or not str(raw_name).strip():
            continue
        name = str(raw_name).strip()
        key = name.lower()
        if key in seen:
            raise SurveyDataError(
                f"{path.name}: '{name}' appears twice (rows {seen[key]} and "
                f"{line_no}). Each point may be sighted once -- fix the label "
                "in the source workbook."
            )
        seen[key] = line_no

        distance = _number(row[dist_col], "distance", name, path)
        angle = _number(row[angle_col], "angle", name, path)
        height = _number(row[height_col], "instrument height", name, path)

        if distance <= 0:
            raise SurveyDataError(f"{path.name}: {name} has distance {distance} m; must be > 0")
        if not 0.0 < angle < _MAX_ANGLE_DEG:
            raise SurveyDataError(
                f"{path.name}: {name} has angle {angle}deg; expected 0-{_MAX_ANGLE_DEG:g}"
            )
        if not 0.0 < height <= _MAX_INSTRUMENT_HEIGHT_M:
            raise SurveyDataError(
                f"{path.name}: {name} has binocular height {height} m; "
                f"expected 0-{_MAX_INSTRUMENT_HEIGHT_M:g}"
            )

        readings.append(
            BinocReading(
                name=name,
                distance_m=distance,
                angle_deg=angle,
                instrument_height_m=height,
            )
        )

    if not readings:
        raise SurveyDataError(f"{path.name}: no sightings found")
    return tuple(readings)
