"""Sigmas are inputs, and the campaign's own fit is reported beside them."""

import math

import pytest

from gnb_survey.triangulate import geo
from gnb_survey.triangulate.models import Campaign, SurveyPoint
from gnb_survey.triangulate.solver import SIGMA_DISTANCE_M, SIGMA_ELEVATION_DEG, solve_campaign

# A gNB 40 m up and off to one side, seen from four spread points.
#
# The readings are generated with the SAME geo.to_enu the solver uses, and the
# first point sits exactly on the origin the solver will pick (it builds its
# origin from points[0]). That makes the synthetic data exactly consistent, so
# residuals land at machine precision. Generating them from an approximate
# metres-per-degree formula instead would leave centimetre residuals and the
# "perfect fit" test below would silently stop testing anything.
_ORIGIN_LAT, _ORIGIN_LON, _ORIGIN_ALT = 1.35570, 103.69390, 30.0
_GNB_ENU = (12.0, 25.0, 40.0)  # east, north, up in metres from that origin


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
def clean_campaign() -> Campaign:
    return Campaign(
        name="synthetic",
        points=(
            _exact_point("A", 0.0, 0.0, _ORIGIN_ALT),  # exactly on the origin
            _exact_point("B", 0.00005, 0.00030, 31.0),
            _exact_point("C", 0.00020, -0.00020, 32.0),
            _exact_point("D", -0.00010, -0.00030, 30.5),
        ),
    )


@pytest.mark.unit
def test_defaults_are_unchanged():
    """Published 20260716 results must stay reproducible."""
    assert SIGMA_DISTANCE_M == 2.0
    assert SIGMA_ELEVATION_DEG == 1.4


@pytest.mark.unit
def test_solve_campaign_still_accepts_one_argument(clean_campaign):
    solution = solve_campaign(clean_campaign)
    assert solution.assumed_sigma_distance_m == SIGMA_DISTANCE_M
    assert solution.assumed_sigma_elevation_deg == SIGMA_ELEVATION_DEG


@pytest.mark.unit
def test_scaling_both_sigmas_changes_nothing(clean_campaign):
    """_covariance rescales by rss/dof, so only the ratio can matter."""
    base = solve_campaign(clean_campaign, 2.0, 1.4)
    scaled = solve_campaign(clean_campaign, 20.0, 14.0)
    assert scaled.latitude == pytest.approx(base.latitude, abs=1e-9)
    assert scaled.longitude == pytest.approx(base.longitude, abs=1e-9)
    assert scaled.horiz_sigma_m == pytest.approx(base.horiz_sigma_m, rel=1e-6)


@pytest.fixture()
def noisy_campaign(clean_campaign) -> Campaign:
    """The same geometry with the readings perturbed, so residuals exist.

    Weighting is invisible on a perfect fit -- any ratio reproduces exact data
    exactly -- so anything about relative weights has to be tested on data that
    disagrees with itself.
    """
    return Campaign(
        name="noisy",
        points=tuple(
            SurveyPoint(
                label=p.label,
                latitude=p.latitude,
                longitude=p.longitude,
                altitude_m=p.altitude_m,
                elevation_deg=p.elevation_deg + bump,
                distance_m=p.distance_m + shift,
            )
            for p, shift, bump in zip(
                clean_campaign.points, (1.5, -1.0, 2.0, -1.5), (1.0, -0.8, 1.2, -1.0)
            )
        ),
    )


@pytest.mark.unit
def test_changing_the_ratio_changes_the_answer(noisy_campaign):
    trust_angles = solve_campaign(noisy_campaign, 2.0, 0.05)
    trust_distances = solve_campaign(noisy_campaign, 2.0, 5.0)
    assert trust_angles.altitude_m != pytest.approx(trust_distances.altitude_m, abs=1e-6)


@pytest.mark.unit
def test_a_perfect_fit_reports_no_calibration(clean_campaign):
    """Nothing can be learned about noise from noiseless data."""
    solution = solve_campaign(clean_campaign)
    assert solution.fitted_sigma_distance_m is None
    assert solution.fitted_sigma_elevation_deg is None


@pytest.mark.unit
def test_noisy_data_reports_a_fit(noisy_campaign):
    solution = solve_campaign(noisy_campaign)
    assert solution.fitted_sigma_distance_m > 0.0
    assert solution.fitted_sigma_elevation_deg > 0.0
    # Reported only -- the assumed values are what was actually used.
    assert solution.assumed_sigma_distance_m == SIGMA_DISTANCE_M


@pytest.mark.unit
def test_the_minimum_three_points_still_solves_and_does_not_crash_the_fit():
    """dof is 1.5 at n=3 -- positive, so the fit runs rather than being skipped."""
    minimal = Campaign(
        name="three",
        points=(
            _exact_point("A", 0.0, 0.0, _ORIGIN_ALT),
            _exact_point("B", 0.00005, 0.00030, 31.0),
            _exact_point("C", 0.00020, -0.00020, 32.0),
        ),
    )
    solution = solve_campaign(minimal)
    assert solution.n_points == 3
    assert solution.assumed_sigma_distance_m == SIGMA_DISTANCE_M
