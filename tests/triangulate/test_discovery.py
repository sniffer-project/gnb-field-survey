"""Discovery pairs each survey folder with its sightings workbook."""

import dataclasses
import json
from pathlib import Path

import pytest

from gnb_survey.cli.capability import animate_blocked
from gnb_survey.cli import dispatch
from gnb_survey.triangulate.discovery import SurveyFiles, discover_surveys


def _survey(root: Path, name: str, exports: tuple[str, ...]) -> None:
    folder = root / "surveys" / name
    folder.mkdir(parents=True)
    for export in exports:
        (folder / export).write_text("Point Name\n", encoding="latin-1")
    sightings = root / "sightings"
    sightings.mkdir(exist_ok=True)
    (sightings / f"{name}_measurment_binoc.xlsx").write_bytes(b"stub")


@pytest.mark.unit
def test_pairs_survey_folder_with_its_workbook(tmp_path):
    _survey(tmp_path, "20260716", ("dd (Decimal).csv", "Radian.csv"))
    result = discover_surveys(tmp_path)
    assert len(result.surveys) == 1
    found = result.surveys[0]
    assert found.name == "20260716"
    assert found.export_count == 2
    assert found.binoc.name == "20260716_measurment_binoc.xlsx"


@pytest.mark.unit
def test_prefers_the_decimal_degree_export(tmp_path):
    """8 dp is ~1.1 mm, the least quantised of the nine formats."""
    _survey(tmp_path, "20260716", ("Radian.csv", "dd (Decimal).csv", "dd.mmssss.csv"))
    assert discover_surveys(tmp_path).surveys[0].mappro.name == "dd (Decimal).csv"


@pytest.mark.unit
def test_falls_back_to_first_alphabetical_export(tmp_path):
    _survey(tmp_path, "20260716", ("Radian.csv", "dd.mmssss.csv"))
    assert discover_surveys(tmp_path).surveys[0].mappro.name == "Radian.csv"


@pytest.mark.unit
def test_skips_excel_lock_files(tmp_path):
    """Excel writes ~$NAME.xlsx while a workbook is open; one is in the real data."""
    _survey(tmp_path, "20260716", ("dd (Decimal).csv",))
    (tmp_path / "sightings" / "~$20260716_measurment_binoc.xlsx").write_bytes(b"lock")
    assert discover_surveys(tmp_path).surveys[0].binoc.name.startswith("20260716")


@pytest.mark.unit
def test_a_survey_without_a_workbook_is_still_discovered(tmp_path):
    """MapPro comes back from the field days before the sightings are typed up.

    Such a survey is fully convertible, so dropping it from the results (as
    the old available/unavailable split did) hides work the user can do.
    """
    folder = tmp_path / "surveys" / "20260722" / "mappro"
    folder.mkdir(parents=True)
    (folder / "dd (Decimal).csv").write_text("Point Name\nPt1\n", encoding="latin-1")

    result = discover_surveys(tmp_path)

    assert [s.name for s in result.surveys] == ["20260722"]
    assert result.surveys[0].binoc is None
    assert result.unreadable == ()


@pytest.mark.unit
def test_a_folder_with_no_exports_is_unreadable(tmp_path):
    (tmp_path / "surveys" / "20260723").mkdir(parents=True)

    result = discover_surveys(tmp_path)

    assert result.surveys == ()
    assert len(result.unreadable) == 1
    name, reason = result.unreadable[0]
    assert name == "20260723"
    assert "csv" in reason.lower()


@pytest.mark.unit
def test_sorts_newest_first(tmp_path):
    for name in ("20260716", "20260801", "20260620"):
        _survey(tmp_path, name, ("dd (Decimal).csv",))
    names = [c.name for c in discover_surveys(tmp_path).surveys]
    assert names == ["20260801", "20260716", "20260620"]


@pytest.mark.unit
def test_missing_data_root_yields_nothing_rather_than_crashing(tmp_path):
    result = discover_surveys(tmp_path / "does-not-exist")
    assert result.surveys == ()
    assert result.unreadable == ()


@pytest.mark.unit
def test_data_root_without_survey_subdir_yields_nothing(tmp_path):
    (tmp_path / "unrelated").mkdir()
    assert discover_surveys(tmp_path).surveys == ()


@pytest.mark.integration
def test_finds_the_real_survey():
    fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    if not fixtures.is_dir():
        pytest.skip("fixtures not present")
    result = discover_surveys(fixtures)
    names = [c.name for c in result.surveys]
    assert "20260716" in names
    found = next(c for c in result.surveys if c.name == "20260716")
    assert found.export_count == 9
    assert found.mappro.name.endswith("dd (Decimal).csv")
    assert not found.binoc.name.startswith("~$")


@pytest.mark.integration
def test_a_solved_survey_is_rediscovered_with_its_scene_json(tmp_path):
    fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    output_dir = tmp_path / "output"

    code = dispatch.main(
        [
            "survey.py",
            "20260716",
            "solve",
            "--data-root",
            str(fixtures),
            "--output-dir",
            str(output_dir),
        ],
        output_fn=lambda _: None,
        is_tty=False,
    )
    result = discover_surveys(fixtures, output_dir)

    assert code == 0
    found = next(s for s in result.surveys if s.name == "20260716")
    assert found.scene_json == output_dir / "20260716_scene.json"


@pytest.mark.integration
def test_a_custom_report_name_keeps_the_stable_scene_identity(tmp_path):
    fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    output_dir = tmp_path / "output"

    code = dispatch.main(
        [
            "survey.py",
            "20260716",
            "solve",
            "--name",
            "Cetran",
            "--data-root",
            str(fixtures),
            "--output-dir",
            str(output_dir),
        ],
        output_fn=lambda _: None,
        is_tty=False,
    )
    result = discover_surveys(fixtures, output_dir)

    assert code == 0
    found = next(s for s in result.surveys if s.name == "20260716")
    assert found.scene_json == output_dir / "20260716_scene.json"
    scene = json.loads(found.scene_json.read_text(encoding="utf-8"))
    assert scene["survey"] == "Cetran"

    archived = dataclasses.replace(found, binoc=None)
    assert animate_blocked(archived, manim_available=True) is None
