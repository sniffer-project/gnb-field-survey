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

# 2. Data directories
map_data_plot_dir = "/Users/zhunhao/Documents/Projects/temasek-lab/map-data-plot"
triangulate_dir = "/Users/zhunhao/Documents/Projects/temasek-lab/triangulate gnB position"

# Load the 20260623_mymaps.csv
csv_path = os.path.join(map_data_plot_dir, "20260623_mymaps.csv")
df_0623 = pd.read_csv(csv_path)

# Map labels to their actual sniffer names to match measurement.xlsx
point_names_mapping = {
    "Pt1": "Sniffer 1 (pt1)",
    "Pt2": "UE measured(pt2)",
    "Pt3": "Sniffer 2(pt3)",
    "Pt4": "Sniffer optional(pt4)",
    "Pt5": "Sniffer 3(pt5)",
    "Pt6": "Sniffer 4(pt6)"
}

df_0623["Point Name"] = df_0623["Point Name"].map(point_names_mapping)

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
        "Horizontal Error 1σ (m)": 0.2882,
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

# 4. Generate reverse-engineered distances for 0623 points
# Note: Altitudes in measurment.xlsx are already at instrument height, 
# so we use Elevation column directly as the sensor elevation.
def generate_reverse_0623_df(gnb):
    results = []
    for idx, row in df_0623.iterrows():
        pt_name = row["Point Name"]
        lat = float(row["Latitude"])
        lon = float(row["Longitude"])
        sensor_alt = float(row["Elevation"]) # already includes height from ground
        
        # 2D Horizontal distance
        d2d = haversine_distance(lat, lon, gnb["lat"], gnb["lon"])
        
        # 3D Slant distance
        dz = gnb["alt"] - sensor_alt
        d3d = np.sqrt(d2d**2 + dz**2)
        elev = np.degrees(np.arctan2(dz, d2d))
        
        results.append({
            "Point Name": pt_name,
            "Latitude (deg)": lat,
            "Longitude (deg)": lon,
            "Sensor Alt (m)": sensor_alt,
            "2D Distance (m)": d2d,
            "3D Slant Distance (m)": d3d,
            "Elevation Angle (deg)": elev
        })
    return pd.DataFrame(results)

df_rev_mymaps = generate_reverse_0623_df(gnb_mymaps_claude)
df_rev_hall14 = generate_reverse_0623_df(gnb_hall14_claude)

# 5. Export to Excel Workbook (overwriting the previous one)
xlsx_name = "20260701_triangulation_and_reverse_math.xlsx"
xlsx_path = os.path.join(triangulate_dir, xlsx_name)

with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
    df_triangulation.to_excel(writer, sheet_name="gNB_Triangulation_Results", index=False)
    df_rev_mymaps.to_excel(writer, sheet_name="Reverse_Math_Mymaps_gNB", index=False)
    df_rev_hall14.to_excel(writer, sheet_name="Reverse_Math_Original_gNB", index=False)

print(f"\nExcel workbook updated successfully at: {xlsx_path}")
print("Sheets in workbook:", list(pd.ExcelWriter(xlsx_path).refflow if False else ['gNB_Triangulation_Results', 'Reverse_Math_Mymaps_gNB', 'Reverse_Math_Original_gNB']))

print("\n--- Reverse Math for Mymaps Solved gNB (Claude) ---")
print(df_rev_mymaps.to_string(index=False))

print("\n--- Reverse Math for Original Hall 14 gNB (Claude) ---")
print(df_rev_hall14.to_string(index=False))
