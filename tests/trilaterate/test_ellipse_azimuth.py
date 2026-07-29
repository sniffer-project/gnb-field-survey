"""The solver keeps which way the error ellipse points, not just its size."""

import math

import pytest

from gnb_survey.trilaterate import geo
from gnb_survey.trilaterate.models import Survey, SurveyPoint
from gnb_survey.trilaterate.solver import solve_survey

_ORIGIN_LAT, _ORIGIN_LON, _ORIGIN_ALT = 1.35570, 103.69390, 30.0
_GNB_ENU = (12.0, 25.0, 40.0)


def _exact_point(label: str, d_lat: float, d_lon: float, alt: float) -> SurveyPoint:
    lat, lon = _ORIGIN_LAT + d_lat, _ORIGIN_LON + d_lon
    origin = geo.make_origin(_ORIGIN_LAT, _ORIGIN_LON, _ORIGIN_ALT)
    east, north, up = geo.to_enu(lat, lon, alt, origin)
    dx, dy, dz = _GNB_ENU[0] - east, _GNB_ENU[1] - north, _GNB_ENU[2] - up
    horiz = math.hypot(dx, dy)
    return SurveyPoint(
        label=label,
        latitude=lat,
        longitude=lon,
        altitude_m=alt,
        elevation_deg=math.degrees(math.atan2(dz, horiz)),
        distance_m=math.hypot(horiz, dz),
    )


@pytest.fixture()
def survey() -> Survey:
    return Survey(
        name="synthetic",
        points=(
            _exact_point("A", 0.0, 0.0, _ORIGIN_ALT),
            _exact_point("B", 0.00005, 0.00030, 31.0),
            _exact_point("C", 0.00020, -0.00020, 32.0),
            _exact_point("D", -0.00010, -0.00030, 30.5),
        ),
    )


@pytest.mark.unit
def test_azimuth_is_populated(survey):
    solution = solve_survey(survey)
    assert solution.ellipse_azimuth_deg is not None


@pytest.mark.unit
def test_azimuth_is_a_bearing_in_the_half_circle(survey):
    """An axis has no direction, so 190 degrees and 10 degrees are the same axis."""
    azimuth = solve_survey(survey).ellipse_azimuth_deg
    assert 0.0 <= azimuth < 180.0


@pytest.mark.unit
def test_major_axis_is_at_least_as_long_as_the_minor(survey):
    solution = solve_survey(survey)
    assert solution.ellipse_major_m >= solution.ellipse_minor_m


@pytest.mark.integration
def test_real_survey_azimuth_is_reported():
    from pathlib import Path

    from gnb_survey.trilaterate.binoc import read_binoc_readings
    from gnb_survey.trilaterate.assemble import build_survey
    from gnb_survey.trilaterate.mappro import read_stations

    fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    if not fixtures.is_dir():
        pytest.skip("fixtures not present")
    real = build_survey(
        read_stations(fixtures / "surveys" / "20260716" / "mappro" / "20260716_dd (Decimal).csv"),
        read_binoc_readings(fixtures / "surveys" / "20260716" / "binoc" / "20260716_measurment_binoc.xlsx"),
        name="20260716",
    )
    solution = solve_survey(real)
    assert 0.0 <= solution.ellipse_azimuth_deg < 180.0
    # The ellipse is markedly elongated, so its direction is meaningful.
    assert solution.ellipse_major_m > 2.0 * solution.ellipse_minor_m
