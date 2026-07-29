"""Find surveys under a data root by pairing MapPro exports with sightings.

A survey is one directory under ``surveys/``; its name is the directory
name. Its sightings workbook is whatever ``<name>*.xlsx`` sits anywhere under
the same data root -- the binoc directory's own name describes one day's field
conditions and must never be assumed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SURVEY_SUBDIR = "surveys"
# 8 decimal places is ~1.1 mm, the least quantised of MapPro's nine formats.
# All nine are equivalent, so this choice is cosmetic -- but it must be
# deterministic, or repeated runs would disagree in the last millimetre.
PREFERRED_EXPORT = "dd (Decimal).csv"

# Excel writes ~$NAME.xlsx alongside a workbook while it is open. Pairing one
# of those as if it were the workbook fails confusingly much later.
_LOCK_PREFIX = "~$"


@dataclass(frozen=True)
class SurveyFiles:
    """One survey on disk, and which of its inputs are present."""

    name: str
    mappro: Path                    # the preferred MapPro export
    exports: tuple[Path, ...]       # every export found, newest-preferred first
    binoc: Path | None              # None until the sightings are typed up
    scene_json: Path | None = None  # written by a previous solve

    @property
    def export_count(self) -> int:
        return len(self.exports)


@dataclass(frozen=True)
class DiscoveryResult:
    """What a scan found, and which folders held nothing usable at all."""

    surveys: tuple[SurveyFiles, ...]
    unreadable: tuple[tuple[str, str], ...]  # (name, reason)


def _usable(paths: list[Path]) -> list[Path]:
    return sorted(p for p in paths if not p.name.startswith(_LOCK_PREFIX))


def _preferred_export(exports: list[Path]) -> Path:
    for export in exports:
        if export.name == PREFERRED_EXPORT or export.name.endswith(PREFERRED_EXPORT):
            return export
    return exports[0]


def _find_binoc(data_root: Path, name: str) -> Path | None:
    matches = _usable(list(data_root.rglob(f"{name}*.xlsx")))
    return matches[0] if matches else None


def discover_surveys(
    data_root: Path, output_dir: Path | None = None
) -> DiscoveryResult:
    """Scan a data root, newest survey first.

    A survey needs only a MapPro export to be discovered. Whether it can be
    solved or animated is a separate question, answered by cli.capability --
    keeping "what exists" apart from "what you can do with it".
    """
    survey_root = Path(data_root) / SURVEY_SUBDIR
    if not survey_root.is_dir():
        return DiscoveryResult(surveys=(), unreadable=())

    surveys: list[SurveyFiles] = []
    unreadable: list[tuple[str, str]] = []
    folders = sorted(
        (d for d in survey_root.iterdir() if d.is_dir()),
        key=lambda d: d.name,
        reverse=True,
    )
    for folder in folders:
        exports = _usable(list(folder.rglob("*.csv")))
        if not exports:
            unreadable.append((folder.name, "no .csv exports in the survey folder"))
            continue
        scene = None
        if output_dir is not None:
            candidate = Path(output_dir) / f"{folder.name}_scene.json"
            scene = candidate if candidate.is_file() else None
        surveys.append(
            SurveyFiles(
                name=folder.name,
                mappro=_preferred_export(exports),
                exports=tuple(exports),
                binoc=_find_binoc(Path(data_root), folder.name),
                scene_json=scene,
            )
        )
    return DiscoveryResult(tuple(surveys), tuple(unreadable))
