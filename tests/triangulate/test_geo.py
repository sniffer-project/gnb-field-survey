"""geo round-trip accuracy."""

import math

from gnb_survey.triangulate import geo


def test_enu_roundtrip_sub_millimetre():
    origin = geo.make_origin(1.3528, 103.6816, 27.0)
    lat, lon, alt = 1.35315, 103.68185, 51.3
    e, n, u = geo.to_enu(lat, lon, alt, origin)
    lat2, lon2, alt2 = geo.to_geodetic(e, n, u, origin)

    # Convert degree error back to metres at this latitude for a fair tolerance.
    lat_err_m = abs(lat2 - lat) * origin.m_per_deg_lat
    lon_err_m = abs(lon2 - lon) * origin.m_per_deg_lon
    assert lat_err_m < 1e-3
    assert lon_err_m < 1e-3
    assert abs(alt2 - alt) < 1e-6


def test_origin_is_enu_zero():
    origin = geo.make_origin(1.3528, 103.6816, 27.0)
    e, n, u = geo.to_enu(1.3528, 103.6816, 27.0, origin)
    assert math.isclose(e, 0.0, abs_tol=1e-9)
    assert math.isclose(n, 0.0, abs_tol=1e-9)
    assert math.isclose(u, 0.0, abs_tol=1e-9)


def test_east_and_north_signs():
    origin = geo.make_origin(1.3528, 103.6816, 0.0)
    e, n, _ = geo.to_enu(1.3530, 103.6818, 0.0, origin)
    assert e > 0  # larger longitude -> east
    assert n > 0  # larger latitude -> north
