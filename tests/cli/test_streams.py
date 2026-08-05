"""clig.dev Basics #3-4: results on stdout, diagnostics on stderr.

Every other CLI test merges output_fn and error_fn into one capture, because
it only cares that a message appears somewhere (see the docstring on
tests/cli/test_dispatch_resolution.py::_run). This file is the one place
that keeps the two sinks apart, so a regression that quietly routes an error
back onto stdout -- the original bug this fixes -- fails here even if every
substring-only test above stays green.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gnb_survey.cli import dispatch as cli

_MAPPRO_HEADER = (
    "Point Name,Code,Northing,Easting,Elevation,Latitude,Longitude,Altitude,"
    "Original Altitude,Measuring height,Antenna Height\n"
)
_MAPPRO_ROWS = (
    "Pt1,,149955.9668,354634.9606,32.5729,1.35579855,103.69391447,32.5729,34.6389,2.0000,2.0660\n"
    "Pt2,,149962.1319,354630.4524,33.6284,1.35585427,103.69387394,33.6284,35.6944,2.0000,2.0660\n"
)


def _run_split(argv, **kwargs):
    kwargs.setdefault("is_tty", False)
    out: list[str] = []
    err: list[str] = []
    code = cli.main(
        ["survey.py", *argv], output_fn=out.append, error_fn=err.append, **kwargs
    )
    return code, "\n".join(out), "\n".join(err)


@pytest.mark.unit
def test_unknown_survey_error_goes_to_stderr_only(tmp_path):
    (tmp_path / "surveys").mkdir()
    code, out, err = _run_split(["nosuchsurvey", "--data-root", str(tmp_path)])
    assert code == 1
    assert out == ""
    assert "no survey named" in err


@pytest.mark.unit
def test_no_surveys_found_goes_to_stderr_only(tmp_path):
    code, out, err = _run_split(["--data-root", str(tmp_path)])
    assert code == 1
    assert out == ""
    assert "no surveys found" in err


@pytest.mark.unit
def test_list_of_no_surveys_goes_to_stderr_only(tmp_path):
    code, out, err = _run_split(["--list", "--data-root", str(tmp_path)])
    assert code == 1
    assert out == ""
    assert "no surveys found" in err


@pytest.mark.unit
def test_blocked_verb_error_goes_to_stderr_only(tmp_path):
    folder = tmp_path / "surveys" / "20260722" / "mappro"
    folder.mkdir(parents=True)
    (folder / "dd (Decimal).csv").write_text("x", encoding="latin-1")

    code, out, err = _run_split(
        ["20260722", "solve", "--data-root", str(tmp_path)]
    )
    assert code == 1
    assert out == ""
    assert "cannot solve" in err
    assert "To fix:" in err


@pytest.mark.unit
def test_successful_list_goes_to_stdout_only(tmp_path):
    folder = tmp_path / "surveys" / "20260722" / "mappro"
    folder.mkdir(parents=True)
    (folder / "dd (Decimal).csv").write_text("x", encoding="latin-1")

    code, out, err = _run_split(["--list", "--data-root", str(tmp_path)])
    assert code == 0
    assert "20260722" in out
    assert err == ""


@pytest.mark.unit
def test_a_survey_named_twice_error_goes_to_stderr_only(tmp_path):
    folder = tmp_path / "surveys" / "20260716" / "mappro"
    folder.mkdir(parents=True)
    survey = folder / "dd (Decimal).csv"
    survey.write_text("x", encoding="latin-1")
    binoc = tmp_path / "20260716_measurment_binoc.xlsx"
    binoc.write_bytes(b"x")

    code, out, err = _run_split(
        [
            "20260716", "solve", str(survey), str(binoc),
            "--data-root", str(tmp_path),
        ]
    )
    assert code == 1
    assert out == ""
    assert "not both" in err


@pytest.mark.unit
def test_a_corrupt_binoc_workbook_error_goes_to_stderr_only(tmp_path):
    """The original bug this whole audit started from: `2>/dev/null` used to
    hide nothing, because `survey.py solve A.csv B.xlsx > out.txt` wrote the
    error prose straight into the results file."""
    survey = tmp_path / "m.csv"
    survey.write_text(_MAPPRO_HEADER + _MAPPRO_ROWS, encoding="latin-1")
    binoc = tmp_path / "b.xlsx"
    binoc.write_bytes(b"not a zip file")

    code, out, err = _run_split(["solve", str(survey), str(binoc)])
    assert code == 1
    assert out == ""
    assert "cannot read workbook" in err


@pytest.mark.unit
def test_quiet_silences_stdout_but_not_exit_code_or_files(tmp_path):
    folder = tmp_path / "surveys" / "20260722" / "mappro"
    folder.mkdir(parents=True)
    (folder / "dd (Decimal).csv").write_text("x", encoding="latin-1")

    code, out, err = _run_split(
        ["--list", "--quiet", "--data-root", str(tmp_path)]
    )
    assert code == 0
    assert out == ""


@pytest.mark.unit
def test_quiet_does_not_silence_errors(tmp_path):
    code, out, err = _run_split(["--quiet", "--data-root", str(tmp_path)])
    assert code == 1
    assert out == ""
    assert "no surveys found" in err
