"""Decode any MapPro Lat/Lon export format to decimal degrees.

MapPro can export the same survey in nine coordinate formats. Four of them are
bare numbers that are indistinguishable from one another by inspection --
1.35579855 (degrees), 1.21208748 (packed DMS), 1.50644284 (grads) and
0.023663149 (radians) are all Pt1's latitude. Guessing from magnitude alone is
how a radian file silently shipped as if it were degrees.

So we arbitrate with the ``Northing``/``Easting`` columns, which MapPro writes
in metres regardless of the angle format: only the correct interpretation
reproduces the surveyed baselines between points. That check also runs on the
self-identifying formats, turning format detection into a validation step.

All arithmetic is exact ``Decimal``; the source resolution is 0.0001" (~3 mm).
"""

from __future__ import annotations

import re
from decimal import Decimal, localcontext
from enum import Enum
from typing import Iterable, Sequence

from . import geo

# Working precision for the intermediate divisions; far beyond the data's ~8
# significant decimal places of real accuracy.
_PREC = 50

# 180/pi to 40 significant figures, for the radian conversion.
_DEG_PER_RAD = Decimal("57.29577951308232087679815481410517033240")

_GRADS_TO_DEG = Decimal("0.9")  # 400 grads == 360 degrees

_NUM = re.compile(r"\d+(?:\.\d+)?")
_BARE_NUMERIC = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_HEMISPHERES = ("N", "S", "E", "W")
_NEGATIVE_HEMISPHERES = ("S", "W")

# The receiver writes 0x1a as its minute/second mark and 0xb0 as the degree
# sign. They are field *separators*: deleting them merges "21" and "20.8748"
# into "2120.8748", which then fails the minutes<60 check. Map them to spaces.
_SEPARATORS = {c: " " for c in range(0x20) if c not in (0x09, 0x0A, 0x0D)}
_SEPARATORS[0xB0] = " "


class CoordinateFormat(Enum):
    """One of MapPro's nine Lat/Lon export formats (DMS variants collapsed)."""

    DMS = "dms"                      # N1d21m20.8748s / N1:21:20.8748 / N1°21'20.8748"
    GRADS_CC = "grads_cc"            # 1g50c64.4284cc
    DECIMAL = "decimal"              # 1.35579855
    DMS_PACKED = "dms_packed"        # 1.21208748          -> 1° 21' 20.8748"
    GRADS_DECIMAL = "grads_decimal"  # 1.50644284 grads
    GRADS_PACKED = "grads_packed"    # 150.644284          -> 1g 50c 64.4284cc
    RADIAN = "radian"                # 0.023663149

    @property
    def is_bare_numeric(self) -> bool:
        """True when the format carries no marker distinguishing it."""
        return self in _BARE_NUMERIC_FORMATS


_BARE_NUMERIC_FORMATS = frozenset(
    {
        CoordinateFormat.DECIMAL,
        CoordinateFormat.DMS_PACKED,
        CoordinateFormat.GRADS_DECIMAL,
        CoordinateFormat.GRADS_PACKED,
        CoordinateFormat.RADIAN,
    }
)


class UnknownCoordinateFormat(ValueError):
    """The Lat/Lon format could not be determined, or contradicts Northing/Easting."""


def _split_hemisphere(text: str) -> tuple[str, bool]:
    """Strip a leading/trailing N/S/E/W, reporting whether it means negative."""
    cleaned = text.strip()
    if not cleaned:
        return "", False
    head = cleaned[0].upper()
    if head in _HEMISPHERES:
        return cleaned[1:].strip(), head in _NEGATIVE_HEMISPHERES
    tail = cleaned[-1].upper()
    # A trailing "s" is the seconds unit in "1d21m20.8748s", not South.
    is_seconds_unit = tail == "S" and "d" in cleaned.lower() and "m" in cleaned.lower()
    if tail in _HEMISPHERES and not is_seconds_unit:
        return cleaned[:-1].strip(), tail in _NEGATIVE_HEMISPHERES
    return cleaned, False


def _sexagesimal(degrees: Decimal, minutes: Decimal, seconds: Decimal) -> Decimal | None:
    if not (0 <= minutes < 60 and 0 <= seconds < 60):
        return None
    return degrees + minutes / Decimal(60) + seconds / Decimal(3600)


def _centesimal(grads: Decimal, cmin: Decimal, csec: Decimal) -> Decimal | None:
    if not (0 <= cmin < 100 and 0 <= csec < 100):
        return None
    return (grads + cmin / Decimal(100) + csec / Decimal(10000)) * _GRADS_TO_DEG


def _from_tokens(text: str, centesimal: bool) -> Decimal | None:
    tokens = _NUM.findall(text)
    if len(tokens) < 2:
        return None
    major, minor = Decimal(tokens[0]), Decimal(tokens[1])
    sub = Decimal(tokens[2]) if len(tokens) > 2 else Decimal(0)
    return _centesimal(major, minor, sub) if centesimal else _sexagesimal(major, minor, sub)


def _from_packed(value: Decimal, centesimal: bool) -> Decimal | None:
    """Unpack ``d.mmssssss`` (or ``ggg cc.ssssss``) held in one number."""
    whole = int(value)
    frac = value - whole
    if centesimal:
        # 11521.546052 -> 115 grads, 21 centesimal minutes, 54.6052 cc.
        return _centesimal(Decimal(whole // 100), Decimal(whole % 100), frac * Decimal(100))
    # 1.21208748 -> 1 degree, 21 minutes, 20.8748 seconds.
    digits = f"{frac:.10f}".split(".")[1]
    return _sexagesimal(
        Decimal(whole),
        Decimal(digits[0:2]),
        Decimal(f"{digits[2:4]}.{digits[4:]}"),
    )


def parse_coordinate(raw: object, fmt: CoordinateFormat) -> Decimal | None:
    """Decode one cell to signed decimal degrees, or None if unreadable."""
    if raw is None:
        return None
    text = str(raw).translate(_SEPARATORS).strip()
    if not text:
        return None
    text, negative = _split_hemisphere(text)
    if not text:
        return None

    with localcontext() as ctx:
        ctx.prec = _PREC
        try:
            degrees = _decode(text, fmt)
        except (ArithmeticError, ValueError, IndexError):
            return None
        if degrees is None:
            return None
        return -degrees if negative else degrees


def _decode(text: str, fmt: CoordinateFormat) -> Decimal | None:
    if fmt is CoordinateFormat.DMS:
        return _from_tokens(text, centesimal=False)
    if fmt is CoordinateFormat.GRADS_CC:
        return _from_tokens(text, centesimal=True)

    if not _BARE_NUMERIC.match(text):
        return None
    value = Decimal(text)
    magnitude = value.copy_abs()

    if fmt is CoordinateFormat.DECIMAL:
        return magnitude
    if fmt is CoordinateFormat.RADIAN:
        return magnitude * _DEG_PER_RAD
    if fmt is CoordinateFormat.GRADS_DECIMAL:
        return magnitude * _GRADS_TO_DEG
    if fmt is CoordinateFormat.DMS_PACKED:
        return _from_packed(magnitude, centesimal=False)
    if fmt is CoordinateFormat.GRADS_PACKED:
        return _from_packed(magnitude, centesimal=True)
    return None


# --- format detection ------------------------------------------------------

# A candidate must reproduce the surveyed baselines this closely, and beat the
# runner-up by this factor, before we trust it. Wrong interpretations miss by
# kilometres, so the gap is never marginal in practice.
_MAX_BASELINE_ERROR_M = 1.0
_MIN_MARGIN = 10.0

CoordRow = Sequence[object]  # (latitude, longitude, northing, easting)


def _candidate_formats(rows: Sequence[CoordRow]) -> list[CoordinateFormat]:
    """Narrow by self-identifying markers before falling back to the bare set."""
    sample = " ".join(
        str(cell) for row in rows for cell in row[:2] if cell is not None
    ).translate(_SEPARATORS)
    lowered = sample.lower()
    if "cc" in lowered and "g" in lowered:
        return [CoordinateFormat.GRADS_CC]
    if re.search(r"\d\s*[dm:]\s*\d", lowered) or re.search(r"\d\s+\d+\s+\d", lowered):
        return [CoordinateFormat.DMS]
    return [f for f in CoordinateFormat if f.is_bare_numeric]


def _baseline_error(rows: Sequence[CoordRow], fmt: CoordinateFormat) -> float | None:
    """RMS metres between lat/lon-implied and surveyed point-to-point offsets."""
    fixes: list[tuple[float, float, float, float]] = []
    for lat_raw, lon_raw, northing, easting in rows:
        if northing is None or easting is None:
            return None
        lat = parse_coordinate(lat_raw, fmt)
        lon = parse_coordinate(lon_raw, fmt)
        if lat is None or lon is None:
            return None
        fixes.append((float(lat), float(lon), float(northing), float(easting)))
    if len(fixes) < 2:
        return None

    origin = geo.make_origin(fixes[0][0], fixes[0][1])
    squares = 0.0
    for (lat_a, lon_a, n_a, e_a), (lat_b, lon_b, n_b, e_b) in zip(fixes, fixes[1:]):
        d_north = (lat_b - lat_a) * origin.m_per_deg_lat - (n_b - n_a)
        d_east = (lon_b - lon_a) * origin.m_per_deg_lon - (e_b - e_a)
        squares += d_north * d_north + d_east * d_east
    return (squares / (len(fixes) - 1)) ** 0.5


def detect_format(rows: Iterable[CoordRow]) -> CoordinateFormat:
    """Identify the Lat/Lon format of a MapPro export.

    ``rows`` yields ``(latitude, longitude, northing, easting)`` as written in
    the CSV; northing/easting may be None, in which case only self-identifying
    formats can be resolved.

    Raises UnknownCoordinateFormat when nothing fits, when two candidates fit
    comparably well, or when the coordinates contradict Northing/Easting.
    """
    rows = [tuple(r) for r in rows]
    if not rows:
        raise UnknownCoordinateFormat("no rows to inspect")

    candidates = _candidate_formats(rows)
    scored = [(fmt, _baseline_error(rows, fmt)) for fmt in candidates]
    usable = sorted(
        ((fmt, err) for fmt, err in scored if err is not None), key=lambda p: p[1]
    )

    if not usable:
        # No Northing/Easting to check against: only a marker can save us.
        if len(candidates) == 1:
            return candidates[0]
        raise UnknownCoordinateFormat(
            "Lat/Lon is a bare number and Northing/Easting is missing, so "
            f"{', '.join(f.value for f in candidates)} are indistinguishable. "
            "Re-export with Northing/Easting, or pass the format explicitly."
        )

    best_fmt, best_err = usable[0]
    if best_err > _MAX_BASELINE_ERROR_M:
        raise UnknownCoordinateFormat(
            f"no coordinate format reproduces the surveyed Northing/Easting "
            f"(closest: {best_fmt.value}, off by {best_err:,.1f} m). The "
            "Latitude/Longitude and Northing/Easting columns disagree."
        )
    if len(usable) > 1:
        runner_up_fmt, runner_up_err = usable[1]
        if runner_up_err < best_err * _MIN_MARGIN:
            raise UnknownCoordinateFormat(
                f"ambiguous: {best_fmt.value} ({best_err:.2f} m) and "
                f"{runner_up_fmt.value} ({runner_up_err:.2f} m) both fit."
            )
    return best_fmt
