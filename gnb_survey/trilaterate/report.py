"""Human-readable and machine-readable (`--json`) rendering of a Solution."""

from __future__ import annotations

from dataclasses import asdict

from .models import CONDITION_WARN_THRESHOLD, Solution

# Flag the model when the survey's own fit is more than this far from the
# assumed sigma in either direction. Only the ratio of the two sigmas affects
# the solution, so this is a check on relative weighting, not absolute scale.
MODEL_CHECK_FACTOR = 2.0


def _model_check(sol: Solution) -> str | None:
    """Compare the assumed measurement model against what the data implies."""
    if sol.fitted_sigma_distance_m is None or sol.fitted_sigma_elevation_deg is None:
        return None
    if sol.assumed_sigma_distance_m is None or sol.assumed_sigma_elevation_deg is None:
        return None

    pairs = (
        (sol.fitted_sigma_distance_m, sol.assumed_sigma_distance_m),
        (sol.fitted_sigma_elevation_deg, sol.assumed_sigma_elevation_deg),
    )
    off = any(
        assumed <= 0.0
        or fitted / assumed > MODEL_CHECK_FACTOR
        or fitted / assumed < 1.0 / MODEL_CHECK_FACTOR
        for fitted, assumed in pairs
    )
    verdict = "<-- CHECK" if off else "ok"
    return (
        f"  Model check: assumed σ {sol.assumed_sigma_distance_m:.2f} m / "
        f"{sol.assumed_sigma_elevation_deg:.2f}°  ·  this survey fits "
        f"{sol.fitted_sigma_distance_m:.2f} m / "
        f"{sol.fitted_sigma_elevation_deg:.2f}°   {verdict}"
    )


def format_solution(sol: Solution) -> str:
    lines: list[str] = []
    lines.append(f"=== {sol.survey_name} gNB ===")
    lines.append(f"  Position : {sol.latitude:.7f}, {sol.longitude:.7f}   alt {sol.altitude_m:.1f} m")
    if sol.svy21_easting is not None and sol.svy21_northing is not None:
        lines.append(
            f"  SVY21    : E {sol.svy21_easting:.1f}  N {sol.svy21_northing:.1f}  (EPSG:3414)"
        )
    lines.append(
        f"  Uncertainty (1σ): horiz ±{sol.horiz_sigma_m:.1f} m "
        f"(ellipse {sol.ellipse_major_m:.1f}×{sol.ellipse_minor_m:.1f} m), "
        f"vert ±{sol.vert_sigma_m:.1f} m"
    )

    if sol.n_points < 3:
        geom = f"UNDER-CONSTRAINED ({sol.n_points} points)"
    elif sol.condition_number >= CONDITION_WARN_THRESHOLD:
        geom = f"WEAK — points too clustered (cond {sol.condition_number:.0f})"
    else:
        geom = f"OK (cond {sol.condition_number:.0f})"
    lines.append(f"  Geometry : {geom}   seed: {sol.seed_method}")

    check = _model_check(sol)
    if check is not None:
        lines.append(check)

    lines.append("  Residuals:")
    worst = max(sol.residuals, key=lambda r: abs(r.distance_residual_m), default=None)
    for r in sol.residuals:
        flag = "   <-- largest" if r is worst and len(sol.residuals) > 1 else ""
        lines.append(
            f"    {r.label:<22} dist {r.distance_residual_m:+5.1f} m   "
            f"elev {r.elevation_residual_deg:+4.1f}°{flag}"
        )
    return "\n".join(lines)


def solution_to_dict(sol: Solution) -> dict[str, object]:
    """Every field of `sol`, JSON-serializable, for `solve --json`.

    `well_constrained` is added because it is a derived property rather than
    a dataclass field, and it is exactly the thing a script polling for
    solve success would otherwise have to re-derive from n_points and
    condition_number by hand.
    """
    data = asdict(sol)
    data["well_constrained"] = sol.well_constrained
    return data
