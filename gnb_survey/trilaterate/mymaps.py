"""Write a solved gNB as a Google My Maps CSV.

One row, one pin. My Maps draws every CSV row as its own marker, so a ring of
points tracing the confidence contour arrives as a scatter of dozens of pins
rather than an ellipse — unreadable. The uncertainty instead rides along as
text on the gNB pin, so the map still states it rather than implying a
precision the data does not have.

Why 95% and not "1 sigma": in two dimensions the 1-sigma ellipse contains only
1 - exp(-1/2) = 39.3% of the probability, not the 68% that "1 sigma" suggests
to almost everyone who reads it. The 95% contour sits at sqrt(-2*ln(0.05))
= 2.4477 sigma.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from .models import Solution

# Two-dimensional 95% confidence scale factor. In 2-D the probability inside
# k sigma is 1 - exp(-k^2/2), so 95% needs k = sqrt(-2*ln(0.05)).
CONFIDENCE_SCALE = math.sqrt(-2.0 * math.log(0.05))
CONFIDENCE_LABEL = "95%"

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


def default_csv_name(survey_name: str) -> str:
    """File name for a survey's export, e.g. '20260716_gnb.csv'.

    Spaces become underscores so the result is safe to type unquoted.
    """
    safe = "_".join(str(survey_name).split())
    return f"{safe}_gnb.csv"


def uncertainty_note(sol: Solution) -> str:
    """The 95% ellipse as text, e.g. '95% ellipse 15.7 x 3.4 m @ 118 deg'.

    Full axes, not semi-axes, because that is what a reader pacing out the
    ground would measure. The bearing is omitted when unknown.
    """
    major = 2.0 * CONFIDENCE_SCALE * sol.ellipse_major_m
    minor = 2.0 * CONFIDENCE_SCALE * sol.ellipse_minor_m
    note = f"{CONFIDENCE_LABEL} ellipse {major:.1f} x {minor:.1f} m"
    if sol.ellipse_azimuth_deg is None:
        return note
    return f"{note} @ {sol.ellipse_azimuth_deg:.0f} deg"


def write_csv(sol: Solution, path: str | Path) -> None:
    """Write the gNB as a single My Maps pin."""
    out = Path(path)
    if out.parent and not out.parent.is_dir():
        raise ValueError(f"output directory does not exist: {out.parent}")

    row = [
        f"{sol.survey_name} gNB",
        _GNB_CODE,
        "",  # Northing: My Maps positions by Latitude/Longitude alone
        "",  # Easting
        f"{sol.altitude_m:.4f}",
        f"{sol.latitude:.8f}",
        f"{sol.longitude:.8f}",
        f"{sol.altitude_m:.4f}",
        "Trilaterated",
        f"Weighted 3-D LS, {sol.n_points} pts, {uncertainty_note(sol)}",
    ]

    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerow(row)
