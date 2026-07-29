"""MapPro CSV + binocular workbook readers, and the join that validates them."""

import math
from pathlib import Path

import openpyxl
import pytest

from gnb_survey.trilaterate.binoc import read_binoc_readings
from gnb_survey.trilaterate.assemble import SurveyDataError, build_survey
from gnb_survey.trilaterate.mappro import read_stations

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

_HEADER = (
    "Point Name,Code,Northing,Easting,Elevation,Latitude,Longitude,Altitude,"
    "Original Altitude,Measuring height,Antenna Height\n"
)
_ROWS = (
    "Pt1,,149955.9668,354634.9606,32.5729,1.35579855,103.69391447,32.5729,34.6389,2.0000,2.0660\n"
    "Pt2,,149962.1319,354630.4524,33.6284,1.35585427,103.69387394,33.6284,35.6944,2.0000,2.0660\n"
    "Pt3,,149965.0253,354619.5814,34.5987,1.35588038,103.69377627,34.5987,36.6647,2.0000,2.0660\n"
)


@pytest.fixture()
def survey_csv(tmp_path) -> Path:
    p = tmp_path / "survey.csv"
    p.write_text(_HEADER + _ROWS, encoding="latin-1")
    return p


def _write_binoc(path: Path, rows) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(
        [
            "Point Name",
            "distance from binoc viewfiner to gnb",  # verbatim typo from the real sheet
            "angle from binoc viewfinder to gnb",
            "height of binoc from ground (in meters)",
        ]
    )
    for row in rows:
        ws.append(list(row))
    wb.save(path)
    return path


@pytest.fixture()
def binoc_xlsx(tmp_path) -> Path:
    return _write_binoc(
        tmp_path / "binoc.xlsx",
        [("pt1", 49.4, 51, 2.06), ("pt2", 54.0, 46, 2.08), ("pt3", 54.6, 46, 2.08)],
    )


# --- MapPro reader ---------------------------------------------------------


@pytest.mark.unit
def test_reads_stations_with_ground_altitude(survey_csv):
    stations = read_stations(survey_csv)
    assert [s.name for s in stations] == ["Pt1", "Pt2", "Pt3"]
    first = stations[0]
    assert first.latitude == pytest.approx(1.35579855)
    assert first.longitude == pytest.approx(103.69391447)
    # "Altitude" is the ground mark; "Original Altitude" is the GNSS antenna
    # 2.066 m up the pole. The binoculars sat at their own height, so the
    # ground mark is the datum we build on.
    assert first.ground_altitude_m == pytest.approx(32.5729)
    assert first.antenna_height_m == pytest.approx(2.0660)


@pytest.mark.unit
def test_rejects_csv_whose_altitude_columns_are_inconsistent(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        _HEADER
        + "Pt1,,149955.9668,354634.9606,32.5729,1.35579855,103.69391447,32.5729,99.9999,2.0000,2.0660\n"
        + _ROWS.split("\n", 1)[1],
        encoding="latin-1",
    )
    with pytest.raises(SurveyDataError, match="Original Altitude"):
        read_stations(bad)


@pytest.mark.unit
def test_rejects_csv_missing_required_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("Point Name,Latitude\nPt1,1.3\n", encoding="latin-1")
    with pytest.raises(SurveyDataError, match="column"):
        read_stations(bad)


# The DMS exports resolve to 0.0001 arc-seconds (~3 mm), so formats agree to
# within their own quantisation, not bit-for-bit. 2 cm is comfortably below the
# receiver's own HRMS (3.6-9.9 mm) and far below any wrong-format error, which
# lands kilometres out.
_FORMAT_AGREEMENT_M = 0.02
_M_PER_DEG = 111_320.0


@pytest.mark.integration
def test_reads_every_real_export_format_identically():
    """All nine exports of 20260716 describe one survey; all must agree."""
    folder = FIXTURES / "surveys" / "20260716" / "mappro"
    if not folder.is_dir():
        pytest.skip("raw data not present")
    exports = sorted(folder.glob("*.csv"))
    assert len(exports) == 9, f"expected 9 exports, found {len(exports)}"

    baseline = {s.name: s for s in read_stations(folder / "20260716_dd (Decimal).csv")}
    for export in exports:
        stations = read_stations(export)
        assert {s.name for s in stations} == set(baseline), f"{export.name}: point set differs"
        for station in stations:
            truth = baseline[station.name]
            offset_m = math.hypot(
                (station.latitude - truth.latitude) * _M_PER_DEG,
                (station.longitude - truth.longitude) * _M_PER_DEG * math.cos(math.radians(1.36)),
            )
            assert offset_m < _FORMAT_AGREEMENT_M, (
                f"{export.name}: {station.name} is {offset_m:.3f} m from the "
                "dd (Decimal) export"
            )
            assert station.ground_altitude_m == pytest.approx(truth.ground_altitude_m, abs=1e-3)


# --- binocular reader ------------------------------------------------------


@pytest.mark.unit
def test_reads_binoc_readings(binoc_xlsx):
    readings = read_binoc_readings(binoc_xlsx)
    assert [r.name for r in readings] == ["pt1", "pt2", "pt3"]
    assert readings[0].distance_m == pytest.approx(49.4)
    assert readings[0].angle_deg == pytest.approx(51)
    assert readings[0].instrument_height_m == pytest.approx(2.06)


@pytest.mark.unit
def test_binoc_duplicate_point_name_is_rejected(tmp_path):
    """The real 20260716 sheet lists pt4 twice; that must not pass silently."""
    path = _write_binoc(
        tmp_path / "dupe.xlsx",
        [("pt4", 54.6, 46, 2.08), ("pt4", 46.6, 58, 1.94)],
    )
    with pytest.raises(SurveyDataError, match="pt4"):
        read_binoc_readings(path)


@pytest.mark.unit
def test_binoc_rejects_out_of_range_angle(tmp_path):
    path = _write_binoc(tmp_path / "bad.xlsx", [("pt1", 49.4, 950, 2.06)])
    with pytest.raises(SurveyDataError, match="angle"):
        read_binoc_readings(path)


@pytest.mark.unit
def test_binoc_rejects_nonpositive_distance(tmp_path):
    path = _write_binoc(tmp_path / "bad.xlsx", [("pt1", 0, 51, 2.06)])
    with pytest.raises(SurveyDataError, match="distance"):
        read_binoc_readings(path)


# --- the join --------------------------------------------------------------


@pytest.mark.unit
def test_join_adds_binoc_height_to_ground_altitude(survey_csv, binoc_xlsx):
    survey = build_survey(
        read_stations(survey_csv), read_binoc_readings(binoc_xlsx), name="Cetran"
    )
    assert survey.name == "Cetran"
    assert len(survey.points) == 3
    pt1 = survey.points[0]
    assert pt1.altitude_m == pytest.approx(32.5729 + 2.06)  # ground + binoc height
    assert pt1.distance_m == pytest.approx(49.4)
    assert pt1.elevation_deg == pytest.approx(51)


@pytest.mark.unit
def test_join_matches_point_names_case_insensitively(survey_csv, binoc_xlsx):
    survey = build_survey(
        read_stations(survey_csv), read_binoc_readings(binoc_xlsx), name="x"
    )
    assert [p.label for p in survey.points] == ["Pt1", "Pt2", "Pt3"]


@pytest.mark.unit
def test_join_rejects_reading_with_no_surveyed_station(survey_csv, tmp_path):
    """Guards the mislabelled pt7/pt8 class of error."""
    binoc = _write_binoc(tmp_path / "b.xlsx", [("pt1", 49.4, 51, 2.06), ("pt9", 67.9, 36, 1.89)])
    with pytest.raises(SurveyDataError, match="pt9"):
        build_survey(read_stations(survey_csv), read_binoc_readings(binoc), name="x")


@pytest.mark.unit
def test_join_needs_at_least_three_points(survey_csv, tmp_path):
    binoc = _write_binoc(tmp_path / "b.xlsx", [("pt1", 49.4, 51, 2.06), ("pt2", 54.0, 46, 2.08)])
    with pytest.raises(SurveyDataError, match="at least 3"):
        build_survey(read_stations(survey_csv), read_binoc_readings(binoc), name="x")


@pytest.mark.unit
def test_surveyed_stations_without_a_binoc_reading_are_simply_unused(survey_csv, tmp_path):
    """Pt5, Pt6, Pt9, Pt10 were surveyed but never sighted -- not an error."""
    wide = tmp_path / "wide.csv"
    wide.write_text(
        _HEADER
        + _ROWS
        + "Pt5,,149949.3158,354623.1317,32.5942,1.35573836,103.69380824,32.5942,34.6602,2.0000,2.0660\n",
        encoding="latin-1",
    )
    binoc = _write_binoc(
        tmp_path / "b.xlsx",
        [("pt1", 49.4, 51, 2.06), ("pt2", 54.0, 46, 2.08), ("pt3", 54.6, 46, 2.08)],
    )
    survey = build_survey(read_stations(wide), read_binoc_readings(binoc), name="x")
    assert len(survey.points) == 3
