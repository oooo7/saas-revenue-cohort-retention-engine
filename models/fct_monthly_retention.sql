-- models/fct_monthly_retention.sql
-- Description: Advanced Cohort Retention & Net Revenue Retention (NRR) Mart.
-- Employs DENSE_RANK, LAG/LEAD, DATE_TRUNC, and Window Functions.

WITH mrr_movements AS (
    SELECT * FROM fct_mrr_movements
),

-- Aggregate user cohort activity per cohort_month and report_month
cohort_activity AS (
    SELECT
        cohort_month,
        report_month,
        -- Month index calculation (Month 0, Month 1, Month 2...)
        (EXTRACT(YEAR FROM report_month) - EXTRACT(YEAR FROM cohort_month)) * 12 +
        (EXTRACT(MONTH FROM report_month) - EXTRACT(MONTH FROM cohort_month)) AS cohort_index,
        
        -- Window DENSE_RANK for sequence validation
        DENSE_RANK() OVER (
            PARTITION BY cohort_month 
            ORDER BY report_month
        ) - 1 AS cohort_rank_index,

        -- Customer Counts
        COUNT(DISTINCT user_id) AS total_evaluated_users,
        COUNT(DISTINCT CASE WHEN current_mrr > 0 THEN user_id END) AS retained_users,
        COUNT(DISTINCT CASE WHEN churned_mrr > 0 THEN user_id END) AS churned_users_this_month,

        -- Revenue Aggregations
        SUM(current_mrr) AS cohort_current_mrr,
        SUM(new_mrr) AS cohort_new_mrr,
        SUM(expansion_mrr) AS cohort_expansion_mrr,
        SUM(contraction_mrr) AS cohort_contraction_mrr,
        SUM(churned_mrr) AS cohort_churned_mrr,
        SUM(net_mrr_change) AS cohort_net_mrr_change
    FROM mrr_movements
    GROUP BY cohort_month, report_month
),

cohort_baselines AS (
    SELECT
        *,
        -- Starting cohort size (at Month 0)
        FIRST_VALUE(retained_users) OVER (
            PARTITION BY cohort_month 
            ORDER BY cohort_index
        ) AS cohort_size,
        
        -- Starting cohort MRR baseline (at Month 0)
        FIRST_VALUE(cohort_current_mrr) OVER (
            PARTITION BY cohort_month 
            ORDER BY cohort_index
        ) AS cohort_baseline_mrr,

        -- Previous month retained users for MoM churn gradient
        LAG(retained_users, 1) OVER (
            PARTITION BY cohort_month 
            ORDER BY cohort_index
        ) AS prior_month_retained_users,

        -- Previous month cohort MRR for MoM Net Revenue velocity
        LAG(cohort_current_mrr, 1) OVER (
            PARTITION BY cohort_month 
            ORDER BY cohort_index
        ) AS prior_month_cohort_mrr
    FROM cohort_activity
),

final_metrics AS (
    SELECT
        cohort_month,
        report_month,
        cohort_index,
        cohort_size,
        retained_users,
        churned_users_this_month,
        
        -- Customer Retention Rate (%)
        ROUND(
            (retained_users * 100.0) / NULLIF(cohort_size, 0),
            2
        ) AS user_retention_rate_pct,

        -- MoM User Dropoff Rate (%)
        ROUND(
            ((prior_month_retained_users - retained_users) * 100.0) / NULLIF(prior_month_retained_users, 0),
            2
        ) AS mom_user_churn_rate_pct,

        -- Revenue Metrics
        cohort_baseline_mrr,
        cohort_current_mrr,
        cohort_new_mrr,
        cohort_expansion_mrr,
        cohort_contraction_mrr,
        cohort_churned_mrr,
        cohort_net_mrr_change,

        -- Net Revenue Retention (NRR %) = (Current Cohort MRR / Baseline Cohort MRR) * 100
        ROUND(
            (cohort_current_mrr * 100.0) / NULLIF(cohort_baseline_mrr, 0),
            2
        ) AS net_revenue_retention_pct,

        -- MoM MRR Growth Rate (%)
        ROUND(
            ((cohort_current_mrr - prior_month_cohort_mrr) * 100.0) / NULLIF(prior_month_cohort_mrr, 0),
            2
        ) AS mom_mrr_growth_pct
    FROM cohort_baselines
    WHERE cohort_size > 0
)

SELECT * FROM final_metrics
ORDER BY cohort_month ASC, cohort_index ASC;
