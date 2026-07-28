import os
import pandas as pd
import pyproj
import numpy as np

# 1. Load the original CSV
csv_path = os.path.join(os.path.dirname(__file__), "20260701_mymaps.csv")
df = pd.read_csv(csv_path)

# 2. Fit conformal 2D transformation from UTM 48N (WGS84) to CSV Easting/Northing
t = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32648', always_xy=True)

e_utm_list = []
n_utm_list = []
e_csv_list = []
n_csv_list = []

for idx, row in df.iterrows():
    lat, lon = row['Latitude'], row['Longitude']
    e_csv, n_csv = row['Easting'], row['Northing']
    e_utm, n_utm = t.transform(lon, lat)
    e_utm_list.append(e_utm)
    n_utm_list.append(n_utm)
    e_csv_list.append(e_csv)
    n_csv_list.append(n_csv)

e_utm = np.array(e_utm_list)
n_utm = np.array(n_utm_list)
e_csv = np.array(e_csv_list)
n_csv = np.array(n_csv_list)

M = []
rhs = []
for i in range(len(e_utm)):
    M.append([e_utm[i], -n_utm[i], 1, 0])
    M.append([n_utm[i], e_utm[i], 0, 1])
    rhs.append(e_csv[i])
    rhs.append(n_csv[i])

M = np.array(M)
rhs = np.array(rhs)
p, res, rank, s = np.linalg.lstsq(M, rhs, rcond=None)
a, b, c, d = p

def utm_to_csv_coords(e, n):
    e_local = a * e - b * n + c
    n_local = b * e + a * n + d
    return e_local, n_local

# 3. Solved gNB positions
# Antigravity Original (sigma_theta = 1.0 deg)
lat_ag = 1.35237355
lon_ag = 103.68217910
alt_ag = 53.9160

# Claude Original (sigma_theta = 0.3 deg)
lat_cl = 1.35237467
lon_cl = 103.68217823
alt_cl = 53.7973

# Compute UTM 48N
e_utm_ag, n_utm_ag = t.transform(lon_ag, lat_ag)
e_utm_cl, n_utm_cl = t.transform(lon_cl, lat_cl)

# Compute Local CSV Easting/Northing
e_csv_ag, n_csv_ag = utm_to_csv_coords(e_utm_ag, n_utm_ag)
e_csv_cl, n_csv_cl = utm_to_csv_coords(e_utm_cl, n_utm_cl)

print("Antigravity gNB UTM 48N:", e_utm_ag, n_utm_ag)
print("Antigravity gNB Local CSV:", e_csv_ag, n_csv_ag)
print("Claude gNB UTM 48N:", e_utm_cl, n_utm_cl)
print("Claude gNB Local CSV:", e_csv_cl, n_csv_cl)

# 4. Create new rows
new_rows = []

# Template from the first row of CSV
row_template = df.iloc[0].copy()
# Reset all values to NaN or None
for col in row_template.index:
    row_template[col] = None

# Row 1: Antigravity gNB
row_ag = row_template.copy()
row_ag["Point Name"] = "gNB_triangulated_antigravity"
row_ag["Code"] = "gNB"
row_ag["Easting"] = round(e_csv_ag, 4)
row_ag["Northing"] = round(n_csv_ag, 4)
row_ag["Elevation"] = round(alt_ag, 4)
row_ag["Latitude"] = lat_ag
row_ag["Longitude"] = lon_ag
row_ag["Altitude"] = round(alt_ag, 4)
row_ag["Measuring type"] = "Triangulated"
row_ag["Local time"] = "2026-07-02 11:05:00"
row_ag["Solution Status"] = "FIXED"
row_ag["Measurement Method"] = "Least-squares (Antigravity implementation)"

# Row 2: Claude gNB
row_cl = row_template.copy()
row_cl["Point Name"] = "gNB_triangulated_claude"
row_cl["Code"] = "gNB"
row_cl["Easting"] = round(e_csv_cl, 4)
row_cl["Northing"] = round(n_csv_cl, 4)
row_cl["Elevation"] = round(alt_cl, 4)
row_cl["Latitude"] = lat_cl
row_cl["Longitude"] = lon_cl
row_cl["Altitude"] = round(alt_cl, 4)
row_cl["Measuring type"] = "Triangulated"
row_cl["Local time"] = "2026-07-02 11:05:00"
row_cl["Solution Status"] = "FIXED"
row_cl["Measurement Method"] = "Least-squares (Claude implementation)"

# 5. Append new rows to dataframe
df_new = pd.concat([df, pd.DataFrame([row_ag, row_cl])], ignore_index=True)

# 6. Save modified dataframe
output_name = "20260701_mymaps_with_gnb.csv"
output_path = os.path.join(os.path.dirname(__file__), output_name)
df_new.to_csv(output_path, index=False)

print(f"\nModified CSV saved successfully to: {output_path}")
print("Number of rows in original CSV:", len(df))
print("Number of rows in modified CSV:", len(df_new))
