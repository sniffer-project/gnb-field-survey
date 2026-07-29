"""Parse the command line, decide which survey, run the verb.

Arguments are a contract: given a survey and a verb, nothing here prompts.
The menu appears only when there is nothing to act on and stdin is a
terminal -- clig.dev's rule that a prompt must never be the only way in.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

from ..trilaterate import solver
from ..trilaterate.discovery import (
    SURVEY_SUBDIR,
    DiscoveryResult,
    SurveyFiles,
    discover_surveys,
)
from . import actions, menu
from .capability import VERBS, blocked_for

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DATA_ROOT = _ROOT / "data" / "raw"
_DEFAULT_PROCESSED_ROOT = _ROOT / "data" / "processed"
# Generated output lives outside data/raw/, which stays purely raw.
_DEFAULT_OUTPUT_DIR = _ROOT / "data" / "output"

# What `survey.py 20260716` does with no verb and no terminal to ask at.
# Matches what `main.py 20260716` used to do.
_DEFAULT_VERB = "solve"

_MAPPRO_DIRS = ("mappro", "map_pro")


def split_target_and_verb(
    positionals: list[str],
) -> tuple[str | None, str | None, list[str]]:
    """Separate the survey from the verb.

    Two orderings are legal, and a verb name is what tells them apart:

        survey.py 20260716 solve       -> ("20260716", "solve", [])
        survey.py solve A.csv B.xlsx   -> (None, "solve", ["A.csv", "B.xlsx"])

    A survey named "solve" would be ambiguous. Survey names are dates, so
    this cannot arise in practice; `main` rejects it explicitly rather than
    resolving it silently.
    """
    if not positionals:
        return None, None, []
    if positionals[0] in VERBS:
        return None, positionals[0], positionals[1:]
    if len(positionals) >= 2 and positionals[1] in VERBS:
        return positionals[0], positionals[1], positionals[2:]
    return positionals[0], None, positionals[1:]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="survey.py",
        description="Convert, solve and animate gNB field surveys.",
        epilog=(
            "Verbs:\n"
            "  convert    convert raw MapPro exports to My Maps CSVs\n"
            "  solve      trilaterate gNB position and write results & scene JSON\n"
            "  animate    render ManimGL visualization scene\n\n"
            "Examples:\n"
            "  survey.py                            interactive picker\n"
            "  survey.py 20260716                   pick a verb for one survey\n"
            "  survey.py 20260716 convert         convert one survey\n"
            "  survey.py 20260716 solve           solve one survey\n"
            "  survey.py 20260716 animate         render scene for one survey\n"
            "  survey.py --list                   list surveys and capabilities\n"
            "  survey.py convert FILE.csv...      convert files by path\n"
            "  survey.py solve SURVEY.csv BINOC.xlsx"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "positionals", nargs="*", metavar="SURVEY|VERB|FILE",
        help="a survey name then a verb, or a verb then explicit file paths",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="print what each survey can do, and exit",
    )
    parser.add_argument(
        "--data-root", type=Path, default=_DEFAULT_DATA_ROOT,
        help="folder to scan for surveys (default: this project's data/raw/)",
    )
    parser.add_argument(
        "--processed-root", type=Path, default=_DEFAULT_PROCESSED_ROOT,
        help="where converted CSVs go (default: this project's data/processed/)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=_DEFAULT_OUTPUT_DIR,
        help="where solutions and videos go (default: this project's data/output/)",
    )
    parser.add_argument(
        "--no-input", "--non-interactive", action="store_true", dest="no_input",
        help="never prompt; error instead if inputs are missing",
    )
    parser.add_argument("--name", help="survey name for the report")
    parser.add_argument(
        "--csv", type=Path, metavar="OUT.csv",
        help="write the My Maps CSV here instead of the default output folder",
    )
    parser.add_argument(
        "--no-csv", action="store_true", help="skip writing the My Maps CSV",
    )
    parser.add_argument(
        "--sigma-distance", type=float, default=solver.SIGMA_DISTANCE_M,
        help=f"1-sigma distance error, metres (default {solver.SIGMA_DISTANCE_M})",
    )
    parser.add_argument(
        "--sigma-elevation", type=float, default=solver.SIGMA_ELEVATION_DEG,
        help=(
            f"1-sigma elevation error, degrees (default {solver.SIGMA_ELEVATION_DEG}). "
            "Only the ratio of the two sigmas affects the result."
        ),
    )
    parser.add_argument(
        "--quality", choices=("low", "medium", "hd", "uhd"), default="hd",
        help="render quality for `animate` (default hd)",
    )
    parser.add_argument(
        "--scene", choices=("GnbTrilateration", "GnbMath"),
        default="GnbTrilateration",
        help="which scene to render (default GnbTrilateration)",
    )
    return parser.parse_args(argv[1:])


def _no_surveys_message(data_root: Path) -> str:
    return (
        f"error: no surveys found under {data_root}. Expected MapPro exports "
        f"in {data_root / SURVEY_SUBDIR}/<NAME>/mappro/*.csv."
    )


def _describe(
    result: DiscoveryResult, data_root: Path, output_fn: OutputFn
) -> None:
    output_fn(f"  Surveys under {data_root}:")
    for files in result.surveys:
        can = ", ".join(v for v in VERBS if blocked_for(v, files) is None)
        output_fn(
            f"    {files.name}   {files.export_count} export(s)"
            f" · can: {can or 'nothing'}"
        )
    for name, reason in result.unreadable:
        output_fn(f"    {name}   unreadable: {reason}")


def _survey_name_for(path: Path) -> str:
    """Name a one-off survey after its folder, skipping the mappro/ level."""
    parent = path.parent.name
    if parent in _MAPPRO_DIRS:
        return path.parent.parent.name
    return parent


def _files_from_paths(verb: str, rest: list[str]) -> SurveyFiles | str:
    """Build a one-off SurveyFiles from paths typed on the command line."""
    paths = [Path(raw).expanduser() for raw in rest]
    for path in paths:
        if not path.is_file():
            return f"error: not a file: {path}"

    if verb == "convert":
        return SurveyFiles(
            name=_survey_name_for(paths[0]),
            mappro=paths[0],
            exports=tuple(paths),
            binoc=None,
            scene_json=None,
        )

    if len(paths) != 2:
        return (
            f"error: `survey.py {verb}` with explicit paths needs exactly two: "
            "the MapPro CSV and the sightings workbook."
        )
    return SurveyFiles(
        name=_survey_name_for(paths[0]),
        mappro=paths[0],
        exports=(paths[0],),
        binoc=paths[1],
        scene_json=None,
    )


def _named_twice(target: str, verb: str | None, rest: list[str]) -> str:
    """Refuse a command that names its subject twice, naming both readings.

    `survey.py 20260701 solve /other/A.csv /other/B.xlsx` and its verbless
    cousin `survey.py 20260701 /other/A.csv /other/B.xlsx` each supply a
    discovered survey *and* explicit paths. Acting on either discards
    whatever the user typed for the other, so neither is chosen for them.

    Silence is especially costly when the paths are what gets dropped: the
    run continues to the capability check and reports a missing sightings
    workbook while the user is looking at the workbook path they just typed.
    That sends them hunting for a file that is already in their hand, so
    this must fire before any capability check.
    """
    joined = " ".join(rest)
    shown = verb if verb is not None else "<verb>"
    return (
        "error: give a survey name or explicit file paths, not both. Use "
        f"`survey.py {target} {shown}` to act on the discovered survey, or "
        f"`survey.py {shown} {joined}` to act on those files."
    )


def _resolve(
    args: argparse.Namespace,
    result: DiscoveryResult,
    target: str | None,
    verb: str | None,
    rest: list[str],
    *,
    interactive: bool,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> SurveyFiles | str:
    """Return the survey to act on, or an error message explaining why not."""
    if target is not None and verb is not None and rest:
        return _named_twice(target, verb, rest)

    if verb is not None and rest:
        return _files_from_paths(verb, rest)

    if target is not None:
        for files in result.surveys:
            if files.name == target:
                # The name matched, but trailing paths were never consumed by
                # anything. Non-empty `rest` here is evidence of a malformed
                # command, not of a survey to act on.
                if rest:
                    return _named_twice(target, verb, rest)
                return files
        if Path(target).exists():
            return (
                f"error: {target} is a file. Put the verb first, e.g. "
                f"`survey.py convert {target}`."
            )
        found = ", ".join(f.name for f in result.surveys) or "none"
        return f"error: no survey named {target!r}. Found: {found}"

    if not result.surveys:
        return _no_surveys_message(args.data_root)
    if not interactive:
        return (
            "error: no survey given and not running interactively. Pass a "
            "survey name, or a verb with explicit file paths."
        )

    chosen = menu.select_survey(result, input_fn=input_fn, output_fn=output_fn)
    if chosen is None:
        return "error: cancelled."
    return chosen


def main(
    argv: list[str],
    *,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    is_tty: bool | None = None,
) -> int:
    args = _parse_args(argv)
    if is_tty is None:
        is_tty = sys.stdin.isatty()
    interactive = is_tty and not args.no_input

    result = discover_surveys(args.data_root, args.output_dir)

    if args.list:
        if not result.surveys and not result.unreadable:
            output_fn(_no_surveys_message(args.data_root))
            return 1
        _describe(result, args.data_root, output_fn)
        return 0

    # A survey folder named after a verb would make `survey.py solve`
    # ambiguous. Dates never collide, but say so plainly if one ever does
    # rather than picking an interpretation.
    collisions = sorted({f.name for f in result.surveys} & set(VERBS))
    if collisions:
        output_fn(
            f"error: these surveys are named after verbs, so they cannot be "
            f"addressed unambiguously: {', '.join(collisions)}. Rename the "
            f"folder under {args.data_root / SURVEY_SUBDIR}/."
        )
        return 1

    target, verb, rest = split_target_and_verb(args.positionals)

    resolved = _resolve(
        args, result, target, verb, rest,
        interactive=interactive, input_fn=input_fn, output_fn=output_fn,
    )
    if isinstance(resolved, str):
        output_fn(resolved)
        return 1

    if verb is None:
        if interactive:
            verb = menu.select_verb(
                resolved, input_fn=input_fn, output_fn=output_fn
            )
            if verb is None:
                output_fn("cancelled.")
                return 1
        else:
            verb = _DEFAULT_VERB

    blocked = blocked_for(verb, resolved)
    if blocked is not None:
        output_fn(f"error: cannot {verb} {resolved.name}: {blocked.reason}")
        output_fn(f"  To fix: {blocked.fix}")
        return 1

    if verb == "convert":
        return actions.do_convert(
            resolved,
            raw_root=args.data_root,
            processed_root=args.processed_root,
            output_fn=output_fn,
        )
    if verb == "solve":
        return actions.do_solve(
            resolved, args, output_dir=args.output_dir, output_fn=output_fn
        )
    return actions.do_animate(
        resolved, args, output_dir=args.output_dir, output_fn=output_fn
    )
