# 📈 SaaS Subscription Revenue & Customer Cohort Retention Engine
> **Staff Analytics Engineer & Growth Analytics Lead Portfolio Project**  
> *Production-Grade SQL Modeling • Embedded DuckDB OLAP • Behavioral RFM Segmentation • Executive Streamlit Dashboard*

---

## 📌 Executive Summary & Business Problem

In high-growth SaaS business models, customer acquisition cost (CAC) often exceeds the first 6–12 months of annual contract value (ACV). Sustaining high-multiple enterprise valuations requires top-decile **Net Revenue Retention (NRR > 110%)** and minimal **Gross Monthly Churn (< 2.5%)**.

However, executive leadership teams often suffer from:
1. **Vanity Top-Line Metrics**: Celebrating top-line MRR additions while obscuring rapid cohort decay in lower-tier plans.
2. **Lagging Indicators of Churn**: Measuring churn only after contract cancellation requests arrive, missing the critical **30-day pre-churn engagement cliff**.
3. **Fragmented Data Warehousing**: Inconsistent definitions of New vs. Expansion vs. Contraction vs. Churned MRR between Finance and Product Analytics.

### 🎯 The Objective
This project delivers a **production-grade Analytics Engineering & Growth Intelligence engine** built on **DuckDB**, standardizing dbt-style SQL transformation layers, survival cohort models, behavioral RFM segmentation, and an executive Streamlit portal with quantified growth recommendations for the **VP of Growth** and **Chief Revenue Officer (CRO)**.

---

## 🏗️ Architecture & Pipeline Flow

```mermaid
flowchart TD
    subgraph Ingestion ["1. Relational Ingestion & Synthesis"]
        GEN[scripts/generate_data.py]
        U[(raw_users)]
        S[(raw_subscriptions)]
        A[(raw_activity_logs)]
        GEN --> U
        GEN --> S
        GEN --> A
    end

    subgraph Staging ["2. dbt-Style Staging Layer (DuckDB Views)"]
        STG_U[models/stg_users.sql]
        STG_S[models/stg_subscriptions.sql]
        STG_A[models/stg_activity.sql]
        U --> STG_U
        S --> STG_S
        A --> STG_A
    end

    subgraph Marts ["3. Core Dimensional Marts (DuckDB Tables)"]
        FCT_MRR[models/fct_mrr_movements.sql<br/><i>LAG/LEAD MRR Bridge</i>]
        FCT_RET[models/fct_monthly_retention.sql<br/><i>Cohort Survival & NRR Matrix</i>]
        STG_U & STG_S --> FCT_MRR
        FCT_MRR --> FCT_RET
    end

    subgraph Intelligence ["4. Growth Intelligence & ML Layer"]
        RFM[analysis/retention_analysis.py<br/><i>SaaS RFM Segmentation & Logistic Telemetry</i>]
        FCT_RFM[(fct_rfm_segments)]
        STG_A & FCT_MRR --> RFM
        RFM --> FCT_RFM
    end

    subgraph Presentation ["5. Executive Decision Portal"]
        APP[app.py - Streamlit Engine]
        KPI[Executive KPI Cards: MRR, ARR, NRR, LTV]
        HEAT[Interactive Cohort Retention Heatmaps]
        WATER[MRR Waterfall Bridge]
        STRAT[VP of Growth Strategic ROI Plays]
        
        FCT_RET & FCT_MRR & FCT_RFM --> APP
        APP --> KPI
        APP --> HEAT
        APP --> WATER
        APP --> STRAT
    end
```

---

## 🗄️ Relational Data Model & Warehouse Schema

The data warehouse persists in **DuckDB (`data/warehouse.duckdb`)** and models a multi-year B2B/B2C SaaS subscription lifecycle across 3,000+ customer accounts and 370,000+ telemetry records:

| Entity / Model | Type | Granularity | Key Dimensions & Measures |
| :--- | :--- | :--- | :--- |
| `raw_users` | Source Table | 1 row per Account | `user_id`, `signup_date`, `country`, `acquisition_channel`, `initial_plan_tier` |
| `raw_subscriptions` | Source Table | 1 row per Subscription Phase | `subscription_id`, `user_id`, `plan_tier`, `start_date`, `end_date`, `status`, `monthly_price` |
| `raw_activity_logs` | Source Table | 1 row per User per Day | `log_id`, `user_id`, `activity_date`, `daily_sessions`, `feature_usage_count`, `support_tickets_logged` |
| `stg_users` | Staging View | 1 row per Account | Standardized dates, derived `cohort_month` via `DATE_TRUNC` |
| `stg_subscriptions` | Staging View | 1 row per Subscription | Validated tenure in days, active booleans, sanitized pricing |
| `stg_activity` | Staging View | 1 row per Activity Log | Window functions: rolling 7-day sessions, rolling 30-day feature usage & support tickets |
| `fct_mrr_movements` | Analytical Mart | 1 row per User per Month | Full month calendar spine, `prior_mrr`, `current_mrr`, categorized: `new_mrr`, `expansion_mrr`, `contraction_mrr`, `churned_mrr`, `retained_mrr`, `net_mrr_change` |
| `fct_monthly_retention` | Analytical Mart | 1 row per Cohort per Offset | `cohort_month`, `cohort_index`, `cohort_size`, `retained_users`, `user_retention_rate_pct`, `cohort_baseline_mrr`, `cohort_current_mrr`, `net_revenue_retention_pct` |
| `fct_rfm_segments` | Analytical Mart | 1 row per Account | Quantile scores: Recency (days), Frequency (sessions/mo), Monetary (LTV), Assigned SaaS Cohort |

---

## 🔬 Production SQL Engineering Deep Dive

### 1. Robust MRR Accounting Engine (`fct_mrr_movements.sql`)
To prevent double counting and ensure financial compliance, a monthly calendar spine is crossed with every user from their `cohort_month` onwards. Using analytical window functions:
```sql
COALESCE(LAG(current_mrr, 1) OVER (
    PARTITION BY user_id 
    ORDER BY report_month
), 0.0) AS prior_mrr
```
Revenue transitions are classified into six discrete financial categories:
- **New MRR**: First month of billing where `prior_mrr = 0` and `report_month = first_active_month`.
- **Expansion MRR**: Customer upgrades their tier or adds capacity (`current_mrr > prior_mrr`).
- **Contraction MRR**: Customer downgrades to a lower tier (`0 < current_mrr < prior_mrr`).
- **Churned MRR**: Active customer ceases subscription (`prior_mrr > 0 AND current_mrr = 0`).
- **Retained MRR**: Base revenue preserved MoM (`MIN(current_mrr, prior_mrr)`).

### 2. Dual Retention Modeling: User vs. Net Revenue Retention (`fct_monthly_retention.sql`)
The cohort mart combines window functions (`DENSE_RANK`, `FIRST_VALUE`, `LAG`) to evaluate both **Logo Retention** and **Dollar Retention**:
$$\text{User Retention Rate (\%)}_{i, t} = \frac{\text{Retained Users}_{i, t}}{\text{Cohort Initial Size}_i} \times 100$$
$$\text{Net Revenue Retention (NRR \%)}_{i, t} = \frac{\text{Current Cohort MRR}_{i, t}}{\text{Baseline Cohort MRR}_i} \times 100$$

---

## 📊 Predictive Telemetry & Churn Drivers

Statistical regression and correlation analysis (`analysis/retention_analysis.py`) identified two critical leading indicators:

1. **The 30-Day Pre-Churn Engagement Cliff**:
   - Accounts that cancel experience an average **74% drop in weekly sessions** and an **82% drop in feature usage** 30 days prior to their official cancellation date.
   - Session duration decay has a strong inverse correlation with churn likelihood ($r = -0.472$, Spearman $\rho = -0.608$).
2. **The Support Ticket Churn Multiplier**:
   - Accounts logging **2 or more support tickets** without subsequent feature usage spikes exhibit a **3.1x higher churn rate** than accounts with zero tickets.
   - Strongest signal: Unresolved tickets paired with dropping login frequency indicates catastrophic onboarding or operational friction.

---

## 💼 Executive Recommendations for VP of Growth

| Priority | Initiative | Empirical Driver | Operational Execution | Projected ARR Impact |
| :--- | :--- | :--- | :--- | :--- |
| **P0** | **Day-14 Guided Feature Onboarding** | Accounts with low Month-1 feature usage churn at **62.4%** vs **24.8%** for activated accounts (60% risk reduction). | In-app interactive checklists, template libraries, automated CS trigger if events < 3 by Day 7. | **+$339,100 / yr** ARR saved by lifting early retention +6.4 pp. |
| **P1** | **Automated Pre-Churn Support Escalation** | 82% of churn events are preceded by a 30-day session decline paired with support tickets (3.1x hazard). | Real-time webhook alerting CS when an account has >30% session decay and open tickets. 2-hr SLA response. | **+$271,000 / yr** at-risk ARR recovered. |
| **P2** | **Enterprise Expansion Funnel for Pro Champions** | 340+ active Pro accounts ($99/mo) exhibit Enterprise-grade session depth without seat monetization. | In-app feature gates & AE outreach offering 30-day Enterprise trials once usage crosses 15 sessions/mo for 2 months. | **+$187,200 / yr** in net expansion ARR (12% conversion). |

**Total Estimated Growth Impact:** **+$797,300 in annualized net ARR contribution**.

---

## ⚡ Quickstart & Reproducibility Guide

### 1. Clone & Set Up Python Environment
```bash
# Clone the repository
git clone https://github.com/oooo7/saas-revenue-cohort-retention-engine.git
cd saas-revenue-cohort-retention-engine

# Install required analytics dependencies
pip install -r requirements.txt
```

### 2. Generate Synthetic Relational Dataset
Generates 3,000 users, 3,200+ subscription episodes, and 370,000+ telemetry rows with realistic SaaS churn and engagement dynamics:
```bash
python3 scripts/generate_data.py
```
*Outputs: `data/warehouse.duckdb` and raw CSV exports in `data/raw/`.*

### 3. Run dbt-Style Production SQL Transformations
Compiles and executes staging views and materialized fact marts inside DuckDB:
```bash
python3 models/run_models.py
```

### 4. Execute RFM Segmentation & Predictive Insights
Calculates SaaS RFM quantile scoring and correlation telemetry:
```bash
python3 analysis/retention_analysis.py
```

### 5. Launch Executive Streamlit Dashboard
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501` to explore:
- Top-level KPI cards (MRR, ARR, NRR, LTV, Churn Rate).
- Interactive Plotly Cohort Retention Heatmap with User % and NRR % toggle.
- MRR Waterfall bridge with New, Expansion, Contraction, and Churn attribution.
- RFM Behavioral segmentation matrix and customer value scatter plots.
- Executive briefing tab with root cause telemetry and ROI calculations.

---

## 🛠️ Tech Stack & Design Principles

- **Warehouse Engine**: [DuckDB](https://duckdb.org/) (High-performance embedded vectorized OLAP engine).
- **Data Modeling**: ANSI SQL (dbt modeling conventions, CTE architecture, Window Functions).
- **Analytics & ML**: [pandas](https://pandas.pydata.org/), [NumPy](https://numpy.org/), [scikit-learn](https://scikit-learn.org/).
- **Visual Presentation**: [Streamlit](https://streamlit.io/), [Plotly](https://plotly.com/python/).
- **Data Engineering Standards**: Deterministic random seeding, schema integrity validations, decoupled ingestion from presentation.

---

## 👤 Author & Portfolio Context
- **Role Target**: Staff Analytics Engineer / Lead Growth Analytics Lead / Senior Business Analyst
- **Focus Areas**: SaaS Unit Economics, Subscription Lifecycle Modeling, Cohort Survival Analysis, dbt/SQL Warehouse Architecture.
