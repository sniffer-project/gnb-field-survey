"""What each verb can do with a given survey, and why not when it cannot.

Availability is computed here rather than baked into discovery so that "what
files exist" and "what you can do with them" stay separable: the menu, the
--list table and the error paths all ask the same question and get the same
answer.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..animate import availability
from ..animate.availability import Renderer
from ..trilaterate.discovery import SurveyFiles

VERBS: tuple[str, ...] = ("convert", "solve", "animate")

MANIM_BINARY = availability.BINARY
_INSTALL_HINT = availability.INSTALL_HINT


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
    files: SurveyFiles,
    *,
    manim_available: bool | None = None,
    renderer: Renderer | None = None,
) -> Blocked | None:
    """Animation needs a solution and a renderer that runs.

    An existing scene JSON stands in for the solve, so a survey whose workbook
    has been archived can still be re-rendered.

    Both overrides are for callers that already know the answer: `renderer`
    gives the exact state, `manim_available` is the shorthand for the two
    states that existed before a broken install could be told apart from an
    absent one. Given neither, the renderer is probed once per process.
    """
    if files.scene_json is None:
        blocked = solve_blocked(files)
        if blocked is not None:
            return blocked

    state = _renderer(manim_available=manim_available, renderer=renderer)
    if not state.on_path:
        return Blocked(
            reason=f"{MANIM_BINARY} is not installed",
            fix=_INSTALL_HINT,
        )
    if state.start_error is not None:
        return Blocked(
            reason=(
                f"{MANIM_BINARY} is installed but will not start: "
                f"{state.start_error}"
            ),
            fix=_INSTALL_HINT,
        )
    return None


def _renderer(
    *, manim_available: bool | None, renderer: Renderer | None
) -> Renderer:
    """Resolve the renderer state, probing only when nobody supplied one."""
    if renderer is not None:
        return renderer
    if manim_available is not None:
        return availability.READY if manim_available else availability.MISSING
    return availability.current()


_CHECKS = {
    "convert": convert_blocked,
    "solve": solve_blocked,
}


def blocked_for(
    verb: str,
    files: SurveyFiles,
    *,
    manim_available: bool | None = None,
    renderer: Renderer | None = None,
) -> Blocked | None:
    """Dispatch to the check for `verb`."""
    if verb == "animate":
        return animate_blocked(
            files, manim_available=manim_available, renderer=renderer
        )
    check = _CHECKS.get(verb)
    if check is None:
        raise ValueError(f"unknown verb {verb!r}; expected one of {', '.join(VERBS)}")
    return check(files)
