"""Alaska (Tongass + Chugach) analysis, built around the data that actually describes Alaska.

Unlike the Lower-48 regions, Alaska has no designated critical habitat in these forests and almost no roads, so the story
is told with: remoteness, salmon streams, productive old-growth forest, and the Forest Service's own logging history.

Outputs: data/ak/summary.json (all page statistics) and data/ak/map.json (simplified SVG layers for two map panels).
Run with REGION=ak after fetch_ira, fetch_roads_habitat, fetch_nfs_land, analysis_exposure and ak_fetch_extra.
"""
from region import REGION, CFG, DATA, RAW
import json, re
import numpy as np, pandas as pd, geopandas as gpd

A = 3338  # Alaska Albers, equal-area
ACRE = 4046.856
CELL = 250 * 250 / ACRE
FORESTS = {"Tongass": "Tongass National Forest", "Chugach": "Chugach National Forest"}

ira = gpd.read_file(f"{RAW}/ira.gpkg").to_crs(A)
nfs = gpd.read_file(f"{RAW}/nfs_land.gpkg").to_crs(A)
roads = gpd.read_file(f"{RAW}/roads_nfs.gpkg").to_crs(A)
pts = gpd.read_parquet(f"{DATA}/ira_points.parquet")
streams = gpd.read_file(f"{RAW}/awc_streams.gpkg").to_crs(A)
lakes = gpd.read_file(f"{RAW}/awc_lakes.gpkg").to_crs(A)
apoints = gpd.read_file(f"{RAW}/awc_points.gpkg").to_crs(A)
harvest = gpd.read_file(f"{RAW}/harvest.gpkg").to_crs(A)
ts = gpd.read_file(f"{RAW}/timber_suitable.gpkg").to_crs(A)  # Tongass forest plan: Suitable OG / Suitable YG

for g in (ira, nfs, lakes, harvest, ts):  # generalized downloads can contain self-intersecting rings; repair before any union
    g["geometry"] = g.geometry.make_valid()
from shapely.geometry import MultiPolygon

def polys_only(g):
    """A union of repaired layers can come back as a GeometryCollection (stray lines/points); keep just the polygons."""
    if g.geom_type in ("Polygon", "MultiPolygon"):
        return g
    ps = [p for part in getattr(g, "geoms", []) for p in ([part] if part.geom_type == "Polygon" else list(part.geoms) if part.geom_type == "MultiPolygon" else [])]
    return MultiPolygon(ps)

own = {f: polys_only(nfs[nfs.forestname == full].union_all()) for f, full in FORESTS.items()}  # Forest Service-owned land
iraU = {f: polys_only(ira[ira.forest == f].union_all()) for f in FORESTS}
S = {"total_acres": round(len(pts) * CELL), "forests": {}}

# ---------- 1. size and remoteness ----------
for f in FORESTS:
    p = pts[pts.forest == f]
    d = p.road_dist_m
    S["forests"][f] = {
        "roadless_acres": round(len(p) * CELL), "fs_owned_acres": round(own[f].area / ACRE),
        "median_road_km": round(float(d.median()) / 1000, 1),
        "within_km": {k: round(float((d <= k * 1000).mean()), 4) for k in (1, 5, 10, 25)},
    }
    S["forests"][f]["share_of_forest"] = round(S["forests"][f]["roadless_acres"] / S["forests"][f]["fs_owned_acres"], 3)
d = pts.road_dist_m
S["median_road_km"] = round(float(d.median()) / 1000, 1)
S["within_km"] = {k: round(float((d <= k * 1000).mean()), 4) for k in (1, 5, 10, 25)}
S["near1km_acres"] = round(float((d <= 1000).sum()) * CELL)
S["hab_acres"] = 0  # no critical habitat polygons intersect these forests
S["road_km_in_data"] = round(float(roads.length.sum()) / 1000)
print("remoteness:", S["median_road_km"], "km median;", S["within_km"], flush=True)

# ---------- 2. salmon: streams, lakes, species ----------
def tokens(s):
    return set(re.findall(r"([A-Z]{1,2})[a-z]*", str(s)))
# ADF&G AWC codes: CO coho, P pink, CH chum, S sockeye, K chinook (king); lower-case suffix = use (p present, s spawning, r rearing)
SPECIES = {"CO": "Coho", "P": "Pink", "CH": "Chum", "S": "Sockeye", "K": "Chinook"}
by_code = apoints.assign(t=apoints.SPECIES.map(tokens)).groupby("AWC_CODE").t.agg(lambda x: set().union(*x))
S["salmon"] = {}
for f in FORESTS:
    s_own = gpd.clip(streams, own[f])
    s_ira = gpd.clip(streams, iraU[f])
    codes_own = set(s_own[s_own.length > 50].AWC_CODE)
    codes_ira = set(s_ira[s_ira.length > 50].AWC_CODE)
    lk = lakes[lakes.intersects(iraU[f])]
    lk_all = lakes[lakes.intersects(own[f])]
    sp = {}
    for code, name in SPECIES.items():
        n_ira = sum(1 for c in codes_ira if code in by_code.get(c, set()))
        n_all = sum(1 for c in codes_own if code in by_code.get(c, set()))
        sp[name] = {"in_roadless": n_ira, "all": n_all}
    S["salmon"][f] = {
        "stream_km_all": round(float(s_own.length.sum()) / 1000), "stream_km_roadless": round(float(s_ira.length.sum()) / 1000),
        "streams_all": len(codes_own), "streams_roadless": len(codes_ira),
        "lakes_all": len(lk_all), "lakes_roadless": len(lk), "species": sp,
    }
    S["salmon"][f]["share_km"] = round(S["salmon"][f]["stream_km_roadless"] / max(S["salmon"][f]["stream_km_all"], 1), 3)
    print("salmon", f, S["salmon"][f]["stream_km_roadless"], "of", S["salmon"][f]["stream_km_all"], "km", flush=True)

# ---------- 3. productive old growth + timber suitability (Tongass forest plan layers) ----------
OGS = json.load(open(f"{RAW}/old_growth_stats.json"))
tot, ins = sum(OGS["all_tongass"].values()), sum(OGS["intersects"].values())
S["old_growth"] = {
    "pog_acres_tongass": round(tot), "pog_acres_roadless_upper": round(ins),
    "share_in_roadless_upper": round(ins / tot, 3),
    "high_volume_acres": round(OGS["all_tongass"]["H"]), "high_volume_in_roadless_upper": round(OGS["intersects"]["H"]),
}
print("old growth:", S["old_growth"], flush=True)

ts_in = ts.copy()
ts_in["total"] = ts_in.geometry.area / ACRE
ts_cand = ts_in.geometry.intersects(iraU["Tongass"])
ts_in["in_roadless"] = 0.0
ts_in.loc[ts_cand, "in_roadless"] = ts_in[ts_cand].geometry.intersection(iraU["Tongass"]).area / ACRE
g = ts_in.groupby("SUITABILITY")[["total", "in_roadless"]].sum().round().astype(int)
S["suitable"] = {"by_class": {k: {"total": int(r.total), "in_roadless": int(r.in_roadless)} for k, r in g.iterrows()},
                 "total": int(g.total.sum()), "in_roadless": int(g.in_roadless.sum())}
S["suitable"]["share_of_forest"] = round(S["suitable"]["total"] / S["forests"]["Tongass"]["fs_owned_acres"], 3)
S["suitable"]["share_in_roadless"] = round(S["suitable"]["in_roadless"] / S["suitable"]["total"], 3)
print("timber-suitable:", S["suitable"], flush=True)

# ---------- 4. logging history (Forest Service harvest records, Tongass, Forest Service land) ----------
h = harvest[(harvest.ownership_desc == "USDA FOREST SERVICE") & harvest.admin_forest_name.str.contains("Tongass")].copy()
h["yr"] = pd.to_numeric(h.fy_completed, errors="coerce")
h = h[h.yr.between(1900, 2025)].copy()
h["acres"] = h.geometry.area / ACRE
cand = h.geometry.intersects(iraU["Tongass"])
h["in_roadless"] = 0.0
h.loc[cand, "in_roadless"] = h[cand].geometry.intersection(iraU["Tongass"]).area / ACRE
h["decade"] = np.where(h.yr < 1950, 1940, (h.yr // 10 * 10).astype(int))
dec = h.groupby("decade").agg(total=("acres", "sum"), roadless=("in_roadless", "sum")).round(0).astype(int)
S["logging"] = {"by_decade": [{"decade": int(i), "label": ("Before 1950" if i == 1940 else f"{int(i)}s"), "acres": int(r.total), "in_roadless": int(r.roadless)}
                              for i, r in dec.iterrows()]}
byyr = h.groupby(h.yr.astype(int)).acres.sum()
def pace(a, b):
    return float(byyr.reindex(range(a, b + 1)).fillna(0).mean())
S["logging"]["pace_per_year"] = {"recent": round(pace(2011, 2020)), "2000s": round(pace(2001, 2010)), "1990s": round(pace(1991, 2000)), "1970s": round(pace(1971, 1980))}
S["logging"]["total_acres_ever"] = int(h.acres.sum())
S["logging"]["roadless_acres_ever"] = int(h.in_roadless.sum())
S["logging"]["clearcut_share"] = round(float(h[h.activity_name.str.contains("Clearcut", na=False)].acres.sum() / h.acres.sum()), 3)
print("logging pace:", S["logging"]["pace_per_year"], "| ever in roadless:", S["logging"]["roadless_acres_ever"], flush=True)

# ---------- 5. scenarios ----------
# (a) history-based, for the Alaska page: what logging at past rates would cover
P = S["logging"]["pace_per_year"]
S["pace_scenarios"] = [{"scenario": n, "label": l, "per_year": P[k], **{f"acres_{y}": P[k] * y for y in (5, 10)}}
                       for n, l, k in (("Low", "Recent pace (2011-2020)", "recent"), ("Mid", "2000s pace", "2000s"), ("High", "1990s pace", "1990s"))]
# (b) for the national page: the same low/mid/high labels, with acres from Alaska's own logging pace (the forest plan's
#     "suitable" land contains almost no roadless acres, so it cannot say how much could be opened).
S["scenarios"] = [{"scenario": p["scenario"], "horizon_yr": y, "activated_acres": round(p[f"acres_{y}"]), "crit_hab_acres": 0}
                  for p in S["pace_scenarios"] for y in (5, 10)]

json.dump(S, open(f"{DATA}/summary.json", "w"), indent=1)

# ---------- 6. map panels ----------
def path(geom, tx, ty):
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms) if geom.geom_type == "MultiPolygon" else []
    out = []
    for p in polys:
        c = [(round(tx(x), 1), round(ty(y), 1)) for x, y in p.exterior.coords]
        out.append("M" + "L".join(f"{x:g} {y:g}" for x, y in c) + "Z")
    return "".join(out)

def lines(geom, tx, ty):
    parts = [geom] if geom.geom_type == "LineString" else list(geom.geoms) if geom.geom_type == "MultiLineString" else []
    return "".join("M" + "L".join(f"{round(tx(x), 1):g} {round(ty(y), 1):g}" for x, y in l.coords) for l in parts)

W = 760
MAP = {}
for f in FORESTS:
    minx, miny, maxx, maxy = iraU[f].union(own[f]).bounds
    pad = 15000
    minx, miny, maxx, maxy = minx - pad, miny - pad, maxx + pad, maxy + pad
    sc = W / (maxx - minx)
    tx, ty = (lambda x: (x - minx) * sc), (lambda y: (maxy - y) * sc)
    H = round((maxy - miny) * sc)
    box = iraU[f].union(own[f]).envelope.buffer(pad)
    layer = {"w": W, "h": H}
    big = [p for p in (own[f].geoms if own[f].geom_type == "MultiPolygon" else [own[f]]) if p.area > 2e7]  # drop islands < ~5,000 acres
    layer["forest"] = path(MultiPolygon(big).simplify(2500), tx, ty)
    layer["roadless"] = "".join(path(g.simplify(400), tx, ty) for g in ira[ira.forest == f].geometry if not g.is_empty)
    sl = streams[streams.intersects(own[f])]
    layer["salmon"] = "".join(lines(g.simplify(250), tx, ty) for g in sl.geometry if not g.is_empty)
    layer["roads"] = "".join(lines(g.simplify(150), tx, ty) for g in roads[roads.intersects(box)].geometry if not g.is_empty)
    if f == "Tongass":
        c = h[h.geometry.intersects(box)].geometry.centroid
        layer["cuts"] = "".join(f"M{round(tx(p.x), 1):g} {round(ty(p.y), 1):g}h2v2h-2z" for p in c)
    MAP[f] = layer
    print("map", f, {k: len(v) for k, v in layer.items() if isinstance(v, str)}, flush=True)
json.dump(MAP, open(f"{DATA}/map.json", "w"))
print("done")
