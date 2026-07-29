"""What each verb can do with a given survey, and why not when it cannot.

Availability is computed here rather than baked into discovery so that "what
files exist" and "what you can do with them" stay separable: the menu, the
--list table and the error paths all ask the same question and get the same
answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from shutil import which

from ..triangulate.discovery import SurveyFiles

VERBS: tuple[str, ...] = ("convert", "solve", "animate")

MANIM_BINARY = "manimgl"
_INSTALL_HINT = 'pip install -e ".[animation]"'


@dataclass(frozen=True)
class Blocked:
    """Why a verb cannot run, and the single action that would unblock it."""

    reason: str
    fix: str


def convert_blocked(files: SurveyFiles) -> Blocked | None:
    if not files.exports:
        return Blocked(
            reason="no MapPro CSV export",
            fix=f"put an export in data/raw/surveys/{files.name}/mappro/",
        )
    return None


def solve_blocked(files: SurveyFiles) -> Blocked | None:
    if files.binoc is None:
        return Blocked(
            reason=f"no {files.name}*.xlsx sightings workbook",
            fix=f"add the binocular workbook under data/raw/surveys/{files.name}/binoc/",
        )
    return None


def animate_blocked(
    files: SurveyFiles, *, manim_available: bool | None = None
) -> Blocked | None:
    """Animation needs a solution and a renderer.

    An existing scene JSON stands in for the solve, so a survey whose workbook
    has been archived can still be re-rendered.
    """
    if files.scene_json is None:
        blocked = solve_blocked(files)
        if blocked is not None:
            return blocked
    if manim_available is None:
        manim_available = which(MANIM_BINARY) is not None
    if not manim_available:
        return Blocked(
            reason=f"{MANIM_BINARY} is not installed",
            fix=_INSTALL_HINT,
        )
    return None


_CHECKS = {
    "convert": convert_blocked,
    "solve": solve_blocked,
}


def blocked_for(
    verb: str, files: SurveyFiles, *, manim_available: bool | None = None
) -> Blocked | None:
    """Dispatch to the check for `verb`."""
    if verb == "animate":
        return animate_blocked(files, manim_available=manim_available)
    check = _CHECKS.get(verb)
    if check is None:
        raise ValueError(f"unknown verb {verb!r}; expected one of {', '.join(VERBS)}")
    return check(files)
