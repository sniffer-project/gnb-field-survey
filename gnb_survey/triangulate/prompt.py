"""Ask which survey to solve.

Every stream is injected, so the whole flow is exercised in tests without a
terminal. Nothing here touches the filesystem except to check that a typed
path exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .discovery import SurveyFiles, DiscoveryResult

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

_MANUAL_KEY = "m"


def select_survey(
    result: DiscoveryResult,
    *,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> SurveyFiles | None:
    """Return the chosen survey, or None if the user aborted."""
    output_fn("")
    output_fn("  Surveys found:")
    output_fn("")
    for index, survey in enumerate(result.surveys, start=1):
        output_fn(
            f"    {index}) {survey.name}   {survey.export_count} export format(s)"
            f" · binoc: {survey.binoc.name}"
        )
    for name, reason in result.unavailable:
        output_fn(f"       {name}   unavailable: {reason}")
    output_fn(f"    {_MANUAL_KEY}) enter file paths manually")
    output_fn("")

    while True:
        try:
            answer = input_fn("  Select [1]: ").strip()
        except EOFError:
            return None
        if not answer:
            answer = "1"
        if answer.lower() == _MANUAL_KEY:
            return _manual_entry(input_fn, output_fn)
        if answer.isdigit() and 1 <= int(answer) <= len(result.surveys):
            return result.surveys[int(answer) - 1]
        output_fn(f"  Not a choice: {answer!r}")


def _ask_for_file(label: str, input_fn: InputFn, output_fn: OutputFn) -> Path | None:
    while True:
        try:
            raw = input_fn(f"  {label}: ").strip()
        except EOFError:
            return None
        # Dragging a file into a terminal, or copying a path with spaces,
        # brings the surrounding quotes along.
        raw = raw.strip('"').strip("'").strip()
        if not raw:
            output_fn("  Required.")
            continue
        path = Path(raw).expanduser()
        if path.is_file():
            return path
        output_fn(f"  Not a file: {path}")


def _manual_entry(input_fn: InputFn, output_fn: OutputFn) -> SurveyFiles | None:
    mappro = _ask_for_file("MapPro CSV", input_fn, output_fn)
    if mappro is None:
        return None
    binoc = _ask_for_file("Sightings workbook", input_fn, output_fn)
    if binoc is None:
        return None
    return SurveyFiles(
        name=mappro.parent.name,
        mappro=mappro,
        binoc=binoc,
        export_count=1,
    )
