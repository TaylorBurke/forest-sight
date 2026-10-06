"""Tongass forest-plan layers from the Forest Service (Alaska Region): timber suitability and productive old growth.

* Timber suitability (2016 forest plan): download the polygons classed 'Suitable OG' / 'Suitable YG' (~27k) so they can
  be intersected exactly with the roadless areas.
* Productive old growth (size/density): ~590k polygons, too many to download, so ask the service for acreage totals
  (by volume class) inside the roadless areas, chunk by chunk. 'within' (polygon fully inside) is a conservative lower
  bound; 'intersects' counts edge-straddling polygons too and is an upper bound. Both are saved.

Run with REGION=ak after fetch_ira.py.
"""
from region import REGION, CFG, DATA, RAW
import json, requests, geopandas as gpd, pandas as pd
from shapely.geometry import MultiPolygon
from shapely.geometry.polygon import orient

SVC = "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services"
TS = f"{SVC}/Tongass_National_Forest_Timber_Suitability/FeatureServer/0/query"
OG = f"{SVC}/TNF_Size_Density_sync_enabled_2_view/FeatureServer/0/query"

# --- timber-suitable land ---------------------------------------------------------------------------------------
frames, offset = [], 0
while True:
    r = requests.get(TS, params=dict(where="SUITABILITY LIKE 'Suitable%'", outFields="SUITABILITY,GISACRES", outSR=4326,
                                     f="geojson", maxAllowableOffset=0.0003, resultOffset=offset, resultRecordCount=1000), timeout=600)
    r.raise_for_status()
    feats = r.json()["features"]
    if not feats:
        break
    frames.append(gpd.GeoDataFrame.from_features(feats, crs=4326))
    offset += len(feats)
    print("suitable polygons", offset, flush=True)
ts = pd.concat(frames, ignore_index=True)
ts.to_file(f"{RAW}/timber_suitable.gpkg", driver="GPKG")
print("timber-suitable polygons:", len(ts), "| acres by class:", ts.groupby("SUITABILITY").GISACRES.sum().round().to_dict())

# --- productive old growth totals ------------------------------------------------------------------------------
STAT = json.dumps([{"statisticType": "sum", "onStatisticField": "GISACRES", "outStatisticFieldName": "ac"}])


def totals(geom=None, rel=None):
    data = dict(where="1=1", groupByFieldsForStatistics="VOLSTRATA", outStatistics=STAT, f="json")
    if geom is not None:
        rings = []
        for p in ([geom] if geom.geom_type == "Polygon" else geom.geoms):
            p = orient(p, sign=-1.0)
            rings.append(list(p.exterior.coords))
            rings += [list(i.coords) for i in p.interiors]
        data.update(geometry=json.dumps({"rings": rings, "spatialReference": {"wkid": 4326}}),
                    geometryType="esriGeometryPolygon", inSR=4326, spatialRel=rel)
    r = requests.post(OG, data=data, timeout=600).json()
    if "error" in r:
        raise RuntimeError(r["error"])
    return {f["attributes"]["VOLSTRATA"]: f["attributes"]["ac"] or 0 for f in r.get("features", [])}


ira = gpd.read_file(f"{RAW}/ira.gpkg")
tong = ira[ira.forest == "Tongass"].geometry.make_valid().union_all().simplify(0.002)
parts = [p for g in ([tong] if tong.geom_type == "Polygon" else tong.geoms) for p in ([g] if g.geom_type == "Polygon" else g.geoms)]
print("roadless polygons to query:", len(parts), flush=True)
out = {"all_tongass": totals(), "within": {}, "intersects": {}}
for rel, key in (("esriSpatialRelWithin", "within"), ("esriSpatialRelIntersects", "intersects")):
    agg = {}
    for i in range(0, len(parts), 15):
        chunk = parts[i:i + 15]
        for k, v in totals(MultiPolygon(chunk), rel).items():
            agg[k] = agg.get(k, 0) + v
        print(key, i + len(chunk), "/", len(parts), flush=True)
    out[key] = agg
json.dump(out, open(f"{RAW}/old_growth_stats.json", "w"), indent=1)
print("old growth acres, all Tongass:", {k: round(v) for k, v in out["all_tongass"].items()})
print("inside roadless (within / intersects):", {k: (round(out['within'].get(k, 0)), round(out['intersects'].get(k, 0))) for k in out["all_tongass"]})
