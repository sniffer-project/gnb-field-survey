#!/usr/bin/env python3
"""Rewrite a MapPro survey CSV's coordinate columns to decimal degrees for Google My Maps.

MapPro exports the same survey in nine Lat/Lon formats. Google My Maps plots
*decimal degrees* only, so this writes a new `*_mymaps.csv` that keeps every
column but **replaces the coordinate columns in place** with clean decimal
degrees (no confusing duplicate columns — the original CSV on disk is the
untouched full-fidelity record). In My Maps' import dialog just choose the
naturally-named Latitude + Longitude to position the placemarks.

The nine formats, all showing Pt1's latitude of 1.35579855 degrees:

    N1d21m20.8748s      DMS, letter separators
    N1:21:20.8748       DMS, colons
    N1<b0>21<1a>...     DMS, degree sign + the receiver's 0x1a marks
    1g50c64.4284cc      grads, centesimal minutes/seconds
    1.35579855          decimal degrees
    1.21208748          packed DMS       -> 1d 21m 20.8748s
    1.50644284          decimal grads    -> x 0.9
    150.644284          packed grads     -> 1g 50c 64.4284cc
    0.023663149         radians          -> x 180/pi

The last five are bare numbers that nothing in the cell distinguishes — all
five above are the *same* latitude. Magnitude heuristics get this wrong, and a
wrong guess writes plausible-looking coordinates in the wrong hemisphere.

So the format is decided by the `Northing`/`Easting` columns, which MapPro
writes in metres whatever the angle format: only the correct interpretation
reproduces the surveyed distances between points. If nothing fits, or two
candidates fit comparably well, the file is refused rather than converted wrong.

Precision: PRECISION decimal places via exact Decimal math (default 16), emitted in fixed-point
notation. NOTE: 8 dp is the real *accuracy* ceiling for this data (source resolution 0.0001" ~
3 mm; receiver HRMS 3.6-9.9 mm); digits beyond the 8th are the exact decimal of the source,
not measured accuracy. My Maps imposes no documented cap on decimal places.

Text cells are passed through verbatim except for a number-safe guard against spreadsheet
formula injection (a non-numeric cell starting with = + - @ is prefixed with a quote).

My Maps import limits to keep in mind: 2,000 rows/layer, 10 layers, 5 MB/layer, 100 photos/import.
"""
import argparse
import csv
import math
import re
import sys
from decimal import Decimal, localcontext
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional, Sequence

PRECISION = 16  # output decimal places. NOTE: 8 dp = the data's real accuracy ceiling.
QUANT = Decimal(1).scaleb(-PRECISION)  # e.g. 1e-16
_PREC = 50  # working precision for the intermediate divisions

# 180/pi to 40 significant figures.
_DEG_PER_RAD = Decimal("57.29577951308232087679815481410517033240")
_GRADS_TO_DEG = Decimal("0.9")  # 400 grads == 360 degrees

NUM = re.compile(r"\d+(?:\.\d+)?")
_BARE_NUMERIC = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_HEMISPHERES = ("N", "S", "E", "W")
_NEGATIVE_HEMISPHERES = ("S", "W")

# Coordinate columns to convert in place. Latitude/Longitude are what My Maps
# plots; the others are converted too so no mangled text is left in any
# coordinate column.
COORD_COLS = (
    "Latitude", "Longitude",
    "Original Latitude", "Original Longitude",
    "Base Latitude", "Base Longitude",
)
PLOT_COLS = ("Latitude", "Longitude")  # the ones My Maps positions points by

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
# Regex to match valid optional-signed integer, decimal, and scientific notation
_NUMERIC_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
# XML-illegal C0 control bytes. Left in place they corrupt the KML that My Maps
# exports and make QGIS/OGR reject it, so we strip them from pass-through text.
_C0_STRIP = {c: None for c in range(0x20) if c not in (0x09, 0x0A, 0x0D)}

# For *parsing*, those same bytes must become spaces rather than vanish: the
# receiver writes 0x1a as its minute/second mark, so deleting it merges "21" and
# "20.8748" into "2120.8748", which fails the minutes<60 check and makes the
# whole degree-sign export unconvertible. 0xb0 is the degree sign.
_SEPARATORS = {c: " " for c in range(0x20) if c not in (0x09, 0x0A, 0x0D)}
_SEPARATORS[0xB0] = " "


class Format(Enum):
    """A MapPro Lat/Lon export format (the three DMS variants collapse into one)."""

    DMS = "dms"
    GRADS_CC = "grads (g/c/cc)"
    DECIMAL = "decimal degrees"
    DMS_PACKED = "packed dms"
    GRADS_DECIMAL = "decimal grads"
    GRADS_PACKED = "packed grads"
    RADIAN = "radians"


# The formats that carry no marker distinguishing them from one another.
BARE_NUMERIC_FORMATS = (
    Format.DECIMAL,
    Format.DMS_PACKED,
    Format.GRADS_DECIMAL,
    Format.GRADS_PACKED,
    Format.RADIAN,
)


class UnknownFormat(ValueError):
    """The Lat/Lon format could not be determined, or contradicts Northing/Easting."""


def _safe_cell(value: object) -> str:
    """Strip XML-illegal control bytes, then neutralise spreadsheet formula injection.

    Only a cell that starts with a formula trigger AND is not a valid number gets a leading
    quote, so coordinates and negative values (e.g. '-0.0012', '1.3531...') pass through clean.
    """
    s = str(value).translate(_C0_STRIP)
    if s[:1] in _FORMULA_PREFIXES:
        if not _NUMERIC_RE.match(s):
            return "'" + s
    return s


def _split_hemisphere(text: str) -> "tuple[str, bool]":
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


def _sexagesimal(degrees: Decimal, minutes: Decimal, seconds: Decimal) -> Optional[Decimal]:
    if not (0 <= minutes < 60 and 0 <= seconds < 60):
        return None
    return degrees + minutes / Decimal(60) + seconds / Decimal(3600)


def _centesimal(grads: Decimal, cmin: Decimal, csec: Decimal) -> Optional[Decimal]:
    if not (0 <= cmin < 100 and 0 <= csec < 100):
        return None
    return (grads + cmin / Decimal(100) + csec / Decimal(10000)) * _GRADS_TO_DEG


def _from_tokens(text: str, centesimal: bool) -> Optional[Decimal]:
    tokens = NUM.findall(text)
    if len(tokens) < 2:
        return None
    major, minor = Decimal(tokens[0]), Decimal(tokens[1])
    sub = Decimal(tokens[2]) if len(tokens) > 2 else Decimal(0)
    return _centesimal(major, minor, sub) if centesimal else _sexagesimal(major, minor, sub)


def _from_packed(value: Decimal, centesimal: bool) -> Optional[Decimal]:
    """Unpack `d.mmssssss` (or `gggcc.ssssss`) held in a single number."""
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


def _decode(text: str, fmt: Format) -> Optional[Decimal]:
    if fmt is Format.DMS:
        return _from_tokens(text, centesimal=False)
    if fmt is Format.GRADS_CC:
        return _from_tokens(text, centesimal=True)

    if not _BARE_NUMERIC.match(text):
        return None
    magnitude = Decimal(text).copy_abs()

    if fmt is Format.DECIMAL:
        return magnitude
    if fmt is Format.RADIAN:
        return magnitude * _DEG_PER_RAD
    if fmt is Format.GRADS_DECIMAL:
        return magnitude * _GRADS_TO_DEG
    if fmt is Format.DMS_PACKED:
        return _from_packed(magnitude, centesimal=False)
    if fmt is Format.GRADS_PACKED:
        return _from_packed(magnitude, centesimal=True)
    return None


def to_decimal(raw: Optional[str], fmt: Format) -> Optional[str]:
    """Decode one cell to a signed decimal-degree string, or None if unreadable."""
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
        if negative:
            degrees = -degrees
        return format(degrees.quantize(QUANT), "f")


# --- format detection ------------------------------------------------------

# A candidate must reproduce the surveyed baselines this closely, and beat the
# runner-up by this factor. Wrong interpretations miss by kilometres, so in
# practice the gap is never marginal.
_MAX_BASELINE_ERROR_M = 1.0
_MIN_MARGIN = 10.0
_M_PER_DEG_LAT = 110_574.0
_M_PER_DEG_LON_EQ = 111_320.0


def _as_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or not _NUMERIC_RE.match(text):
        return None
    return float(text)


def _baseline_error(rows: Sequence[dict], fmt: Format) -> Optional[float]:
    """RMS metres between lat/lon-implied and surveyed point-to-point offsets.

    Works against any near-conformal projection at unit scale (the exports seen
    so far carry UTM 48N); over the tens of metres between survey points the
    projection's own scale error is millimetres, far inside the threshold.
    """
    fixes = []
    for row in rows:
        northing, easting = _as_float(row.get("Northing")), _as_float(row.get("Easting"))
        if northing is None or easting is None:
            return None
        lat, lon = to_decimal(row.get("Latitude"), fmt), to_decimal(row.get("Longitude"), fmt)
        if lat is None or lon is None:
            return None
        fixes.append((float(lat), float(lon), northing, easting))
    if len(fixes) < 2:
        return None

    m_per_deg_lon = _M_PER_DEG_LON_EQ * math.cos(math.radians(fixes[0][0]))
    squares = 0.0
    for (lat_a, lon_a, n_a, e_a), (lat_b, lon_b, n_b, e_b) in zip(fixes, fixes[1:]):
        d_north = (lat_b - lat_a) * _M_PER_DEG_LAT - (n_b - n_a)
        d_east = (lon_b - lon_a) * m_per_deg_lon - (e_b - e_a)
        squares += d_north * d_north + d_east * d_east
    return math.sqrt(squares / (len(fixes) - 1))


def _candidate_formats(rows: Sequence[dict]) -> list:
    """Narrow by self-identifying markers before falling back to the bare set."""
    sample = " ".join(
        str(row.get(col) or "") for row in rows for col in PLOT_COLS
    ).translate(_SEPARATORS).lower()
    if "cc" in sample and "g" in sample:
        return [Format.GRADS_CC]
    if re.search(r"\d\s*[dm:]\s*\d", sample) or re.search(r"\d\s+\d+\s+\d", sample):
        return [Format.DMS]
    return list(BARE_NUMERIC_FORMATS)


def detect_format(rows: Iterable[dict]) -> Format:
    """Identify a MapPro export's Lat/Lon format, verified against Northing/Easting.

    Raises UnknownFormat when nothing fits, when two candidates fit comparably
    well, or when the coordinates contradict Northing/Easting.
    """
    rows = list(rows)
    if not rows:
        raise UnknownFormat("no data rows to inspect")

    candidates = _candidate_formats(rows)
    scored = [(fmt, _baseline_error(rows, fmt)) for fmt in candidates]
    usable = sorted(((f, e) for f, e in scored if e is not None), key=lambda p: p[1])

    if not usable:
        if len(candidates) == 1:
            return candidates[0]
        raise UnknownFormat(
            "Latitude/Longitude are bare numbers and Northing/Easting is missing, so "
            + ", ".join(f.value for f in candidates)
            + " are indistinguishable. Re-export including Northing/Easting."
        )

    best_fmt, best_err = usable[0]
    if best_err > _MAX_BASELINE_ERROR_M:
        raise UnknownFormat(
            f"no format reproduces the surveyed Northing/Easting (closest: "
            f"{best_fmt.value}, off by {best_err:,.1f} m). The Latitude/Longitude "
            "and Northing/Easting columns disagree."
        )
    if len(usable) > 1 and usable[1][1] < best_err * _MIN_MARGIN:
        raise UnknownFormat(
            f"ambiguous: {best_fmt.value} ({best_err:.2f} m) and "
            f"{usable[1][0].value} ({usable[1][1]:.2f} m) both fit."
        )
    return best_fmt


def convert(in_path: Path) -> Path:
    out_path = in_path.with_name(in_path.stem + "_mymaps.csv")
    unparsed: list = []
    # latin-1 never raises on the mangled 0xB0 / 0x1A bytes; decoding is lossless.
    with in_path.open(newline="", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        fieldnames: list = list(reader.fieldnames or [])
        rows_out: list = list(reader)

    if not fieldnames:
        print(
            f"WARNING: {in_path.name}: empty or no header - nothing written.",
            file=sys.stderr
        )
        return out_path

    fmt = detect_format(rows_out)  # raises UnknownFormat rather than guess wrong

    convert_cols: list = [c for c in COORD_COLS if c in fieldnames]
    if not convert_cols:
        print(
            f"WARNING: {in_path.name}: none of the expected coordinate "
            f"columns found - output is an unchanged copy.",
            file=sys.stderr
        )

    for row in rows_out:
        plot_ok = True
        for col in convert_cols:
            dec = to_decimal(row.get(col), fmt)
            if dec is not None:
                row[col] = dec  # replace in place; leave untouched if unparseable
            elif col in PLOT_COLS:
                plot_ok = False
        if not plot_ok:
            unparsed.append(row.get("Point Name", "?"))

    # same columns as the source - only the coordinate values changed. Headers are sanitized
    # too (the receiver mangles two with a 0x1A byte) so the file is XML-clean end to end.
    clean_fields: list = [str(fn).translate(_C0_STRIP) for fn in fieldnames]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(clean_fields)
        for row in rows_out:
            writer.writerow([_safe_cell(row.get(fn, "")) for fn in fieldnames])

    print(
        f"{in_path.name}: {len(rows_out)} rows -> {out_path.name} "
        f"({len(fieldnames)} columns; detected {fmt.value}; "
        f"converted in place: {', '.join(convert_cols) or 'none'})"
    )
    if unparsed:
        print(
            f"   WARNING: Latitude/Longitude unparseable for: "
            f"{', '.join(unparsed)} (left as-is - they won't plot in My Maps)",
            file=sys.stderr
        )
    preview_limit = 2
    if len(rows_out) > preview_limit:
        print(f"   Preview of first {preview_limit} rows:")
    for row in rows_out[:preview_limit]:
        print(
            f"   {row.get('Point Name', '?')}: "
            f"{row.get('Latitude')}, {row.get('Longitude')}"
        )
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Rewrite a MapPro survey CSV's coordinate columns "
            "to decimal degrees for Google My Maps."
        )
    )
    parser.add_argument(
        "files",
        metavar="FILE",
        nargs="+",
        help="One or more CSV files to convert."
    )

    args = parser.parse_args()

    exit_code = 0
    for file_str in args.files:
        path = Path(file_str)
        try:
            if not path.is_file():
                raise FileNotFoundError(f"File not found: {file_str}")
            convert(path)
        except UnknownFormat as e:
            print(f"ERROR: {path.name}: {e}", file=sys.stderr)
            exit_code = 1
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            exit_code = 1
        except Exception as e:
            print(f"ERROR: failed to convert {file_str}: {e}", file=sys.stderr)
            exit_code = 1
    raise SystemExit(exit_code)
