"""Selection is driven through injected streams, so no terminal is needed."""

from pathlib import Path

import pytest

from gnb_triangulate.discovery import CampaignFiles, DiscoveryResult
from gnb_triangulate.prompt import select_campaign


def _result(tmp_path) -> DiscoveryResult:
    survey = tmp_path / "dd (Decimal).csv"
    binoc = tmp_path / "b.xlsx"
    survey.write_text("x", encoding="latin-1")
    binoc.write_bytes(b"x")
    return DiscoveryResult(
        campaigns=(
            CampaignFiles("20260801", survey, binoc, 9),
            CampaignFiles("20260716", survey, binoc, 9),
        ),
        unavailable=(("20260620", "no workbook"),),
    )


class _Answers:
    """Replays scripted answers, then raises EOFError like a closed stdin."""

    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.answers:
            raise EOFError
        return self.answers.pop(0)


@pytest.mark.unit
def test_empty_input_takes_the_first_campaign(tmp_path):
    chosen = select_campaign(_result(tmp_path), input_fn=_Answers(""), output_fn=lambda _: None)
    assert chosen.name == "20260801"


@pytest.mark.unit
def test_numeric_selection(tmp_path):
    chosen = select_campaign(_result(tmp_path), input_fn=_Answers("2"), output_fn=lambda _: None)
    assert chosen.name == "20260716"


@pytest.mark.unit
def test_out_of_range_reprompts_then_succeeds(tmp_path):
    lines: list[str] = []
    chosen = select_campaign(
        _result(tmp_path), input_fn=_Answers("9", "abc", "1"), output_fn=lines.append
    )
    assert chosen.name == "20260801"
    assert any("Not a choice" in line for line in lines)


@pytest.mark.unit
def test_unavailable_campaigns_are_shown_with_their_reason(tmp_path):
    lines: list[str] = []
    select_campaign(_result(tmp_path), input_fn=_Answers(""), output_fn=lines.append)
    assert any("20260620" in line and "no workbook" in line for line in lines)


@pytest.mark.unit
def test_manual_entry_returns_paths_named_after_the_parent_folder(tmp_path):
    survey = tmp_path / "20260901" / "dd (Decimal).csv"
    survey.parent.mkdir()
    survey.write_text("x", encoding="latin-1")
    binoc = tmp_path / "b.xlsx"
    binoc.write_bytes(b"x")
    chosen = select_campaign(
        _result(tmp_path),
        input_fn=_Answers("m", str(survey), str(binoc)),
        output_fn=lambda _: None,
    )
    assert chosen.name == "20260901"
    assert chosen.survey == survey
    assert chosen.export_count == 1


@pytest.mark.unit
def test_manual_entry_reprompts_on_a_bad_path(tmp_path):
    survey = tmp_path / "s.csv"
    survey.write_text("x", encoding="latin-1")
    binoc = tmp_path / "b.xlsx"
    binoc.write_bytes(b"x")
    lines: list[str] = []
    chosen = select_campaign(
        _result(tmp_path),
        input_fn=_Answers("m", "/no/such/file.csv", str(survey), str(binoc)),
        output_fn=lines.append,
    )
    assert chosen.survey == survey
    assert any("Not a file" in line for line in lines)


@pytest.mark.unit
def test_manual_entry_strips_quotes_from_dragged_in_paths(tmp_path):
    survey = tmp_path / "s.csv"
    survey.write_text("x", encoding="latin-1")
    binoc = tmp_path / "b.xlsx"
    binoc.write_bytes(b"x")
    chosen = select_campaign(
        _result(tmp_path),
        input_fn=_Answers("m", f'"{survey}"', f"'{binoc}'"),
        output_fn=lambda _: None,
    )
    assert chosen.survey == survey


@pytest.mark.unit
def test_eof_aborts_cleanly(tmp_path):
    assert select_campaign(
        _result(tmp_path), input_fn=_Answers(), output_fn=lambda _: None
    ) is None
