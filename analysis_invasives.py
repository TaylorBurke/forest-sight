"""Invasive-plant intensity vs. distance from nearest National Forest road, corrected for observer bias.

relative intensity(band) = share of invasive records in band / share of ALL-plant records in band.
1.0 = invasives occur there as often as plant observers generally record anything; >1 = over-represented.
"""
from region import REGION, CFG, DATA, RAW
import numpy as np, geopandas as gpd, pandas as pd
from shapely import STRtree

A = 5070
BANDS = [0, 100, 250, 500, 1000, 2000, 5000, np.inf]
LABELS = ["0-100 m", "100-250 m", "250-500 m", "0.5-1 km", "1-2 km", "2-5 km", ">5 km"]
rng = np.random.default_rng(42)

roads = gpd.read_file(f"{RAW}/roads_nfs.gpkg").to_crs(A)
forests = gpd.read_file(f"{RAW}/forest_boundaries.gpkg").to_crs(A)
# Region 6 national forests only: the NFS road layer omits highways/county roads that dominate the Columbia
# River Gorge NSA's mixed ownership, and neighbouring regions' forests are only partly covered by our road pull.
forests = forests[(forests.region == CFG["forest_region"]) & ~forests.forestname.str.contains("|".join(CFG["exclude_forests"]))]
tree = STRtree(roads.geometry.values)


def prep(path):
    df = pd.read_parquet(path).dropna(subset=["decimalLatitude", "decimalLongitude"])
    g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.decimalLongitude, df.decimalLatitude), crs=4326).to_crs(A)
    g = gpd.sjoin(g, forests[["forestname", "geometry"]], predicate="within").drop(columns="index_right")
    g = g[~g.index.duplicated()].copy()
    _, d = tree.query_nearest(g.geometry.values, return_distance=True, all_matches=False)
    g["road_dist_m"] = d
    g["band"] = pd.cut(g.road_dist_m, BANDS, labels=LABELS, right=False)
    return g


inv, ctrl = prep(f"{RAW}/gbif_invasives.parquet"), prep(f"{RAW}/gbif_control.parquet")
print(f"records on national forest land: invasive={len(inv)}, control={len(ctrl)}")


def shares(g):
    return g.band.value_counts(normalize=True).reindex(LABELS).fillna(0).values


point = shares(inv) / shares(ctrl)
boot = np.array([
    shares(inv.sample(len(inv), replace=True, random_state=int(s))) /
    shares(ctrl.sample(len(ctrl), replace=True, random_state=int(s)))
    for s in rng.integers(0, 1e9, 500)])
out = pd.DataFrame({
    "band": LABELS, "rel_intensity": point,
    "ci_lo": np.nanpercentile(boot, 2.5, axis=0), "ci_hi": np.nanpercentile(boot, 97.5, axis=0),
    "n_inv": inv.band.value_counts().reindex(LABELS).values, "n_ctrl": ctrl.band.value_counts().reindex(LABELS).values,
})
out.to_csv(f"{DATA}/invasive_decay.csv", index=False)
print(out.round(2).to_string(index=False))

print("\nPer-species relative intensity, near (<500 m) vs far (>=2 km):")
rows = []
c_near, c_far = (ctrl.road_dist_m < 500).mean(), (ctrl.road_dist_m >= 2000).mean()
for sp, g in inv.groupby("species"):
    if len(g) >= 100:
        rows.append((sp, len(g), (g.road_dist_m < 500).mean() / c_near, (g.road_dist_m >= 2000).mean() / c_far))
print(pd.DataFrame(rows, columns=["species", "n", "near<500m", "far>=2km"]).round(2).to_string(index=False))
