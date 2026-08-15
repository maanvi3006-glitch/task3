# Source of Truth — Key Metrics

Project: **E-commerce Analytics Mini-Project** (Task 3 — The Data Lifecycle)

This document names, for every key metric on the dashboard, the single
system of record it must be traced back to, the exact calculation, the
owner of that stage, and how often the underlying source refreshes.
If two people ever disagree on a number, this file is the tie-breaker.

---

## 1. Total Revenue
- **Source of truth:** `orders.csv` — Transactional Order DB (OLTP)
- **Definition:** `SUM(order_amount)` where `status = 'completed'`
- **Excludes:** cancelled and refunded orders
- **Owner:** Backend/Order Systems Team (source) → Data Analyst (metric)
- **Refresh cadence:** Daily, 02:00 UTC batch export

## 2. Average Order Value (AOV)
- **Source of truth:** derived from `orders.csv` (same completed-order set as Revenue)
- **Definition:** `Total Revenue / COUNT(completed orders)`
- **Owner:** Data Analyst
- **Refresh cadence:** Daily (depends on Orders refresh)

## 3. Active Customers
- **Source of truth:** `orders.csv` joined to `customers.csv` (CRM)
- **Definition:** `COUNT(DISTINCT customer_id)` with at least one completed
  order in the trailing 30 days of observed data
- **Owner:** Data Analyst (logic) / CRM-Sales Ops (customer master)
- **Refresh cadence:** Daily for orders; weekly for the customer master
  (Monday export) — active-customer count can lag CRM changes by up to 6 days

## 4. Conversion Rate
- **Source of truth:** `web_events.csv` — Web Analytics / Clickstream Collector
- **Definition:** `(sessions containing a 'purchase' event / total sessions) * 100`
- **Owner:** Growth/Analytics Engineering Team
- **Refresh cadence:** Hourly rollup (streamed)
- **Note:** This is an *engagement* metric, independent of the Orders DB —
  it is not reconciled 1:1 against Total Revenue because a session can
  convert without yet appearing as a `completed` order (e.g. pending payment).

## 5. Revenue by Category / Region
- **Source of truth:** `orders.csv` enriched with `products.csv` (category)
  and `customers.csv` (region)
- **Definition:** `SUM(order_amount)` grouped by `category` / `region`,
  same completed-order filter as Total Revenue
- **Owner:** Data Analyst
- **Refresh cadence:** Daily, following Orders

---

## Why this matters
Every number above can be traced backward to exactly one raw file and
forward through exactly one transformation path (see the lineage diagram
in the dashboard's "Lineage Diagram" tab, and the live trace in the
"Live Validation" tab). No metric is allowed to be "eyeballed" from more
than one candidate source — where two sources could plausibly answer the
same question (e.g. Revenue could theoretically be estimated from
`web_events.csv` purchase counts), the raw transactional source
(`orders.csv`) always wins.
