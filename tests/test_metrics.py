"""
tests/test_metrics.py: Validation suite for SaaS Retention & Revenue Engine.

Validates:
1. Cohort retention rate bounds:
   - user_retention_rate_pct <= 100% and >= 0%
   - user_retention_rate_pct == 100% at Month 0
   - retained_users <= cohort_size
2. MRR waterfall mathematical consistency:
   - net_mrr_change == new_mrr + reactivation_mrr + expansion_mrr - contraction_mrr - churned_mrr
   - current_mrr - prior_mrr == net_mrr_change
   - non-negative component values
3. RFM segment score bounds and coverage
"""

import os
import duckdb
import pytest
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "warehouse.duckdb")

@pytest.fixture(scope="session")
def db_connection():
    # If the database does not exist (e.g. in fresh CI environment), generate it
    if not os.path.exists(DB_PATH):
        from scripts.generate_data import generate_dataset
        from models.run_models import run_pipeline
        from analysis.retention_analysis import run_retention_analysis

        generate_dataset(num_users=500)
        run_pipeline()
        run_retention_analysis()

    con = duckdb.connect(DB_PATH, read_only=True)
    yield con
    con.close()

def test_cohort_retention_bounds(db_connection):
    """
    Validate that cohort retention percentage never exceeds 100%
    and is exactly 100% at Month 0.
    """
    df = db_connection.execute("""
        SELECT 
            cohort_month,
            cohort_index,
            cohort_size,
            retained_users,
            user_retention_rate_pct
        FROM fct_monthly_retention
    """).fetchdf()

    assert not df.empty, "fct_monthly_retention should not be empty."

    # 1. Retention percentage must be <= 100% and >= 0%
    assert (df["user_retention_rate_pct"] <= 100.0).all(), (
        f"Found retention rate exceeding 100%: {df[df['user_retention_rate_pct'] > 100.0]}"
    )
    assert (df["user_retention_rate_pct"] >= 0.0).all(), "Retention rate must be non-negative."

    # 2. Retained users cannot exceed initial cohort size
    assert (df["retained_users"] <= df["cohort_size"]).all(), (
        "Retained users count cannot exceed starting cohort size."
    )

    # 3. At Month 0, retention must be exactly 100%
    month_zero = df[df["cohort_index"] == 0]
    assert (month_zero["user_retention_rate_pct"] == 100.0).all(), (
        f"Month 0 retention must be 100%: {month_zero[month_zero['user_retention_rate_pct'] != 100.0]}"
    )

def test_mrr_waterfall_math(db_connection):
    """
    Validate MRR waterfall arithmetic:
    net_mrr_change = (New + Reactivation + Expansion - Contraction - Churned)
    current_mrr - prior_mrr == net_mrr_change
    """
    df = db_connection.execute("""
        SELECT 
            user_id,
            report_month,
            prior_mrr,
            current_mrr,
            new_mrr,
            reactivation_mrr,
            expansion_mrr,
            contraction_mrr,
            churned_mrr,
            retained_mrr,
            net_mrr_change
        FROM fct_mrr_movements
    """).fetchdf()

    assert not df.empty, "fct_mrr_movements should not be empty."

    # 1. Component non-negativity
    assert (df["new_mrr"] >= 0.0).all(), "new_mrr must be >= 0"
    assert (df["reactivation_mrr"] >= 0.0).all(), "reactivation_mrr must be >= 0"
    assert (df["expansion_mrr"] >= 0.0).all(), "expansion_mrr must be >= 0"
    assert (df["contraction_mrr"] >= 0.0).all(), "contraction_mrr must be >= 0"
    assert (df["churned_mrr"] >= 0.0).all(), "churned_mrr must be >= 0"
    assert (df["retained_mrr"] >= 0.0).all(), "retained_mrr must be >= 0"

    # 2. Waterfall formula: New + Reactivation + Expansion - Contraction - Churned == Net Delta
    expected_net = (
        df["new_mrr"] + 
        df["reactivation_mrr"] + 
        df["expansion_mrr"] - 
        df["contraction_mrr"] - 
        df["churned_mrr"]
    )
    np.testing.assert_allclose(
        df["net_mrr_change"].values,
        expected_net.values,
        rtol=1e-5,
        atol=1e-5,
        err_msg="MRR waterfall formula mismatch: New + Reactivation + Exp - Cont - Churn != Net"
    )

    # 3. Delta formula: current_mrr - prior_mrr == net_mrr_change
    mrr_diff = df["current_mrr"] - df["prior_mrr"]
    np.testing.assert_allclose(
        mrr_diff.values,
        df["net_mrr_change"].values,
        rtol=1e-5,
        atol=1e-5,
        err_msg="current_mrr - prior_mrr does not equal net_mrr_change"
    )

def test_rfm_segments_integrity(db_connection):
    """
    Validate that RFM scores are in [1, 5] and segment classifications are exhaustive.
    """
    df = db_connection.execute("""
        SELECT 
            user_id,
            r_score,
            f_score,
            m_score,
            rfm_segment
        FROM fct_rfm_segments
    """).fetchdf()

    assert not df.empty, "fct_rfm_segments should not be empty."

    # Scores within 1 to 5
    assert df["r_score"].between(1, 5).all(), "r_score must be between 1 and 5"
    assert df["f_score"].between(1, 5).all(), "f_score must be between 1 and 5"
    assert df["m_score"].between(1, 5).all(), "m_score must be between 1 and 5"

    # No null segments
    assert df["rfm_segment"].notna().all(), "All users must have an assigned rfm_segment"
