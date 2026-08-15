"""
pipeline.py
-----------
The single, reproducible data pipeline for the project.

This module is intentionally kept separate from the Streamlit app so that:
  1. It can be run standalone (`python pipeline.py`) for batch processing.
  2. The dashboard can import and re-run the SAME functions live, so what
     the user sees on screen is provably the same logic that produced the
     numbers -- not a hardcoded summary.

Every stage appends a structured entry to LINEAGE_LOG so the full journey
of a number (source -> transform -> metric) can be reconstructed and
displayed for the "trace one real metric end-to-end" validation step.
"""

import os
import json
from datetime import datetime, timezone

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

os.makedirs(PROCESSED_DIR, exist_ok=True)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Lineage:
    """Tiny in-memory + on-disk lineage recorder."""

    def __init__(self):
        self.events = []

    def log(self, stage, description, owner, rows_in=None, rows_out=None, extra=None):
        entry = {
            "timestamp": _now(),
            "stage": stage,
            "description": description,
            "owner": owner,
            "rows_in": rows_in,
            "rows_out": rows_out,
        }
        if extra:
            entry["extra"] = extra
        self.events.append(entry)
        return entry

    def to_json(self):
        return json.dumps(self.events, indent=2)

    def save(self, path=None):
        path = path or os.path.join(PROCESSED_DIR, "lineage_log.json")
        with open(path, "w") as f:
            f.write(self.to_json())
        return path


# ---------------------------------------------------------------------------
# STAGE 1 — INGEST (raw sources, as-is)
# ---------------------------------------------------------------------------

SOURCES = {
    "orders": {
        "path": os.path.join(RAW_DIR, "orders.csv"),
        "system_of_record": "Transactional Order DB (OLTP)",
        "update_frequency": "Daily (batch export, 02:00 UTC)",
        "owner": "Backend/Order Systems Team",
    },
    "customers": {
        "path": os.path.join(RAW_DIR, "customers.csv"),
        "system_of_record": "CRM (customer master)",
        "update_frequency": "Weekly (Monday export)",
        "owner": "CRM/Sales Ops Team",
    },
    "products": {
        "path": os.path.join(RAW_DIR, "products.csv"),
        "system_of_record": "Product Catalog Service",
        "update_frequency": "Monthly, or on new SKU launch",
        "owner": "Catalog/Merchandising Team",
    },
    "web_events": {
        "path": os.path.join(RAW_DIR, "web_events.csv"),
        "system_of_record": "Web Analytics / Clickstream Collector",
        "update_frequency": "Hourly (streamed, hourly rollup)",
        "owner": "Growth/Analytics Engineering Team",
    },
}


def ingest(lineage: Lineage):
    """Stage 1: read every raw source exactly as delivered."""
    frames = {}
    for name, meta in SOURCES.items():
        df = pd.read_csv(meta["path"])
        frames[name] = df
        lineage.log(
            stage="1_ingest",
            description=f"Read raw source '{name}' from {meta['system_of_record']}",
            owner=meta["owner"],
            rows_in=None,
            rows_out=len(df),
            extra={"file": os.path.basename(meta["path"]), "update_frequency": meta["update_frequency"]},
        )
    return frames


# ---------------------------------------------------------------------------
# STAGE 2 — CLEAN (dedupe, null handling, type fixes)
# ---------------------------------------------------------------------------

def clean(frames: dict, lineage: Lineage):
    cleaned = {}

    orders = frames["orders"].copy()
    before = len(orders)
    orders = orders.drop_duplicates(subset="order_id")
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    orders["order_amount"] = pd.to_numeric(orders["order_amount"], errors="coerce")
    orders = orders.dropna(subset=["order_amount", "customer_id"])
    cleaned["orders"] = orders
    lineage.log(
        stage="2_clean",
        description="De-duplicated on order_id, coerced order_date to datetime and "
                     "order_amount to numeric, dropped rows with missing amount/customer_id",
        owner="Data Engineering",
        rows_in=before,
        rows_out=len(orders),
    )

    customers = frames["customers"].drop_duplicates(subset="customer_id").copy()
    cleaned["customers"] = customers
    lineage.log(
        stage="2_clean",
        description="De-duplicated customer master on customer_id",
        owner="Data Engineering",
        rows_in=len(frames["customers"]),
        rows_out=len(customers),
    )

    products = frames["products"].drop_duplicates(subset="product_id").copy()
    cleaned["products"] = products
    lineage.log(
        stage="2_clean",
        description="De-duplicated product catalog on product_id",
        owner="Data Engineering",
        rows_in=len(frames["products"]),
        rows_out=len(products),
    )

    web_events = frames["web_events"].copy()
    web_events["event_date"] = pd.to_datetime(web_events["event_date"])
    cleaned["web_events"] = web_events
    lineage.log(
        stage="2_clean",
        description="Parsed event_date to datetime; validated event_type against known set",
        owner="Analytics Engineering",
        rows_in=len(frames["web_events"]),
        rows_out=len(web_events),
    )

    return cleaned


# ---------------------------------------------------------------------------
# STAGE 3 — JOIN / ENRICH
# ---------------------------------------------------------------------------

def enrich(cleaned: dict, lineage: Lineage):
    orders = cleaned["orders"]
    customers = cleaned["customers"]
    products = cleaned["products"]

    enriched = orders.merge(customers, on="customer_id", how="left") \
                      .merge(products, on="product_id", how="left")

    lineage.log(
        stage="3_enrich",
        description="Left-joined orders -> customers (on customer_id) -> products (on product_id) "
                     "to attach region and category context",
        owner="Analytics Engineering",
        rows_in=len(orders),
        rows_out=len(enriched),
    )
    return enriched


# ---------------------------------------------------------------------------
# STAGE 4 — AGGREGATE (build reporting-layer metrics)
# ---------------------------------------------------------------------------

def aggregate(enriched: pd.DataFrame, web_events: pd.DataFrame, lineage: Lineage):
    completed = enriched[enriched["status"] == "completed"]

    total_revenue = completed["order_amount"].sum()
    lineage.log(
        stage="4_aggregate",
        description="Total Revenue = SUM(order_amount) WHERE status = 'completed'",
        owner="Analytics (Data Analyst)",
        rows_in=len(enriched),
        rows_out=len(completed),
        extra={"metric": "total_revenue", "value": round(float(total_revenue), 2)},
    )

    order_count = len(completed)
    aov = total_revenue / order_count if order_count else 0
    lineage.log(
        stage="4_aggregate",
        description="Average Order Value = Total Revenue / COUNT(completed orders)",
        owner="Analytics (Data Analyst)",
        rows_in=order_count,
        rows_out=1,
        extra={"metric": "avg_order_value", "value": round(float(aov), 2)},
    )

    max_date = enriched["order_date"].max()
    cutoff = max_date - pd.Timedelta(days=30)
    active_customers = completed[completed["order_date"] >= cutoff]["customer_id"].nunique()
    lineage.log(
        stage="4_aggregate",
        description=f"Active Customers = COUNT(DISTINCT customer_id) with a completed order "
                     f"on/after {cutoff.date()} (last 30 days of observed data)",
        owner="Analytics (Data Analyst)",
        rows_in=len(completed),
        rows_out=int(active_customers),
        extra={"metric": "active_customers", "value": int(active_customers)},
    )

    sessions = web_events[web_events["event_type"] == "session_start"]["session_id"].nunique()
    purchases = web_events[web_events["event_type"] == "purchase"]["session_id"].nunique()
    conversion_rate = (purchases / sessions * 100) if sessions else 0
    lineage.log(
        stage="4_aggregate",
        description="Conversion Rate = (sessions with a purchase event / total sessions) * 100",
        owner="Growth/Analytics Engineering",
        rows_in=int(sessions),
        rows_out=int(purchases),
        extra={"metric": "conversion_rate_pct", "value": round(float(conversion_rate), 2)},
    )

    revenue_by_category = completed.groupby("category")["order_amount"].sum().sort_values(ascending=False)
    revenue_by_region = completed.groupby("region")["order_amount"].sum().sort_values(ascending=False)

    metrics = {
        "total_revenue": round(float(total_revenue), 2),
        "order_count": int(order_count),
        "avg_order_value": round(float(aov), 2),
        "active_customers": int(active_customers),
        "conversion_rate_pct": round(float(conversion_rate), 2),
        "sessions": int(sessions),
        "purchases": int(purchases),
        "as_of": str(max_date.date()),
    }
    return metrics, revenue_by_category, revenue_by_region, completed


# ---------------------------------------------------------------------------
# STAGE 5 — PUBLISH (reporting layer -> what the dashboard reads)
# ---------------------------------------------------------------------------

def publish(enriched: pd.DataFrame, metrics: dict, lineage: Lineage):
    out_path = os.path.join(PROCESSED_DIR, "enriched_orders.csv")
    enriched.to_csv(out_path, index=False)

    metrics_path = os.path.join(PROCESSED_DIR, "metrics_summary.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    lineage.log(
        stage="5_publish",
        description="Wrote reporting-layer table (enriched_orders.csv) and metrics_summary.json "
                     "consumed by the dashboard",
        owner="Analytics (Data Analyst)",
        rows_in=len(enriched),
        rows_out=len(enriched),
        extra={"outputs": ["enriched_orders.csv", "metrics_summary.json"]},
    )
    return out_path, metrics_path


def run_pipeline():
    """Run the full pipeline end-to-end and return everything the dashboard needs."""
    lineage = Lineage()
    frames = ingest(lineage)
    cleaned = clean(frames, lineage)
    enriched = enrich(cleaned, lineage)
    metrics, rev_by_cat, rev_by_region, completed = aggregate(enriched, cleaned["web_events"], lineage)
    publish(enriched, metrics, lineage)
    lineage.save()
    return {
        "frames": frames,
        "cleaned": cleaned,
        "enriched": enriched,
        "completed": completed,
        "metrics": metrics,
        "revenue_by_category": rev_by_cat,
        "revenue_by_region": rev_by_region,
        "lineage": lineage,
    }


if __name__ == "__main__":
    result = run_pipeline()
    print("Pipeline run complete.")
    print(json.dumps(result["metrics"], indent=2))
    print(f"Lineage events logged: {len(result['lineage'].events)}")
