"""Join surveyed positions to binocular sightings into a solvable Survey.

This is the boundary where the two independently recorded files meet, so it is
where their disagreements have to surface. A sighting of a point that was never
surveyed is an error (that is what a mislabelled pt7/pt8 looks like); a
surveyed point that was never sighted is not (plenty of points are occupied
without a line of sight to the gNB).
"""

from __future__ import annotations

from collections import Counter

from .errors import SurveyDataError
from .models import BinocReading, Survey, Station, SurveyPoint

__all__ = ["SurveyDataError", "build_survey"]

# Three sightings are the minimum for a 3-D fix; two leaves the solver
# underdetermined and scipy fails with an opaque message instead.
_MIN_POINTS = 3


def build_survey(
    stations: tuple[Station, ...],
    readings: tuple[BinocReading, ...],
    name: str,
) -> Survey:
    """Pair each sighting with its surveyed station, in survey order."""
    by_name = {s.name.lower(): s for s in stations}
    counts = Counter(s.name.lower() for s in stations)
    duplicates = sorted(name for name, n in counts.items() if n > 1)
    if duplicates:
        raise SurveyDataError(
            f"MapPro CSV lists these points more than once: {', '.join(duplicates)}"
        )

    orphans = [r.name for r in readings if r.name.lower() not in by_name]
    if orphans:
        raise SurveyDataError(
            f"sighted but never surveyed: {', '.join(orphans)}. "
            f"Surveyed points are: {', '.join(s.name for s in stations)}. "
            "Check the point labels in the binocular workbook."
        )

    points = tuple(_survey_point(by_name[r.name.lower()], r) for r in readings)
    if len(points) < _MIN_POINTS:
        raise SurveyDataError(
            f"only {len(points)} sighting(s); at least {_MIN_POINTS} are needed "
            "to fix a position in 3-D."
        )
    return Survey(name=name, points=points)


def _survey_point(station: Station, reading: BinocReading) -> SurveyPoint:
    """Lift the ground mark to the height the binoculars were actually held at."""
    return SurveyPoint(
        label=station.name,
        latitude=station.latitude,
        longitude=station.longitude,
        altitude_m=station.ground_altitude_m + reading.instrument_height_m,
        elevation_deg=reading.angle_deg,
        distance_m=reading.distance_m,
    )
