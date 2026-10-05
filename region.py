"""Shared region config. Select a region with the REGION env var (default: pnw); settings live in regions.json."""
import json, os

REGION = os.environ.get("REGION", "pnw")
CFG = json.load(open("regions.json"))[REGION]
DATA = f"data/{REGION}"
RAW = f"{DATA}/raw"
MIN_BAND_RECORDS = 60  # a distance band with fewer invasive-plant records than this is neither charted nor modelled
