"""Selection is driven through injected streams, so no terminal is needed."""

from pathlib import Path

import pytest

from gnb_survey.cli import menu
from gnb_survey.cli.menu import select_survey
from gnb_survey.trilaterate.discovery import SurveyFiles, DiscoveryResult


def _result(tmp_path) -> DiscoveryResult:
    survey = tmp_path / "dd (Decimal).csv"
    binoc = tmp_path / "b.xlsx"
    survey.write_text("x", encoding="latin-1")
    binoc.write_bytes(b"x")
    exports = tuple(survey for _ in range(9))
    return DiscoveryResult(
        surveys=(
            SurveyFiles("20260801", survey, exports, binoc),
            SurveyFiles("20260716", survey, exports, binoc),
        ),
        unreadable=(("20260620", "no .csv exports in the survey folder"),),
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
def test_empty_input_takes_the_first_survey(tmp_path):
    chosen = select_survey(_result(tmp_path), input_fn=_Answers(""), output_fn=lambda _: None)
    assert chosen.name == "20260801"


@pytest.mark.unit
def test_numeric_selection(tmp_path):
    chosen = select_survey(_result(tmp_path), input_fn=_Answers("2"), output_fn=lambda _: None)
    assert chosen.name == "20260716"


@pytest.mark.unit
def test_out_of_range_reprompts_then_succeeds(tmp_path):
    lines: list[str] = []
    chosen = select_survey(
        _result(tmp_path),
        input_fn=_Answers("9", "abc", "1"),
        output_fn=lines.append,
        error_fn=lines.append,
    )
    assert chosen.name == "20260801"
    assert any("Not a choice" in line for line in lines)


@pytest.mark.unit
def test_unreadable_surveys_are_shown_with_their_reason(tmp_path):
    lines: list[str] = []
    select_survey(_result(tmp_path), input_fn=_Answers(""), output_fn=lines.append)
    assert any("20260620" in line and "no .csv exports" in line for line in lines)


@pytest.mark.unit
def test_manual_entry_returns_paths_named_after_the_parent_folder(tmp_path):
    survey = tmp_path / "20260901" / "dd (Decimal).csv"
    survey.parent.mkdir()
    survey.write_text("x", encoding="latin-1")
    binoc = tmp_path / "b.xlsx"
    binoc.write_bytes(b"x")
    chosen = select_survey(
        _result(tmp_path),
        input_fn=_Answers("m", str(survey), str(binoc)),
        output_fn=lambda _: None,
    )
    assert chosen.name == "20260901"
    assert chosen.mappro == survey
    assert chosen.export_count == 1


@pytest.mark.unit
def test_manual_entry_reprompts_on_a_bad_path(tmp_path):
    survey = tmp_path / "s.csv"
    survey.write_text("x", encoding="latin-1")
    binoc = tmp_path / "b.xlsx"
    binoc.write_bytes(b"x")
    lines: list[str] = []
    chosen = select_survey(
        _result(tmp_path),
        input_fn=_Answers("m", "/no/such/file.csv", str(survey), str(binoc)),
        output_fn=lines.append,
        error_fn=lines.append,
    )
    assert chosen.mappro == survey
    assert any("Not a file" in line for line in lines)


@pytest.mark.unit
def test_manual_entry_strips_quotes_from_dragged_in_paths(tmp_path):
    survey = tmp_path / "s.csv"
    survey.write_text("x", encoding="latin-1")
    binoc = tmp_path / "b.xlsx"
    binoc.write_bytes(b"x")
    chosen = select_survey(
        _result(tmp_path),
        input_fn=_Answers("m", f'"{survey}"', f"'{binoc}'"),
        output_fn=lambda _: None,
    )
    assert chosen.mappro == survey


@pytest.mark.unit
def test_eof_aborts_cleanly(tmp_path):
    assert select_survey(
        _result(tmp_path), input_fn=_Answers(), output_fn=lambda _: None
    ) is None


def test_verb_menu_shows_a_blocked_verb_with_its_reason():
    lines: list[str] = []
    files = SurveyFiles(
        name="20260722",
        mappro=Path("/p/m.csv"),
        exports=(Path("/p/m.csv"),),
        binoc=None,
        scene_json=None,
    )

    chosen = menu.select_verb(
        files,
        input_fn=lambda _: "1",
        output_fn=lines.append,
        manim_available=True,
    )

    assert chosen == "convert"
    listing = "\n".join(lines)
    assert "Solve the gNB position" in listing
    assert "20260722*.xlsx" in listing


def test_verb_menu_refuses_to_pick_a_blocked_verb():
    """Typing the number of a blocked verb must not run it."""
    answers = iter(["2", "b"])
    lines: list[str] = []
    files = SurveyFiles(
        name="20260722",
        mappro=Path("/p/m.csv"),
        exports=(Path("/p/m.csv"),),
        binoc=None,
        scene_json=None,
    )

    chosen = menu.select_verb(
        files,
        input_fn=lambda _: next(answers),
        output_fn=lines.append,
        error_fn=lines.append,
        manim_available=True,
    )

    assert chosen is None
    assert any("To fix:" in line for line in lines)
