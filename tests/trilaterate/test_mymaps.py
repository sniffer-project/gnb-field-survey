"""The exported CSV is one gNB pin; its uncertainty rides along as text."""

import csv
import math

import pytest

from gnb_survey.trilaterate.models import PointResidual, Solution
from gnb_survey.trilaterate.mymaps import (
    CONFIDENCE_SCALE,
    HEADER,
    uncertainty_note,
    write_csv,
)

_LAT, _LON = 1.3555437, 103.6937797


def _solution(**overrides) -> Solution:
    base = dict(
        survey_name="20260716",
        latitude=_LAT,
        longitude=_LON,
        altitude_m=74.7,
        horiz_sigma_m=3.2,
        ellipse_major_m=3.2,
        ellipse_minor_m=0.7,
        vert_sigma_m=0.7,
        condition_number=34.0,
        n_points=6,
        residuals=(PointResidual("Pt1", 1.8, 0.4),),
        ellipse_azimuth_deg=0.0,  # major axis runs north-south
    )
    base.update(overrides)
    return Solution(**base)


@pytest.mark.unit
def test_confidence_scale_is_the_two_dimensional_95_percent_factor():
    """1 sigma in 2-D is only 39%; 95% needs 2.4477 sigma."""
    assert CONFIDENCE_SCALE == pytest.approx(math.sqrt(-2.0 * math.log(0.05)), abs=1e-9)
    assert CONFIDENCE_SCALE == pytest.approx(2.4477, abs=1e-4)


@pytest.mark.unit
def test_uncertainty_note_reports_full_axes_and_bearing():
    note = uncertainty_note(_solution(ellipse_azimuth_deg=118.2))
    major = 2.0 * CONFIDENCE_SCALE * 3.2
    minor = 2.0 * CONFIDENCE_SCALE * 0.7
    assert note == f"95% ellipse {major:.1f} x {minor:.1f} m @ 118 deg"


@pytest.mark.unit
def test_uncertainty_note_omits_an_unknown_bearing():
    assert uncertainty_note(_solution(ellipse_azimuth_deg=None)).endswith(" m")


@pytest.mark.unit
def test_write_csv_produces_a_header_and_a_single_row(tmp_path):
    out = tmp_path / "gnb.csv"
    write_csv(_solution(), out)

    with out.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert tuple(rows[0]) == HEADER
    assert len(rows) == 2  # header + gNB


@pytest.mark.unit
def test_gnb_row_carries_the_solution(tmp_path):
    out = tmp_path / "gnb.csv"
    write_csv(_solution(), out)
    with out.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["Point Name"] == "20260716 gNB"
    assert row["Code"] == "gNB"
    assert float(row["Latitude"]) == pytest.approx(_LAT)
    assert float(row["Altitude"]) == pytest.approx(74.7)
    assert row["Measuring type"] == "Trilaterated"
    assert "6 pts" in row["Measurement Method"]
    assert "95% ellipse" in row["Measurement Method"]


@pytest.mark.unit
def test_an_unknown_orientation_still_writes_the_pin(tmp_path):
    """The bearing is decoration on a pin; only a ring needed it."""
    out = tmp_path / "gnb.csv"
    write_csv(_solution(ellipse_azimuth_deg=None), out)
    assert out.is_file()


@pytest.mark.unit
def test_northing_and_easting_are_left_blank(tmp_path):
    """My Maps positions by Latitude/Longitude; the columns exist for concat only."""
    out = tmp_path / "gnb.csv"
    write_csv(_solution(), out)
    with out.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["Northing"] == ""
    assert row["Easting"] == ""


@pytest.mark.unit
def test_missing_output_directory_is_reported(tmp_path):
    with pytest.raises(ValueError, match="directory"):
        write_csv(_solution(), tmp_path / "nope" / "gnb.csv")
