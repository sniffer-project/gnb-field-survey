"""Reverse calc: distance + elevation angle from each point to the shared gNB.

Given the trilaterated gNB and each point's known coordinates (RTK lat/lon +
ground altitude + measuring height), compute the predicted slant distance and
angle of elevation, and compare to the measured rangefinder readings.
"""

from __future__ import annotations

import math

from gnb_triangulate import geo
from gnb_triangulate.solver import solve_campaign
from solve_same_gnb import _build_campaign


def main() -> None:
    campaign = _build_campaign()
    sol = solve_campaign(campaign)

    # Local ENU frame about the gNB; each point's vector back to it.
    origin = geo.make_origin(sol.latitude, sol.longitude, sol.altitude_m)
    gx, gy, gz = geo.to_enu(sol.latitude, sol.longitude, sol.altitude_m, origin)

    print(
        f"Shared gNB: {sol.latitude:.7f}, {sol.longitude:.7f}  alt {sol.altitude_m:.2f} m\n"
    )
    header = (
        f"{'Point':<16}{'pred dist':>10}{'meas dist':>10}{'d dist':>8}"
        f"{'pred elev':>11}{'meas elev':>11}{'d elev':>8}"
    )
    print(header)
    print("-" * len(header))

    for p in campaign.points:
        px, py, pz = geo.to_enu(p.latitude, p.longitude, p.altitude_m, origin)
        dx, dy, dz = gx - px, gy - py, gz - pz
        horiz = math.hypot(dx, dy)
        slant = math.hypot(horiz, dz)
        elev = math.degrees(math.atan2(dz, horiz))
        print(
            f"{p.label:<16}{slant:>9.1f}m{p.distance_m:>9.1f}m{slant - p.distance_m:>+7.1f}"
            f"{elev:>10.1f}°{p.elevation_deg:>10.1f}°{elev - p.elevation_deg:>+7.1f}"
        )


if __name__ == "__main__":
    main()
