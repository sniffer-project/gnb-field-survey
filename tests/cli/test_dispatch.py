"""`survey.py 20260716 solve` and `survey.py solve A.csv B.xlsx` must both parse.

The noun comes first (clig.dev: "noun verb seems to be more common"), but the
explicit-paths form has no noun, so the first positional is a verb. Which is
which is decided by membership in VERBS, not by position alone.
"""

from __future__ import annotations

import pytest

from gnb_survey.cli import dispatch as cli
from gnb_survey.cli.dispatch import split_target_and_verb


@pytest.mark.parametrize(
    "positionals,expected",
    [
        ([], (None, None, [])),
        (["20260716"], ("20260716", None, [])),
        (["20260716", "solve"], ("20260716", "solve", [])),
        (["20260716", "convert"], ("20260716", "convert", [])),
        (["convert"], (None, "convert", [])),
        (["convert", "a.csv", "b.csv"], (None, "convert", ["a.csv", "b.csv"])),
        (["solve", "A.csv", "B.xlsx"], (None, "solve", ["A.csv", "B.xlsx"])),
        (["/tmp/A.csv", "/tmp/B.xlsx"], ("/tmp/A.csv", None, ["/tmp/B.xlsx"])),
    ],
)
def test_splits_target_from_verb(positionals, expected):
    assert split_target_and_verb(positionals) == expected


# --- run(): the shared entry point behind `python survey.py` and the
# installed `gnb-survey` console script (pyproject.toml's [project.scripts])


@pytest.mark.unit
def test_run_returns_mains_exit_code(monkeypatch, tmp_path):
    code = cli.run(["survey.py", "--list", "--data-root", str(tmp_path)])
    assert code == 1  # no surveys under an empty tmp_path


@pytest.mark.unit
def test_run_turns_keyboard_interrupt_into_exit_130(monkeypatch):
    def raise_interrupt(_argv):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "main", raise_interrupt)
    assert cli.run(["survey.py"]) == 130


@pytest.mark.unit
def test_cli_entry_raises_system_exit_with_runs_code(monkeypatch):
    monkeypatch.setattr(cli, "run", lambda: 7)
    with pytest.raises(SystemExit) as exc_info:
        cli.cli_entry()
    assert exc_info.value.code == 7
