"""Grid-sample IRAs (250 m) -> distance to nearest NFS road + critical-habitat overlap."""
import numpy as np, geopandas as gpd, pandas as pd
from shapely import STRtree, points

A, STEP = 5070, 250
CELL_ACRES = STEP * STEP / 4046.856

ira = gpd.read_file("data/raw/ira_pnw.gpkg").to_crs(A)
roads = gpd.read_file("data/raw/roads_nfs.gpkg").to_crs(A)
hab = gpd.read_file("data/raw/critical_habitat.gpkg").to_crs(A)
print("roads km:", round(roads.length.sum() / 1000), flush=True)

# grid points inside IRAs; first match wins so overlapping polygons aren't double counted
minx, miny, maxx, maxy = ira.total_bounds
xs, ys = np.meshgrid(np.arange(minx, maxx, STEP), np.arange(miny, maxy, STEP))
pts = gpd.GeoDataFrame(geometry=points(xs.ravel(), ys.ravel()), crs=A)
pts = gpd.sjoin(pts, ira[["forest", "state", "name", "geometry"]], predicate="within")
pts = pts[~pts.index.duplicated()].drop(columns="index_right").copy()
print("sample points:", len(pts), "=> acres", round(len(pts) * CELL_ACRES), flush=True)

# distance to nearest road
tree = STRtree(roads.geometry.values)
_, d = tree.query_nearest(pts.geometry.values, return_distance=True, all_matches=False)
pts["road_dist_m"] = d

# critical habitat overlap per species
pts["in_crit_hab"] = False
hab_hits = {}
for name, g in hab.dissolve("comname").geometry.items():
    m = pts.within(g)
    if m.any():
        hab_hits[name] = int(m.sum())
        pts.loc[m, "in_crit_hab"] = True
pts.to_parquet("data/ira_points.parquet")

print("\nShare of roadless area by distance to nearest existing NFS road:")
for km in (0.5, 1, 2, 5):
    print(f"  within {km:>3} km: {(pts.road_dist_m <= km*1000).mean():.1%}")
print("  median distance:", round(pts.road_dist_m.median()), "m")
print("\nCritical habitat overlap:", f"{pts.in_crit_hab.mean():.1%}", "of roadless area")
print(pd.Series(hab_hits).mul(CELL_ACRES).round().sort_values(ascending=False).to_string())
print("\nBy forest (acres | share within 1 km of road | share in crit hab):")
g = pts.groupby("forest").agg(acres=("road_dist_m", lambda s: len(s) * CELL_ACRES),
    near1km=("road_dist_m", lambda s: (s <= 1000).mean()), hab=("in_crit_hab", "mean"))
print(g.sort_values("acres", ascending=False).head(12).round(3).to_string())
