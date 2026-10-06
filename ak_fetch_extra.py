"""Alaska-specific layers: Forest Service timber-harvest history, Southeast Alaska productive old growth, and the
ADF&G Anadromous Waters Catalog (salmon streams, lakes, species points) trimmed to the roadless study area.

Run with REGION=ak after fetch_ira.py. The AWC statewide geodatabase zip must already be in data/ak/raw/ (see README).
"""
from region import REGION, CFG, DATA, RAW
import requests, geopandas as gpd, pandas as pd

minx, miny, maxx, maxy = gpd.read_file(f"{RAW}/ira.gpkg").total_bounds
pad = 0.5
BBOX = (minx - pad, miny - pad, maxx + pad, maxy + pad)

# --- Forest Service timber harvest, Alaska (Region 10), every decade -------------------------------------------
H = "https://apps.fs.usda.gov/ArcX/rest/services/EDW/EDW_TimberHarvest_01/MapServer/8/query"
fields = ("admin_forest_name,activity_name,treatment_type,fy_completed,fy_awarded,gis_acres,"
          "land_suitability_class_desc,ownership_desc,sale_name")
frames, offset = [], 0
while True:
    r = requests.get(H, params=dict(where="admin_region_code='10'", outFields=fields, outSR=4326, f="geojson",
                                    maxAllowableOffset=0.0003, resultOffset=offset, resultRecordCount=1000), timeout=600)
    r.raise_for_status()
    feats = r.json()["features"]
    if not feats:
        break
    frames.append(gpd.GeoDataFrame.from_features(feats, crs=4326))
    offset += len(feats)
    print("harvest polygons", offset, flush=True)
harvest = pd.concat(frames, ignore_index=True)
harvest.to_file(f"{RAW}/harvest.gpkg", driver="GPKG")
print("harvest:", len(harvest), "| forests:", harvest.admin_forest_name.value_counts().to_dict())

# --- Productive old-growth forest, Southeast Alaska (Audubon Alaska) -------------------------------------------
G = "https://gis.audubon.org/arcgisweb/rest/services/Hosted/SEALT_Input_Layers/FeatureServer/10/query"
r = requests.get(G, params=dict(where="1=1", outFields="type", outSR=4326, f="geojson", maxAllowableOffset=0.0005), timeout=900)
r.raise_for_status()
og = gpd.GeoDataFrame.from_features(r.json()["features"], crs=4326)
og.to_file(f"{RAW}/old_growth.gpkg", driver="GPKG")
print("old growth features:", len(og), "| types:", og["type"].tolist())

# --- ADF&G Anadromous Waters Catalog (2026 statewide geodatabase) ---------------------------------------------
GDB = f"/vsizip/{RAW}/awc_statewide.zip/AWC2026.gdb"
for layer, out in (("AWC_stream", "awc_streams"), ("AWC_lake", "awc_lakes"), ("AWC_Point", "awc_points")):
    g = gpd.read_file(GDB, layer=layer).to_crs(4326).cx[BBOX[0]:BBOX[2], BBOX[1]:BBOX[3]]
    g.to_file(f"{RAW}/{out}.gpkg", driver="GPKG")
    print(layer, "->", len(g), "features in study area")
