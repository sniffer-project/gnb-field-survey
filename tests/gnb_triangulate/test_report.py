"""The report states the assumed model and what the campaign's data implies."""

import pytest

from gnb_triangulate.models import PointResidual, Solution
from gnb_triangulate.report import format_solution


def _solution(**overrides) -> Solution:
    base = dict(
        campaign_name="20260716",
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
def test_campaign_name_and_position_still_render():
    text = format_solution(_solution())
    assert "20260716 gNB" in text
    assert "1.3555437" in text
