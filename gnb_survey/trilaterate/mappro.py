"""Read a MapPro survey-point CSV in any of its nine coordinate formats.

The reader takes the raw export straight off the receiver -- no normalisation
step in between -- because the format is detected and then *verified* against
the Northing/Easting columns, which MapPro writes in metres whatever the angle
format. A file whose Latitude/Longitude disagrees with its own Northing/Easting
is rejected rather than plotted in the wrong hemisphere.

Altitude datum: ``Altitude`` is the ground mark and ``Original Altitude`` is
the GNSS antenna one ``Antenna Height`` further up the pole. We keep the ground
mark, because the binoculars that took the sightings sat at their own height
above it (see binoc.py).
"""

from __future__ import annotations

import csv
from pathlib import Path

from .coords import CoordinateFormat, UnknownCoordinateFormat, detect_format, parse_coordinate
from .errors import SurveyDataError
from .models import Station

_REQUIRED = ("Point Name", "Latitude", "Longitude", "Altitude")
_NORTHING, _EASTING = "Northing", "Easting"
_ORIGINAL_ALTITUDE = "Original Altitude"
_ANTENNA_HEIGHT = "Antenna Height"

# Altitude - Original Altitude must equal the antenna height to this tolerance.
_ALTITUDE_TOLERANCE_M = 0.002


def _clean_headers(fieldnames: list[str] | None) -> list[str]:
    """The receiver embeds control bytes in two header names."""
    strip = {c: None for c in range(0x20) if c not in (0x09, 0x0A, 0x0D)}
    return [str(f).translate(strip).strip() for f in (fieldnames or [])]


def _optional_float(row: dict[str, str], column: str) -> float | None:
    raw = (row.get(column) or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _required_float(row: dict[str, str], column: str, name: str, path: Path) -> float:
    value = _optional_float(row, column)
    if value is None:
        raise SurveyDataError(f"{path.name}: {name} has no readable '{column}'")
    return value


def _check_altitude_datum(row: dict[str, str], name: str, ground: float, path: Path) -> float | None:
    """Confirm Original Altitude sits exactly one antenna height above ground."""
    original = _optional_float(row, _ORIGINAL_ALTITUDE)
    antenna = _optional_float(row, _ANTENNA_HEIGHT)
    if original is None or antenna is None:
        return antenna
    if abs((original - ground) - antenna) > _ALTITUDE_TOLERANCE_M:
        raise SurveyDataError(
            f"{path.name}: {name} has Original Altitude {original:.4f} m and "
            f"Altitude {ground:.4f} m, a gap of {original - ground:.4f} m, but "
            f"Antenna Height says {antenna:.4f} m. The altitude columns are "
            "inconsistent -- re-export rather than guess the datum."
        )
    return antenna


def read_stations(csv_path: str | Path) -> tuple[Station, ...]:
    """Read every surveyed point, with coordinates verified against Northing/Easting."""
    path = Path(csv_path)
    try:
        # latin-1 never raises on the receiver's 0xb0 / 0x1a bytes.
        with path.open(newline="", encoding="latin-1") as handle:
            reader = csv.reader(handle)
            try:
                headers = _clean_headers(next(reader))
            except StopIteration:
                raise SurveyDataError(f"{path.name}: file is empty") from None
            rows = [
                dict(zip(headers, line)) for line in reader if any(c.strip() for c in line)
            ]
    except OSError as exc:
        raise SurveyDataError(f"{path.name}: cannot read file: {exc}") from exc

    missing = [c for c in _REQUIRED if c not in headers]
    if missing:
        raise SurveyDataError(
            f"{path.name}: missing required column(s): {', '.join(missing)}. "
            "Export with MapPro's 'Survey point data format (csv)'."
        )
    if not rows:
        raise SurveyDataError(f"{path.name}: no data rows")

    has_ne = _NORTHING in headers and _EASTING in headers
    try:
        fmt = detect_format(
            (
                r.get("Latitude"),
                r.get("Longitude"),
                _optional_float(r, _NORTHING) if has_ne else None,
                _optional_float(r, _EASTING) if has_ne else None,
            )
            for r in rows
        )
    except UnknownCoordinateFormat as exc:
        raise SurveyDataError(f"{path.name}: {exc}") from None

    return tuple(_station(row, fmt, path) for row in rows)


def _station(row: dict[str, str], fmt: CoordinateFormat, path: Path) -> Station:
    name = (row.get("Point Name") or "").strip()
    if not name:
        raise SurveyDataError(f"{path.name}: a row has no Point Name")

    latitude = parse_coordinate(row.get("Latitude"), fmt)
    longitude = parse_coordinate(row.get("Longitude"), fmt)
    if latitude is None or longitude is None:
        raise SurveyDataError(
            f"{path.name}: {name} has unreadable coordinates "
            f"({row.get('Latitude')!r}, {row.get('Longitude')!r}) as {fmt.value}"
        )

    ground = _required_float(row, "Altitude", name, path)
    antenna = _check_altitude_datum(row, name, ground, path)

    return Station(
        name=name,
        latitude=float(latitude),
        longitude=float(longitude),
        ground_altitude_m=ground,
        antenna_height_m=antenna,
    )
