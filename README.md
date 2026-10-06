# Forest Sight

Open-data analysis of forests and land use. Two projects live here:

1. **Roadless Rule analysis** (active): what the proposed rescission of the 2001 Roadless Rule could mean for habitat and invasive plants, region by region. Published as a static site from `docs/`.
2. **Global deforestation analysis** (planned): see the research plan below.

---

## Roadless Rule analysis

The Forest Service proposed rescinding the 2001 Roadless Area Conservation Rule in August 2026. This project measures what is at stake in each region and models 5- and 10-year "what if" scenarios. Colorado and Idaho are excluded because their own state rules replace the national one.

**Site layout** (built into `docs/`, served by GitHub Pages)

| Page | What it shows |
|---|---|
| `docs/index.html` | Hub with a card for the U.S. totals and one for each region |
| `docs/us/` | Totals summed across every analyzed region |
| `docs/<region>/` | The full study for one region (currently `pnw`: Oregon and Washington) |

**Pipeline** (run per region with `REGION=<slug>`, default `pnw`; settings live in `regions.json`)

```
fetch_ira.py             roadless area boundaries (USFS)
fetch_roads_habitat.py   Forest Service roads + USFWS critical habitat
fetch_invasives.py       GBIF invasive-plant records + all-plant control, forest boundaries
fetch_nfs_land.py        Forest Service-owned land (invasive records are counted only on it)
analysis_exposure.py     distance to nearest road + habitat overlap (250 m grid)
analysis_invasives.py    invasive-plant intensity vs distance from a road (observer-bias corrected)
analysis_scenarios.py    low / mid / high scenarios at 5 and 10 years
analysis_species_context.py   each species' habitat in the study area, and the roadless share
build_site.py            builds docs/ (hub, U.S. totals, region pages, share image)
```

Raw downloads go to `data/<region>/raw/` (git-ignored); small analysis outputs in `data/<region>/` are committed.

**Alaska is built differently.** Its roadless land is far from roads, no critical habitat overlaps it, and it has a long logging record, so it does not use the Lower 48 template. It is flagged `"custom": true` in `regions.json` and has its own scripts and page (`site/alaska.html`):

```
ak_fetch_extra.py        Forest Service harvest history, ADF&G Anadromous Waters Catalog (salmon streams, lakes, species)
ak_fetch_forestplan.py   Tongass timber suitability and productive old growth (forest plan layers)
ak_analysis.py           remoteness, salmon, old growth, logging history by decade, pace-based scenarios, map layers
```

Run order for Alaska (`REGION=ak`): `fetch_ira.py`, `fetch_roads_habitat.py`, `fetch_nfs_land.py`, `analysis_exposure.py` (it uses Alaska Albers, EPSG:3338, from `regions.json`), then the three `ak_*` scripts. Download the statewide catalog (`2026GDB_statewide.zip` from the [ADF&G Anadromous Waters Catalog data files](https://www.adfg.alaska.gov/sf/SARR/AWC/index.cfm?ADFG=maps.dataFiles)) into `data/ak/raw/awc_statewide.zip` first. The hub's national map shows the western states with Alaska set in at the same scale.

**Add a region**

1. Add an entry to `regions.json`: states, Forest Service region code, forests to exclude (mixed-ownership units with many non-Forest-Service roads, like the Columbia River Gorge or Lake Tahoe Basin), the invasive plants to track (GBIF taxon keys), and a short note for each region-specific caveat.
2. Run `fetch_ira.py`, `fetch_roads_habitat.py` and `analysis_exposure.py` with `REGION=<slug>`. The exposure output lists species by roadless overlap; put the top four in `species`.
3. Run the remaining scripts (`fetch_invasives.py`, `analysis_invasives.py`, `analysis_scenarios.py`, `analysis_species_context.py`).
4. Run `python build_site.py`. The region gets its own page and a card on the hub, and the U.S. totals include it automatically. The build stops if any roadless area would be counted in two regions.

Each page's headings and conclusions are computed from that region's own numbers, so a region where roads and invasive plants are only weakly linked (California) says so instead of repeating another region's finding. A distance band with fewer than `MIN_BAND_RECORDS` invasive-plant records (see `region.py`) is neither charted nor used in the scenario model.

Setup: `python -m venv .venv && .venv/bin/pip install pandas geopandas matplotlib pyogrio shapely requests pyarrow`.

Key assumptions are stated on each page: the eligible share of roadless land (10.7%) comes from the Forest Service's own national figure, and the activation pace in each scenario is an assumption, not a forecast.

---

## Global deforestation analysis (planned)

A data analytics project exploring global deforestation patterns, drivers, and their relationship to economic and policy factors. Built following the Google Data Analytics framework: **Ask, Prepare, Process, Analyze, Share, Act**.

### Research Questions

- What are the trends over the last three decades regarding reforestation vs deforestation?
- What economic factors are driving deforestation in the last 10 years?

---

## Data Sources

| Source | What You Get | Format |
|--------|-------------|--------|
| [Global Forest Watch](https://data.globalforestwatch.org/) | Tree cover loss by country/year, primary forest loss, drivers of loss | CSV |
| [FAO FAOSTAT](https://www.fao.org/faostat/en/#data/RL) | Land use data — agricultural land, forest area by country over time | CSV |
| [World Bank Open Data](https://data.worldbank.org/) | GDP, population, agricultural % of GDP, CO2 emissions by country | CSV / API |
| [Our World in Data](https://ourworldindata.org/forests-and-deforestation) | Curated, clean datasets with great context | CSV / GitHub |
| [Hansen Global Forest Change](https://earthenginepartners.appspot.com/science-2013-global-forest) | Satellite-derived forest loss data (advanced, raster data) | GeoTIFF |

**Starting point:** Global Forest Watch + World Bank — clean CSVs, well-documented, easy to join on country/year.

---

## Tools & Skills

| Tool | Purpose |
|------|---------|
| Spreadsheets | Initial data exploration, pivot tables |
| SQL (BigQuery) | Query and aggregate data at scale |
| R or Python | Cleaning, merging datasets, statistical analysis |
| Tableau / Looker Studio | Visualization and dashboarding |

---

## Project Structure (Google Data Analytics Framework)

```
1. Ask       → Define 2–3 specific research questions
2. Prepare   → Download datasets, document sources
3. Process   → Clean data, handle missing values, join datasets
4. Analyze   → Statistical analysis, correlations, trends over time
5. Share     → Visualizations, dashboard, or written report
6. Act       → Recommendations based on findings
```

---

## Visualization Ideas

- **Choropleth map** — Forest loss by country (color intensity = severity)
- **Line chart** — Top 10 countries' forest loss trends over 20 years
- **Stacked bar** — Drivers of deforestation by region
- **Scatter plot** — GDP growth vs. forest loss (is there a trade-off?)
- **Small multiples** — Compare continents side by side

---

## Getting Started

1. Go to [Global Forest Watch Open Data](https://data.globalforestwatch.org/) and download the tree cover loss dataset
2. Open it in a spreadsheet — examine columns, time range, and structure
3. Pick 2 research questions that excite you
4. Start exploring

---

## Repository Structure

```
forest-sight/
├── README.md
├── data/              # Raw and processed datasets
│   ├── raw/
│   └── processed/
├── notebooks/         # Jupyter / R notebooks for analysis
├── sql/               # SQL queries
├── visualizations/    # Charts, dashboards, exports
└── docs/              # Documentation and findings
```

---

## License

This project uses publicly available datasets. See individual data source pages for their respective licenses and terms of use.
