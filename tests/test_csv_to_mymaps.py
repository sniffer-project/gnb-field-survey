"""All nine MapPro Lat/Lon export formats must convert to the same coordinates.

Vectors are Pt1-Pt3 of the 20260716 survey, which MapPro exported nine times.
Four of these formats used to convert wrongly or not at all:

    decimal grads / packed grads -- read as if they were degrees
    radians                      -- read as if they were degrees
    degree-sign DMS              -- the 0x1a marks were deleted rather than
                                    treated as separators, merging the minutes
                                    and seconds fields
"""
import math

import pytest

from csv_to_mymaps import Format, UnknownFormat, detect_format, to_decimal

PT1_LAT, PT1_LON = 1.35579855, 103.69391447
# The DMS exports resolve to 0.0001 arc-seconds (~3 mm) and the radian export to
# 9 significant figures (~4 mm), so formats agree to within their own
# quantisation. 2 cm is far below any wrong-format error, which lands km out.
TOL_M = 0.02
_M_PER_DEG = 111_320.0

# (format, latitude, longitude) for Pt1 in each of the nine exports.
PT1 = [
    (Format.DMS, "N1d21m20.8748s", "E103d41m38.0921s"),
    (Format.DMS, "N1:21:20.8748", "E103:41:38.0921"),
    (Format.DMS, "N1\xb021\x1a20.8748\x1a", "E103\xb041\x1a38.0921\x1a"),
    (Format.GRADS_CC, "1g50c64.4284cc", "115g21c54.6052cc"),
    (Format.DECIMAL, "1.35579855", "103.69391447"),
    (Format.DMS_PACKED, "1.21208748", "103.41380921"),
    (Format.GRADS_DECIMAL, "1.50644284", "115.21546052"),
    (Format.GRADS_PACKED, "150.644284", "11521.546052"),
    (Format.RADIAN, "0.023663149", "1.809800222"),
]

# Pt2 and Pt3 in the five bare-numeric formats, plus their surveyed Northing /
# Easting (UTM 48N metres) which are identical across every export.
NE = {
    "Pt1": ("149955.9668", "354634.9606"),
    "Pt2": ("149962.1319", "354630.4524"),
    "Pt3": ("149965.0253", "354619.5814"),
}
BARE = {
    Format.DECIMAL: [
        ("1.35579855", "103.69391447"),
        ("1.35585427", "103.69387394"),
        ("1.35588038", "103.69377627"),
    ],
    Format.DMS_PACKED: [
        ("1.21208748", "103.41380921"),
        ("1.21210754", "103.41379462"),
        ("1.21211694", "103.41375946"),
    ],
    Format.GRADS_DECIMAL: [
        ("1.50644284", "115.21546052"),
        ("1.50650475", "115.21541549"),
        ("1.50653375", "115.21530697"),
    ],
    Format.GRADS_PACKED: [
        ("150.644284", "11521.546052"),
        ("150.650475", "11521.541549"),
        ("150.653375", "11521.530697"),
    ],
    Format.RADIAN: [
        ("0.023663149", "1.809800222"),
        ("0.023664121", "1.809799514"),
        ("0.023664577", "1.809797810"),
    ],
}


def _offset_m(lat, lon):
    return math.hypot(
        (lat - PT1_LAT) * _M_PER_DEG,
        (lon - PT1_LON) * _M_PER_DEG * math.cos(math.radians(PT1_LAT)),
    )


def _rows(fmt):
    return [
        {"Point Name": name, "Latitude": lat, "Longitude": lon,
         "Northing": NE[name][0], "Easting": NE[name][1]}
        for name, (lat, lon) in zip(("Pt1", "Pt2", "Pt3"), BARE[fmt])
    ]


@pytest.mark.parametrize("fmt,lat,lon", PT1)
def test_every_format_converts_to_the_same_point(fmt, lat, lon):
    got_lat, got_lon = to_decimal(lat, fmt), to_decimal(lon, fmt)
    assert got_lat is not None and got_lon is not None
    assert _offset_m(float(got_lat), float(got_lon)) < TOL_M


@pytest.mark.parametrize("fmt", list(BARE))
def test_bare_numeric_formats_are_told_apart_by_northing_easting(fmt):
    """Every one of these is a plausible-looking number on its own."""
    assert detect_format(_rows(fmt)) is fmt


@pytest.mark.parametrize("fmt,lat,lon", [p for p in PT1 if p[0] in (Format.DMS, Format.GRADS_CC)])
def test_marked_formats_are_detected_without_northing_easting(fmt, lat, lon):
    assert detect_format([{"Latitude": lat, "Longitude": lon}]) is fmt


def test_refuses_a_file_whose_coordinates_contradict_northing_easting():
    """The failure mode that shipped a radian file as if it were degrees."""
    rows = _rows(Format.DECIMAL)
    rows[1]["Latitude"] = "9.99999999"  # nowhere near Pt2's Northing/Easting
    with pytest.raises(UnknownFormat):
        detect_format(rows)


def test_refuses_bare_numbers_with_no_northing_easting_to_check_against():
    with pytest.raises(UnknownFormat):
        detect_format([{"Latitude": "1.35579855", "Longitude": "103.69391447"}])


def test_southern_and_western_hemispheres_are_negative():
    assert float(to_decimal("S1d21m20.8748s", Format.DMS)) < 0
    assert float(to_decimal("W103d41m38.0921s", Format.DMS)) < 0


def test_blank_and_garbage_are_left_alone():
    assert to_decimal("", Format.DECIMAL) is None
    assert to_decimal(None, Format.DECIMAL) is None
    assert to_decimal("Not Set", Format.DECIMAL) is None


def test_out_of_range_minutes_and_seconds_are_rejected():
    assert to_decimal("N1d99m20.0s", Format.DMS) is None
    assert to_decimal("N1d21m99.0s", Format.DMS) is None
