"""Find campaigns under a data root by pairing survey exports with sightings.

A campaign is one directory under ``map-pro-csv/``; its name is the directory
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
class CampaignFiles:
    """One solvable campaign: where its two input files are."""

    name: str
    survey: Path
    binoc: Path
    export_count: int


@dataclass(frozen=True)
class DiscoveryResult:
    """What a scan found, and what it deliberately could not use."""

    campaigns: tuple[CampaignFiles, ...]
    unavailable: tuple[tuple[str, str], ...]  # (name, reason)


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


def discover_campaigns(data_root: Path) -> DiscoveryResult:
    """Scan a data root, newest campaign first."""
    survey_root = Path(data_root) / SURVEY_SUBDIR
    if not survey_root.is_dir():
        return DiscoveryResult(campaigns=(), unavailable=())

    campaigns: list[CampaignFiles] = []
    unavailable: list[tuple[str, str]] = []
    folders = sorted(
        (d for d in survey_root.iterdir() if d.is_dir()),
        key=lambda d: d.name,
        reverse=True,
    )
    for folder in folders:
        exports = _usable(list(folder.glob("*.csv")))
        if not exports:
            unavailable.append((folder.name, "no .csv exports in the survey folder"))
            continue
        binoc = _find_binoc(Path(data_root), folder.name)
        if binoc is None:
            unavailable.append(
                (folder.name, f"no '{folder.name}*.xlsx' sightings workbook found")
            )
            continue
        campaigns.append(
            CampaignFiles(
                name=folder.name,
                survey=_preferred_export(exports),
                binoc=binoc,
                export_count=len(exports),
            )
        )
    return DiscoveryResult(tuple(campaigns), tuple(unavailable))
