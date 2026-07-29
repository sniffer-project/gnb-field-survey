"""Geodetic <-> local ENU conversions.

For a survey area only a few hundred metres across, a local tangent-plane
(East-North-Up) approximation about a chosen origin is accurate to well under
a centimetre, and keeps the solver in a clean flat metric frame.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# WGS84 ellipsoid parameters.
_WGS84_A = 6378137.0           # semi-major axis (m)
_WGS84_F = 1.0 / 298.257223563  # flattening
_WGS84_E2 = _WGS84_F * (2.0 - _WGS84_F)  # eccentricity squared


@dataclass(frozen=True)
class Origin:
    """Local tangent-plane origin and the metres-per-degree scale at that lat."""

    latitude: float
    longitude: float
    altitude_m: float
    m_per_deg_lat: float
    m_per_deg_lon: float


def _meridian_scales(latitude_deg: float) -> tuple[float, float]:
    """Metres per degree of latitude and longitude at a given latitude."""
    lat = math.radians(latitude_deg)
    sin2 = math.sin(lat) ** 2
    # Radii of curvature.
    denom = (1.0 - _WGS84_E2 * sin2)
    m = _WGS84_A * (1.0 - _WGS84_E2) / (denom ** 1.5)   # meridional
    n = _WGS84_A / math.sqrt(denom)                      # prime vertical
    m_per_deg_lat = math.radians(1.0) * m
    m_per_deg_lon = math.radians(1.0) * n * math.cos(lat)
    return m_per_deg_lat, m_per_deg_lon


def make_origin(latitude: float, longitude: float, altitude_m: float = 0.0) -> Origin:
    """Build a local ENU origin at the given geodetic point."""
    m_lat, m_lon = _meridian_scales(latitude)
    return Origin(latitude, longitude, altitude_m, m_lat, m_lon)


def to_enu(latitude: float, longitude: float, altitude_m: float, origin: Origin) -> tuple[float, float, float]:
    """Geodetic -> local East/North/Up metres relative to origin."""
    east = (longitude - origin.longitude) * origin.m_per_deg_lon
    north = (latitude - origin.latitude) * origin.m_per_deg_lat
    up = altitude_m - origin.altitude_m
    return east, north, up


def to_geodetic(east: float, north: float, up: float, origin: Origin) -> tuple[float, float, float]:
    """Local East/North/Up metres -> geodetic latitude/longitude/altitude."""
    longitude = origin.longitude + east / origin.m_per_deg_lon
    latitude = origin.latitude + north / origin.m_per_deg_lat
    altitude_m = origin.altitude_m + up
    return latitude, longitude, altitude_m


def to_svy21(latitude: float, longitude: float) -> tuple[float, float] | None:
    """WGS84 lat/lon -> SVY21 / EPSG:3414 easting, northing (metres).

    Output only -- never used in the solve (the trilateration runs in true-
    distance ENU). Returns None if pyproj is unavailable.
    """
    transformer = _svy21_transformer()
    if transformer is None:
        return None
    easting, northing = transformer.transform(longitude, latitude)
    return easting, northing


def _svy21_transformer():
    """Lazily build and cache the EPSG:4326 -> EPSG:3414 transformer."""
    global _SVY21_TRANSFORMER
    if _SVY21_TRANSFORMER is _UNSET:
        try:
            from pyproj import Transformer

            _SVY21_TRANSFORMER = Transformer.from_crs("EPSG:4326", "EPSG:3414", always_xy=True)
        except Exception:
            _SVY21_TRANSFORMER = None
    return _SVY21_TRANSFORMER


_UNSET = object()
_SVY21_TRANSFORMER = _UNSET
