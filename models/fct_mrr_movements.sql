-- models/fct_mrr_movements.sql
-- Description: Core revenue accounting engine calculating monthly MRR movements:
-- New, Expansion, Contraction, Churn, Reactivation, and Net MRR per customer and month.

WITH months AS (
    SELECT UNNEST(GENERATE_SERIES(
        DATE '2024-01-01',
        DATE '2026-03-01',
        INTERVAL 1 MONTH
    )) AS report_month
),

users AS (
    SELECT user_id, cohort_month, acquisition_channel, country
    FROM stg_users
),

user_months AS (
    -- Spine: evaluate months starting from user's signup cohort month
    SELECT
        u.user_id,
        u.cohort_month,
        u.acquisition_channel,
        u.country,
        m.report_month
    FROM users u
    CROSS JOIN months m
    WHERE m.report_month >= u.cohort_month
),

active_subscriptions AS (
    SELECT
        um.user_id,
        um.cohort_month,
        um.acquisition_channel,
        um.country,
        um.report_month,
        s.subscription_id,
        s.plan_tier,
        COALESCE(s.monthly_price, 0.0) AS current_mrr
    FROM user_months um
    LEFT JOIN stg_subscriptions s
        ON um.user_id = s.user_id
        AND s.start_date <= (um.report_month + INTERVAL 1 MONTH - INTERVAL 1 DAY)
        AND (s.end_date IS NULL OR s.end_date >= um.report_month)
),

deduped_user_months AS (
    SELECT
        user_id,
        cohort_month,
        acquisition_channel,
        country,
        report_month,
        MAX(plan_tier) AS plan_tier,
        MAX(current_mrr) AS current_mrr
    FROM active_subscriptions
    GROUP BY user_id, cohort_month, acquisition_channel, country, report_month
),

with_lags AS (
    SELECT
        user_id,
        cohort_month,
        acquisition_channel,
        country,
        report_month,
        plan_tier,
        COALESCE(current_mrr, 0.0) AS current_mrr,
        COALESCE(LAG(current_mrr, 1) OVER (
            PARTITION BY user_id 
            ORDER BY report_month
        ), 0.0) AS prior_mrr,
        MIN(CASE WHEN current_mrr > 0 THEN report_month END) OVER (
            PARTITION BY user_id
        ) AS first_active_month
    FROM deduped_user_months
),

classified_movements AS (
    SELECT
        user_id,
        cohort_month,
        acquisition_channel,
        country,
        report_month,
        plan_tier,
        prior_mrr,
        current_mrr,
        -- MRR Movement Classification
        CASE
            WHEN prior_mrr = 0 AND current_mrr > 0 AND report_month = first_active_month THEN current_mrr
            ELSE 0.0
        END AS new_mrr,
        
        CASE
            WHEN prior_mrr = 0 AND current_mrr > 0 AND report_month > first_active_month THEN current_mrr
            ELSE 0.0
        END AS reactivation_mrr,

        CASE
            WHEN prior_mrr > 0 AND current_mrr > prior_mrr THEN (current_mrr - prior_mrr)
            ELSE 0.0
        END AS expansion_mrr,

        CASE
            WHEN prior_mrr > 0 AND current_mrr > 0 AND current_mrr < prior_mrr THEN (prior_mrr - current_mrr)
            ELSE 0.0
        END AS contraction_mrr,

        CASE
            WHEN prior_mrr > 0 AND current_mrr = 0 THEN prior_mrr
            ELSE 0.0
        END AS churned_mrr,

        CASE
            WHEN prior_mrr > 0 AND current_mrr >= prior_mrr THEN prior_mrr
            WHEN prior_mrr > 0 AND current_mrr < prior_mrr AND current_mrr > 0 THEN current_mrr
            ELSE 0.0
        END AS retained_mrr
    FROM with_lags
)

SELECT
    user_id,
    cohort_month,
    acquisition_channel,
    country,
    report_month,
    plan_tier,
    prior_mrr,
    current_mrr,
    new_mrr,
    reactivation_mrr,
    expansion_mrr,
    contraction_mrr,
    churned_mrr,
    retained_mrr,
    (new_mrr + reactivation_mrr + expansion_mrr - contraction_mrr - churned_mrr) AS net_mrr_change
FROM classified_movements;
