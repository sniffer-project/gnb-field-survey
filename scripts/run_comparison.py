import os
import sys
import pandas as pd
import numpy as np
from scipy.optimize import least_squares

# Add local path and sibling paths to python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "claude")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "antigravity")))

from svy21 import SVY21
from gnb_triangulate import geo
from gnb_triangulate.models import Campaign, SurveyPoint
import gnb_triangulate.solver

# 1. Load the CSV
csv_path = os.path.join(os.path.dirname(__file__), "20260701_mymaps.csv")
df = pd.read_csv(csv_path)

# User provided rangefinder measurements
measurements = {
    "Pt1": {"distance": 31.8, "elevation": 45.0, "height_from_ground_cm": 186.0},
    "Pt2": {"distance": 33.2, "elevation": 45.0, "height_from_ground_cm": 184.0},
    "Pt3": {"distance": 26.7, "elevation": 59.0, "height_from_ground_cm": 190.0},
    "Pt4": {"distance": 36.7, "elevation": 38.0, "height_from_ground_cm": 201.0},
    "Pt5": {"distance": 26.2, "elevation": 48.0, "height_from_ground_cm": 191.0},
    "Pt6": {"distance": 39.4, "elevation": 36.0, "height_from_ground_cm": 199.0},
    "Pt7": {"distance": 33.6, "elevation": 44.0, "height_from_ground_cm": 184.0},
    "Pt8": {"distance": 34.5, "elevation": 42.0, "height_from_ground_cm": 184.0},
}

# Construct survey points
parsed_points = []
for idx, row in df.iterrows():
    pt_name = str(row["Point Name"]).strip()
    match_key = None
    for k in measurements.keys():
        if k.lower() == pt_name.lower():
            match_key = k
            break
    
    if match_key is None:
        continue
        
    meas = measurements[match_key]
    lat = float(row["Latitude"])
    lon = float(row["Longitude"])
    ground_alt = float(row["Elevation"])
    h_fg = meas["height_from_ground_cm"] / 100.0  # convert to meters
    instrument_alt = ground_alt + h_fg
    
    parsed_points.append({
        "name": pt_name,
        "lat": lat,
        "lon": lon,
        "ground_alt": ground_alt,
        "height_from_ground": h_fg,
        "instrument_alt": instrument_alt,
        "distance": meas["distance"],
        "elevation": meas["elevation"],
    })

# Project points to SVY21
svy = SVY21()
points_svy = []
for pt in parsed_points:
    x, y = svy.compute_svy21(pt['lat'], pt['lon'])
    points_svy.append({
        'name': pt['name'],
        'x': x, 'y': y, 'z': pt['instrument_alt'],
        'angle': pt['elevation'], 'distance': pt['distance']
    })

def residual_function_antigravity(G, points_svy, sigma_d=1.0, sigma_theta_rad=np.radians(1.0)):
    x_g, y_g, z_g = G
    residuals = []
    for pt in points_svy:
        x_i, y_i, z_i = pt['x'], pt['y'], pt['z']
        d_meas = pt['distance']
        theta_meas_rad = np.radians(pt['angle'])
        
        dx = x_g - x_i
        dy = y_g - y_i
        dz = z_g - z_i
        d_mod = np.sqrt(dx**2 + dy**2 + dz**2)
        r_mod = np.sqrt(dx**2 + dy**2)
        theta_mod = np.arctan2(dz, r_mod)
        
        res_d = (d_mod - d_meas) / sigma_d
        res_theta = (theta_mod - theta_meas_rad) / sigma_theta_rad
        
        residuals.append(res_d)
        residuals.append(res_theta)
    return np.array(residuals)

# Bound limits
xs = [p['x'] for p in points_svy]
ys = [p['y'] for p in points_svy]
zs_est = [p['z'] + p['distance'] * np.sin(np.radians(p['angle'])) for p in points_svy]
x0_antigravity = [np.mean(xs), np.mean(ys), np.mean(zs_est)]
lower_bounds = [min(xs) - 500, min(ys) - 500, min([p['z'] for p in points_svy]) - 10]
upper_bounds = [max(xs) + 500, max(ys) + 500, max([p['z'] for p in points_svy]) + 150]

# Build SurveyPoint objects for Claude
survey_points = []
for pt in parsed_points:
    sp = SurveyPoint(
        label=pt["name"],
        latitude=pt["lat"],
        longitude=pt["lon"],
        altitude_m=pt["instrument_alt"],
        elevation_deg=pt["elevation"],
        distance_m=pt["distance"]
    )
    survey_points.append(sp)
campaign = Campaign(name="20260701_mymaps", points=tuple(survey_points))

# Run 4 scenarios:
# 1. Antigravity with sigma_theta = 1.0 deg
res_ag_1_0 = least_squares(
    residual_function_antigravity, x0_antigravity, 
    args=(points_svy, 1.0, np.radians(1.0)),
    bounds=(lower_bounds, upper_bounds), method='trf'
)
x_ag_1_0 = res_ag_1_0.x
lat_ag_1_0, lon_ag_1_0 = svy.compute_wgs84(x_ag_1_0[0], x_ag_1_0[1])

# Compute errors for Antigravity 1.0
jacobian_ag_1_0 = res_ag_1_0.jac
jtj_ag_1_0 = np.dot(jacobian_ag_1_0.T, jacobian_ag_1_0) + np.eye(3) * 1e-10
dof_ag_1_0 = len(res_ag_1_0.fun) - 3
mse_ag_1_0 = np.sum(res_ag_1_0.fun**2) / dof_ag_1_0 if dof_ag_1_0 > 0 else 1.0
cov_ag_1_0 = np.linalg.inv(jtj_ag_1_0) * mse_ag_1_0
std_errors_ag_1_0 = np.sqrt(np.diag(cov_ag_1_0))

# 2. Claude with sigma_theta = 1.0 deg
gnb_triangulate.solver.SIGMA_ELEVATION_DEG = 1.0
sol_cl_1_0 = gnb_triangulate.solver.solve_campaign(campaign)

# 3. Antigravity with sigma_theta = 0.3 deg
res_ag_0_3 = least_squares(
    residual_function_antigravity, x0_antigravity, 
    args=(points_svy, 1.0, np.radians(0.3)),
    bounds=(lower_bounds, upper_bounds), method='trf'
)
x_ag_0_3 = res_ag_0_3.x
lat_ag_0_3, lon_ag_0_3 = svy.compute_wgs84(x_ag_0_3[0], x_ag_0_3[1])

# 4. Claude with sigma_theta = 0.3 deg
gnb_triangulate.solver.SIGMA_ELEVATION_DEG = 0.3
sol_cl_0_3 = gnb_triangulate.solver.solve_campaign(campaign)

print("\n" + "="*70)
print(f"{'Solver / Scenario':<40} | {'Easting (m)':<12} | {'Northing (m)':<12} | {'Altitude (m)':<12}")
print("-" * 85)
print(f"{'Antigravity Original (sigma_theta = 1.0 deg)':<40} | {x_ag_1_0[0]:<12.4f} | {x_ag_1_0[1]:<12.4f} | {x_ag_1_0[2]:<12.4f}")
print(f"{'Claude Aligned (sigma_theta = 1.0 deg)':<40} | {sol_cl_1_0.svy21_easting:<12.4f} | {sol_cl_1_0.svy21_northing:<12.4f} | {sol_cl_1_0.altitude_m:<12.4f}")
print(f"{'Antigravity Aligned (sigma_theta = 0.3 deg)':<40} | {x_ag_0_3[0]:<12.4f} | {x_ag_0_3[1]:<12.4f} | {x_ag_0_3[2]:<12.4f}")
print(f"{'Claude Original (sigma_theta = 0.3 deg)':<40} | {sol_cl_0_3.svy21_easting:<12.4f} | {sol_cl_0_3.svy21_northing:<12.4f} | {sol_cl_0_3.altitude_m:<12.4f}")
print("="*70)

# Calculate differences
diff_1_0_horiz = np.sqrt((x_ag_1_0[0] - sol_cl_1_0.svy21_easting)**2 + (x_ag_1_0[1] - sol_cl_1_0.svy21_northing)**2)
diff_1_0_vert = abs(x_ag_1_0[2] - sol_cl_1_0.altitude_m)

diff_0_3_horiz = np.sqrt((x_ag_0_3[0] - sol_cl_0_3.svy21_easting)**2 + (x_ag_0_3[1] - sol_cl_0_3.svy21_northing)**2)
diff_0_3_vert = abs(x_ag_0_3[2] - sol_cl_0_3.altitude_m)

print(f"\nDifferences when aligned at sigma_theta = 1.0 deg:")
print(f"  Horizontal Difference: {diff_1_0_horiz:.6f} m")
print(f"  Vertical Difference:   {diff_1_0_vert:.6f} m")

print(f"\nDifferences when aligned at sigma_theta = 0.3 deg:")
print(f"  Horizontal Difference: {diff_0_3_horiz:.6f} m")
print(f"  Vertical Difference:   {diff_0_3_vert:.6f} m")

# Let's compute standard errors for Claude original and write detailed stats
print("\n--- Detailed Stats for Claude Original (0.3 deg) ---")
print(f"WGS84: ({sol_cl_0_3.latitude:.8f}, {sol_cl_0_3.longitude:.8f})")
print(f"Easting:  {sol_cl_0_3.svy21_easting:.4f} m (ellipse major error: {sol_cl_0_3.ellipse_major_m:.4f} m, minor: {sol_cl_0_3.ellipse_minor_m:.4f} m)")
print(f"Northing: {sol_cl_0_3.svy21_northing:.4f} m")
print(f"Altitude: {sol_cl_0_3.altitude_m:.4f} \u00b1 {sol_cl_0_3.vert_sigma_m:.4f} m")

print("\n--- Detailed Stats for Antigravity Original (1.0 deg) ---")
print(f"WGS84: ({lat_ag_1_0:.8f}, {lon_ag_1_0:.8f})")
print(f"Easting:  {x_ag_1_0[0]:.4f} \u00b1 {std_errors_ag_1_0[0]:.4f} m")
print(f"Northing: {x_ag_1_0[1]:.4f} \u00b1 {std_errors_ag_1_0[1]:.4f} m")
print(f"Altitude: {x_ag_1_0[2]:.4f} \u00b1 {std_errors_ag_1_0[2]:.4f} m")
