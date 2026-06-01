# config.py — change TABLE_NAME here after migration to shared schema
TABLE_NAME = "avant_orgs.revenue.competiscan_master_with_competitor"

# Pre-approved filter — matches Crystal's exact definition
PRE_APPROVED_FILTER = """(
    (origination = 'Credit Karma'
     AND approval_odds IN ('Outstanding', 'CKG'))
    OR
    (origination = 'Experian'
     AND approval_odds = 'Pre-Approved')
)"""

# Avant competitor name as it appears in the `competitor` column
AVANT_NAME = "Avant"

# Top-N limits
TOP_COMPETITORS_OVERALL = 5
TOP_COMPETITORS_PREAPPROVED = 5
TOP_COMPETITORS_RANK = 5
TOP_COMPETITORS_SHELF = 5
