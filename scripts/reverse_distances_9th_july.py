import sys
import pandas as pd
import numpy as np

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000.0  # Earth radius in meters
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    
    a = np.sin(dphi / 2.0)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0)**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c

# Load the CSV
csv_path = "/Users/zhunhao/Downloads/Hall 14 and CleanTechLoop 9th July Field Survey with Dr Siraj- Hall 14.csv"
df = pd.read_csv(csv_path)

# Extract gNB row
gnb_row = df[df["Point Name"].str.contains("gNB", case=False, na=True)]
if gnb_row.empty:
    print("Error: gNB_triangulated row not found in the CSV.")
    sys.exit(1)

gnb_lat = float(gnb_row["Latitude"].values[0])
gnb_lon = float(gnb_row["Longitude"].values[0])
gnb_alt = float(gnb_row["Altitude"].values[0])

# Filter out gNB to get survey points
df_survey = df[~df["Point Name"].str.contains("gNB", case=False, na=True)].copy()

results = []
for idx, row in df_survey.iterrows():
    pt_name = row["Point Name"]
    if pd.isna(pt_name):
        continue
    lat = float(row["Latitude"])
    lon = float(row["Longitude"])
    ground_alt = float(row["Elevation"])
    
    try:
        meas_height = float(row["Measuring height"]) if pd.notna(row["Measuring height"]) else 2.0
    except Exception:
        meas_height = 2.0
        
    inst_alt = ground_alt + meas_height
    
    # 2D Horizontal distance
    d2d = haversine_distance(lat, lon, gnb_lat, gnb_lon)
    
    # 3D Slant distance (Ground level)
    dz_ground = gnb_alt - ground_alt
    d3d_ground = np.sqrt(d2d**2 + dz_ground**2)
    elev_ground = np.degrees(np.arctan2(dz_ground, d2d))
    
    # 3D Slant distance (Instrument level)
    dz_inst = gnb_alt - inst_alt
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
print("="*95)
print("TRILATERATED gNB POSITION")
print(f"Latitude:  {gnb_lat:.8f}°")
print(f"Longitude: {gnb_lon:.8f}°")
print(f"Altitude:  {gnb_alt:.2f} m")
print("="*95)
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
print("="*95)
