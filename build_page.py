"""Build the shareable page: derive chart data + a simplified SVG map, then fill site/template.html.

Reads the analysis outputs for one region (here: PNW = OR/WA). To add a region, point the inputs at that region's
files and change REGION; the template and charts are region-agnostic.
"""
import json, numpy as np, pandas as pd, geopandas as gpd

REGION = {"name": "Oregon & Washington", "short": "the Pacific Northwest"}
A, STEP = 5070, 250
CELL_ACRES = STEP * STEP / 4046.856
W = 760  # map viewBox width

pts = gpd.read_parquet("data/ira_points.parquet")
ira = gpd.read_file("data/raw/ira_pnw.gpkg").to_crs(A)
hab = gpd.read_file("data/raw/critical_habitat.gpkg").to_crs(A)
forests = gpd.read_file("data/raw/forest_boundaries.gpkg").to_crs(A)
forests = forests[(forests.region == "06") & ~forests.forestname.str.contains("Scenic Area")]

total_acres = len(pts) * CELL_ACRES
prox = {f"{km}": round(float((pts.road_dist_m <= km * 1000).mean()), 3) for km in (0.5, 1, 2, 5)}

# per-species acres of roadless land inside critical habitat
species = []
for name, g in hab.dissolve("comname").geometry.items():
    n = int(pts.within(g).sum())
    if n * CELL_ACRES >= 20000:
        species.append({"name": name, "acres": round(n * CELL_ACRES)})
species.sort(key=lambda s: -s["acres"])

by_forest = pts.groupby("forest").agg(
    acres=("road_dist_m", lambda s: len(s) * CELL_ACRES),
    near1km=("road_dist_m", lambda s: float((s <= 1000).mean())),
    hab=("in_crit_hab", "mean")).reset_index()
by_forest = by_forest[by_forest.acres >= 100_000].sort_values("acres", ascending=False)
forest_rows = [{"forest": r.forest, "acres": round(r.acres), "near1km": round(r.near1km, 3), "hab": round(r.hab, 3)}
               for r in by_forest.itertuples()]

data = {
    "region": REGION, "total_acres": round(total_acres), "polygons": int(len(ira)),
    "median_road_m": round(float(pts.road_dist_m.median())), "hab_share": round(float(pts.in_crit_hab.mean()), 3),
    "proximity": prox, "species": species, "forests": forest_rows,
    "decay": pd.read_csv("data/invasive_decay.csv").round(3).to_dict("records"),
    "scenarios": pd.read_csv("data/scenarios.csv").to_dict("records"),
    "species_context": json.load(open("data/species_context.json")),
}
json.dump(data, open("site/data.json", "w"), indent=1)

# --- simplified map ---
minx, miny, maxx, maxy = ira.total_bounds
pad = 20_000
minx, miny, maxx, maxy = minx - pad, miny - pad, maxx + pad, maxy + pad
S = W / (maxx - minx)
H = round((maxy - miny) * S)


def path(geom):
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    out = []
    for p in polys:
        for ring in [p.exterior, *p.interiors][:1]:  # outer rings only keeps the file small
            c = [(round((x - minx) * S, 1), round((maxy - y) * S, 1)) for x, y in ring.coords]
            out.append("M" + "L".join(f"{x:g} {y:g}" for x, y in c) + "Z")
    return "".join(out)


ira_s = ira[ira.acres >= 400].copy()
ira_s["geometry"] = ira_s.geometry.simplify(600)
f_s = forests.copy()
f_s["geometry"] = f_s.geometry.simplify(1500)
ira_path = "".join(path(g) for g in ira_s.geometry if not g.is_empty)
for_path = "".join(path(g) for g in f_s.geometry if not g.is_empty)
json.dump({"w": W, "h": H, "ira": ira_path, "forests": for_path}, open("site/map_paths.json", "w"))

# --- fill template ---
tpl = open("site/template.html").read()
tpl = tpl.replace("/*__DATA__*/null", json.dumps(data))
tpl = tpl.replace("__MAP_W__", str(W)).replace("__MAP_H__", str(H))
tpl = tpl.replace("__IRA_PATH__", ira_path).replace("__FOREST_PATH__", for_path)
open("site/index.html", "w").write(tpl)
print("page bytes:", len(tpl), "| map h:", H, "| species:", [s["name"] for s in species])
