"""Solver correctness against a synthetic gNB with known truth."""

import math

import numpy as np

from gnb_survey.triangulate import geo
from gnb_survey.triangulate.models import Campaign, SurveyPoint
from gnb_survey.triangulate.solver import solve_campaign

# A realistic Hall-14-like cluster of survey points (lat, lon, alt).
_POINT_COORDS = [
    ("pt1", 1.3528553, 103.6816590, 27.54),
    ("pt2", 1.3528920, 103.6817160, 27.61),
    ("pt3", 1.3529674, 103.6815798, 24.94),
    ("pt5", 1.3531019, 103.6817632, 24.90),
    ("pt6", 1.3531431, 103.6818504, 24.83),
]


def _synthesise(true_lat, true_lon, true_alt, noise_d=0.0, noise_e=0.0, seed=0):
    """Build a Campaign whose readings point exactly (+noise) at a known gNB."""
    rng = np.random.default_rng(seed)
    origin = geo.make_origin(true_lat, true_lon, true_alt)
    gx, gy, gz = geo.to_enu(true_lat, true_lon, true_alt, origin)

    points = []
    for label, lat, lon, alt in _POINT_COORDS:
        px, py, pu = geo.to_enu(lat, lon, alt, origin)
        dx, dy, dz = gx - px, gy - py, gz - pu
        horiz = math.hypot(dx, dy)
        slant = math.sqrt(horiz * horiz + dz * dz)
        elev = math.degrees(math.atan2(dz, horiz))
        slant += rng.normal(0.0, noise_d)
        elev += rng.normal(0.0, noise_e)
        points.append(SurveyPoint(label, lat, lon, alt, elev, slant))
    return Campaign("synthetic", tuple(points))


def test_recovers_noise_free_truth():
    true = (1.353150, 103.681700, 51.0)
    campaign = _synthesise(*true)
    sol = solve_campaign(campaign)

    origin = geo.make_origin(*true)
    e, n, _ = geo.to_enu(sol.latitude, sol.longitude, sol.altitude_m, origin)
    assert math.hypot(e, n) < 0.05      # within 5 cm horizontally
    assert abs(sol.altitude_m - true[2]) < 0.05


def test_reported_sigma_brackets_error_under_noise():
    true = (1.353150, 103.681700, 51.0)
    errors = []
    within = 0
    trials = 30
    for seed in range(trials):
        campaign = _synthesise(*true, noise_d=1.0, noise_e=0.3, seed=seed)
        sol = solve_campaign(campaign)
        origin = geo.make_origin(*true)
        e, n, _ = geo.to_enu(sol.latitude, sol.longitude, sol.altitude_m, origin)
        err = math.hypot(e, n)
        errors.append(err)
        if err <= 3.0 * max(sol.horiz_sigma_m, 1e-6):
            within += 1
    # Most trials should fall inside the reported 3-sigma horizontal bound.
    assert within >= int(0.8 * trials)
    assert np.median(errors) < 10.0  # clustered geometry, but still sane


def test_solution_carries_per_point_residuals():
    sol = solve_campaign(_synthesise(1.353150, 103.681700, 51.0))
    assert len(sol.residuals) == len(_POINT_COORDS)
    # Noise-free fit -> residuals essentially zero.
    assert max(abs(r.distance_residual_m) for r in sol.residuals) < 0.05
