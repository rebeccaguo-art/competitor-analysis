"""
app.py — FastAPI backend for the Competiscan Dashboard Databricks App.
"""
import os
import traceback
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from databricks import sql

import queries

app = FastAPI(title="Competiscan Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

def _get_http_path() -> str:
    if os.environ.get("DATABRICKS_HTTP_PATH"):
        return os.environ["DATABRICKS_HTTP_PATH"]
    if os.environ.get("DATABRICKS_WAREHOUSE_ID"):
        return f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}"
    return "/sql/1.0/warehouses/ca4d400fc8ce3eea"

def _get_access_token() -> str:
    if os.environ.get("DATABRICKS_TOKEN"):
        return os.environ["DATABRICKS_TOKEN"]
    return "dapic0ecc77902eb2488d42bc5d99fcdb28a"

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
    if not months_param or months_param == "all":
        return None
    return [m.strip() for m in months_param.split(",") if m.strip()]

@app.get("/api/filters/months")
def filter_months():
    with get_cursor() as cur:
        return queries.get_available_months(cur)

@app.get("/api/filters/competitors")
def filter_competitors():
    with get_cursor() as cur:
        return queries.get_available_competitors(cur)

@app.get("/api/market/overall-share")
def market_overall_share(origination: Optional[str] = None, months: Optional[str] = None):
    with get_cursor() as cur:
        return queries.get_overall_market_share(cur, origination, parse_months(months))

@app.get("/api/market/preapproved-share")
def market_preapproved_share(origination: Optional[str] = None, months: Optional[str] = None):
    with get_cursor() as cur:
        return queries.get_preapproved_market_share(cur, origination, parse_months(months))

@app.get("/api/market/avg-rank")
def market_avg_rank(origination: Optional[str] = None, months: Optional[str] = None):
    with get_cursor() as cur:
        return queries.get_avg_rank(cur, origination, parse_months(months))

@app.get("/api/market/avg-shelf-space")
def market_avg_shelf_space(origination: Optional[str] = None, months: Optional[str] = None):
    with get_cursor() as cur:
        return queries.get_avg_shelf_space(cur, origination, parse_months(months))

@app.get("/api/market/card-portfolio")
def market_card_portfolio(origination: Optional[str] = None, months: Optional[str] = None):
    with get_cursor() as cur:
        return queries.get_card_portfolio(cur, origination, parse_months(months))

@app.get("/api/market/preapproved-offers-share")
def market_preapproved_offers_share(origination: Optional[str] = None, months: Optional[str] = None):
    with get_cursor() as cur:
        return queries.get_preapproved_share(cur, origination, parse_months(months))

@app.get("/api/shelf-space")
def shelf_space(origination: Optional[str] = None, months: Optional[str] = None, competitor: Optional[str] = None):
    with get_cursor() as cur:
        return queries.get_shelf_space(cur, origination, parse_months(months), competitor)

@app.get("/api/cooccurrence")
def cooccurrence(origination: Optional[str] = None, months: Optional[str] = None):
    with get_cursor() as cur:
        return queries.get_cooccurrence_matrix(cur, origination, parse_months(months))

@app.get("/api/cooccurrence/detail")
def cooccurrence_detail(comp_a: str = Query(...), comp_b: str = Query(...), origination: Optional[str] = None, months: Optional[str] = None):
    with get_cursor() as cur:
        return queries.get_cooccurrence_detail(cur, comp_a, comp_b, origination, parse_months(months))

@app.get("/api/avant-view")
def avant_view(origination: Optional[str] = None, months: Optional[str] = None, competitor: Optional[str] = None):
    with get_cursor() as cur:
        return queries.get_avant_view(cur, origination, parse_months(months), competitor)

@app.get("/api/competitor-view")
def competitor_view(
    origination: Optional[str] = None,
    months: Optional[str] = None,
    competitor: Optional[str] = None,
):
    with get_cursor() as cur:
        return queries.get_competitor_view(cur, origination, parse_months(months), competitor)

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="static")
