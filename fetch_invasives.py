"""Download GBIF occurrences for PNW invasive plants + an all-plants control, and national forest boundaries.

The control (all Plantae records) is how we correct for observer bias: people record plants near roads,
so we compare invasive records to *all* plant records at each distance from a road.
"""
from region import REGION, CFG, DATA, RAW
import requests, geopandas as gpd, pandas as pd

_minx, _miny, _maxx, _maxy = gpd.read_file(f"{RAW}/ira.gpkg").total_bounds  # study-area bounds from the roadless data
BBOX = dict(decimalLatitude=f"{_miny - 0.01:.2f},{_maxy + 0.01:.2f}", decimalLongitude=f"{_minx - 0.1:.2f},{_maxx + 0.03:.2f}")
BASE = {"hasCoordinate": "true", "hasGeospatialIssue": "false", "coordinateUncertaintyInMeters": "0,100",
        "year": "2005,2025", **BBOX}

INVASIVES = {
    "Bromus tectorum": 2703746, "Centaurea stoebe": 3127727, "Centaurea diffusa": 3128962,
    "Rubus armeniacus": 2996525, "Cirsium arvense": 3113414, "Cytisus scoparius": 5354656,
    "Taeniatherum caput-medusae": 2705666, "Linaria dalmatica": 5415011,
    "Hypericum perforatum": 3189486, "Hedera helix": 8351737, "Cirsium vulgare": 3112801,
}
PLANTAE = 6


def gbif(params, cap):
    rows, offset = [], 0
    while offset < min(cap, 100_000):
        r = requests.get("https://api.gbif.org/v1/occurrence/search",
                         params={**BASE, **params, "limit": 300, "offset": offset}, timeout=120)
        r.raise_for_status()
        j = r.json()
        rows += [{k: o.get(k) for k in ("species", "decimalLatitude", "decimalLongitude", "year", "basisOfRecord")}
                 for o in j["results"]]
        offset += 300
        if j["endOfRecords"]:
            break
    return rows


inv = []
for name, key in INVASIVES.items():
    rows = gbif({"taxonKey": key}, cap=6000)
    print(name, len(rows), flush=True)
    inv += rows
pd.DataFrame(inv).to_parquet(f"{RAW}/gbif_invasives.parquet")

# control: all plants, sampled evenly across years so one year/project doesn't dominate
ctrl = []
for y in range(2005, 2026):
    ctrl += gbif({"taxonKey": PLANTAE, "year": f"{y},{y}"}, cap=3000)
    print("control", y, len(ctrl), flush=True)
pd.DataFrame(ctrl).to_parquet(f"{RAW}/gbif_control.parquet")

# national forest administrative boundaries in the bbox
ira = gpd.read_file(f"{RAW}/ira.gpkg")
minx, miny, maxx, maxy = ira.total_bounds
r = requests.get("https://apps.fs.usda.gov/ArcX/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/0/query",
                 params=dict(where="1=1", geometry=f"{minx},{miny},{maxx},{maxy}", geometryType="esriGeometryEnvelope",
                             inSR=4326, spatialRel="esriSpatialRelIntersects", outFields="*", outSR=4326, f="geojson"),
                 timeout=180)
r.raise_for_status()
nf = gpd.GeoDataFrame.from_features(r.json()["features"], crs=4326)
nf.to_file(f"{RAW}/forest_boundaries.gpkg", driver="GPKG")
print(len(nf), "forests;", list(nf.columns))
