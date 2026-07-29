"""Turn a solved survey into the numbers the animation draws.

The scene runs as a separate manimgl process, so it cannot be handed Python
objects -- it reads this JSON instead. The ENU frame is rebuilt exactly as
solver.solve_survey builds it (origin at the first point, same geo.to_enu),
so the picture is the solution rather than a redrawing of it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from ..triangulate import geo
from ..triangulate.models import Solution, Survey
from ..triangulate.report import format_solution
from ..triangulate.srls import srls_position

SCHEMA: int = 1


def _srls_seed(
    points: list[dict[str, Any]], survey: Survey, solution: Solution
) -> list[float] | None:
    """Return the horizontal SR-LS seed the animation shows before refinement.

    The scene is top-down, so this recomputes the public two-dimensional form
    from the same East/North anchors and ranges. When the solver says it used
    its SR-LS seed, this is the corresponding horizontal story beat.
    """
    if solution.seed_method != "srls":
        return None
    anchors = np.array([[p["e"], p["n"]] for p in points], dtype=float)
    ranges = np.array([p.distance_m for p in survey.points], dtype=float)
    try:
        seed = srls_position(anchors, ranges)
    except (ValueError, np.linalg.LinAlgError):
        return None
    return [round(float(seed[0]), 4), round(float(seed[1]), 4)]


def build_scene(survey: Survey, solution: Solution) -> dict[str, Any]:
    first = survey.points[0]
    origin = geo.make_origin(first.latitude, first.longitude, first.altitude_m)

    points: list[dict[str, Any]] = []
    for point in survey.points:
        east, north, _up = geo.to_enu(
            point.latitude, point.longitude, point.altitude_m, origin
        )
        points.append(
            {
                "label": point.label,
                "e": round(east, 4),
                "n": round(north, 4),
                "dist_m": point.distance_m,
                "elev_deg": point.elevation_deg,
            }
        )

    gnb_e, gnb_n, _gnb_u = geo.to_enu(
        solution.latitude, solution.longitude, solution.altitude_m, origin
    )

    return {
        "schema": SCHEMA,
        "survey": solution.survey_name,
        "origin": {
            "lat": origin.latitude,
            "lon": origin.longitude,
            "alt_m": origin.altitude_m,
        },
        "points": points,
        "gnb_en": [round(gnb_e, 4), round(gnb_n, 4)],
        "srls_seed_en": _srls_seed(points, survey, solution),
        "ellipse": {
            "major_m": solution.ellipse_major_m,
            "minor_m": solution.ellipse_minor_m,
            "azimuth_deg": solution.ellipse_azimuth_deg,
        },
        "result_lines": format_solution(solution).splitlines(),
    }


def write_scene(survey: Survey, solution: Solution, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_scene(survey, solution), indent=2), encoding="utf-8"
    )
    return path


def load_scene(path: Path) -> dict[str, Any]:
    """Read scene data, refusing anything this version cannot draw correctly."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    found = data.get("schema")
    if found != SCHEMA:
        raise ValueError(
            f"{path} has scene schema {found!r}, expected {SCHEMA}. "
            "Re-run `python survey.py <name> solve` to regenerate it."
        )
    return data
