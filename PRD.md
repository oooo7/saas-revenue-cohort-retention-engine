# Production Hardening Tasks
- [x] Task 1: Create tests/test_metrics.py using pytest to validate that cohort retention % is always between 0 and 100%, and MRR waterfall math balances (New + Expansion - Contraction - Churn = MoM Net Delta).
- [x] Task 2: Add @st.cache_data decorators to all DuckDB query functions inside app.py to optimize dashboard load times.
- [ ] Task 3: Wrap division denominators in models/fct_monthly_retention.sql with NULLIF(..., 0) to prevent runtime divide-by-zero exceptions.
- [ ] Task 4: Create a GitHub Actions workflow in .github/workflows/ci.yml to automatically run pytest on push and PR.
