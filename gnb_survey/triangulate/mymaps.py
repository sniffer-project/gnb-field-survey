"""Write a solved gNB, and its uncertainty, as a Google My Maps CSV.

A single pin claims a precision the data does not have: the horizontal
uncertainty here is a long thin ellipse, not a dot. So the file carries the gNB
plus a ring of points tracing the 95% confidence contour, and the map shows the
uncertainty instead of hiding it.

Why 95% and not "1 sigma": in two dimensions the 1-sigma ellipse contains only
1 - exp(-1/2) = 39.3% of the probability, not the 68% that "1 sigma" suggests
to almost everyone who reads it. The 95% contour sits at sqrt(-2*ln(0.05))
= 2.4477 sigma.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from . import geo
from .models import Solution

# Two-dimensional 95% confidence scale factor. In 2-D the probability inside
# k sigma is 1 - exp(-k^2/2), so 95% needs k = sqrt(-2*ln(0.05)).
CONFIDENCE_SCALE = math.sqrt(-2.0 * math.log(0.05))
CONFIDENCE_LABEL = "95%"

# Enough points to read as an ellipse; My Maps allows 2,000 rows per layer.
RING_POINTS = 36

# Copied verbatim from trilaterated_gnb.csv so the output concatenates with
# what this project already produces.
HEADER = (
    "Point Name",
    "Code",
    "Northing",
    "Easting",
    "Elevation",
    "Latitude",
    "Longitude",
    "Altitude",
    "Measuring type",
    "Measurement Method",
)

_GNB_CODE = "gNB"
_RING_CODE = "ellipse95"


def default_csv_name(campaign_name: str) -> str:
    """File name for a campaign's export, e.g. '20260716_gnb.csv'.

    Spaces become underscores so the result is safe to type unquoted.
    """
    safe = "_".join(str(campaign_name).split())
    return f"{safe}_gnb.csv"


def ellipse_ring(sol: Solution, points: int = RING_POINTS) -> tuple[tuple[float, float], ...]:
    """(latitude, longitude) tracing the 95% contour around the solution.

    Built in local ENU metres about the gNB, then converted back to geodetic.
    `ellipse_major_m` and `ellipse_minor_m` are SEMI-axes, so the ring spans
    twice these distances end to end.
    """
    if sol.ellipse_azimuth_deg is None:
        raise ValueError(
            "the error ellipse orientation is unavailable, so its ring cannot "
            "be drawn; refusing to emit a ring of the wrong shape"
        )

    origin = geo.make_origin(sol.latitude, sol.longitude, sol.altitude_m)
    semi_major = CONFIDENCE_SCALE * sol.ellipse_major_m
    semi_minor = CONFIDENCE_SCALE * sol.ellipse_minor_m
    azimuth = math.radians(sol.ellipse_azimuth_deg)
    sin_az, cos_az = math.sin(azimuth), math.cos(azimuth)

    ring: list[tuple[float, float]] = []
    for step in range(points):
        angle = 2.0 * math.pi * step / points
        along = semi_major * math.cos(angle)   # along the major axis
        across = semi_minor * math.sin(angle)  # perpendicular to it
        east = along * sin_az + across * cos_az
        north = along * cos_az - across * sin_az
        lat, lon, _ = geo.to_geodetic(east, north, 0.0, origin)
        ring.append((lat, lon))
    return tuple(ring)


def _row(name: str, code: str, lat: float, lon: float, alt: float, method: str) -> list[str]:
    return [
        name,
        code,
        "",  # Northing: My Maps positions by Latitude/Longitude alone
        "",  # Easting
        f"{alt:.4f}",
        f"{lat:.8f}",
        f"{lon:.8f}",
        f"{alt:.4f}",
        "Triangulated" if code == _GNB_CODE else "Derived",
        method,
    ]


def write_csv(sol: Solution, path: str | Path) -> int:
    """Write the gNB and its confidence ring. Returns the number of data rows."""
    out = Path(path)
    if out.parent and not out.parent.is_dir():
        raise ValueError(f"output directory does not exist: {out.parent}")

    ring = ellipse_ring(sol)  # raises before touching the filesystem

    rows = [
        _row(
            f"{sol.campaign_name} gNB",
            _GNB_CODE,
            sol.latitude,
            sol.longitude,
            sol.altitude_m,
            f"Weighted 3-D LS, {sol.n_points} pts",
        )
    ]
    ring_method = f"{CONFIDENCE_LABEL} confidence ({CONFIDENCE_SCALE:.2f} sigma)"
    for index, (lat, lon) in enumerate(ring, start=1):
        rows.append(
            _row(
                f"{sol.campaign_name} {CONFIDENCE_LABEL} ring {index:02d}",
                _RING_CODE,
                lat,
                lon,
                sol.altitude_m,
                ring_method,
            )
        )

    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return len(rows)
