import os
import glob
import pandas as pd
import numpy as np
import re

# Geodetic distance function (Haversine formula)
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000.0  # Earth radius in meters
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    
    a = np.sin(dphi / 2.0)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0)**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c

# Directories
map_data_plot_dir = "/Users/zhunhao/Documents/Projects/temasek-lab/map-data-plot"
triangulate_dir = "/Users/zhunhao/Documents/Projects/temasek-lab/triangulate gnB position"

# Load the target CSV files
target_files = {
    "20260701_mymaps.csv": os.path.join(triangulate_dir, "20260701_mymaps.csv"),
    "20260701_hall14_mymaps.csv": os.path.join(triangulate_dir, "20260701_hall14_mymaps.csv")
}

# Load target points
target_points = {}
for name, path in target_files.items():
    if os.path.exists(path):
        df = pd.read_csv(path)
        # Exclude triangulated gNB points to only compare survey points
        df_survey = df[~df["Point Name"].str.contains("gNB|trilaterated", case=False, na=True)]
        points = []
        for idx, row in df_survey.iterrows():
            points.append({
                "name": row["Point Name"],
                "lat": float(row["Latitude"]),
                "lon": float(row["Longitude"])
            })
        target_points[name] = points
        print(f"Loaded {len(points)} survey points from {name}")

# Find all CSV files in map-data-plot
csv_files = glob.glob(os.path.join(map_data_plot_dir, "*.csv"))

# Parse date and type of CSV files
file_details = []
for f in csv_files:
    basename = os.path.basename(f)
    # Skip the 20260701 files we are comparing against to avoid trivial 0m matches
    if "20260701" in basename:
        continue
    
    # Try to parse date from basename (e.g. 20260519 or 2026-05-19)
    date_match = re.search(r"2026-?(\d{2})-?(\d{2})", basename)
    if date_match:
        month = date_match.group(1)
        day = date_match.group(2)
        date_str = f"2026-{month}-{day}"
    else:
        # Fallback to mtime
        mtime = os.path.getmtime(f)
        date_str = pd.to_datetime(mtime, unit='s').strftime('%Y-%m-%d')
        
    file_details.append({
        "path": f,
        "name": basename,
        "date": date_str
    })

# Sort by date (newest first)
file_details.sort(key=lambda x: x["date"], reverse=True)

print(f"\nFound {len(file_details)} candidate CSV files in map-data-plot to check.")

# Check distances
for target_name, t_pts in target_points.items():
    print(f"\n" + "="*80)
    print(f"CHECKING FOR POINTS WITHIN 50M OF: {target_name}")
    print(f"="*80)
    
    matches_found = False
    for f_info in file_details:
        f_path = f_info["path"]
        f_name = f_info["name"]
        f_date = f_info["date"]
        
        try:
            # Read with latin-1 to avoid encoding errors with degree symbol
            df_other = pd.read_csv(f_path, encoding='latin-1')
            # Ensure it has Latitude and Longitude columns
            lat_col = None
            lon_col = None
            name_col = None
            for col in df_other.columns:
                if col.lower() in ["latitude", "lat"]:
                    lat_col = col
                if col.lower() in ["longitude", "lon", "long"]:
                    lon_col = col
                if col.lower() in ["point name", "pointname", "name", "label"]:
                    name_col = col
            
            if lat_col is None or lon_col is None:
                continue
                
            # Filter rows with valid coordinates
            df_other = df_other.dropna(subset=[lat_col, lon_col])
            
            # Find close points
            close_points = []
            for t_pt in t_pts:
                for idx, row in df_other.iterrows():
                    try:
                        other_lat = float(row[lat_col])
                        other_lon = float(row[lon_col])
                        other_name = row[name_col] if name_col else f"Row {idx}"
                        
                        dist = haversine_distance(t_pt["lat"], t_pt["lon"], other_lat, other_lon)
                        if dist <= 50.0:
                            close_points.append({
                                "target_point": t_pt["name"],
                                "other_point": other_name,
                                "distance_m": dist,
                                "lat": other_lat,
                                "lon": other_lon
                            })
                    except (ValueError, TypeError):
                        pass
            
            if close_points:
                matches_found = True
                print(f"\n📂 File: {f_name} (Date: {f_date})")
                print(f"   --> Found {len(close_points)} points within 50m:")
                # Group by target point to print neatly
                grouped = {}
                for cp in close_points:
                    grouped.setdefault(cp["target_point"], []).append(f"'{cp['other_point']}' ({cp['distance_m']:.2f}m)")
                
                for t_node, matches in list(grouped.items())[:3]:  # show first 3 target points
                    print(f"       * Target '{t_node}' matches: {', '.join(matches[:3])}" + (f" ... and {len(matches)-3} more" if len(matches) > 3 else ""))
                if len(grouped) > 3:
                    print(f"       * ... and matches for {len(grouped)-3} more target points.")
                    
        except Exception as e:
            print(f"Error reading {f_name}: {e}")
            
    if not matches_found:
        print("No matches within 50m found in any of the CSV files.")
