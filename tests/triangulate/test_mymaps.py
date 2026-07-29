"""The exported CSV carries the gNB and a 95% ellipse ring, not a bare pin."""

import csv
import math

import pytest

from gnb_survey.triangulate.models import PointResidual, Solution
from gnb_survey.triangulate.mymaps import (
    CONFIDENCE_SCALE,
    HEADER,
    RING_POINTS,
    ellipse_ring,
    write_csv,
)

_LAT, _LON = 1.3555437, 103.6937797
_M_PER_DEG_LAT = 110574.0


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


def _metres_from_centre(lat: float, lon: float) -> tuple[float, float]:
    m_per_deg_lon = 111320.0 * math.cos(math.radians(_LAT))
    return (lon - _LON) * m_per_deg_lon, (lat - _LAT) * _M_PER_DEG_LAT


@pytest.mark.unit
def test_confidence_scale_is_the_two_dimensional_95_percent_factor():
    """1 sigma in 2-D is only 39%; 95% needs 2.4477 sigma."""
    assert CONFIDENCE_SCALE == pytest.approx(math.sqrt(-2.0 * math.log(0.05)), abs=1e-9)
    assert CONFIDENCE_SCALE == pytest.approx(2.4477, abs=1e-4)


@pytest.mark.unit
def test_ring_has_the_expected_number_of_points():
    assert len(ellipse_ring(_solution())) == RING_POINTS


@pytest.mark.unit
def test_ring_extremes_match_the_scaled_semi_axes():
    ring = ellipse_ring(_solution())
    radii = [math.hypot(*_metres_from_centre(lat, lon)) for lat, lon in ring]
    assert max(radii) == pytest.approx(CONFIDENCE_SCALE * 3.2, abs=0.01)
    assert min(radii) == pytest.approx(CONFIDENCE_SCALE * 0.7, abs=0.01)


@pytest.mark.unit
def test_north_south_ellipse_is_longest_along_north():
    """azimuth 0 means the major axis runs north-south."""
    ring = ellipse_ring(_solution(ellipse_azimuth_deg=0.0))
    farthest = max(ring, key=lambda p: math.hypot(*_metres_from_centre(*p)))
    east, north = _metres_from_centre(*farthest)
    assert abs(north) > abs(east)
    assert abs(north) == pytest.approx(CONFIDENCE_SCALE * 3.2, abs=0.02)


@pytest.mark.unit
def test_east_west_ellipse_is_longest_along_east():
    ring = ellipse_ring(_solution(ellipse_azimuth_deg=90.0))
    farthest = max(ring, key=lambda p: math.hypot(*_metres_from_centre(*p)))
    east, north = _metres_from_centre(*farthest)
    assert abs(east) > abs(north)


@pytest.mark.unit
def test_a_circular_covariance_gives_a_constant_radius():
    ring = ellipse_ring(_solution(ellipse_major_m=2.0, ellipse_minor_m=2.0))
    radii = [math.hypot(*_metres_from_centre(lat, lon)) for lat, lon in ring]
    assert max(radii) - min(radii) < 0.01
    assert radii[0] == pytest.approx(CONFIDENCE_SCALE * 2.0, abs=0.01)


@pytest.mark.unit
def test_every_ring_point_lies_on_the_ellipse():
    """(x/A)^2 + (y/B)^2 == 1 in the ellipse's own frame."""
    solution = _solution(ellipse_azimuth_deg=0.0)
    semi_major = CONFIDENCE_SCALE * solution.ellipse_major_m
    semi_minor = CONFIDENCE_SCALE * solution.ellipse_minor_m
    for lat, lon in ellipse_ring(solution):
        east, north = _metres_from_centre(lat, lon)
        # azimuth 0: major axis is north, minor is east
        assert (north / semi_major) ** 2 + (east / semi_minor) ** 2 == pytest.approx(
            1.0, abs=0.001
        )


@pytest.mark.unit
def test_write_csv_produces_header_and_thirty_seven_rows(tmp_path):
    out = tmp_path / "gnb.csv"
    written = write_csv(_solution(), out)
    assert written == RING_POINTS + 1

    with out.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert tuple(rows[0]) == HEADER
    assert len(rows) == RING_POINTS + 2  # header + gNB + ring


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


@pytest.mark.unit
def test_ring_rows_are_labelled_and_sort_in_order(tmp_path):
    out = tmp_path / "gnb.csv"
    write_csv(_solution(), out)
    with out.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ring = rows[1:]
    assert len(ring) == RING_POINTS
    assert ring[0]["Point Name"] == "20260716 95% ring 01"
    assert ring[-1]["Point Name"] == f"20260716 95% ring {RING_POINTS:02d}"
    assert all(r["Code"] == "ellipse95" for r in ring)
    assert [r["Point Name"] for r in ring] == sorted(r["Point Name"] for r in ring)


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
def test_refuses_to_write_without_an_orientation(tmp_path):
    out = tmp_path / "gnb.csv"
    with pytest.raises(ValueError, match="orientation"):
        write_csv(_solution(ellipse_azimuth_deg=None), out)
    assert not out.exists()


@pytest.mark.unit
def test_missing_output_directory_is_reported(tmp_path):
    with pytest.raises(ValueError, match="directory"):
        write_csv(_solution(), tmp_path / "nope" / "gnb.csv")
