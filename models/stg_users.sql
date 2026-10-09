-- models/stg_users.sql
-- Description: Staging model for raw user acquisition data.
-- Standardizes types, formats timestamps, and extracts customer metadata.

WITH source AS (
    SELECT * FROM raw_users
),

cleaned AS (
    SELECT
        CAST(user_id AS VARCHAR) AS user_id,
        CAST(signup_date AS DATE) AS signup_date,
        DATE_TRUNC('month', CAST(signup_date AS DATE)) AS cohort_month,
        TRIM(country) AS country,
        TRIM(acquisition_channel) AS acquisition_channel,
        TRIM(initial_plan_tier) AS initial_plan_tier
    FROM source
    WHERE user_id IS NOT NULL
)

SELECT * FROM cleaned;
