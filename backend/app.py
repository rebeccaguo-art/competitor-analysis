"""
app.py — FastAPI backend for the Competiscan Dashboard Databricks App.

In a Databricks App, DATABRICKS_HOST and DATABRICKS_TOKEN are set automatically.
You only need to set DATABRICKS_HTTP_PATH (your SQL warehouse endpoint) in the
App's environment variables settings.
"""
import os
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from databricks import sql

import queries

app = FastAPI(title="Competiscan Dashboard API")

# Allow local React dev server to call the API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# DB connection
# ─────────────────────────────────────────────

@contextmanager
def get_cursor():
    conn = sql.connect(
        server_hostname=os.environ["DATABRICKS_HOST"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    )
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()
        conn.close()


def parse_months(months_param: Optional[str]) -> Optional[list[str]]:
    """Comma-separated month string → list, or None for 'all'."""
    if not months_param or months_param == "all":
        return None
    return [m.strip() for m in months_param.split(",") if m.strip()]


# ─────────────────────────────────────────────
# Filter options
# ─────────────────────────────────────────────

@app.get("/api/filters/months")
def filter_months():
    with get_cursor() as cur:
        return queries.get_available_months(cur)


@app.get("/api/filters/competitors")
def filter_competitors():
    with get_cursor() as cur:
        return queries.get_available_competitors(cur)


# ─────────────────────────────────────────────
# Market Trends
# ─────────────────────────────────────────────

@app.get("/api/market/overall-share")
def market_overall_share(
    origination: Optional[str] = None,
    months: Optional[str] = None,
):
    with get_cursor() as cur:
        return queries.get_overall_market_share(cur, origination, parse_months(months))


@app.get("/api/market/preapproved-share")
def market_preapproved_share(
    origination: Optional[str] = None,
    months: Optional[str] = None,
):
    with get_cursor() as cur:
        return queries.get_preapproved_market_share(cur, origination, parse_months(months))


@app.get("/api/market/avg-rank")
def market_avg_rank(
    origination: Optional[str] = None,
    months: Optional[str] = None,
):
    with get_cursor() as cur:
        return queries.get_avg_rank(cur, origination, parse_months(months))


@app.get("/api/market/avg-shelf-space")
def market_avg_shelf_space(
    origination: Optional[str] = None,
    months: Optional[str] = None,
):
    with get_cursor() as cur:
        return queries.get_avg_shelf_space(cur, origination, parse_months(months))


@app.get("/api/market/card-portfolio")
def market_card_portfolio(
    origination: Optional[str] = None,
    months: Optional[str] = None,
):
    with get_cursor() as cur:
        return queries.get_card_portfolio(cur, origination, parse_months(months))


@app.get("/api/market/preapproved-offers-share")
def market_preapproved_offers_share(
    origination: Optional[str] = None,
    months: Optional[str] = None,
):
    with get_cursor() as cur:
        return queries.get_preapproved_share(cur, origination, parse_months(months))


# ─────────────────────────────────────────────
# Shelf Space
# ─────────────────────────────────────────────

@app.get("/api/shelf-space")
def shelf_space(
    origination: Optional[str] = None,
    months: Optional[str] = None,
    competitor: Optional[str] = None,
):
    with get_cursor() as cur:
        return queries.get_shelf_space(cur, origination, parse_months(months), competitor)


# ─────────────────────────────────────────────
# Co-occurrence
# ─────────────────────────────────────────────

@app.get("/api/cooccurrence")
def cooccurrence(
    origination: Optional[str] = None,
    months: Optional[str] = None,
):
    with get_cursor() as cur:
        return queries.get_cooccurrence_matrix(cur, origination, parse_months(months))


@app.get("/api/cooccurrence/detail")
def cooccurrence_detail(
    comp_a: str = Query(...),
    comp_b: str = Query(...),
    origination: Optional[str] = None,
    months: Optional[str] = None,
):
    with get_cursor() as cur:
        return queries.get_cooccurrence_detail(
            cur, comp_a, comp_b, origination, parse_months(months)
        )


# ─────────────────────────────────────────────
# Avant View
# ─────────────────────────────────────────────

@app.get("/api/avant-view")
def avant_view(
    origination: Optional[str] = None,
    months: Optional[str] = None,
    competitor: Optional[str] = None,
):
    with get_cursor() as cur:
        return queries.get_avant_view(cur, origination, parse_months(months), competitor)


# ─────────────────────────────────────────────
# Serve React frontend (production)
# Only active when frontend/dist exists (after npm run build)
# ─────────────────────────────────────────────

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="static")
