"""Write a converted MapPro CSV, and decide where a converted copy belongs.

Text cells are passed through verbatim except for a number-safe guard against
spreadsheet formula injection (a non-numeric cell starting with = + - @ is
prefixed with a quote).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable

from .formats import COORD_COLS, PLOT_COLS, _NUMERIC_RE, detect_format, to_decimal

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
# XML-illegal C0 control bytes. Left in place they corrupt the KML that My Maps
# exports and make QGIS/OGR reject it, so we strip them from pass-through text.
_C0_STRIP = {c: None for c in range(0x20) if c not in (0x09, 0x0A, 0x0D)}


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


def processed_destination(
    source: Path, raw_root: Path, processed_root: Path
) -> Path:
    """Where a converted copy of `source` belongs.

    Mirrors the path under raw_root into processed_root, so
    data/raw/surveys/X/mappro/E.csv becomes
    data/processed/surveys/X/mappro/E_mymaps.csv. Sources from outside the
    raw tree -- a one-off file a user passed by path -- are written beside
    themselves, because inventing a location under data/processed/ for them
    would bury the output somewhere the user never looks.
    """
    name = source.stem + "_mymaps.csv"
    try:
        relative = source.parent.relative_to(raw_root)
    except ValueError:
        return source.with_name(name)
    return processed_root / relative / name


def convert(
    in_path: Path,
    out_path: Path | None = None,
    *,
    output_fn: Callable[[str], None],
    warn_fn: Callable[[str], None] | None = None,
) -> Path:
    """Rewrite a MapPro CSV's coordinate columns to decimal degrees.

    `out_path` defaults to a sibling `*_mymaps.csv`, preserving the behaviour
    of the standalone script. Warnings go to `warn_fn` if given, else to
    `output_fn`; nothing is printed directly, so callers control the stream
    and tests need no capsys.
    """
    if out_path is None:
        out_path = in_path.with_name(in_path.stem + "_mymaps.csv")
    if warn_fn is None:
        warn_fn = output_fn
    out_path.parent.mkdir(parents=True, exist_ok=True)
    unparsed: list = []
    # latin-1 never raises on the mangled 0xB0 / 0x1A bytes; decoding is lossless.
    with in_path.open(newline="", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        fieldnames: list = list(reader.fieldnames or [])
        rows_out: list = list(reader)

    if not fieldnames:
        warn_fn(
            f"WARNING: {in_path.name}: empty or no header - nothing written."
        )
        return out_path

    fmt = detect_format(rows_out)  # raises UnknownFormat rather than guess wrong

    convert_cols: list = [c for c in COORD_COLS if c in fieldnames]
    if not convert_cols:
        warn_fn(
            f"WARNING: {in_path.name}: none of the expected coordinate "
            f"columns found - output is an unchanged copy."
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

    output_fn(
        f"{in_path.name}: {len(rows_out)} rows -> {out_path.name} "
        f"({len(fieldnames)} columns; detected {fmt.value}; "
        f"converted in place: {', '.join(convert_cols) or 'none'})"
    )
    if unparsed:
        warn_fn(
            f"   WARNING: Latitude/Longitude unparseable for: "
            f"{', '.join(unparsed)} (left as-is - they won't plot in My Maps)"
        )
    preview_limit = 2
    if len(rows_out) > preview_limit:
        output_fn(f"   Preview of first {preview_limit} rows:")
    for row in rows_out[:preview_limit]:
        output_fn(
            f"   {row.get('Point Name', '?')}: "
            f"{row.get('Latitude')}, {row.get('Longitude')}"
        )
    return out_path
