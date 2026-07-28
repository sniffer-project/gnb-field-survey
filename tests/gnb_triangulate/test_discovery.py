"""Discovery pairs each survey folder with its sightings workbook."""

from pathlib import Path

import pytest

from gnb_triangulate.discovery import CampaignFiles, discover_campaigns


def _campaign(root: Path, name: str, exports: tuple[str, ...], binoc: bool = True) -> None:
    folder = root / "map-pro-csv" / name
    folder.mkdir(parents=True)
    for export in exports:
        (folder / export).write_text("Point Name\n", encoding="latin-1")
    if binoc:
        sightings = root / "sightings"
        sightings.mkdir(exist_ok=True)
        (sightings / f"{name}_measurment_binoc.xlsx").write_bytes(b"stub")


@pytest.mark.unit
def test_pairs_survey_folder_with_its_workbook(tmp_path):
    _campaign(tmp_path, "20260716", ("dd (Decimal).csv", "Radian.csv"))
    result = discover_campaigns(tmp_path)
    assert len(result.campaigns) == 1
    found = result.campaigns[0]
    assert found.name == "20260716"
    assert found.export_count == 2
    assert found.binoc.name == "20260716_measurment_binoc.xlsx"


@pytest.mark.unit
def test_prefers_the_decimal_degree_export(tmp_path):
    """8 dp is ~1.1 mm, the least quantised of the nine formats."""
    _campaign(tmp_path, "20260716", ("Radian.csv", "dd (Decimal).csv", "dd.mmssss.csv"))
    assert discover_campaigns(tmp_path).campaigns[0].survey.name == "dd (Decimal).csv"


@pytest.mark.unit
def test_falls_back_to_first_alphabetical_export(tmp_path):
    _campaign(tmp_path, "20260716", ("Radian.csv", "dd.mmssss.csv"))
    assert discover_campaigns(tmp_path).campaigns[0].survey.name == "Radian.csv"


@pytest.mark.unit
def test_skips_excel_lock_files(tmp_path):
    """Excel writes ~$NAME.xlsx while a workbook is open; one is in the real data."""
    _campaign(tmp_path, "20260716", ("dd (Decimal).csv",))
    (tmp_path / "sightings" / "~$20260716_measurment_binoc.xlsx").write_bytes(b"lock")
    assert discover_campaigns(tmp_path).campaigns[0].binoc.name.startswith("20260716")


@pytest.mark.unit
def test_reports_campaign_with_no_workbook_as_unavailable(tmp_path):
    _campaign(tmp_path, "20260801", ("dd (Decimal).csv",), binoc=False)
    result = discover_campaigns(tmp_path)
    assert result.campaigns == ()
    assert result.unavailable[0][0] == "20260801"
    assert "xlsx" in result.unavailable[0][1]


@pytest.mark.unit
def test_reports_campaign_with_no_csv_as_unavailable(tmp_path):
    (tmp_path / "map-pro-csv" / "20260801").mkdir(parents=True)
    result = discover_campaigns(tmp_path)
    assert result.campaigns == ()
    assert "csv" in result.unavailable[0][1]


@pytest.mark.unit
def test_sorts_newest_first(tmp_path):
    for name in ("20260716", "20260801", "20260620"):
        _campaign(tmp_path, name, ("dd (Decimal).csv",))
    names = [c.name for c in discover_campaigns(tmp_path).campaigns]
    assert names == ["20260801", "20260716", "20260620"]


@pytest.mark.unit
def test_missing_data_root_yields_nothing_rather_than_crashing(tmp_path):
    result = discover_campaigns(tmp_path / "does-not-exist")
    assert result.campaigns == ()
    assert result.unavailable == ()


@pytest.mark.unit
def test_data_root_without_survey_subdir_yields_nothing(tmp_path):
    (tmp_path / "unrelated").mkdir()
    assert discover_campaigns(tmp_path).campaigns == ()


@pytest.mark.integration
def test_finds_the_real_campaign():
    raw = Path(__file__).resolve().parents[2] / "raw_data"
    if not raw.is_dir():
        pytest.skip("raw data not present")
    result = discover_campaigns(raw)
    names = [c.name for c in result.campaigns]
    assert "20260716" in names
    found = next(c for c in result.campaigns if c.name == "20260716")
    assert found.export_count == 9
    assert found.survey.name == "dd (Decimal).csv"
    assert not found.binoc.name.startswith("~$")
