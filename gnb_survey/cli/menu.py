"""Ask which survey to act on, and what to do with it.

Every stream is injected, so the whole flow is exercised in tests without a
terminal. Nothing here touches the filesystem except to check that a typed
path exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..triangulate.discovery import SurveyFiles, DiscoveryResult
from .capability import VERBS, blocked_for

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
    for index, files in enumerate(result.surveys, start=1):
        binoc = files.binoc.name if files.binoc is not None else "-- not yet"
        output_fn(
            f"    {index}) {files.name}   {files.export_count} export format(s)"
            f" · binoc: {binoc}"
        )
    for name, reason in result.unreadable:
        output_fn(f"       {name}   unreadable: {reason}")
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
        exports=(mappro,),
        binoc=binoc,
    )


def select_verb(
    files: SurveyFiles,
    *,
    input_fn: InputFn,
    output_fn: OutputFn,
    manim_available: bool | None = None,
) -> str | None:
    """Ask what to do with `files`. Blocked verbs are listed, not hidden.

    Seeing "solve -- needs 20260722*.xlsx" tells the user what to go and
    fetch. Omitting the line would leave them wondering whether the tool
    supports solving at all.
    """
    blocks = {
        verb: blocked_for(verb, files, manim_available=manim_available)
        for verb in VERBS
    }
    output_fn("")
    output_fn(f"  {files.name}")
    output_fn("")
    for index, verb in enumerate(VERBS, start=1):
        blocked = blocks[verb]
        if blocked is None:
            output_fn(f"    {index}) {_VERB_LABELS[verb]}")
        else:
            output_fn(f"       {_VERB_LABELS[verb]}   -- {blocked.reason}")
    output_fn("    b) back")
    output_fn("")

    while True:
        try:
            answer = input_fn("  Select: ").strip().lower()
        except EOFError:
            return None
        if answer in ("b", ""):
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(VERBS):
            verb = VERBS[int(answer) - 1]
            blocked = blocks[verb]
            if blocked is None:
                return verb
            output_fn(f"  {verb} is unavailable: {blocked.reason}")
            output_fn(f"  To fix: {blocked.fix}")
            continue
        output_fn(f"  Not a choice: {answer!r}")


_VERB_LABELS = {
    "convert": "Convert MapPro exports to My Maps CSV",
    "solve": "Solve the gNB position",
    "animate": "Render the animation",
}
