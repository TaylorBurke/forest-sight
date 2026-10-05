"""Build the GitHub Pages site into docs/:  hub (docs/index.html), U.S. totals (docs/us/), one page per region.

A region appears automatically once data/<slug>/scenarios.csv exists (see regions.json). The U.S. page sums every
analyzed region, so adding a region updates the totals and adds a card on the hub with no template edits.
"""
import hashlib, json, os, shutil
from region import usable_bands, MIN_BAND_RECORDS
MIN_RECORDS_TXT = MIN_BAND_RECORDS
import numpy as np, pandas as pd, geopandas as gpd

# Version tag for the stylesheet link: browsers cache Pages assets for ~10 min, so a changed stylesheet must change its URL.
ASSET_V = hashlib.md5(open("site/assets/style.css", "rb").read()).hexdigest()[:8]

SITE_URL = "https://taylorburke.github.io/forest-sight"
GITHUB = "https://github.com/TaylorBurke/forest-sight"
COMMENT_URL = "https://www.regulations.gov/document/FS-2025-0001-223869"
NATIONAL_ACRES = 44_700_000  # Forest Service: acres where the national rule applies (CO and ID have their own rules)
A, STEP = 5070, 250
CELL_ACRES = STEP * STEP / 4046.856
MAP_W = 760
OUT = "docs"
ELIGIBLE = 4.8 / 44.7


def page(title, desc, path, depth, body):
    assets = "../" * depth + "assets/"
    url = f"{SITE_URL}/{path}"
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:type" content="website"><meta property="og:title" content="{title}"><meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}"><meta property="og:image" content="{SITE_URL}/assets/share.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="{assets}style.css?v={ASSET_V}">
</head><body>
{body}
</body></html>
"""


def n_bands(decay, cfg):
    """How many leading distance bands to chart (enough records, and within the region's max_bands)."""
    return usable_bands(decay, cfg)


def load_region(slug, cfg):
    d, raw = f"data/{slug}", f"data/{slug}/raw"
    pts = gpd.read_parquet(f"{d}/ira_points.parquet")
    ira = gpd.read_file(f"{raw}/ira.gpkg").to_crs(A)
    forests = gpd.read_file(f"{raw}/forest_boundaries.gpkg").to_crs(A)
    codes = [cfg["forest_region"]] if isinstance(cfg["forest_region"], str) else cfg["forest_region"]
    excl = "|".join(cfg["exclude_forests"])
    forests = forests[forests.region.isin(codes) & (~forests.forestname.str.contains(excl) if excl else True)]
    # map outlines: keep forests inside this region's own states (a Forest Service region spans other states too)
    study = lower48_outline().query("STUSPS in @cfg['states']").union_all().buffer(3000)
    forests = forests.assign(geometry=forests.geometry.intersection(study))
    forests = forests[~forests.geometry.is_empty]
    total = len(pts) * CELL_ACRES
    scen = pd.read_csv(f"{d}/scenarios.csv")
    by_forest = pts.groupby("forest").agg(
        acres=("road_dist_m", lambda s: len(s) * CELL_ACRES),
        near1km=("road_dist_m", lambda s: float((s <= 1000).mean())),
        hab=("in_crit_hab", "mean")).reset_index()
    by_forest = by_forest[by_forest.acres >= 100_000].sort_values("acres", ascending=False)
    data = {
        "region": {"name": cfg["name"], "places": cfg["places"]},
        "total_acres": round(total), "polygons": int(len(ira)),
        "median_road_m": round(float(pts.road_dist_m.median())), "hab_share": round(float(pts.in_crit_hab.mean()), 3),
        "proximity": {f"{km}": round(float((pts.road_dist_m <= km * 1000).mean()), 3) for km in (0.5, 1, 2, 5)},
        "forests": [{"forest": r.forest, "acres": round(r.acres), "near1km": round(r.near1km, 3), "hab": round(r.hab, 3)}
                    for r in by_forest.itertuples()],
        "decay": pd.read_csv(f"{d}/invasive_decay.csv").round(3).head(n_bands(pd.read_csv(f"{d}/invasive_decay.csv"), cfg)).to_dict("records"),
        "scenarios": scen.to_dict("records"),
        "species_context": json.load(open(f"{d}/species_context.json")),
    }
    decay_all = pd.read_csv(f"{d}/invasive_decay.csv")  # all bands; the chart shows the first five
    data["invasive_meta"] = {"n_records": int(decay_all.n_inv.sum()), "n_dropped": int(decay_all.n_inv.iloc[n_bands(decay_all, cfg):].sum()),
                             "reason": "there are too few records to read a trend" if (decay_all.n_inv.iloc[n_bands(decay_all, cfg):] < MIN_RECORDS_TXT).any() else "the estimate there is too uncertain to read a trend",
                             "species_text": cfg["invasives_text"]}
    summary = {
        "slug": slug, "name": cfg["name"], "places": cfg["places"], "total_acres": data["total_acres"],
        "hab_acres": round(float(pts.in_crit_hab.sum()) * CELL_ACRES), "hab_share": data["hab_share"],
        "near1km_acres": round(float((pts.road_dist_m <= 1000).sum()) * CELL_ACRES),
        "scenarios": scen[scen.allocation == "near_roads"][["scenario", "horizon_yr", "activated_acres", "crit_hab_acres"]].to_dict("records"),
    }
    return data, summary, ira, forests


def map_paths(ira, forests):
    minx, miny, maxx, maxy = ira.total_bounds
    pad = 20_000
    minx, miny, maxx, maxy = minx - pad, miny - pad, maxx + pad, maxy + pad
    S = MAP_W / (maxx - minx)
    H = round((maxy - miny) * S)

    def path(geom):
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        out = []
        for p in polys:
            c = [(round((x - minx) * S, 1), round((maxy - y) * S, 1)) for x, y in p.exterior.coords]
            out.append("M" + "L".join(f"{x:g} {y:g}" for x, y in c) + "Z")
        return "".join(out)

    i = ira[ira.acres >= 400].copy(); i["geometry"] = i.geometry.simplify(600)
    f = forests.copy(); f["geometry"] = f.geometry.simplify(1500)
    return H, "".join(path(g) for g in i.geometry if not g.is_empty), "".join(path(g) for g in f.geometry if not g.is_empty)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)


def fmt(n):
    return f"{round(n):,}"


def lower48_outline():
    """Lower-48 state outlines from the Census cartographic boundary file (20m, clipped to the shoreline so the
    Great Lakes are water, not state area), cached so builds don't need the network."""
    cache = "site/us_states_20m.geojson"
    if not os.path.exists(cache):
        import io, tempfile, requests, zipfile
        r = requests.get("https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_state_20m.zip", timeout=300)
        r.raise_for_status()
        with tempfile.TemporaryDirectory() as tmp:
            zipfile.ZipFile(io.BytesIO(r.content)).extractall(tmp)
            g = gpd.read_file(f"{tmp}/cb_2022_us_state_20m.shp")
        g = g[~g.STUSPS.isin(["AK", "HI", "PR", "GU", "VI", "AS", "MP"])][["STUSPS", "geometry"]]
        g.to_file(cache, driver="GeoJSON")
    return gpd.read_file(cache).to_crs(A)


def thumb(layers, bounds, w=400, h=240, pad=0.07, svg_class="thumb"):
    """Small inline SVG map. layers = [(GeoDataFrame, css_class, simplify_m, min_acres_or_None)]; outer rings only."""
    minx, miny, maxx, maxy = bounds
    s = min(w * (1 - 2 * pad) / (maxx - minx), h * (1 - 2 * pad) / (maxy - miny))
    ox, oy = (w - (maxx - minx) * s) / 2, (h - (maxy - miny) * s) / 2

    def ring(geom):
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        out = []
        for p in polys:
            c = [(round((x - minx) * s + ox, 1), round((maxy - y) * s + oy, 1)) for x, y in p.exterior.coords]
            out.append("M" + "L".join(f"{x:g} {y:g}" for x, y in c) + "Z")
        return "".join(out)

    parts = []
    for gdf, cls, tol, min_acres in layers:
        g = gdf if min_acres is None else gdf[gdf.acres >= min_acres]
        geoms = g.geometry.simplify(tol)
        parts.append(f'<path class="{cls}" d="{"".join(ring(x) for x in geoms if not x.is_empty)}"/>')
    return f'<svg class="{svg_class}" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">{"".join(parts)}</svg>'


# ---------- build ----------
shutil.rmtree(OUT, ignore_errors=True)
shutil.copytree("site/assets", f"{OUT}/assets")
open(f"{OUT}/.nojekyll", "w").close()

regions = json.load(open("regions.json"))
summaries, iras, forest_sets = [], [], []
seen_ids = set()
region_tpl = open("site/region.html").read()
for slug, cfg in regions.items():
    if not os.path.exists(f"data/{slug}/scenarios.csv"):
        print("skip (not analyzed yet):", slug)
        continue
    data, summary, ira, forests = load_region(slug, cfg)
    # the U.S. totals add regions together, so no roadless area may be counted in two of them
    dup = set(ira.objectid) & seen_ids
    assert not dup, f"{slug}: {len(dup)} roadless areas are already counted in another region (e.g. state-line polygons)"
    seen_ids |= set(ira.objectid)
    H, ira_path, for_path = map_paths(ira, forests)
    body = (region_tpl.replace("/*__DATA__*/null", json.dumps(data))
            .replace("__MAP_W__", str(MAP_W)).replace("__MAP_H__", str(H))
            .replace("__IRA_PATH__", ira_path).replace("__FOREST_PATH__", for_path)
            .replace("__NAME__", cfg["name"]).replace("__PLACES_AND__", cfg["places"].replace(" & ", " and "))
            .replace("__PLACES__", cfg["places"].replace("&", "&amp;"))
            .replace("__ROADS_NOTE__", cfg["roads_note"])
            .replace("__ELIGIBLE__", fmt(round(data["total_acres"] * ELIGIBLE, -3))))
    title = f"{cfg['name']} Roadless Report"
    desc = (f"What the proposed end of the Roadless Rule could mean for habitat and invasive plants in "
            f"{cfg['places']} national forests, with 5- and 10-year scenarios.")
    write(f"{OUT}/{slug}/index.html", page(title, desc, f"{slug}/", 1, body))
    summaries.append(summary)
    iras.append(ira)
    forest_sets.append(forests)
    print("built region:", slug, f"({len(body):,} bytes)")

# U.S. aggregate: sums and acre-weighted shares across every analyzed region
total = sum(s["total_acres"] for s in summaries)
us = {
    "national_acres": NATIONAL_ACRES, "total_acres": total,
    "hab_share": round(sum(s["hab_acres"] for s in summaries) / total, 3),
    "near1km_share": round(sum(s["near1km_acres"] for s in summaries) / total, 3),
    "regions": [{k: s[k] for k in ("slug", "name", "places", "total_acres", "hab_share")} for s in summaries],
}
agg = {}
for s in summaries:
    for r in s["scenarios"]:
        a = agg.setdefault((r["scenario"], r["horizon_yr"]), {"scenario": r["scenario"], "horizon_yr": r["horizon_yr"],
                                                             "activated_acres": 0, "crit_hab_acres": 0})
        a["activated_acres"] += r["activated_acres"]; a["crit_hab_acres"] += r["crit_hab_acres"]
for a in agg.values():
    a["share_of_all_roadless"] = round(a["activated_acres"] / total, 4)
us["scenarios"] = list(agg.values())
n_reg = len(summaries)
us_body = (open("site/us.html").read().replace("/*__DATA__*/null", json.dumps(us)))
write(f"{OUT}/us/index.html", page(
    "United States Roadless Totals",
    f"Combined results for every region analyzed so far ({n_reg}): roadless acres, critical habitat overlap and 5- and 10-year scenarios.",
    "us/", 1, us_body))

# hub
states = lower48_outline()
# each region is its own path (class region-<slug>) so hovering that region's card can light it up on the U.S. map
us_map = thumb([(states, "map-state", 4000, None)] + [(i, f"map-ira region-{s['slug']}", 4000, 3000) for s, i in zip(summaries, iras)],
               states.total_bounds, svg_class="thumb us-map")
cards = [f"""<a class="card card-us" href="us/index.html"><div class="card-img">{us_map}</div><div class="card-body"><span class="kicker">All regions combined</span><h3>United States totals</h3>
<p>Combined results for every region analyzed so far: {n_reg} region{'s' if n_reg != 1 else ''}, {total / 1e6:.2f} million roadless acres, {total / NATIONAL_ACRES:.0%} of the ~44.7 million acres where the national rule applies.</p><span class="go">Open the totals →</span></div></a>"""]
for s, ira, forests in zip(summaries, iras, forest_sets):
    region_map = thumb([(forests, "map-forest", 3000, None), (ira, "map-ira", 2500, 1500)], ira.total_bounds)
    cards.append(f"""<a class="card" data-region="{s['slug']}" href="{s['slug']}/index.html"><div class="card-img">{region_map}</div><div class="card-body"><span class="kicker">{s['places'].replace('&', '&amp;')}</span><h3>{s['name']}</h3>
<p>{s['total_acres'] / 1e6:.2f} million roadless acres, {s['hab_acres'] / s['total_acres']:.0%} inside critical habitat. Habitat, invasive plants and 5- and 10-year scenarios.</p><span class="go">Open the study →</span></div></a>""")
hub_body = (open("site/hub.html").read().replace("__CARDS__", "\n".join(cards)).replace("__COMMENT_URL__", COMMENT_URL)
            .replace("__GITHUB__", GITHUB))
write(f"{OUT}/index.html", page(
    "Forest Sight Roadless Rule",
    "What could happen to America's roadless forests if the Roadless Rule ends? Open data, region by region.",
    "", 0, hub_body))

# social share image (1200x630): all analyzed roadless areas on the site's paper background
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig = plt.figure(figsize=(12, 6.3), dpi=100, facecolor="#f3f5f1")
ax = fig.add_axes([0.52, 0.04, 0.46, 0.92]); ax.set_axis_off()
for ira in iras:
    g = ira[ira.acres >= 400].copy(); g["geometry"] = g.geometry.simplify(800)
    g.plot(ax=ax, color="#2f6b4f", linewidth=0)
ax.set_aspect("equal")
fig.text(0.05, 0.82, "FOREST SIGHT", fontsize=15, color="#4f5d55", family="monospace", va="top")
fig.text(0.05, 0.74, "What the proposed end of\nthe Roadless Rule\ncould mean", fontsize=34, color="#14201a", weight="bold", linespacing=1.15, va="top")
fig.text(0.05, 0.22, f"{total / 1e6:.2f} million roadless acres analyzed so far", fontsize=16, color="#2f6b4f")
fig.text(0.05, 0.12, "Public comments due October 6, 2026", fontsize=14, color="#4f5d55")
fig.savefig(f"{OUT}/assets/share.png", facecolor=fig.get_facecolor())
print("built hub, us, share image;", n_reg, "region(s),", f"{total:,} acres")
