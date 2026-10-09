"""
Orchestration Script: Executes SQL Data Transformation Pipeline in DuckDB.

Simulates dbt execution:
1. Compiles and executes staging models (stg_users, stg_subscriptions, stg_activity).
2. Executes analytical marts (fct_mrr_movements, fct_monthly_retention).
3. Verifies schema integrity and prints summary diagnostics.
"""

import os
import time
import duckdb

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "warehouse.duckdb")
MODELS_DIR = os.path.join(BASE_DIR, "models")

PIPELINE = [
    ("stg_users", "VIEW", "stg_users.sql"),
    ("stg_subscriptions", "VIEW", "stg_subscriptions.sql"),
    ("stg_activity", "VIEW", "stg_activity.sql"),
    ("fct_mrr_movements", "TABLE", "fct_mrr_movements.sql"),
    ("fct_monthly_retention", "TABLE", "fct_monthly_retention.sql")
]

def run_pipeline():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Run scripts/generate_data.py first.")

    con = duckdb.connect(DB_PATH)
    print("=" * 60)
    print("🚀 Starting Production Data Modeling Pipeline (DuckDB)")
    print("=" * 60)

    start_total = time.time()

    for model_name, materialization, sql_file in PIPELINE:
        sql_path = os.path.join(MODELS_DIR, sql_file)
        with open(sql_path, "r") as f:
            sql_query = f.read()

        t0 = time.time()
        print(f"▶️  Building {materialization.lower()} '{model_name}' from {sql_file}...")

        # Create or replace VIEW or TABLE
        if materialization == "VIEW":
            stmt = f"CREATE OR REPLACE VIEW {model_name} AS \n{sql_query}"
        else:
            stmt = f"CREATE OR REPLACE TABLE {model_name} AS \n{sql_query}"

        con.execute(stmt)
        elapsed = time.time() - t0

        # Row count check
        count_res = con.execute(f"SELECT COUNT(*) FROM {model_name}").fetchone()[0]
        print(f"   ✓ Materialized {model_name} ({count_res:,} rows) in {elapsed:.2f}s")

    total_elapsed = time.time() - start_total
    print("=" * 60)
    print(f"✨ Pipeline completed successfully in {total_elapsed:.2f}s")
    print("=" * 60)

    # Diagnostic verification
    print("\n📊 Sample Check: fct_monthly_retention (First 5 Cohort Rows):")
    sample = con.execute("""
        SELECT 
            cohort_month, 
            cohort_index, 
            cohort_size, 
            retained_users, 
            user_retention_rate_pct,
            cohort_current_mrr,
            net_revenue_retention_pct
        FROM fct_monthly_retention
        WHERE cohort_index IN (0, 1, 3, 6, 12)
        LIMIT 6
    """).fetchdf()
    print(sample.to_string(index=False))

    con.close()

if __name__ == "__main__":
    run_pipeline()
