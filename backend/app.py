"""
app.py — FastAPI backend for the Competiscan Dashboard Databricks App.

In a Databricks App, DATABRICKS_HOST and DATABRICKS_TOKEN are set automatically.
You only need to set DATABRICKS_HTTP_PATH (your SQL warehouse endpoint) in the
App's environment variables settings.
"""
import os
import json
import time
import traceback
import urllib.parse
import urllib.request
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
# Health check — visit /api/health to debug env vars
# ─────────────────────────────────────────────

@app.get("/api/health")
def health():
    host = os.environ.get("DATABRICKS_HOST", "NOT SET")
    token = "SET" if os.environ.get("DATABRICKS_TOKEN") else "NOT SET"
    http_path = os.environ.get("DATABRICKS_HTTP_PATH", "NOT SET")
    warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", "NOT SET")
    all_env = {k: v for k, v in os.environ.items() if "DATABRICKS" in k or "databricks" in k.lower()}
    return {
        "DATABRICKS_HOST": host,
        "DATABRICKS_TOKEN": token,
        "DATABRICKS_HTTP_PATH": http_path,
        "DATABRICKS_WAREHOUSE_ID": warehouse_id,
        "all_databricks_env": list(all_env.keys()),
    }


# ─────────────────────────────────────────────
# DB connection
# ─────────────────────────────────────────────

def _get_http_path() -> str:
    """Return HTTP path — from env var or derived from DATABRICKS_WAREHOUSE_ID."""
    if os.environ.get("DATABRICKS_HTTP_PATH"):
        return os.environ["DATABRICKS_HTTP_PATH"]
    if os.environ.get("DATABRICKS_WAREHOUSE_ID"):
        return f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}"
    # Hardcoded fallback (the Serverless-Small warehouse)
    return "/sql/1.0/warehouses/ca4d400fc8ce3eea"


# Token cache for OAuth M2M (avoid requesting a new token on every query)
_token_cache: dict = {"token": None, "expires_at": 0.0}


def _get_access_token() -> str:
    """Return access token — PAT if set, else OAuth M2M via client credentials."""
    if os.environ.get("DATABRICKS_TOKEN"):
        return os.environ["DATABRICKS_TOKEN"]

    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    host = os.environ["DATABRICKS_HOST"]
    client_id = os.environ["DATABRICKS_CLIENT_ID"]
    client_secret = os.environ["DATABRICKS_CLIENT_SECRET"]

    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "scope": "all-apis",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()

    req = urllib.request.Request(
        f"https://{host}/oidc/v1/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    _token_cache["token"] = result["access_token"]
    _token_cache["expires_at"] = now + result.get("expires_in", 3600)
    return _token_cache["token"]


@contextmanager
def get_cursor():
    conn = sql.connect(
        server_hostname=os.environ["DATABRICKS_HOST"],
        http_path=_get_http_path(),
        access_token=_get_access_token(),
    )
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()
        conn.close()


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "detail": traceback.format_exc()},
    )


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
