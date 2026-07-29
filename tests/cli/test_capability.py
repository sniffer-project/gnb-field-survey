"""Each verb reports whether it can run, and if not, what to do about it."""

from __future__ import annotations

from pathlib import Path

from gnb_survey.cli.capability import (
    animate_blocked,
    blocked_for,
    convert_blocked,
    solve_blocked,
)
from gnb_survey.trilaterate.discovery import SurveyFiles

_CSV = Path("/p/data/raw/surveys/20260722/mappro/dd (Decimal).csv")
_XLSX = Path("/p/data/raw/surveys/20260722/binoc/20260722.xlsx")


def _files(*, binoc: Path | None, scene: Path | None = None) -> SurveyFiles:
    return SurveyFiles(
        name="20260722",
        mappro=_CSV,
        exports=(_CSV,),
        binoc=binoc,
        scene_json=scene,
    )


def test_convert_is_never_blocked_for_a_discovered_survey():
    assert convert_blocked(_files(binoc=None)) is None


def test_solve_is_blocked_without_a_workbook_and_names_the_file():
    blocked = solve_blocked(_files(binoc=None))
    assert blocked is not None
    assert "20260722" in blocked.reason
    assert "xlsx" in blocked.reason
    assert "binoc" in blocked.fix


def test_solve_is_available_with_a_workbook():
    assert solve_blocked(_files(binoc=_XLSX)) is None


def test_animate_is_blocked_when_it_cannot_solve():
    blocked = animate_blocked(_files(binoc=None), manim_available=True)
    assert blocked is not None
    assert "xlsx" in blocked.reason


def test_animate_is_blocked_when_manimgl_is_absent():
    blocked = animate_blocked(_files(binoc=_XLSX), manim_available=False)
    assert blocked is not None
    assert "manimgl" in blocked.reason
    assert "animation" in blocked.fix


def test_animate_is_available_with_a_workbook_and_manimgl():
    assert animate_blocked(_files(binoc=_XLSX), manim_available=True) is None


def test_animate_works_from_an_existing_scene_without_a_workbook():
    """A solve already happened; the workbook can be gone and the video still renders."""
    scene = Path("/p/data/output/20260722_scene.json")
    assert animate_blocked(_files(binoc=None, scene=scene), manim_available=True) is None


def test_blocked_for_rejects_an_unknown_verb():
    import pytest

    with pytest.raises(ValueError, match="unknown verb"):
        blocked_for("teleport", _files(binoc=_XLSX))
