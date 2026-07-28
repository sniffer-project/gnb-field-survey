import os
import pandas as pd
import numpy as np
import pyproj

# 1. Haversine distance function
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000.0  # Earth radius in meters
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    
    a = np.sin(dphi / 2.0)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0)**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c

# 2. Data directories
triangulate_dir = "/Users/zhunhao/Documents/Projects/temasek-lab/triangulate gnB position"
csv_path = os.path.join(triangulate_dir, "20260701_hall14_mymaps.csv")
df = pd.read_csv(csv_path)

# Filter out gNB rows to get only the survey points
df_survey = df[~df["Point Name"].str.contains("gNB|trilaterated", case=False, na=True)].copy()

# 3. Define the solved gNB positions
# New Mymaps campaign solved locations (using the 20260701_mymaps.csv 8 points)
gnb_mymaps_claude = {"lat": 1.35237467, "lon": 103.68217823, "alt": 53.7973, "easting": 11179.7688, "northing": 37164.7598, "name": "Mymaps Solved (Claude)"}
gnb_mymaps_antigravity = {"lat": 1.35237355, "lon": 103.68217910, "alt": 53.9160, "easting": 11179.8660, "northing": 37164.6363, "name": "Mymaps Solved (Antigravity)"}

# Original Hall 14 campaign solved locations (using the measurment.xlsx 6 points)
gnb_hall14_claude = {"lat": 1.35240008, "lon": 103.68221236, "alt": 52.8556, "easting": 11183.5670, "northing": 37167.5692, "name": "Original Hall 14 (Claude)"}
gnb_hall14_antigravity = {"lat": 1.35238359, "lon": 103.68219229, "alt": 52.8260, "easting": 11181.3340, "northing": 37165.7460, "name": "Original Hall 14 (Antigravity)"}

# Create Triangulation Results DataFrame
triangulation_results = [
    {
        "Dataset": "20260701_mymaps (8 pts)",
        "Solver / Implementation": "Antigravity Original (sigma_theta=1.0 deg)",
        "WGS84 Latitude": gnb_mymaps_antigravity["lat"],
        "WGS84 Longitude": gnb_mymaps_antigravity["lon"],
        "Altitude (m)": gnb_mymaps_antigravity["alt"],
        "SVY21 Easting (m)": gnb_mymaps_antigravity["easting"],
        "SVY21 Northing (m)": gnb_mymaps_antigravity["northing"],
        "Horizontal Error 1σ (m)": 0.2882, # circular error from covariance
        "Vertical Error 1σ (m)": 0.1492,
        "Model RMSE": 0.4733
    },
    {
        "Dataset": "20260701_mymaps (8 pts)",
        "Solver / Implementation": "Claude Original (sigma_theta=0.3 deg)",
        "WGS84 Latitude": gnb_mymaps_claude["lat"],
        "WGS84 Longitude": gnb_mymaps_claude["lon"],
        "Altitude (m)": gnb_mymaps_claude["alt"],
        "SVY21 Easting (m)": gnb_mymaps_claude["easting"],
        "SVY21 Northing (m)": gnb_mymaps_claude["northing"],
        "Horizontal Error 1σ (m)": 0.3499,
        "Vertical Error 1σ (m)": 0.2833,
        "Model RMSE": 0.4853
    },
    {
        "Dataset": "Original Hall 14 (6 pts)",
        "Solver / Implementation": "Antigravity Original",
        "WGS84 Latitude": gnb_hall14_antigravity["lat"],
        "WGS84 Longitude": gnb_hall14_antigravity["lon"],
        "Altitude (m)": gnb_hall14_antigravity["alt"],
        "SVY21 Easting (m)": gnb_hall14_antigravity["easting"],
        "SVY21 Northing (m)": gnb_hall14_antigravity["northing"],
        "Horizontal Error 1σ (m)": 2.1793,
        "Vertical Error 1σ (m)": 0.4880,
        "Model RMSE": 0.6682
    },
    {
        "Dataset": "Original Hall 14 (6 pts)",
        "Solver / Implementation": "Claude Original",
        "WGS84 Latitude": gnb_hall14_claude["lat"],
        "WGS84 Longitude": gnb_hall14_claude["lon"],
        "Altitude (m)": gnb_hall14_claude["alt"],
        "SVY21 Easting (m)": gnb_hall14_claude["easting"],
        "SVY21 Northing (m)": gnb_hall14_claude["northing"],
        "Horizontal Error 1σ (m)": 4.4000,
        "Vertical Error 1σ (m)": 0.4000,
        "Model RMSE": 0.6800
    }
]
df_triangulation = pd.DataFrame(triangulation_results)

# 4. Generate reverse-engineered distances helper
def generate_reverse_df(gnb):
    results = []
    for idx, row in df_survey.iterrows():
        pt_name = row["Point Name"]
        lat = float(row["Latitude"])
        lon = float(row["Longitude"])
        ground_alt = float(row["Elevation"])
        meas_height = float(row["Measuring height"]) if pd.notna(row["Measuring height"]) else 2.0
        inst_alt = ground_alt + meas_height
        
        # 2D Horizontal distance
        d2d = haversine_distance(lat, lon, gnb["lat"], gnb["lon"])
        
        # 3D Slant distance (Ground level)
        dz_ground = gnb["alt"] - ground_alt
        d3d_ground = np.sqrt(d2d**2 + dz_ground**2)
        elev_ground = np.degrees(np.arctan2(dz_ground, d2d))
        
        # 3D Slant distance (Instrument level)
        dz_inst = gnb["alt"] - inst_alt
        d3d_inst = np.sqrt(d2d**2 + dz_inst**2)
        elev_inst = np.degrees(np.arctan2(dz_inst, d2d))
        
        results.append({
            "Point Name": pt_name,
            "Latitude (deg)": lat,
            "Longitude (deg)": lon,
            "Ground Alt (m)": ground_alt,
            "Instrument Alt (m)": inst_alt,
            "2D Distance (m)": d2d,
            "3D Dist Ground (m)": d3d_ground,
            "Elevation Ground (deg)": elev_ground,
            "3D Dist Inst (m)": d3d_inst,
            "Elevation Inst (deg)": elev_inst
        })
    return pd.DataFrame(results)

df_rev_mymaps = generate_reverse_df(gnb_mymaps_claude)
df_rev_hall14 = generate_reverse_df(gnb_hall14_claude)

# 5. Export to Excel Workbook
xlsx_name = "20260701_triangulation_and_reverse_math.xlsx"
xlsx_path = os.path.join(triangulate_dir, xlsx_name)

with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
    df_triangulation.to_excel(writer, sheet_name="gNB_Triangulation_Results", index=False)
    df_rev_mymaps.to_excel(writer, sheet_name="Reverse_Math_Mymaps_gNB", index=False)
    df_rev_hall14.to_excel(writer, sheet_name="Reverse_Math_Original_gNB", index=False)

print(f"\nExcel workbook created successfully at: {xlsx_path}")
# Check if sheets are correct
import openpyxl
wb = openpyxl.load_workbook(xlsx_path)
print("Sheets in workbook:", wb.sheetnames)
