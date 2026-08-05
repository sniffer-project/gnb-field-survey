"""The report states the assumed model and what the survey's data implies."""

import json

import pytest

from gnb_survey.trilaterate.models import PointResidual, Solution
from gnb_survey.trilaterate.report import format_solution, solution_to_dict


def _solution(**overrides) -> Solution:
    base = dict(
        survey_name="20260716",
        latitude=1.3555437,
        longitude=103.6937797,
        altitude_m=74.7,
        horiz_sigma_m=3.2,
        ellipse_major_m=3.2,
        ellipse_minor_m=0.7,
        vert_sigma_m=0.7,
        condition_number=34.0,
        n_points=6,
        residuals=(PointResidual("Pt1", 1.8, 0.4),),
        assumed_sigma_distance_m=2.0,
        assumed_sigma_elevation_deg=1.4,
    )
    base.update(overrides)
    return Solution(**base)


@pytest.mark.unit
def test_agreeing_fit_is_reported_without_a_warning():
    text = format_solution(_solution(fitted_sigma_distance_m=1.94, fitted_sigma_elevation_deg=1.43))
    assert "Model check" in text
    assert "1.94" in text and "1.43" in text
    assert "CHECK" not in text


@pytest.mark.unit
def test_disagreeing_fit_is_flagged():
    text = format_solution(_solution(fitted_sigma_distance_m=9.0, fitted_sigma_elevation_deg=1.43))
    assert "CHECK" in text


@pytest.mark.unit
def test_fit_far_below_the_assumption_is_also_flagged():
    text = format_solution(_solution(fitted_sigma_distance_m=0.1, fitted_sigma_elevation_deg=1.43))
    assert "CHECK" in text


@pytest.mark.unit
def test_no_model_check_line_when_the_fit_was_skipped():
    assert "Model check" not in format_solution(_solution())


@pytest.mark.unit
def test_survey_name_and_position_still_render():
    text = format_solution(_solution())
    assert "20260716 gNB" in text
    assert "1.3555437" in text


# --- machine-readable form (clig.dev: `--json` for machine consumers) ------


@pytest.mark.unit
def test_solution_to_dict_is_json_serializable():
    data = solution_to_dict(_solution(fitted_sigma_distance_m=1.94, fitted_sigma_elevation_deg=1.43))
    json.dumps(data)  # raises TypeError if anything isn't serializable


@pytest.mark.unit
def test_solution_to_dict_carries_the_headline_numbers():
    data = solution_to_dict(_solution())
    assert data["survey_name"] == "20260716"
    assert data["latitude"] == pytest.approx(1.3555437)
    assert data["longitude"] == pytest.approx(103.6937797)
    assert data["altitude_m"] == pytest.approx(74.7)
    assert data["horiz_sigma_m"] == pytest.approx(3.2)


@pytest.mark.unit
def test_solution_to_dict_includes_residuals_as_plain_dicts():
    """`asdict` keeps the tuple, but JSON has no tuple type -- it round-trips
    through `json.dumps`/`json.loads` as a list either way."""
    data = solution_to_dict(_solution())
    assert json.loads(json.dumps(data))["residuals"] == [
        {"label": "Pt1", "distance_residual_m": 1.8, "elevation_residual_deg": 0.4}
    ]


@pytest.mark.unit
def test_solution_to_dict_includes_well_constrained():
    well = solution_to_dict(_solution(n_points=6, condition_number=34.0))
    poorly = solution_to_dict(_solution(n_points=2, condition_number=34.0))
    assert well["well_constrained"] is True
    assert poorly["well_constrained"] is False
