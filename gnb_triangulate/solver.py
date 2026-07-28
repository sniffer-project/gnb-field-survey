"""Weighted 3-D least-squares triangulation of a gNB.

For each survey point we form two weighted residuals -- one on the slant
distance, one on the elevation angle -- and let Levenberg-Marquardt find the
gNB position (East, North, Up) that best satisfies all of them at once. The
solver's Jacobian then yields a covariance matrix, giving honest 1-sigma
uncertainties instead of a false-precision point.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import least_squares

from . import geo
from .models import Campaign, PointResidual, Solution
from .srls import srls_position

# --- Instrument / measurement model (tunable in one place) ------------------
# Only the RATIO of these two matters to the reported uncertainty: _covariance
# rescales by the a posteriori variance factor (rss/dof), so multiplying both
# by any constant leaves the solution and its covariance unchanged. Set them to
# realistic *relative* weights; the absolute scale calibrates itself.
#
# These are DEFAULTS, not instrument constants, and not properties of any one
# campaign. Override per run with --sigma-distance / --sigma-elevation.
#
# Distance: the Geovid R manual (Geovid R/EN/2022/06/1, p.18) gives accuracy as
# an explicit 1 sigma below 350 m -- +/-1 m in normal operation, +/-2 m in scan
# mode. 2.0 is kept as the default because the 20260716 campaign fits 1.94 m,
# but a campaign shot in normal mode may well justify 1.0.
SIGMA_DISTANCE_M = 2.0

# Elevation: the Geovid R manual specifies NO angle accuracy, and documents no
# angle readout at all -- it displays distance and Equivalent Horizontal Range
# (p.18). So this cannot be sourced from any instrument spec. 1.4 is a working
# default, close to the 1.43 deg that 20260716 fits and comfortably above the
# +/-0.5 deg that whole-degree recording contributes by rounding alone.
#
# Every run reports what the campaign's own residuals imply, so a campaign that
# disagrees with these defaults says so instead of inheriting them silently.
SIGMA_ELEVATION_DEG = 1.4
# Each point's altitude is already the ground mark plus the height the
# binoculars were held at, applied per point when the campaign is built
# (campaign.py). The solver therefore adds no instrument offset of its own --
# there is no single one to add, as the handheld height varied 1.89-2.08 m.


def _enu_points(campaign: Campaign, origin: geo.Origin) -> np.ndarray:
    """Stack the campaign's points as an (N, 3) array of ENU metres."""
    rows = []
    for p in campaign.points:
        e, n, u = geo.to_enu(p.latitude, p.longitude, p.altitude_m, origin)
        rows.append((e, n, u))
    return np.asarray(rows, dtype=float)


def _residuals(
    unknown: np.ndarray,
    pts: np.ndarray,
    dist: np.ndarray,
    elev_rad: np.ndarray,
    sigma_dist_m: float,
    sigma_elev_rad: float,
) -> np.ndarray:
    """Weighted residual vector: [dist residuals..., elevation residuals...]."""
    raw_dist, raw_elev_rad = _raw_residuals(unknown, pts, dist, elev_rad)
    return np.concatenate([raw_dist / sigma_dist_m, raw_elev_rad / sigma_elev_rad])


def _raw_residuals(
    unknown: np.ndarray, pts: np.ndarray, dist: np.ndarray, elev_rad: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Unweighted (predicted - measured) in metres and radians."""
    dx = unknown[0] - pts[:, 0]
    dy = unknown[1] - pts[:, 1]
    dz = unknown[2] - pts[:, 2]
    horiz = np.sqrt(dx * dx + dy * dy)
    slant = np.sqrt(horiz * horiz + dz * dz)
    return slant - dist, np.arctan2(dz, horiz) - elev_rad


# Fallback only: if the closed-form SR-LS seed is unavailable (degenerate
# geometry), seed the optimiser from several compass directions instead.
_N_AZIMUTH_STARTS = 24


def _elevation_height(xy: np.ndarray, pts: np.ndarray, dist: np.ndarray, elev_rad: np.ndarray) -> float:
    """Up-coordinate implied by the elevation angles at a fixed (E, N).

    SR-LS uses distances only; with near-coplanar anchors the vertical is weak
    and could mirror below the plane. Deriving Z from the (positive) elevation
    angles fixes the correct above-plane height before refinement.
    """
    horiz = np.hypot(xy[0] - pts[:, 0], xy[1] - pts[:, 1])
    z_est = pts[:, 2] + horiz * np.tan(elev_rad)
    return float(np.median(z_est))


def _srls_guess(pts: np.ndarray, dist: np.ndarray, elev_rad: np.ndarray) -> np.ndarray:
    """Globally optimal SR-LS horizontal seed, with elevation-derived height."""
    pos = srls_position(pts, dist)            # may raise on degenerate geometry
    z = _elevation_height(pos[:2], pts, dist, elev_rad)
    return np.array([pos[0], pos[1], z])


def _azimuth_guesses(pts: np.ndarray, dist: np.ndarray, elev_rad: np.ndarray) -> list[np.ndarray]:
    """Fallback ring of starting points around the centroid, one per azimuth."""
    centroid = pts.mean(axis=0)
    horiz = float(np.mean(dist * np.cos(elev_rad)))
    up = float(np.mean(dist * np.sin(elev_rad)))
    guesses = []
    for k in range(_N_AZIMUTH_STARTS):
        az = 2.0 * math.pi * k / _N_AZIMUTH_STARTS
        east = centroid[0] + horiz * math.sin(az)
        north = centroid[1] + horiz * math.cos(az)
        guesses.append(np.array([east, north, centroid[2] + up]))
    return guesses


def _covariance(result, n_obs: int, n_unknown: int) -> np.ndarray:
    """Approximate parameter covariance from the least-squares Jacobian."""
    jac = result.jac
    dof = max(n_obs - n_unknown, 1)
    rss = float(np.sum(result.fun ** 2))
    sigma2 = rss / dof
    jtj = jac.T @ jac
    try:
        cov = np.linalg.inv(jtj) * sigma2
    except np.linalg.LinAlgError:
        cov = np.linalg.pinv(jtj) * sigma2
    return cov


# Variance-component iteration settings. The fit converges in a handful of
# passes; the cap only guards against a pathological campaign.
_FIT_MAX_ITERATIONS = 40
_FIT_TOLERANCE = 1e-6
# Below this a residual set carries no information about noise -- synthetic or
# exactly-determined data lands here, and dividing by it would blow up.
_FIT_FLOOR = 1e-9


def _least_squares(
    pts: np.ndarray,
    dist: np.ndarray,
    elev_rad: np.ndarray,
    sigma_dist_m: float,
    sigma_elev_deg: float,
    seeds: list[np.ndarray],
):
    """Refine from every seed, keeping the lowest-cost fit."""
    best = None
    best_cost = math.inf
    sigma_elev_rad = math.radians(sigma_elev_deg)
    for x0 in seeds:
        candidate = least_squares(
            _residuals,
            x0,
            args=(pts, dist, elev_rad, sigma_dist_m, sigma_elev_rad),
            method="lm",
        )
        if candidate.cost < best_cost:
            best_cost = candidate.cost
            best = candidate
    return best


def _fit_sigmas(
    pts: np.ndarray,
    dist: np.ndarray,
    elev_rad: np.ndarray,
    solved: np.ndarray,
    sigma_dist_m: float,
    sigma_elev_deg: float,
) -> tuple[float | None, float | None]:
    """What this campaign's own residuals imply the two sigmas are.

    Reported only. Three parameters are shared across two equal observation
    groups, so each group carries n - 1.5 degrees of freedom. Returns
    (None, None) when the data cannot support an estimate.

    Reweighting moves the solution by centimetres, so each pass is seeded from
    the already-converged answer rather than the full seed set -- otherwise the
    azimuth-multistart fallback would run 24 seeds x 40 passes.
    """
    n = len(dist)
    dof = n - 1.5
    if n < 3 or dof <= 0.0:
        return None, None

    seeds = [solved]
    for _ in range(_FIT_MAX_ITERATIONS):
        result = _least_squares(pts, dist, elev_rad, sigma_dist_m, sigma_elev_deg, seeds)
        if result is None:
            return None, None
        raw_dist, raw_elev_rad = _raw_residuals(result.x, pts, dist, elev_rad)
        next_dist = math.sqrt(float(np.sum(raw_dist ** 2)) / dof)
        next_elev = math.sqrt(float(np.sum(np.degrees(raw_elev_rad) ** 2)) / dof)
        if next_dist < _FIT_FLOOR or next_elev < _FIT_FLOOR:
            return None, None
        converged = (
            abs(next_dist - sigma_dist_m) < _FIT_TOLERANCE
            and abs(next_elev - sigma_elev_deg) < _FIT_TOLERANCE
        )
        sigma_dist_m, sigma_elev_deg = next_dist, next_elev
        if converged:
            break
    return sigma_dist_m, sigma_elev_deg


def solve_campaign(
    campaign: Campaign,
    sigma_distance_m: float = SIGMA_DISTANCE_M,
    sigma_elevation_deg: float = SIGMA_ELEVATION_DEG,
) -> Solution:
    """Triangulate the gNB for one campaign."""
    origin = geo.make_origin(
        campaign.points[0].latitude,
        campaign.points[0].longitude,
        campaign.points[0].altitude_m,
    )
    pts = _enu_points(campaign, origin)
    dist = np.array([p.distance_m for p in campaign.points], dtype=float)
    elev_rad = np.array([math.radians(p.elevation_deg) for p in campaign.points], dtype=float)

    # Primary: refine once from the globally optimal SR-LS seed. Fall back to
    # the azimuth multi-start only if SR-LS is degenerate, and always keep the
    # lowest-cost fit (defence-in-depth).
    seed_method = "srls"
    seeds: list[np.ndarray] = []
    try:
        seeds.append(_srls_guess(pts, dist, elev_rad))
    except (ValueError, np.linalg.LinAlgError):
        seed_method = "azimuth-multistart"
    if seed_method != "srls":
        seeds.extend(_azimuth_guesses(pts, dist, elev_rad))

    result = _least_squares(pts, dist, elev_rad, sigma_distance_m, sigma_elevation_deg, seeds)

    east, north, up = result.x
    lat, lon, alt = geo.to_geodetic(east, north, up, origin)

    n_obs = 2 * len(campaign.points)
    cov = _covariance(result, n_obs, 3)
    horiz_cov = cov[:2, :2]
    # eigh, not eigvalsh: the eigenvectors are what tell us which way the
    # ellipse points. Eigenvalues are identical either way, so no existing
    # number moves. Ascending order, eigenvectors as columns -- so column 1
    # belongs to the larger eigenvalue and is the major axis.
    eigvals, eigvecs = np.linalg.eigh(horiz_cov)
    eigvals = np.clip(eigvals, 0.0, None)
    ellipse_minor, ellipse_major = math.sqrt(eigvals[0]), math.sqrt(eigvals[1])
    major_east, major_north = float(eigvecs[0, 1]), float(eigvecs[1, 1])
    # horiz_cov is ordered (east, north), so atan2(east, north) is a compass
    # bearing. Modulo 180 because the axis is undirected.
    ellipse_azimuth = math.degrees(math.atan2(major_east, major_north)) % 180.0
    horiz_sigma = math.sqrt(max(horiz_cov[0, 0] + horiz_cov[1, 1], 0.0))
    vert_sigma = math.sqrt(max(cov[2, 2], 0.0))

    jtj = result.jac.T @ result.jac
    condition = float(np.linalg.cond(jtj))

    residuals = _point_residuals(result.x, pts, campaign, dist, elev_rad)
    svy21 = geo.to_svy21(lat, lon)
    fitted_dist, fitted_elev = _fit_sigmas(
        pts, dist, elev_rad, result.x, sigma_distance_m, sigma_elevation_deg
    )

    return Solution(
        campaign_name=campaign.name,
        latitude=lat,
        longitude=lon,
        altitude_m=alt,
        horiz_sigma_m=horiz_sigma,
        ellipse_major_m=ellipse_major,
        ellipse_minor_m=ellipse_minor,
        ellipse_azimuth_deg=ellipse_azimuth,
        vert_sigma_m=vert_sigma,
        condition_number=condition,
        n_points=len(campaign.points),
        residuals=residuals,
        seed_method=seed_method,
        svy21_easting=svy21[0] if svy21 else None,
        svy21_northing=svy21[1] if svy21 else None,
        assumed_sigma_distance_m=sigma_distance_m,
        assumed_sigma_elevation_deg=sigma_elevation_deg,
        fitted_sigma_distance_m=fitted_dist,
        fitted_sigma_elevation_deg=fitted_elev,
    )


def _point_residuals(unknown, pts, campaign, dist, elev_rad) -> tuple[PointResidual, ...]:
    """Per-point physical residuals (metres, degrees) for the report table."""
    dx = unknown[0] - pts[:, 0]
    dy = unknown[1] - pts[:, 1]
    dz = unknown[2] - pts[:, 2]
    horiz = np.sqrt(dx * dx + dy * dy)
    slant = np.sqrt(horiz * horiz + dz * dz)
    pred_elev = np.degrees(np.arctan2(dz, horiz))

    out = []
    for i, p in enumerate(campaign.points):
        out.append(
            PointResidual(
                label=p.label,
                distance_residual_m=float(slant[i] - dist[i]),
                elevation_residual_deg=float(pred_elev[i] - math.degrees(elev_rad[i])),
            )
        )
    return tuple(out)
