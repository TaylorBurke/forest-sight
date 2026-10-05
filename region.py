"""Shared region config. Select a region with the REGION env var (default: pnw); settings live in regions.json."""
import json, os

REGION = os.environ.get("REGION", "pnw")
CFG = json.load(open("regions.json"))[REGION]
DATA = f"data/{REGION}"
RAW = f"{DATA}/raw"
MIN_BAND_RECORDS = 60  # a distance band with fewer invasive-plant records than this is neither charted nor modelled


def usable_bands(decay, cfg=None):
    """How many leading distance bands to chart and model: those with enough records, and no more than a region's optional max_bands."""
    cfg = cfg or CFG
    n = next((i for i, c in enumerate(decay.n_inv) if c < MIN_BAND_RECORDS), len(decay))
    return min(n, cfg.get("max_bands", len(decay)))
