"""Triangulate ONE gNB from the two 2026-07-01 surveys that both face it.

The rangefinder readings (line-of-sight distance, elevation angle, measuring
height) were taken standing on RTK-surveyed points. We look each point's
lat/lon/ground-altitude up from its My Maps CSV, add the measuring height to
get the instrument altitude, and solve all six observations as a single
campaign (wider baseline than either survey alone).
"""

from __future__ import annotations

import csv
from pathlib import Path

from gnb_triangulate.models import Campaign, SurveyPoint
from gnb_triangulate.report import format_solution
from gnb_triangulate.solver import solve_campaign

_HERE = Path(__file__).resolve().parent
_DATA = _HERE.parent  # "triangulate gnB position/"

# (csv file, point name, distance_m, elevation_deg, measuring_height_cm)
_READINGS = [
    # 20260701_mymaps.csv  (S2/S1 cluster)
    ("20260701_mymaps.csv", "Pt1", 65.8, 20, 180),
    ("20260701_mymaps.csv", "Pt8", 47.1, 29, 184),
    ("20260701_mymaps.csv", "Pt2", 53.8, 25, 182),
    # 20260701_hall14_mymaps.csv  (Hall 14 cluster)
    ("20260701_hall14_mymaps.csv", "Pt3", 58.8, 25, 183),
    ("20260701_hall14_mymaps.csv", "Pt2", 63.0, 23, 172),
    ("20260701_hall14_mymaps.csv", "Pt13", 87.6, 19, 181),
]


def _load_coords(filename: str) -> dict[str, tuple[float, float, float]]:
    """point name -> (lat, lon, ground_altitude_m) from a My Maps CSV."""
    coords: dict[str, tuple[float, float, float]] = {}
    with open(_DATA / filename, newline="") as fh:
        for row in csv.DictReader(fh):
            name = row["Point Name"].strip()
            if not name.lower().startswith("pt"):
                continue  # skip triangulated-gnb summary rows
            coords[name] = (
                float(row["Latitude"]),
                float(row["Longitude"]),
                float(row["Altitude"]),
            )
    return coords


def _build_campaign() -> Campaign:
    caches: dict[str, dict[str, tuple[float, float, float]]] = {}
    points: list[SurveyPoint] = []
    for filename, name, dist, elev, height_cm in _READINGS:
        coords = caches.setdefault(filename, _load_coords(filename))
        lat, lon, ground_alt = coords[name]
        instrument_alt = ground_alt + height_cm / 100.0
        site = "S2/S1" if "hall14" not in filename else "Hall14"
        points.append(
            SurveyPoint(
                label=f"{name} ({site})",
                latitude=lat,
                longitude=lon,
                altitude_m=instrument_alt,
                elevation_deg=float(elev),
                distance_m=float(dist),
            )
        )
    return Campaign(name="Shared gNB (both surveys)", points=tuple(points))


def main() -> None:
    campaign = _build_campaign()
    print(f"Solving {len(campaign.points)} observations of one gNB:\n")
    for p in campaign.points:
        print(
            f"  {p.label:<16} {p.latitude:.7f}, {p.longitude:.7f}  "
            f"instr.alt {p.altitude_m:.2f} m   "
            f"dist {p.distance_m:.1f} m  elev {p.elevation_deg:.0f}deg"
        )
    print()
    print(format_solution(solve_campaign(campaign)))


if __name__ == "__main__":
    main()
