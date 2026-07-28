import os
import pandas as pd
import numpy as np

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

# 2. Load the modified 20260701_hall14_mymaps.csv
csv_path = "/Users/zhunhao/Documents/Projects/temasek-lab/triangulate gnB position/20260701_hall14_mymaps.csv"
df = pd.read_csv(csv_path)

# Filter out the gNB rows we added to get only the survey points
df_survey = df[~df["Point Name"].str.contains("gNB|trilaterated", case=False, na=True)].copy()

# 3. Define the two candidate gNB positions
# Position A: Solved from the 20260701_mymaps.csv dataset (this conversation's focus)
gnb_mymaps_claude = {"lat": 1.35237467, "lon": 103.68217823, "alt": 53.7973, "name": "Mymaps Solved (Claude)"}
gnb_mymaps_antigravity = {"lat": 1.35237355, "lon": 103.68217910, "alt": 53.9160, "name": "Mymaps Solved (Antigravity)"}

# Position B: Original Hall 14 Solved from measurment.xlsx (from README.md)
gnb_hall14_claude = {"lat": 1.35240008, "lon": 103.68221236, "alt": 52.8556, "name": "Original Hall 14 (Claude)"}
gnb_hall14_antigravity = {"lat": 1.35238359, "lon": 103.68219229, "alt": 52.8260, "name": "Original Hall 14 (Antigravity)"}

gNBs = [gnb_mymaps_claude, gnb_mymaps_antigravity, gnb_hall14_claude, gnb_hall14_antigravity]

# 4. Compute distances for each gNB position
for gnb in gNBs:
    print("\n" + "="*95)
    print(f"REVERSE ENGINEERED DISTANCES TO: {gnb['name']}")
    print(f"Coordinates: Lat {gnb['lat']:.8f}°, Lon {gnb['lon']:.8f}°, Alt {gnb['alt']:.2f} m")
    print("="*95)
    
    results = []
    for idx, row in df_survey.iterrows():
        pt_name = row["Point Name"]
        lat = float(row["Latitude"])
        lon = float(row["Longitude"])
        ground_alt = float(row["Elevation"])
        
        # Determine measuring/antenna height if available, default to 2.0m if nan
        try:
            meas_height = float(row["Measuring height"]) if pd.notna(row["Measuring height"]) else 2.0
        except Exception:
            meas_height = 2.0
            
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
            "Point": pt_name,
            "Lat": lat,
            "Lon": lon,
            "Gr Alt (m)": ground_alt,
            "Inst Alt (m)": inst_alt,
            "2D Dist (m)": d2d,
            "3D Dist Gr (m)": d3d_ground,
            "Elev Gr (°)": elev_ground,
            "3D Dist Inst (m)": d3d_inst,
            "Elev Inst (°)": elev_inst
        })
        
    res_df = pd.DataFrame(results)
    print(res_df.to_string(index=False, formatters={
        "Lat": "{:.8f}".format,
        "Lon": "{:.8f}".format,
        "Gr Alt (m)": "{:.2f}".format,
        "Inst Alt (m)": "{:.2f}".format,
        "2D Dist (m)": "{:.2f}".format,
        "3D Dist Gr (m)": "{:.2f}".format,
        "Elev Gr (°)": "{:.1f}".format,
        "3D Dist Inst (m)": "{:.2f}".format,
        "Elev Inst (°)": "{:.1f}".format
    }))
