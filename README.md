# Task 3 — The Data Lifecycle
**PlaceMux · Altrodav Technologies Pvt. Ltd. · Phase 1 Industry Immersion · Data Analyst**

A small but complete, demoable project mapping the end-to-end data lifecycle
for a mini e-commerce analytics use case: 4 raw data sources → clean →
enrich → aggregate → publish → retire, with a live Streamlit dashboard on top.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL Streamlit prints (usually http://localhost:8501).

You can also run just the pipeline (no UI) to see the raw metrics + lineage log:

```bash
python pipeline.py
```

## Project structure

```
placemux_task3/
├── app.py                     # Streamlit dashboard (8 tabs, see below)
├── pipeline.py                # The one, reusable, reproducible ETL pipeline
├── requirements.txt
├── docs/
│   └── source_of_truth.md     # Required deliverable: source of truth per metric
└── data/
    ├── raw/                   # 4 independent raw sources (simulated exports)
    │   ├── orders.csv         # Transactional Order DB — daily
    │   ├── customers.csv      # CRM export — weekly
    │   ├── products.csv       # Product catalog — monthly
    │   └── web_events.csv     # Clickstream/web analytics — hourly
    └── processed/             # Generated fresh every run (git-ignore-able)
        ├── enriched_orders.csv
        ├── metrics_summary.json
        └── lineage_log.json
```

## How this maps to the task brief / marking scheme

| Brief requirement | Where it's satisfied |
|---|---|
| List every data source + update frequency | `app.py` → **Data Sources** tab, driven by `SOURCES` dict in `pipeline.py` |
| Draw the flow from source to final report | `app.py` → **Lineage Diagram** tab (live Graphviz DOT diagram) |
| Identify source of truth for each key metric | `docs/source_of_truth.md`, rendered in **Source of Truth** tab |
| Mark transformations + owner per stage | `app.py` → **Transformations & Owners** tab |
| Note retention rules and privacy constraints | `app.py` → **Retention & Privacy** tab, with a live PII check |
| Validate by tracing one real metric end-to-end | `app.py` → **Live Validation** tab, replays the real `lineage_log.json` |
| Deliverable: lineage diagram | Lineage Diagram tab + exportable DOT source |
| Deliverable: source-of-truth doc | `docs/source_of_truth.md` (downloadable from the app) |
| Definition of Done: demoable on real data, not just described | Every number on every tab is computed live by `pipeline.py` on each run — nothing is hardcoded |
| Pitfall: assuming one tidy source | 4 distinct sources modeled, each with its own owner/cadence |
| Pitfall: no clear owner per stage | Every pipeline stage has a named owner (see Transformations & Owners tab) |
| Pitfall: ignoring retention until compliance problem | Retention & Privacy tab defines rules per table up front |

## Notes for the demo / viva

- The dashboard **re-runs the real pipeline** (`pipeline.py`) every time it loads
  (`st.cache_data` just avoids recomputation within a session) — so if you edit
  a CSV in `data/raw/` and rerun, every KPI, chart, and lineage entry updates.
- The **Live Validation** tab is the strongest piece to demo: pick a metric,
  and it shows the exact stage-by-stage trace (ingest → clean → enrich →
  aggregate → publish) that produced that number, pulled from the real
  `lineage_log.json` generated moments earlier.
- The Lineage Diagram is generated from a portable DOT graph (shown in an
  expander) so it can also be pasted into any Graphviz-compatible tool,
  or redrawn in draw.io/Excalidraw if a hand-drawn version is required.
"# task3" 
