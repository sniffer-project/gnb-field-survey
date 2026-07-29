"""Immutable data models for gNB trilateration.

All structures are frozen dataclasses: data flows in, new objects flow out,
nothing is mutated in place.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Station:
    """A surveyed ground mark, straight from the MapPro export.

    Attributes:
        name:               Point Name as exported (e.g. "Pt1").
        latitude:           Decimal degrees, WGS84.
        longitude:          Decimal degrees, WGS84.
        ground_altitude_m:  The ``Altitude`` column -- the mark itself, with the
                            pole and antenna already reduced out.
        antenna_height_m:   ``Antenna Height``, kept only so the reduction can
                            be re-checked; never added back into the solve.
    """

    name: str
    latitude: float
    longitude: float
    ground_altitude_m: float
    antenna_height_m: float | None = None


@dataclass(frozen=True)
class BinocReading:
    """One handheld sighting of the gNB, from the binocular workbook.

    Recorded separately from the GNSS survey, at the same ground mark but at
    whatever height the observer held the binoculars.
    """

    name: str
    distance_m: float
    angle_deg: float
    instrument_height_m: float


@dataclass(frozen=True)
class SurveyPoint:
    """A single rangefinder observation of the gNB from a known location.

    Attributes:
        label:        Verbatim point name from the sheet (e.g. "Sniffer 1 (pt1)").
        latitude:     Decimal degrees, WGS84.
        longitude:    Decimal degrees, WGS84.
        altitude_m:   Metres above ellipsoid/MSL at the *sighting instrument*,
                      i.e. the ground mark plus the binocular height.
        elevation_deg: Angle of elevation to the gNB, degrees above horizontal.
        distance_m:   Slant (line-of-sight) distance to the gNB, metres.
    """

    label: str
    latitude: float
    longitude: float
    altitude_m: float
    elevation_deg: float
    distance_m: float


@dataclass(frozen=True)
class Survey:
    """One measurement survey = one gNB observed from several points."""

    name: str
    points: tuple[SurveyPoint, ...]


@dataclass(frozen=True)
class PointResidual:
    """Fit residual for one point: how far the solution misses its readings."""

    label: str
    distance_residual_m: float   # predicted - measured slant distance
    elevation_residual_deg: float  # predicted - measured elevation


@dataclass(frozen=True)
class Solution:
    """Result of trilaterating one survey's gNB."""

    survey_name: str
    latitude: float
    longitude: float
    altitude_m: float
    horiz_sigma_m: float          # 1-sigma circular-equivalent horizontal error
    ellipse_major_m: float        # 1-sigma error-ellipse SEMI-axes
    ellipse_minor_m: float
    vert_sigma_m: float           # 1-sigma vertical error
    condition_number: float       # geometry quality (higher = weaker)
    n_points: int
    residuals: tuple[PointResidual, ...]
    seed_method: str = "srls"     # how the refinement was initialised
    svy21_easting: float | None = None   # EPSG:3414 (output only)
    svy21_northing: float | None = None
    # The measurement model that was actually used...
    assumed_sigma_distance_m: float | None = None
    assumed_sigma_elevation_deg: float | None = None
    # ...beside what this survey's own residuals imply. Reported only: these
    # are never fed back into the solve, because a fit from a handful of points
    # is far too noisy to weight the next survey with.
    fitted_sigma_distance_m: float | None = None
    fitted_sigma_elevation_deg: float | None = None
    # Compass bearing of the major axis, degrees in [0, 180): 0 is north-south,
    # 90 is east-west. An axis has no direction, hence the half circle. Without
    # this the ellipse's size is known but not its orientation, and it cannot
    # be drawn.
    ellipse_azimuth_deg: float | None = None

    @property
    def well_constrained(self) -> bool:
        """At least 3 points and acceptable geometry conditioning."""
        return self.n_points >= 3 and self.condition_number < CONDITION_WARN_THRESHOLD


# Geometry conditioning above this is flagged as a weak / clustered layout.
CONDITION_WARN_THRESHOLD = 1.0e4
