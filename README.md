# Forest Sight — Global Deforestation & Land Use Analysis

A data analytics project exploring global deforestation patterns, drivers, and their relationship to economic and policy factors. Built following the Google Data Analytics framework: **Ask, Prepare, Process, Analyze, Share, Act**.

---

## Research Questions

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
