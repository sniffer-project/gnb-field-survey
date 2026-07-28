"""Write ONLY the shared-gNB solution as a one-row My Maps CSV.

Solves the combined campaign (see solve_same_gnb.py), fits the local
Easting/Northing grid from the survey points (conformal transform from UTM 48N,
matching add_gnb_to_hall14_csv.py), and writes a single-row CSV with the gNB.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyproj

from gnb_triangulate.solver import solve_campaign
from solve_same_gnb import _build_campaign

_HERE = Path(__file__).resolve().parent
_DATA = _HERE.parent
_GRID_SRC = "20260701_hall14_mymaps.csv"  # any survey file: shared base grid
_OUT = _DATA / "20260701_shared_gnb.csv"

_TO_UTM = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32648", always_xy=True)


def _fit_local_grid(df: pd.DataFrame):
    """Least-squares conformal map UTM 48N -> this file's Easting/Northing."""
    pts = df[df["Point Name"].astype(str).str.lower().str.startswith("pt")]
    M, rhs = [], []
    for _, row in pts.iterrows():
        e_utm, n_utm = _TO_UTM.transform(row["Longitude"], row["Latitude"])
        M.append([e_utm, -n_utm, 1, 0])
        M.append([n_utm, e_utm, 0, 1])
        rhs.extend([row["Easting"], row["Northing"]])
    a, b, c, d = np.linalg.lstsq(np.array(M), np.array(rhs), rcond=None)[0]

    def to_local(lon: float, lat: float) -> tuple[float, float]:
        e_utm, n_utm = _TO_UTM.transform(lon, lat)
        return a * e_utm - b * n_utm + c, b * e_utm + a * n_utm + d

    return to_local


def main() -> None:
    sol = solve_campaign(_build_campaign())
    src = pd.read_csv(_DATA / _GRID_SRC)
    east, north = _fit_local_grid(src)(sol.longitude, sol.latitude)

    row = {col: None for col in src.columns}
    row.update(
        {
            "Point Name": "trilaterated gnb (shared, both surveys)",
            "Code": "gNB",
            "Easting": round(east, 4),
            "Northing": round(north, 4),
            "Elevation": round(sol.altitude_m, 4),
            "Latitude": round(sol.latitude, 8),
            "Longitude": round(sol.longitude, 8),
            "Altitude": round(sol.altitude_m, 4),
            "Measuring type": "Triangulated",
            "Local time": "2026-07-06 00:00:00",
            "Solution Status": "FIXED",
            "Measurement Method": "Weighted 3-D LS (Claude), 6 pts from both surveys",
        }
    )
    pd.DataFrame([row], columns=src.columns).to_csv(_OUT, index=False)
    print(
        f"Shared gNB: {sol.latitude:.7f}, {sol.longitude:.7f}  alt {sol.altitude_m:.2f} m "
        f"(horiz +/-{sol.horiz_sigma_m:.1f} m)\n  E {east:.1f}, N {north:.1f}  -> {_OUT.name}"
    )


if __name__ == "__main__":
    main()
