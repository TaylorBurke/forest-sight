"""Download existing NFS roads and USFWS critical habitat within the OR/WA roadless bbox."""
from region import REGION, CFG, DATA, RAW
import requests, geopandas as gpd, pandas as pd

ira = gpd.read_file(f"{RAW}/ira.gpkg")
minx, miny, maxx, maxy = ira.total_bounds
ENV = f"{minx},{miny},{maxx},{maxy}"

def pull(url, page):
    frames, offset = [], 0
    while True:
        r = requests.get(url, params=dict(
            where="1=1", geometry=ENV, geometryType="esriGeometryEnvelope", inSR=4326,
            spatialRel="esriSpatialRelIntersects", outFields="*", outSR=4326, f="geojson",
            resultOffset=offset, resultRecordCount=page), timeout=180)
        r.raise_for_status()
        feats = r.json()["features"]
        if not feats:
            break
        frames.append(gpd.GeoDataFrame.from_features(feats, crs=4326))
        offset += len(feats)
        print(url.split("/")[-4], offset, flush=True)
    return pd.concat(frames, ignore_index=True)

roads = pull("https://apps.fs.usda.gov/ArcX/rest/services/EDW/EDW_RoadBasic_01/MapServer/0/query", 1000)
roads.to_file(f"{RAW}/roads_nfs.gpkg", driver="GPKG")
hab = pull("https://services.arcgis.com/QVENGdaPbd4LUkLV/arcgis/rest/services/USFWS_Critical_Habitat/FeatureServer/0/query", 100)
hab.to_file(f"{RAW}/critical_habitat.gpkg", driver="GPKG")
print(len(roads), "roads;", len(hab), "habitat polygons")
print(hab.groupby(["comname","listing_status"]).size())
