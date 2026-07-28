"""CLI entry point: triangulate a gNB from a MapPro export + binocular sightings.

Usage:
    python main.py                          interactive survey picker
    python main.py 20260716                 named survey, no prompts
    python main.py MAPPRO.csv BINOC.xlsx    explicit paths
    python main.py --list                   print surveys and exit

Every run also writes output/<survey>_gnb.csv -- the gNB plus a ring tracing
its 95% confidence ellipse, for import into Google My Maps. --csv PATH writes
it elsewhere; --no-csv skips it.

The MapPro file is a "Survey point data format (csv)" export in any of its
nine Lat/Lon formats -- the raw file off the receiver, no pre-processing.
The workbook supplies distance, elevation angle and binocular height for each
point that was sighted.

No survey is built in. Surveys are discovered under --data-root, which
defaults to this project's raw data/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

from gnb_survey.triangulate import solver
from gnb_survey.triangulate.binoc import read_binoc_readings
from gnb_survey.triangulate.assemble import SurveyDataError, build_survey
from gnb_survey.triangulate.discovery import (
    SURVEY_SUBDIR,
    SurveyFiles,
    DiscoveryResult,
    discover_surveys,
)
from gnb_survey.triangulate.mappro import read_stations
from gnb_survey.triangulate.mymaps import default_csv_name, write_csv
from gnb_survey.triangulate.prompt import select_survey
from gnb_survey.triangulate.report import format_solution
from gnb_survey.triangulate.solver import solve_survey

_DEFAULT_DATA_ROOT = Path(__file__).resolve().parent / "data" / "raw"
# Generated output lives outside raw data/, which stays purely raw.
_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "data" / "output"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "target", nargs="?", metavar="SURVEY|MAPPRO.csv",
        help="a discovered survey name, or the MapPro CSV (with BINOC.xlsx)",
    )
    parser.add_argument(
        "binoc", nargs="?", type=Path, metavar="BINOC.xlsx",
        help="binocular sightings workbook, when giving explicit paths",
    )
    parser.add_argument(
        "--data-root", type=Path, default=_DEFAULT_DATA_ROOT,
        help="folder to scan for surveys (default: this project's raw data/)",
    )
    parser.add_argument("--list", action="store_true", help="print surveys and exit")
    parser.add_argument(
        "--non-interactive", action="store_true",
        help="never prompt; error instead if inputs are missing",
    )
    parser.add_argument("--name", help="survey name for the report")
    parser.add_argument(
        "--csv", type=Path, metavar="OUT.csv",
        help="write the My Maps CSV here instead of the default output/ folder",
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
    return parser.parse_args(argv[1:])


def _describe(result: DiscoveryResult, data_root: Path, output_fn) -> None:
    output_fn(f"  Surveys under {data_root}:")
    for survey in result.surveys:
        output_fn(
            f"    {survey.name}   {survey.export_count} export format(s)"
            f" · binoc: {survey.binoc.name}"
        )
    for name, reason in result.unavailable:
        output_fn(f"    {name}   unavailable: {reason}")


def _no_surveys_message(data_root: Path) -> str:
    return (
        f"error: no surveys found under {data_root}. Expected MapPro exports "
        f"in {data_root / SURVEY_SUBDIR}/<NAME>/*.csv and a matching "
        f"<NAME>*.xlsx sightings workbook somewhere under {data_root}."
    )


def _resolve(
    args: argparse.Namespace,
    result: DiscoveryResult,
    *,
    is_tty: bool,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> SurveyFiles | str:
    """Return the survey to solve, or an error message explaining why not."""
    if args.target is not None and args.binoc is not None:
        mappro = Path(args.target)
        for label, path in (("MapPro CSV", mappro), ("binocular workbook", args.binoc)):
            if not path.is_file():
                return f"error: {label} not found: {path}"
        # Arguments are a contract: never silently fall back to prompting.
        parent_name = mappro.parent.name
        name = mappro.parent.parent.name if parent_name in ("mappro", "map_pro") else parent_name
        return SurveyFiles(
            name=name, mappro=mappro, binoc=args.binoc, export_count=1
        )

    if args.target is not None:
        for survey in result.surveys:
            if survey.name == args.target:
                return survey
        if Path(args.target).exists():
            return (
                f"error: {args.target} is a file, so give both the MapPro CSV "
                "and the sightings workbook."
            )
        found = ", ".join(c.name for c in result.surveys) or "none"
        return f"error: no survey named {args.target!r}. Found: {found}"

    if args.binoc is not None:
        return "error: give both the MapPro CSV and the sightings workbook, or neither."

    if not result.surveys:
        return _no_surveys_message(args.data_root)
    if args.non_interactive or not is_tty:
        return (
            "error: no input given and not running interactively. Pass a "
            "survey name, or the two file paths."
        )

    chosen = select_survey(result, input_fn=input_fn, output_fn=output_fn)
    if chosen is None:
        return "error: cancelled."
    return chosen


def main(
    argv: list[str],
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    is_tty: bool | None = None,
) -> int:
    args = _parse_args(argv)
    if is_tty is None:
        is_tty = sys.stdin.isatty()

    result = discover_surveys(args.data_root)

    if args.list:
        if not result.surveys and not result.unavailable:
            output_fn(_no_surveys_message(args.data_root))
            return 1
        _describe(result, args.data_root, output_fn)
        return 0

    resolved = _resolve(
        args, result, is_tty=is_tty, input_fn=input_fn, output_fn=output_fn
    )
    if isinstance(resolved, str):
        output_fn(resolved)
        return 1

    if resolved.export_count > 1:
        output_fn(
            f"  Using {resolved.mappro.name}"
            f" ({resolved.export_count} exports are equivalent)"
        )

    try:
        survey = build_survey(
            read_stations(resolved.mappro),
            read_binoc_readings(resolved.binoc),
            name=args.name or resolved.name,
        )
    except SurveyDataError as exc:
        # Field-data problems, not crashes: say what is wrong and which file to
        # fix. Re-prompting cannot repair a spreadsheet, so this ends the run
        # in interactive mode too.
        output_fn(f"error: {exc}")
        return 1

    solution = solve_survey(survey, args.sigma_distance, args.sigma_elevation)
    output_fn(format_solution(solution))

    if not args.no_csv:
        if args.csv is not None:
            destination = args.csv           # explicit: must already exist
        else:
            _DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            destination = _DEFAULT_OUTPUT_DIR / default_csv_name(survey.name)
        try:
            rows = write_csv(solution, destination)
        except ValueError as exc:
            output_fn(f"error: {exc}")
            return 1
        output_fn(f"  Wrote {rows} rows to {destination}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except KeyboardInterrupt:
        print("\ncancelled.", file=sys.stderr)
        raise SystemExit(130)
