"""5- and 10-year what-if scenarios for PNW roadless areas (OR/WA), built from the exposure + invasive layers.

Anchors from the Forest Service's own proposal (not our estimates):
  * ~44.7M acres currently restricted; ~4.8M acres where current forest plans permit active management
    (=> ~10.7% of roadless acreage "eligible"). We assume PNW matches that national share (sensitivity-tested).
ASSUMPTIONS (illustrative, not forecasts -- no source gives an activation pace):
  * Eligible acres are the ones closest to existing roads (cheapest to reach).
  * Scenarios differ in what share of eligible acres see new road/harvest activity by each horizon.
Invasive pressure: curve from invasive_decay.csv. Activated land moves from its current road-distance band to the
near-road band (0-100 m). Lower bound assumes only 25% of an activated acre lies in a road's influence zone; upper 100%.
"""
from region import REGION, CFG, DATA, RAW
import numpy as np, pandas as pd

ELIGIBLE = 4.8 / 44.7
ACTIVATION = {  # share of eligible acres activated by horizon  (low / mid / high)
    "Low": {5: 0.05, 10: 0.15},
    "Mid": {5: 0.10, 10: 0.30},
    "High": {5: 0.20, 10: 0.60},
}
CORRIDOR_LO = 0.25
STEP = 250
CELL_ACRES = STEP * STEP / 4046.856

pts = pd.read_parquet(f"{DATA}/ira_points.parquet").drop(columns="geometry", errors="ignore")
curve = pd.read_csv(f"{DATA}/invasive_decay.csv")
edges = [0, 100, 250, 500, 1000, 2000, 5000, np.inf]
# Bands beyond 1.2 mi (2 km) have too few records to read a trend (and are not charted), so hold them at the
# last charted band (1-2 km) instead of using their noisy point estimates.
rel = curve.rel_intensity.values.copy()
rel[5:] = rel[4]
pts["pre"] = rel[np.digitize(pts.road_dist_m, edges[1:-1])]
NEAR = rel[0]

pts = pts.sort_values("road_dist_m").reset_index(drop=True)
n_elig = int(len(pts) * ELIGIBLE)
# Two ways eligible land could be chosen -- the gap between them is the key uncertainty for invasives:
#   "near_roads": cost-driven, nearest existing road first (optimistic for invasives)
#   "spread":     plan-driven, eligibility unrelated to road distance (random draw, fixed seed)
ELIG = {"near_roads": pts.iloc[:n_elig],
        "spread": pts.sample(n_elig, random_state=42)}  # keep the shuffled order: activation must be a random subset
print(f"Total roadless: {len(pts)*CELL_ACRES:,.0f} ac | eligible ({ELIGIBLE:.1%}): {n_elig*CELL_ACRES:,.0f} ac")
for k, e in ELIG.items():
    print(f"  {k}: median distance of eligible land to nearest road = {e.road_dist_m.median():.0f} m")

rows = []
for alloc, elig in ELIG.items():
    for sc, hz in ACTIVATION.items():
        for yr, share in hz.items():
            act = elig.iloc[: int(len(elig) * share)]
            pre = act.pre.mean()
            rows.append(dict(
                allocation=alloc, scenario=sc, horizon_yr=yr, activated_acres=round(len(act) * CELL_ACRES),
                crit_hab_acres=round(act.in_crit_hab.sum() * CELL_ACRES),
                crit_hab_share=round(act.in_crit_hab.mean(), 3),
                invasive_mult_lo=round((1 - CORRIDOR_LO) + CORRIDOR_LO * NEAR / pre, 2),
                invasive_mult_hi=round(NEAR / pre, 2),
                share_of_all_roadless=round(len(act) / len(pts), 4)))
out = pd.DataFrame(rows)
out.to_csv(f"{DATA}/scenarios.csv", index=False)
print(out.to_string(index=False))

print("\nSensitivity: eligible share (Mid scenario, 10 yr)")
for e in (0.05, ELIGIBLE, 0.20, 0.35):
    k = int(len(pts) * e)
    a = pts.iloc[: int(k * ACTIVATION["Mid"][10])]
    print(f"  eligible {e:.1%}: activated {len(a)*CELL_ACRES:>9,.0f} ac, in critical habitat {len(a[a.in_crit_hab])*CELL_ACRES:>9,.0f} ac")

