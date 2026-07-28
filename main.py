"""CLI entry point: triangulate a gNB from a MapPro survey + binocular sightings.

Usage:
    python main.py                          interactive campaign picker
    python main.py 20260716                 named campaign, no prompts
    python main.py SURVEY.csv BINOC.xlsx    explicit paths
    python main.py --list                   print campaigns and exit

Every run also writes output/<campaign>_gnb.csv -- the gNB plus a ring tracing
its 95% confidence ellipse, for import into Google My Maps. --csv PATH writes
it elsewhere; --no-csv skips it.

The survey file is a MapPro "Survey point data format (csv)" export in any of
its nine Lat/Lon formats -- the raw file off the receiver, no pre-processing.
The workbook supplies distance, elevation angle and binocular height for each
point that was sighted.

No campaign is built in. Campaigns are discovered under --data-root, which
defaults to this project's raw data/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

from gnb_triangulate import solver
from gnb_triangulate.binoc import read_binoc_readings
from gnb_triangulate.campaign import CampaignDataError, build_campaign
from gnb_triangulate.discovery import (
    SURVEY_SUBDIR,
    CampaignFiles,
    DiscoveryResult,
    discover_campaigns,
)
from gnb_triangulate.mappro import read_stations
from gnb_triangulate.mymaps import default_csv_name, write_csv
from gnb_triangulate.prompt import select_campaign
from gnb_triangulate.report import format_solution
from gnb_triangulate.solver import solve_campaign

_DEFAULT_DATA_ROOT = Path(__file__).resolve().parent / "raw_data"
# Generated output lives outside raw data/, which stays purely raw.
_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "target", nargs="?", metavar="CAMPAIGN|SURVEY.csv",
        help="a discovered campaign name, or the survey CSV (with BINOC.xlsx)",
    )
    parser.add_argument(
        "binoc", nargs="?", type=Path, metavar="BINOC.xlsx",
        help="binocular sightings workbook, when giving explicit paths",
    )
    parser.add_argument(
        "--data-root", type=Path, default=_DEFAULT_DATA_ROOT,
        help="folder to scan for campaigns (default: this project's raw data/)",
    )
    parser.add_argument("--list", action="store_true", help="print campaigns and exit")
    parser.add_argument(
        "--non-interactive", action="store_true",
        help="never prompt; error instead if inputs are missing",
    )
    parser.add_argument("--name", help="campaign name for the report")
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
    output_fn(f"  Campaigns under {data_root}:")
    for campaign in result.campaigns:
        output_fn(
            f"    {campaign.name}   {campaign.export_count} export format(s)"
            f" · binoc: {campaign.binoc.name}"
        )
    for name, reason in result.unavailable:
        output_fn(f"    {name}   unavailable: {reason}")


def _no_campaigns_message(data_root: Path) -> str:
    return (
        f"error: no campaigns found under {data_root}. Expected survey exports "
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
) -> CampaignFiles | str:
    """Return the campaign to solve, or an error message explaining why not."""
    if args.target is not None and args.binoc is not None:
        survey = Path(args.target)
        for label, path in (("survey CSV", survey), ("binocular workbook", args.binoc)):
            if not path.is_file():
                return f"error: {label} not found: {path}"
        # Arguments are a contract: never silently fall back to prompting.
        parent_name = survey.parent.name
        name = survey.parent.parent.name if parent_name in ("mappro", "map_pro") else parent_name
        return CampaignFiles(
            name=name, survey=survey, binoc=args.binoc, export_count=1
        )

    if args.target is not None:
        for campaign in result.campaigns:
            if campaign.name == args.target:
                return campaign
        if Path(args.target).exists():
            return (
                f"error: {args.target} is a file, so give both the survey CSV "
                "and the sightings workbook."
            )
        found = ", ".join(c.name for c in result.campaigns) or "none"
        return f"error: no campaign named {args.target!r}. Found: {found}"

    if args.binoc is not None:
        return "error: give both the survey CSV and the sightings workbook, or neither."

    if not result.campaigns:
        return _no_campaigns_message(args.data_root)
    if args.non_interactive or not is_tty:
        return (
            "error: no input given and not running interactively. Pass a "
            "campaign name, or the two file paths."
        )

    chosen = select_campaign(result, input_fn=input_fn, output_fn=output_fn)
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

    result = discover_campaigns(args.data_root)

    if args.list:
        if not result.campaigns and not result.unavailable:
            output_fn(_no_campaigns_message(args.data_root))
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
            f"  Using {resolved.survey.name}"
            f" ({resolved.export_count} exports are equivalent)"
        )

    try:
        campaign = build_campaign(
            read_stations(resolved.survey),
            read_binoc_readings(resolved.binoc),
            name=args.name or resolved.name,
        )
    except CampaignDataError as exc:
        # Field-data problems, not crashes: say what is wrong and which file to
        # fix. Re-prompting cannot repair a spreadsheet, so this ends the run
        # in interactive mode too.
        output_fn(f"error: {exc}")
        return 1

    solution = solve_campaign(campaign, args.sigma_distance, args.sigma_elevation)
    output_fn(format_solution(solution))

    if not args.no_csv:
        if args.csv is not None:
            destination = args.csv           # explicit: must already exist
        else:
            _DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            destination = _DEFAULT_OUTPUT_DIR / default_csv_name(campaign.name)
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
