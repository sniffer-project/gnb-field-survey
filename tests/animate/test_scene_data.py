"""Scene data must reproduce the solver's own ENU frame, not an approximation."""

from __future__ import annotations

import json
import math

import pytest

from gnb_survey.animate import scene_data
from gnb_survey.trilaterate import geo
from gnb_survey.trilaterate.models import Solution, Survey, SurveyPoint

_POINTS = (
    SurveyPoint("Pt1", 1.35579855, 103.69391447, 32.5729, 17.0, 82.3),
    SurveyPoint("Pt2", 1.35585427, 103.69387394, 33.6284, 17.0, 98.2),
    SurveyPoint("Pt3", 1.35588038, 103.69377627, 34.5987, 16.0, 97.8),
)
_SURVEY = Survey(name="20260716", points=_POINTS)
_SOLUTION = Solution(
    survey_name="20260716",
    latitude=1.35534,
    longitude=103.69447,
    altitude_m=54.2,
    horiz_sigma_m=1.8,
    ellipse_major_m=4.36,
    ellipse_minor_m=0.73,
    vert_sigma_m=2.1,
    condition_number=120.0,
    n_points=3,
    residuals=(),
    ellipse_azimuth_deg=118.2,
)


def test_first_point_is_the_enu_origin():
    scene = scene_data.build_scene(_SURVEY, _SOLUTION)
    first = scene["points"][0]
    assert first["label"] == "Pt1"
    assert first["e"] == pytest.approx(0.0, abs=1e-6)
    assert first["n"] == pytest.approx(0.0, abs=1e-6)


def test_gnb_enu_matches_a_direct_geo_conversion():
    """The scene must not reimplement the projection -- same origin, same call."""
    origin = geo.make_origin(
        _POINTS[0].latitude, _POINTS[0].longitude, _POINTS[0].altitude_m
    )
    expected_e, expected_n, _ = geo.to_enu(
        _SOLUTION.latitude, _SOLUTION.longitude, _SOLUTION.altitude_m, origin
    )

    scene = scene_data.build_scene(_SURVEY, _SOLUTION)

    assert scene["gnb_en"][0] == pytest.approx(expected_e, abs=1e-3)
    assert scene["gnb_en"][1] == pytest.approx(expected_n, abs=1e-3)


def test_distances_survive_the_round_trip():
    """A point's plotted offset from the gNB must equal its measured range."""
    scene = scene_data.build_scene(_SURVEY, _SOLUTION)
    gnb_e, gnb_n = scene["gnb_en"]
    up = _SOLUTION.altitude_m - _POINTS[0].altitude_m
    first = scene["points"][0]

    horizontal = math.hypot(gnb_e - first["e"], gnb_n - first["n"])
    slant = math.hypot(horizontal, up)

    # Within a few metres of the measured 82.3 m -- this is a fabricated
    # solution, so the check is that the frame is coherent, not that it fits.
    assert slant == pytest.approx(first["dist_m"], abs=15.0)


def test_srls_seed_is_included_when_the_solver_used_one():
    scene = scene_data.build_scene(_SURVEY, _SOLUTION)
    seed = scene["srls_seed_en"]
    assert seed is not None
    assert len(seed) == 2
    assert all(isinstance(v, float) for v in seed)


def test_no_srls_seed_when_the_solver_fell_back():
    """seed_method says the closed form was skipped, so there is none to draw."""
    import dataclasses

    fallback = dataclasses.replace(_SOLUTION, seed_method="azimuth-multistart")

    scene = scene_data.build_scene(_SURVEY, fallback)

    assert scene["srls_seed_en"] is None


def test_write_then_load_round_trips(tmp_path):
    path = tmp_path / "20260716_scene.json"
    scene_data.write_scene(_SURVEY, _SOLUTION, path)

    loaded = scene_data.load_scene(path)

    assert loaded["schema"] == scene_data.SCHEMA
    assert loaded["survey"] == "20260716"
    assert loaded["ellipse"]["azimuth_deg"] == pytest.approx(118.2)


def test_a_stale_schema_is_refused(tmp_path):
    """A scene file from an older version must not silently draw a wrong picture."""
    path = tmp_path / "old_scene.json"
    path.write_text(json.dumps({"schema": 0, "survey": "x"}), encoding="utf-8")

    with pytest.raises(ValueError, match="schema"):
        scene_data.load_scene(path)


@pytest.mark.parametrize(
    ("field", "malformed", "message"),
    [
        ("schema", True, "schema"),
        ("srls_seed_en", [], "srls_seed_en"),
        (
            "ellipse",
            {"major_m": 4.36, "azimuth_deg": 118.2},
            r"ellipse\.minor_m",
        ),
        ("points", [], "points"),
        ("points", [{"label": "Pt1", "e": 0.0}], r"points\[0\]\.n"),
        ("gnb_en", [1.0], "gnb_en"),
        ("gnb_en", [10**400, 0.0], "gnb_en"),
    ],
)
def test_a_malformed_schema_one_scene_is_refused(
    tmp_path, field, malformed, message
):
    data = scene_data.build_scene(_SURVEY, _SOLUTION)
    data[field] = malformed
    path = tmp_path / "malformed.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        scene_data.load_scene(path)
