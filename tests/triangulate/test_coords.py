"""Every MapPro Lat/Lon export format decodes to the same decimal degrees.

Vectors are Pt1 of raw data/map-pro-csv/20260716, which MapPro exported nine
times from one survey. All nine must land on the `dd (Decimal)` values.
"""

from decimal import Decimal

import pytest

from gnb_survey.triangulate.coords import (
    CoordinateFormat,
    UnknownCoordinateFormat,
    detect_format,
    parse_coordinate,
)

# Pt1 truth, from "dd (Decimal).csv".
PT1_LAT = Decimal("1.35579855")
PT1_LON = Decimal("103.69391447")
TOL = Decimal("0.0000001")  # ~1 cm

# One row per exported format: (format, raw latitude, raw longitude).
# The 0x1a bytes are the receiver's minute/second marks, kept verbatim.
PT1_BY_FORMAT = [
    (CoordinateFormat.DMS, "N1d21m20.8748s", "E103d41m38.0921s"),
    (CoordinateFormat.DMS, "N1:21:20.8748", "E103:41:38.0921"),
    (CoordinateFormat.DMS, "N1\xb021\x1a20.8748\x1a", "E103\xb041\x1a38.0921\x1a"),
    (CoordinateFormat.GRADS_CC, "1g50c64.4284cc", "115g21c54.6052cc"),
    (CoordinateFormat.DECIMAL, "1.35579855", "103.69391447"),
    (CoordinateFormat.DMS_PACKED, "1.21208748", "103.41380921"),
    (CoordinateFormat.GRADS_DECIMAL, "1.50644284", "115.21546052"),
    (CoordinateFormat.GRADS_PACKED, "150.644284", "11521.546052"),
    (CoordinateFormat.RADIAN, "0.023663149", "1.809800222"),
]


@pytest.mark.unit
@pytest.mark.parametrize("fmt,lat,lon", PT1_BY_FORMAT)
def test_every_format_decodes_to_pt1(fmt, lat, lon):
    assert abs(parse_coordinate(lat, fmt) - PT1_LAT) < TOL
    assert abs(parse_coordinate(lon, fmt) - PT1_LON) < TOL


@pytest.mark.unit
def test_southern_and_western_hemispheres_are_negative():
    assert parse_coordinate("S1d21m20.8748s", CoordinateFormat.DMS) < 0
    assert parse_coordinate("W103d41m38.0921s", CoordinateFormat.DMS) < 0


@pytest.mark.unit
def test_blank_and_garbage_return_none():
    assert parse_coordinate("", CoordinateFormat.DECIMAL) is None
    assert parse_coordinate(None, CoordinateFormat.DECIMAL) is None
    assert parse_coordinate("not a number", CoordinateFormat.DECIMAL) is None


@pytest.mark.unit
def test_dms_rejects_out_of_range_minutes_and_seconds():
    assert parse_coordinate("N1d99m20.0s", CoordinateFormat.DMS) is None
    assert parse_coordinate("N1d21m99.0s", CoordinateFormat.DMS) is None


# --- format auto-detection -------------------------------------------------
# Northing/Easting are format-invariant, so they arbitrate the bare-numeric
# formats (decimal / packed DMS / grads / radian) that look identical.

PT1_NE = (Decimal("149955.9668"), Decimal("354634.9606"))
PT2_NE = (Decimal("149962.1319"), Decimal("354630.4524"))
PT3_NE = (Decimal("149965.0253"), Decimal("354619.5814"))

PT2_BY_FORMAT = {
    CoordinateFormat.DECIMAL: ("1.35585427", "103.69387394"),
    CoordinateFormat.DMS_PACKED: ("1.21210754", "103.41379462"),
    CoordinateFormat.GRADS_DECIMAL: ("1.50650475", "115.21541549"),
    CoordinateFormat.GRADS_PACKED: ("150.650475", "11521.541549"),
    CoordinateFormat.RADIAN: ("0.023664121", "1.809799514"),
}
PT3_BY_FORMAT = {
    CoordinateFormat.DECIMAL: ("1.35588038", "103.69377627"),
    CoordinateFormat.DMS_PACKED: ("1.21211694", "103.41375946"),
    CoordinateFormat.GRADS_DECIMAL: ("1.50653375", "115.21530697"),
    CoordinateFormat.GRADS_PACKED: ("150.653375", "11521.530697"),
    CoordinateFormat.RADIAN: ("0.023664577", "1.809797810"),
}


def _rows_for(fmt):
    lat1, lon1 = next((la, lo) for f, la, lo in PT1_BY_FORMAT if f is fmt)
    return [
        (lat1, lon1, *PT1_NE),
        (*PT2_BY_FORMAT[fmt], *PT2_NE),
        (*PT3_BY_FORMAT[fmt], *PT3_NE),
    ]


@pytest.mark.unit
@pytest.mark.parametrize("fmt", list(PT2_BY_FORMAT))
def test_detects_each_bare_numeric_format(fmt):
    """Radian vs decimal-degrees is unguessable from the value alone here
    (Singapore latitude 1.36 is a plausible radian too) — N/E settles it."""
    assert detect_format(_rows_for(fmt)) is fmt


@pytest.mark.unit
def test_detects_suffixed_formats_without_northing_easting():
    rows = [(lat, lon, None, None) for f, lat, lon in PT1_BY_FORMAT if f in
            (CoordinateFormat.DMS, CoordinateFormat.GRADS_CC)]
    for lat, lon, n, e in rows:
        assert detect_format([(lat, lon, n, e)]) in (
            CoordinateFormat.DMS,
            CoordinateFormat.GRADS_CC,
        )


@pytest.mark.unit
def test_ambiguous_bare_numeric_without_northing_easting_raises():
    with pytest.raises(UnknownCoordinateFormat):
        detect_format([("1.35579855", "103.69391447", None, None)])


@pytest.mark.unit
def test_detection_rejects_coordinates_inconsistent_with_northing_easting():
    """Guards the class of bug that silently shipped Radian_mymaps.csv."""
    rows = [
        ("1.35579855", "103.69391447", *PT1_NE),
        ("9.99999999", "99.99999999", *PT2_NE),  # nowhere near PT2's N/E
        ("1.35588038", "103.69377627", *PT3_NE),
    ]
    with pytest.raises(UnknownCoordinateFormat):
        detect_format(rows)
