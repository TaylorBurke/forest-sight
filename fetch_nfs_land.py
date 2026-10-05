"""Download Forest Service-OWNED land (Basic Ownership, class 'USDA FOREST SERVICE') for the region's bounding box.

Administrative forest boundaries include private land, towns and highways, so invasive-plant records inside them are
measured against a roads layer that does not describe those places. Counting only records on Forest Service-owned
parcels keeps the distance-to-road comparison apples to apples.
"""
from region import REGION, CFG, DATA, RAW
import requests, geopandas as gpd, pandas as pd

URL = "https://apps.fs.usda.gov/ArcX/rest/services/EDW/EDW_BasicOwnership_02/MapServer/0/query"
minx, miny, maxx, maxy = gpd.read_file(f"{RAW}/ira.gpkg").total_bounds
frames, offset = [], 0
while True:
    r = requests.get(URL, params=dict(
        where="ownerclassification='USDA FOREST SERVICE'", geometry=f"{minx},{miny},{maxx},{maxy}",
        geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects",
        outFields="ownerclassification,forestname,region", outSR=4326, f="geojson",
        maxAllowableOffset=0.0003,  # ~30 m generalization: far finer than the 100 m GBIF coordinate cut-off
        resultOffset=offset, resultRecordCount=5), timeout=600)
    r.raise_for_status()
    feats = r.json()["features"]
    if not feats:
        break
    frames.append(gpd.GeoDataFrame.from_features(feats, crs=4326))
    offset += len(feats)
    print("nfs parcels", offset, flush=True)
nfs = pd.concat(frames, ignore_index=True)
nfs.to_file(f"{RAW}/nfs_land.gpkg", driver="GPKG")
print(len(nfs), "Forest Service-owned parcels;", sorted(nfs.forestname.dropna().unique())[:8], "...")
