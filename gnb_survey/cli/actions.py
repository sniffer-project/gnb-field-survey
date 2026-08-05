"""One function per verb. Each returns a process exit code and prints nothing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..animate import runner, scene_data
from ..convert import UnknownFormat, convert, processed_destination
from ..streams import OutputFn, default_error_fn
from ..trilaterate.assemble import build_survey
from ..trilaterate.binoc import read_binoc_readings
from ..trilaterate.discovery import SurveyFiles
from ..trilaterate.errors import SurveyDataError
from ..trilaterate.mappro import read_stations
from ..trilaterate.mymaps import default_csv_name, write_csv
from ..trilaterate.report import format_solution, solution_to_dict
from ..trilaterate.solver import solve_survey


def do_convert(
    files: SurveyFiles,
    *,
    raw_root: Path,
    processed_root: Path,
    output_fn: OutputFn,
    error_fn: OutputFn = default_error_fn,
) -> int:
    """Convert every export of one survey."""
    failures = 0
    for export in files.exports:
        destination = processed_destination(export, raw_root, processed_root)
        try:
            convert(export, destination, output_fn=output_fn)
        except UnknownFormat as exc:
            error_fn(f"error: {export.name}: {exc}")
            failures += 1
    return 1 if failures else 0


def do_solve(
    files: SurveyFiles,
    args: argparse.Namespace,
    *,
    output_dir: Path,
    output_fn: OutputFn,
    error_fn: OutputFn = default_error_fn,
) -> int:
    """Solve one survey, then write the My Maps CSV and the scene JSON."""
    if files.binoc is None:
        error_fn(f"error: {files.name} has no sightings workbook.")
        return 1
    try:
        survey = build_survey(
            read_stations(files.mappro),
            read_binoc_readings(files.binoc),
            name=args.name or files.name,
        )
    except SurveyDataError as exc:
        # Field-data problems, not crashes: name what is wrong and which file
        # to fix. Re-prompting cannot repair a spreadsheet.
        error_fn(f"error: {exc}")
        return 1

    solution = solve_survey(survey, args.sigma_distance, args.sigma_elevation)
    if not args.json:
        output_fn(format_solution(solution))

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path: Path | None = None
    if not args.no_csv:
        csv_path = args.csv or output_dir / default_csv_name(survey.name)
        try:
            write_csv(solution, csv_path)
        except ValueError as exc:
            error_fn(f"error: {exc}")
            return 1
        if not args.json:
            output_fn(f"  Wrote the gNB pin to {csv_path}")

    scene_path = output_dir / f"{files.name}_scene.json"
    scene_data.write_scene(survey, solution, scene_path)
    if args.json:
        # One JSON document on stdout, not the report plus two status lines:
        # a script parsing --json output needs a single parseable value, and
        # csv_path/scene_path are exactly what it would otherwise have to
        # reconstruct from --csv/--output-dir itself.
        payload = solution_to_dict(solution)
        payload["csv_path"] = str(csv_path) if csv_path else None
        payload["scene_path"] = str(scene_path)
        output_fn(json.dumps(payload, indent=2))
    else:
        output_fn(f"  Wrote scene data to {scene_path}")
    return 0


def do_animate(
    files: SurveyFiles,
    args: argparse.Namespace,
    *,
    output_dir: Path,
    output_fn: OutputFn,
    error_fn: OutputFn = default_error_fn,
) -> int:
    """Render the animation, solving first if no scene data exists yet."""
    scene_path = output_dir / f"{files.name}_scene.json"
    if not scene_path.is_file():
        output_fn(f"  No scene data for {files.name}; solving first.")
        code = do_solve(
            files, args, output_dir=output_dir, output_fn=output_fn, error_fn=error_fn
        )
        if code != 0:
            return code
    try:
        return runner.render(
            scene_json=scene_path,
            scene_name=args.scene,
            quality=args.quality,
            video_dir=output_dir,
            output_fn=output_fn,
            error_fn=error_fn,
        )
    except runner.ManimUnusable as exc:
        error_fn(f"error: {exc}")
        return 1
