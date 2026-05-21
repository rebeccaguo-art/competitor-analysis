"""
queries.py — All SQL query functions for the Competiscan Dashboard.
Each function returns a list of dicts (JSON-serialisable).
"""
from typing import Optional
from config import TABLE_NAME, PRE_APPROVED_FILTER, AVANT_NAME
from config import TOP_COMPETITORS_OVERALL, TOP_COMPETITORS_PREAPPROVED
from config import TOP_COMPETITORS_RANK, TOP_COMPETITORS_SHELF


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _build_filters(
    origination: Optional[str],
    months: Optional[list[str]],
    competitor: Optional[str],
    preapproved: bool = False,
    table_alias: str = "",
) -> str:
    """Build a WHERE clause string from optional filter args."""
    alias = f"{table_alias}." if table_alias else ""
    clauses = ["1=1"]

    if preapproved:
        # Replace column refs with aliased version
        pa = PRE_APPROVED_FILTER.replace("origination", f"{alias}origination").replace("approval_odds", f"{alias}approval_odds")
        clauses.append(f"({pa})")

    if origination and origination != "All origination":
        clauses.append(f"{alias}origination = '{origination}'")

    if months:
        month_list = ", ".join(f"'{m}'" for m in months)
        clauses.append(f"{alias}month IN ({month_list})")

    if competitor and competitor not in ("All competitors", ""):
        if competitor == "Concora — all brands":
            clauses.append(
                f"({alias}competitor IN ('Indigo', 'Destiny', 'Milestone') "
                f"OR LOWER({alias}card_name) LIKE '%indigo%' "
                f"OR LOWER({alias}card_name) LIKE '%destiny%' "
                f"OR LOWER({alias}card_name) LIKE '%milestone%')"
            )
        else:
            clauses.append(f"{alias}competitor = '{competitor}'")

    return " AND ".join(clauses)


def run_query(cursor, sql: str) -> list[dict]:
    cursor.execute(sql)
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ─────────────────────────────────────────────
# Filter options
# ─────────────────────────────────────────────

def get_available_months(cursor) -> list[str]:
    sql = f"""
        SELECT DISTINCT month
        FROM {TABLE_NAME}
        WHERE month IS NOT NULL
        ORDER BY month
    """
    rows = run_query(cursor, sql)
    return [r["month"] for r in rows]


def get_available_competitors(cursor) -> list[str]:
    sql = f"""
        SELECT DISTINCT competitor
        FROM {TABLE_NAME}
        WHERE competitor IS NOT NULL
        ORDER BY competitor
    """
    rows = run_query(cursor, sql)
    names = [r["competitor"] for r in rows]
    # Inject Concora bundle option if individual brands present
    concora_brands = {"Indigo", "Destiny", "Milestone"}
    if concora_brands & set(names):
        # Insert after individual brands
        result = ["All competitors", "Concora — all brands"]
        result += sorted(names)
        return result
    return ["All competitors"] + sorted(names)


# ─────────────────────────────────────────────
# Market Trends — Chart 1: Overall market share
# ─────────────────────────────────────────────

def get_overall_market_share(cursor, origination=None, months=None) -> list[dict]:
    where = _build_filters(origination, months, None)
    sql = f"""
        WITH counts AS (
            SELECT month, competitor, COUNT(*) AS cnt
            FROM {TABLE_NAME}
            WHERE {where} AND podium_rank <= 5
            GROUP BY month, competitor
        ),
        totals AS (
            SELECT month, SUM(cnt) AS total FROM counts GROUP BY month
        ),
        ranked AS (
            SELECT c.month, c.competitor, c.cnt,
                   ROUND(c.cnt * 100.0 / t.total, 2) AS share_pct,
                   ROW_NUMBER() OVER (PARTITION BY c.month ORDER BY c.cnt DESC) AS rn
            FROM counts c JOIN totals t ON c.month = t.month
        )
        SELECT month, competitor, share_pct
        FROM ranked
        WHERE rn <= {TOP_COMPETITORS_OVERALL}
        ORDER BY month, share_pct DESC
    """
    return run_query(cursor, sql)


# Chart 2: Pre-approved market share
def get_preapproved_market_share(cursor, origination=None, months=None) -> list[dict]:
    where = _build_filters(origination, months, None, preapproved=True)
    sql = f"""
        WITH counts AS (
            SELECT month, competitor, COUNT(*) AS cnt
            FROM {TABLE_NAME}
            WHERE {where} AND podium_rank <= 5
            GROUP BY month, competitor
        ),
        totals AS (
            SELECT month, SUM(cnt) AS total FROM counts GROUP BY month
        ),
        ranked AS (
            SELECT c.month, c.competitor, c.cnt,
                   ROUND(c.cnt * 100.0 / t.total, 2) AS share_pct,
                   ROW_NUMBER() OVER (PARTITION BY c.month ORDER BY c.cnt DESC) AS rn
            FROM counts c JOIN totals t ON c.month = t.month
        )
        SELECT month, competitor, share_pct
        FROM ranked
        WHERE rn <= {TOP_COMPETITORS_PREAPPROVED}
        ORDER BY month, share_pct DESC
    """
    return run_query(cursor, sql)


# Chart 3: Average rank
def get_avg_rank(cursor, origination=None, months=None) -> list[dict]:
    where = _build_filters(origination, months, None, preapproved=True)
    sql = f"""
        WITH ranked AS (
            SELECT month, competitor,
                   ROUND(AVG(CAST(podium_rank AS DOUBLE)), 2) AS avg_rank,
                   COUNT(*) AS appearances,
                   ROW_NUMBER() OVER (PARTITION BY month ORDER BY COUNT(*) DESC) AS rn
            FROM {TABLE_NAME}
            WHERE {where} AND podium_rank <= 5
            GROUP BY month, competitor
        )
        SELECT month, competitor, avg_rank
        FROM ranked
        WHERE rn <= {TOP_COMPETITORS_RANK}
        ORDER BY month, avg_rank ASC
    """
    return run_query(cursor, sql)


# Chart 4: Average shelf space
def get_avg_shelf_space(cursor, origination=None, months=None) -> list[dict]:
    where = _build_filters(origination, months, None, preapproved=True)
    sql = f"""
        WITH pages AS (
            SELECT month, competitor, link_to_screenshots,
                   COUNT(*) AS slots
            FROM {TABLE_NAME}
            WHERE {where} AND podium_rank <= 5
            GROUP BY month, competitor, link_to_screenshots
        ),
        agg AS (
            SELECT month, competitor,
                   ROUND(AVG(CAST(slots AS DOUBLE)), 2) AS avg_shelf_space,
                   SUM(slots) AS total_slots,
                   ROW_NUMBER() OVER (PARTITION BY month ORDER BY SUM(slots) DESC) AS rn
            FROM pages
            GROUP BY month, competitor
        )
        SELECT month, competitor, avg_shelf_space
        FROM agg
        WHERE rn <= {TOP_COMPETITORS_SHELF}
        ORDER BY month, avg_shelf_space DESC
    """
    return run_query(cursor, sql)


# Chart 5: Card portfolio by AF
def get_card_portfolio(cursor, origination=None, months=None) -> list[dict]:
    where = _build_filters(origination, months, None)
    sql = f"""
        SELECT month, competitor,
               CASE
                 WHEN CAST(REGEXP_REPLACE(annual_fee, '[^0-9.]', '') AS DOUBLE) = 0    THEN '$0 AF'
                 WHEN CAST(REGEXP_REPLACE(annual_fee, '[^0-9.]', '') AS DOUBLE) <= 75  THEN '$1-$75 AF'
                 WHEN CAST(REGEXP_REPLACE(annual_fee, '[^0-9.]', '') AS DOUBLE) <= 150 THEN '$76-$150 AF'
                 ELSE '$150+ AF'
               END AS af_tier,
               COUNT(*) AS cnt
        FROM {TABLE_NAME}
        WHERE {where} AND podium_rank <= 5
          AND annual_fee IS NOT NULL AND annual_fee != 'N/A'
        GROUP BY month, competitor, af_tier
        ORDER BY month, cnt DESC
    """
    return run_query(cursor, sql)


# Chart 6: Share of pre-approved offers
def get_preapproved_share(cursor, origination=None, months=None) -> list[dict]:
    where_all = _build_filters(origination, months, None)
    where_pa = _build_filters(origination, months, None, preapproved=True)
    sql = f"""
        WITH all_counts AS (
            SELECT month, competitor, COUNT(*) AS total
            FROM {TABLE_NAME}
            WHERE {where_all} AND podium_rank <= 5
            GROUP BY month, competitor
        ),
        pa_counts AS (
            SELECT month, competitor, COUNT(*) AS pa_total
            FROM {TABLE_NAME}
            WHERE {where_pa} AND podium_rank <= 5
            GROUP BY month, competitor
        ),
        ranked AS (
            SELECT a.month, a.competitor,
                   ROUND(COALESCE(p.pa_total, 0) * 100.0 / a.total, 2) AS pa_share_pct,
                   ROW_NUMBER() OVER (PARTITION BY a.month ORDER BY a.total DESC) AS rn
            FROM all_counts a LEFT JOIN pa_counts p
              ON a.month = p.month AND a.competitor = p.competitor
        )
        SELECT month, competitor, pa_share_pct
        FROM ranked
        WHERE rn <= {TOP_COMPETITORS_PREAPPROVED}
        ORDER BY month, pa_share_pct DESC
    """
    return run_query(cursor, sql)


# ─────────────────────────────────────────────
# Shelf Space
# ─────────────────────────────────────────────

def get_shelf_space(cursor, origination=None, months=None, competitor=None) -> list[dict]:
    where = _build_filters(origination, months, competitor, preapproved=True)
    sql = f"""
        SELECT
            CAST(FLOOR(vantage_score_use_transunion_score / 10) * 10 AS INT) AS score_band,
            competitor AS brand,
            card_name,
            annual_fee,
            apr,
            rewards_offered,
            approval_odds
        FROM {TABLE_NAME}
        WHERE {where} AND podium_rank <= 5
          AND vantage_score_use_transunion_score IS NOT NULL
        ORDER BY score_band, brand, card_name
    """
    return run_query(cursor, sql)


# ─────────────────────────────────────────────
# Co-occurrence
# ─────────────────────────────────────────────

def get_cooccurrence_matrix(cursor, origination=None, months=None) -> list[dict]:
    """Returns pairwise co-occurrence counts (upper triangle only)."""
    where_a = _build_filters(origination, months, None, preapproved=True, table_alias="a")
    where_b = _build_filters(origination, months, None, preapproved=True, table_alias="b")
    sql = f"""
        SELECT
            a.competitor AS comp_a,
            b.competitor AS comp_b,
            COUNT(DISTINCT a.link_to_screenshots) AS cooccurrence_count
        FROM {TABLE_NAME} a
        JOIN {TABLE_NAME} b
          ON a.link_to_screenshots = b.link_to_screenshots
         AND a.competitor < b.competitor
        WHERE {where_a}
          AND {where_b}
          AND a.podium_rank <= 5
          AND b.podium_rank <= 5
        GROUP BY a.competitor, b.competitor
        ORDER BY cooccurrence_count DESC
    """
    return run_query(cursor, sql)


def get_cooccurrence_detail(cursor, comp_a: str, comp_b: str,
                             origination=None, months=None) -> list[dict]:
    """Drill-down: specific product pairs for two competitors."""
    where_a = _build_filters(origination, months, None, preapproved=True, table_alias="a")
    where_b = _build_filters(origination, months, None, preapproved=True, table_alias="b")
    sql = f"""
        SELECT
            a.card_name AS card_a,
            b.card_name AS card_b,
            a.annual_fee AS af_a,
            b.annual_fee AS af_b,
            COUNT(DISTINCT a.link_to_screenshots) AS cooccurrence_count
        FROM {TABLE_NAME} a
        JOIN {TABLE_NAME} b
          ON a.link_to_screenshots = b.link_to_screenshots
        WHERE {where_a}
          AND {where_b}
          AND a.competitor = '{comp_a}'
          AND b.competitor = '{comp_b}'
          AND a.podium_rank <= 5
          AND b.podium_rank <= 5
        GROUP BY a.card_name, b.card_name, a.annual_fee, b.annual_fee
        ORDER BY cooccurrence_count DESC
        LIMIT 20
    """
    return run_query(cursor, sql)


# ─────────────────────────────────────────────
# Avant View
# ─────────────────────────────────────────────

def get_avant_view(cursor, origination=None, months=None, competitor=None) -> list[dict]:
    """
    For each score band + Avant product, show which competitor products
    also appear pre-approved on the same shopper page.
    """
    where_avant = _build_filters(origination, months, None, preapproved=True, table_alias="a")
    where_other = _build_filters(origination, months, competitor, preapproved=True, table_alias="b")
    sql = f"""
        SELECT
            CAST(FLOOR(a.vantage_score_use_transunion_score / 10) * 10 AS INT) AS score_band,
            COALESCE(CAST(REGEXP_REPLACE(a.annual_fee, '[^0-9.]', '') AS DOUBLE), 0) AS avant_af,
            b.competitor,
            b.card_name,
            COALESCE(a.annual_fee, 'N/A') AS avant_annual_fee,
            COALESCE(b.annual_fee, 'N/A') AS comp_annual_fee,
            COUNT(DISTINCT a.link_to_screenshots) AS cooccurrence_count
        FROM {TABLE_NAME} a
        JOIN {TABLE_NAME} b
          ON a.link_to_screenshots = b.link_to_screenshots
        WHERE {where_avant}
          AND {where_other}
          AND a.competitor = '{AVANT_NAME}'
          AND b.competitor != '{AVANT_NAME}'
          AND a.podium_rank <= 5
          AND b.podium_rank <= 5
          AND a.vantage_score_use_transunion_score IS NOT NULL
        GROUP BY score_band, avant_af, b.competitor, b.card_name,
                 a.annual_fee, b.annual_fee
        ORDER BY score_band, avant_af, cooccurrence_count DESC
    """
    return run_query(cursor, sql)
