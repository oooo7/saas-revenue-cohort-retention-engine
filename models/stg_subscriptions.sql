-- models/stg_subscriptions.sql
-- Description: Staging model for raw subscription records.
-- Handles subscription duration, end dates, active flags, and price validation.

WITH source AS (
    SELECT * FROM raw_subscriptions
),

cleaned AS (
    SELECT
        CAST(subscription_id AS VARCHAR) AS subscription_id,
        CAST(user_id AS VARCHAR) AS user_id,
        TRIM(plan_tier) AS plan_tier,
        CAST(start_date AS DATE) AS start_date,
        CAST(end_date AS DATE) AS end_date,
        TRIM(LOWER(status)) AS status,
        CAST(monthly_price AS DOUBLE) AS monthly_price,
        CASE
            WHEN end_date IS NULL THEN TRUE
            ELSE FALSE
        END AS is_currently_active,
        CASE
            WHEN end_date IS NOT NULL THEN (CAST(end_date AS DATE) - CAST(start_date AS DATE))
            ELSE (DATE '2026-03-31' - CAST(start_date AS DATE))
        END AS subscription_duration_days
    FROM source
    WHERE subscription_id IS NOT NULL
      AND monthly_price > 0
)

SELECT * FROM cleaned;
