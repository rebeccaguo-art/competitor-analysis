"""
queries.py — All SQL query functions for the Competiscan Dashboard.
"""
from typing import Optional
from config import TABLE_NAME, PRE_APPROVED_FILTER, AVANT_NAME
from config import TOP_COMPETITORS_OVERALL, TOP_COMPETITORS_PREAPPROVED
from config import TOP_COMPETITORS_RANK, TOP_COMPETITORS_SHELF


def _build_filters(
    origination: Optional[str],
    months: Optional[list],
    competitor: Optional[str],
    preapproved: bool = False,
    table_alias: str = "",
) -> str:
    alias = f"{table_alias}." if table_alias else ""
    clauses = ["1=1"]

    if preapproved:
        pa = PRE_APPROVED_FILTER.replace("origination", f"{alias}origination").replace("approval_odds", f"{alias}approval_odds")
        clauses.append(f"({pa})")

    if origination and origination != "All origination":
        clauses.append(f"{alias}origination = '{origination}'")

    if months:
        month_list = ", ".join(f"'{m}'" for m in months)
        clauses.append(f"{alias}month IN ({month_list})")

    if competitor and competitor not in ("All competitors", ""):
        # Support comma-separated multi-select
        comp_list = [c.strip() for c in competitor.split(",") if c.strip()]
        sub_clauses = []
        regular = []
        for c in comp_list:
            if c == "Concora — all brands":
                sub_clauses.append(
                    f"({alias}competitor IN ('Indigo', 'Destiny', 'Milestone') "
                    f"OR LOWER({alias}card_name) LIKE '%indigo%' "
                    f"OR LOWER({alias}card_name) LIKE '%destiny%' "
                    f"OR LOWER({alias}card_name) LIKE '%milestone%')"
                )
            else:
                regular.append(c)
        if regular:
            names = ", ".join(f"'{r}'" for r in regular)
            sub_clauses.append(f"{alias}competitor IN ({names})")
        if sub_clauses:
            clauses.append(f"({' OR '.join(sub_clauses)})")

    return " AND ".join(clauses)


def run_query(cursor, sql: str) -> list:
    cursor.execute(sql)
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ─────────────────────────────────────────────
# Filter options
# ─────────────────────────────────────────────

def get_available_months(cursor) -> list:
    sql = f"SELECT DISTINCT month FROM {TABLE_NAME} WHERE month IS NOT NULL ORDER BY month"
    rows = run_query(cursor, sql)
    return [r["month"] for r in rows]


def get_available_competitors(cursor) -> list:
    sql = f"SELECT DISTINCT competitor FROM {TABLE_NAME} WHERE competitor IS NOT NULL ORDER BY competitor"
    rows = run_query(cursor, sql)
    names = [r["competitor"] for r in rows]
    concora_brands = {"Indigo", "Destiny", "Milestone"}
    if concora_brands & set(names):
        result = ["All competitors", "Concora — all brands"]
        result += sorted(names)
        return result
    return ["All competitors"] + sorted(names)


# ─────────────────────────────────────────────
# Market Trends
# ─────────────────────────────────────────────

def get_overall_market_share(cursor, origination=None, months=None, preapproved=True, top_n=None, include_avant=False):
    n = top_n if top_n and top_n > 0 else None
    if n is None: n = TOP_COMPETITORS_OVERALL
    where = _build_filters(origination, months, None, preapproved)
    rn_filter = f"rn <= {n}" + (f" OR competitor = '{AVANT_NAME}'" if include_avant else "")
    sql = f"""
        WITH counts AS (
            SELECT month, competitor, COUNT(*) AS cnt
            FROM {TABLE_NAME}
            WHERE {where} AND podium_rank <= 5
            GROUP BY month, competitor
        ),
        totals AS (SELECT month, SUM(cnt) AS total FROM counts GROUP BY month),
        ranked AS (
            SELECT c.month, c.competitor,
                   ROUND(c.cnt * 100.0 / t.total, 2) AS share_pct,
                   ROW_NUMBER() OVER (PARTITION BY c.month ORDER BY c.cnt DESC) AS rn
            FROM counts c JOIN totals t ON c.month = t.month
        )
        SELECT month, competitor, share_pct FROM ranked WHERE {rn_filter}
        ORDER BY month, share_pct DESC
    """
    return run_query(cursor, sql)


def get_preapproved_market_share(cursor, origination=None, months=None, preapproved=True, top_n=None, include_avant=False):
    n = top_n if top_n and top_n > 0 else TOP_COMPETITORS_PREAPPROVED
    where = _build_filters(origination, months, None, preapproved=True)
    rn_filter = f"rn <= {n}" + (f" OR competitor = '{AVANT_NAME}'" if include_avant else "")
    sql = f"""
        WITH counts AS (
            SELECT month, competitor, COUNT(*) AS cnt
            FROM {TABLE_NAME}
            WHERE {where} AND podium_rank <= 5
            GROUP BY month, competitor
        ),
        totals AS (SELECT month, SUM(cnt) AS total FROM counts GROUP BY month),
        ranked AS (
            SELECT c.month, c.competitor,
                   ROUND(c.cnt * 100.0 / t.total, 2) AS share_pct,
                   ROW_NUMBER() OVER (PARTITION BY c.month ORDER BY c.cnt DESC) AS rn
            FROM counts c JOIN totals t ON c.month = t.month
        )
        SELECT month, competitor, share_pct FROM ranked WHERE {rn_filter}
        ORDER BY month, share_pct DESC
    """
    return run_query(cursor, sql)


def get_avg_rank(cursor, origination=None, months=None, preapproved=True, top_n=None, include_avant=False):
    n = top_n if top_n and top_n > 0 else TOP_COMPETITORS_RANK
    where = _build_filters(origination, months, None, preapproved=True)
    rn_filter = f"rn <= {n}" + (f" OR competitor = '{AVANT_NAME}'" if include_avant else "")
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
        SELECT month, competitor, avg_rank FROM ranked WHERE {rn_filter}
        ORDER BY month, avg_rank ASC
    """
    return run_query(cursor, sql)


def get_avg_shelf_space(cursor, origination=None, months=None, preapproved=True, top_n=None, include_avant=False):
    n = top_n if top_n and top_n > 0 else TOP_COMPETITORS_SHELF
    where = _build_filters(origination, months, None, preapproved=True)
    rn_filter = f"rn <= {n}" + (f" OR competitor = '{AVANT_NAME}'" if include_avant else "")
    sql = f"""
        WITH pages AS (
            SELECT month, competitor, link_to_screenshots, COUNT(*) AS slots
            FROM {TABLE_NAME}
            WHERE {where} AND podium_rank <= 5
            GROUP BY month, competitor, link_to_screenshots
        ),
        agg AS (
            SELECT month, competitor,
                   ROUND(AVG(CAST(slots AS DOUBLE)), 2) AS avg_shelf_space,
                   SUM(slots) AS total_slots,
                   ROW_NUMBER() OVER (PARTITION BY month ORDER BY SUM(slots) DESC) AS rn
            FROM pages GROUP BY month, competitor
        )
        SELECT month, competitor, avg_shelf_space FROM agg WHERE {rn_filter}
        ORDER BY month, avg_shelf_space DESC
    """
    return run_query(cursor, sql)


def get_card_portfolio(cursor, origination=None, months=None, preapproved=False):
    where = _build_filters(origination, months, None, preapproved)
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


def get_preapproved_share(cursor, origination=None, months=None, top_n=None):
    n = top_n or TOP_COMPETITORS_PREAPPROVED
    where_all = _build_filters(origination, months, None)
    where_pa = _build_filters(origination, months, None, preapproved=True)
    sql = f"""
        WITH all_counts AS (
            SELECT month, competitor, COUNT(*) AS total
            FROM {TABLE_NAME} WHERE {where_all} AND podium_rank <= 5
            GROUP BY month, competitor
        ),
        pa_counts AS (
            SELECT month, competitor, COUNT(*) AS pa_total
            FROM {TABLE_NAME} WHERE {where_pa} AND podium_rank <= 5
            GROUP BY month, competitor
        ),
        ranked AS (
            SELECT a.month, a.competitor,
                   ROUND(COALESCE(p.pa_total, 0) * 100.0 / a.total, 2) AS share_pct,
                   ROW_NUMBER() OVER (PARTITION BY a.month ORDER BY a.total DESC) AS rn
            FROM all_counts a LEFT JOIN pa_counts p
              ON a.month = p.month AND a.competitor = p.competitor
        )
        SELECT month, competitor, share_pct FROM ranked WHERE rn <= {n}
        ORDER BY month, share_pct DESC
    """
    return run_query(cursor, sql)


# ─────────────────────────────────────────────
# Shelf Space
# ─────────────────────────────────────────────

def get_shelf_space(cursor, origination=None, months=None, competitor=None, preapproved=True, max_rank=None):
    rank = max_rank or 5
    where = _build_filters(origination, months, competitor, preapproved)
    sql = f"""
        SELECT
            CAST(FLOOR(vantage_score_use_transunion_score / 10) * 10 AS INT) AS score_band,
            competitor AS brand, card_name, annual_fee, apr, rewards_offered, approval_odds
        FROM {TABLE_NAME}
        WHERE {where} AND podium_rank <= {rank}
          AND vantage_score_use_transunion_score IS NOT NULL
        ORDER BY score_band, brand, card_name
    """
    return run_query(cursor, sql)


# ─────────────────────────────────────────────
# Co-occurrence
# ─────────────────────────────────────────────

def get_cooccurrence_matrix(cursor, origination=None, months=None, preapproved=True, max_rank=None):
    rank = max_rank or 5
    where_a = _build_filters(origination, months, None, preapproved, table_alias="a")
    where_b = _build_filters(origination, months, None, preapproved, table_alias="b")
    sql = f"""
        SELECT
            a.competitor AS comp_a,
            b.competitor AS comp_b,
            COUNT(DISTINCT a.link_to_screenshots) AS cooccurrence_count
        FROM {TABLE_NAME} a
        JOIN {TABLE_NAME} b
          ON a.link_to_screenshots = b.link_to_screenshots
         AND a.competitor < b.competitor
        WHERE {where_a} AND {where_b}
          AND a.podium_rank <= {rank} AND b.podium_rank <= {rank}
        GROUP BY a.competitor, b.competitor
        ORDER BY cooccurrence_count DESC
    """
    return run_query(cursor, sql)


def get_cooccurrence_detail(cursor, comp_a, comp_b, origination=None, months=None, preapproved=True, max_rank=None):
    rank = max_rank or 5
    where_a = _build_filters(origination, months, None, preapproved, table_alias="a")
    where_b = _build_filters(origination, months, None, preapproved, table_alias="b")
    sql = f"""
        SELECT
            a.card_name AS card_a, b.card_name AS card_b,
            a.annual_fee AS af_a, b.annual_fee AS af_b,
            COUNT(DISTINCT a.link_to_screenshots) AS cooccurrence_count
        FROM {TABLE_NAME} a
        JOIN {TABLE_NAME} b ON a.link_to_screenshots = b.link_to_screenshots
        WHERE {where_a} AND {where_b}
          AND a.competitor = '{comp_a}' AND b.competitor = '{comp_b}'
          AND a.podium_rank <= {rank} AND b.podium_rank <= {rank}
        GROUP BY a.card_name, b.card_name, a.annual_fee, b.annual_fee
        ORDER BY cooccurrence_count DESC
        LIMIT 20
    """
    return run_query(cursor, sql)


# ─────────────────────────────────────────────
# Avant View
# ─────────────────────────────────────────────

def get_avant_view(cursor, origination=None, months=None, competitor=None, preapproved=True, max_rank=None):
    rank = max_rank or 5
    where_avant = _build_filters(origination, months, None, preapproved, table_alias="a")
    where_other = _build_filters(origination, months, competitor, preapproved, table_alias="b")
    sql = f"""
        SELECT
            CAST(FLOOR(a.vantage_score_use_transunion_score / 10) * 10 AS INT) AS score_band,
            COALESCE(CAST(REGEXP_REPLACE(a.annual_fee, '[^0-9.]', '') AS DOUBLE), 0) AS avant_af,
            b.competitor, b.card_name,
            COALESCE(a.annual_fee, 'N/A') AS avant_annual_fee,
            COALESCE(b.annual_fee, 'N/A') AS comp_annual_fee,
            COUNT(DISTINCT a.link_to_screenshots) AS cooccurrence_count
        FROM {TABLE_NAME} a
        JOIN {TABLE_NAME} b ON a.link_to_screenshots = b.link_to_screenshots
        WHERE {where_avant} AND {where_other}
          AND a.competitor = '{AVANT_NAME}' AND b.competitor != '{AVANT_NAME}'
          AND a.podium_rank <= {rank} AND b.podium_rank <= {rank}
          AND a.vantage_score_use_transunion_score IS NOT NULL
        GROUP BY score_band, avant_af, b.competitor, b.card_name, a.annual_fee, b.annual_fee
        ORDER BY score_band, avant_af, cooccurrence_count DESC
    """
    return run_query(cursor, sql)


# ─────────────────────────────────────────────
# Competitor View
# ─────────────────────────────────────────────

def get_competitor_view(cursor, origination=None, months=None, competitor=None, preapproved=True, max_rank=None):
    if not competitor or competitor in ("All competitors", ""):
        return []
    rank = max_rank or 5
    where_focal = _build_filters(origination, months, competitor, preapproved, table_alias="a")
    where_other = _build_filters(origination, months, None, preapproved, table_alias="b")
    sql = f"""
        SELECT
            CAST(FLOOR(a.vantage_score_use_transunion_score / 10) * 10 AS INT) AS score_band,
            a.competitor AS focal_competitor,
            a.card_name AS focal_card,
            COALESCE(a.annual_fee, 'N/A') AS focal_annual_fee,
            b.competitor AS co_competitor,
            b.card_name AS co_card,
            COALESCE(b.annual_fee, 'N/A') AS co_annual_fee,
            COUNT(DISTINCT a.link_to_screenshots) AS cooccurrence_count
        FROM {TABLE_NAME} a
        JOIN {TABLE_NAME} b ON a.link_to_screenshots = b.link_to_screenshots
        WHERE {where_focal} AND {where_other}
          AND b.competitor != a.competitor
          AND a.podium_rank <= {rank} AND b.podium_rank <= {rank}
          AND a.vantage_score_use_transunion_score IS NOT NULL
        GROUP BY score_band, a.competitor, a.card_name, a.annual_fee,
                 b.competitor, b.card_name, b.annual_fee
        ORDER BY score_band, a.card_name, cooccurrence_count DESC
    """
    return run_query(cursor, sql)
