-- models/stg_activity.sql
-- Description: Staging model for daily user activity logs.
-- Standardizes date fields, computes rolling window aggregations, and identifies engagement health.

WITH source AS (
    SELECT * FROM raw_activity_logs
),

standardized AS (
    SELECT
        CAST(log_id AS BIGINT) AS log_id,
        CAST(user_id AS VARCHAR) AS user_id,
        CAST(activity_date AS DATE) AS activity_date,
        CAST(daily_sessions AS INTEGER) AS daily_sessions,
        CAST(feature_usage_count AS INTEGER) AS feature_usage_count,
        CAST(support_tickets_logged AS INTEGER) AS support_tickets_logged,
        CAST(avg_session_duration_mins AS DOUBLE) AS avg_session_duration_mins
    FROM source
    WHERE user_id IS NOT NULL
),

with_windows AS (
    SELECT
        log_id,
        user_id,
        activity_date,
        daily_sessions,
        feature_usage_count,
        support_tickets_logged,
        avg_session_duration_mins,
        -- Rolling 7-day total sessions
        SUM(daily_sessions) OVER(
            PARTITION BY user_id 
            ORDER BY activity_date 
            RANGE BETWEEN INTERVAL 6 DAYS PRECEDING AND CURRENT ROW
        ) AS rolling_7d_sessions,
        -- Rolling 30-day total feature usage
        SUM(feature_usage_count) OVER(
            PARTITION BY user_id 
            ORDER BY activity_date 
            RANGE BETWEEN INTERVAL 29 DAYS PRECEDING AND CURRENT ROW
        ) AS rolling_30d_feature_usage,
        -- Rolling 30-day total support tickets
        SUM(support_tickets_logged) OVER(
            PARTITION BY user_id 
            ORDER BY activity_date 
            RANGE BETWEEN INTERVAL 29 DAYS PRECEDING AND CURRENT ROW
        ) AS rolling_30d_support_tickets
    FROM standardized
)

SELECT * FROM with_windows;
