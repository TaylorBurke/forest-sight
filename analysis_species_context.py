"""Context for the species chart: each species' TOTAL U.S. critical habitat, and what share of it
(a) lies inside OR/WA roadless areas and (b) would be opened under each scenario.

Scenario allocation logic mirrors analysis_scenarios.py; a consistency check against data/scenarios.csv guards drift.
"""
import json, requests, numpy as np, pandas as pd, geopandas as gpd

A, STEP = 5070, 250
CELL_ACRES = STEP * STEP / 4046.856
SPECIES = ["Northern spotted owl", "Marbled Murrelet", "Canada Lynx", "Pacific marten, Coastal DPS"]
URL = "https://services.arcgis.com/QVENGdaPbd4LUkLV/arcgis/rest/services/USFWS_Critical_Habitat/FeatureServer/0/query"
ELIGIBLE = 4.8 / 44.7
ACTIVATION = {"Low": {5: 0.05, 10: 0.15}, "Mid": {5: 0.10, 10: 0.30}, "High": {5: 0.20, 10: 0.60}}


def fetch_species(name):
    frames, offset = [], 0
    while True:
        r = requests.get(URL, params=dict(where=f"comname='{name}'", outFields="comname,unitname", outSR=4326,
                                          f="geojson", resultOffset=offset, resultRecordCount=5), timeout=300)
        r.raise_for_status()
        feats = r.json()["features"]
        if not feats:
            break
        frames.append(gpd.GeoDataFrame.from_features(feats, crs=4326))
        offset += len(feats)
    return pd.concat(frames, ignore_index=True)


pts = gpd.read_parquet("data/ira_points.parquet")
sc = pd.read_csv("data/scenarios.csv")

# full-U.S. totals + per-point species flags
out = {}
for name in SPECIES:
    g = fetch_species(name).to_crs(A)
    geom = g.union_all()
    total = geom.area / 4046.856
    pts[name] = pts.within(geom).values
    out[name] = {"name": name, "total_acres": round(total), "features": len(g),
                 "roadless_acres": round(int(pts[name].sum()) * CELL_ACRES)}
    out[name]["roadless_share"] = round(out[name]["roadless_acres"] / total, 4)
    print(name, out[name], flush=True)

# scenarios, replicating analysis_scenarios.py
p = pts.drop(columns="geometry").sort_values("road_dist_m").reset_index(drop=True)
n_elig = int(len(p) * ELIGIBLE)
elig = {"near_roads": p.iloc[:n_elig], "spread": p.sample(n_elig, random_state=42).sort_index()}
for name in SPECIES:
    out[name]["scenarios"] = []
for alloc, e in elig.items():
    for scen, hz in ACTIVATION.items():
        for yr, share in hz.items():
            act = e.iloc[: int(len(e) * share)]
            ref = sc[(sc.allocation == alloc) & (sc.scenario == scen) & (sc.horizon_yr == yr)].iloc[0]
            assert abs(len(act) * CELL_ACRES - ref.activated_acres) < 1, "scenario drift: activated acres"
            assert abs(act.in_crit_hab.sum() * CELL_ACRES - ref.crit_hab_acres) < 1, "scenario drift: habitat acres"
            for name in SPECIES:
                a = int(act[name].sum()) * CELL_ACRES
                out[name]["scenarios"].append({"allocation": alloc, "scenario": scen, "horizon_yr": yr,
                                               "acres": round(a), "share": round(a / out[name]["total_acres"], 5)})
json.dump(list(out.values()), open("data/species_context.json", "w"), indent=1)
mid = [(n, [s["share"] for s in v["scenarios"] if s["scenario"] == "Mid" and s["horizon_yr"] == 10]) for n, v in out.items()]
print("Mid/10yr share of total habitat (near_roads, spread):", mid)
