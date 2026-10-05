"""Download Inventoried Roadless Areas (2001 Roadless Rule) for OR/WA from the USFS EDW service."""
import json, requests, geopandas as gpd

URL = "https://apps.fs.usda.gov/ArcX/rest/services/EDW/EDW_InventoriedRoadlessAreas2001_01/MapServer/0/query"
frames = []
offset = 0
while True:
    r = requests.get(URL, params={
        "where": "state IN ('OR','WA') OR state LIKE '%OR%' OR state LIKE '%WA%'",
        "outFields": "*", "f": "geojson", "outSR": 4326,
        "resultOffset": offset, "resultRecordCount": 1000,
    }, timeout=120)
    r.raise_for_status()
    gdf = gpd.GeoDataFrame.from_features(r.json()["features"], crs=4326)
    if gdf.empty:
        break
    frames.append(gdf)
    offset += len(gdf)
    if len(gdf) < 1000:
        break
out = gpd.pd.concat(frames, ignore_index=True)
out.to_file("data/raw/ira_pnw.gpkg", driver="GPKG")
print(len(out), "polygons;", round(out.acres.sum()/1e6, 2), "M acres")
print(out.groupby("state").acres.sum().round(0))
print(out.groupby("forest").acres.sum().sort_values(ascending=False).head(15).round(0))
