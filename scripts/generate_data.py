"""
Synthetic Data Generator for SaaS Subscription Revenue & Customer Cohort Retention Engine.

Generates realistic relational data across:
- raw_users
- raw_subscriptions
- raw_activity_logs

Incorporates real-world B2B/B2C SaaS dynamics:
- Higher churn rates for low-tier plans (Basic > Pro > Enterprise)
- Seasonality in acquisition and end-of-year budget churn
- Expansion (upgrades) and Contraction (downgrades)
- 30-day pre-churn engagement cliff and support ticket surges
"""

import os
import random
import datetime
from datetime import timedelta
import duckdb
import pandas as pd
import numpy as np

# Set deterministic seed for reproducible analytics portfolios
np.random.seed(42)
random.seed(42)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "warehouse.duckdb")

START_DATE = datetime.date(2024, 1, 1)
END_DATE = datetime.date(2026, 3, 31)
TOTAL_DAYS = (END_DATE - START_DATE).days

COUNTRIES = ["United States", "United Kingdom", "Germany", "Canada", "France", "Australia", "India", "Netherlands"]
COUNTRY_WEIGHTS = [0.45, 0.15, 0.10, 0.08, 0.07, 0.06, 0.05, 0.04]

CHANNELS = ["Organic Search", "Paid Search", "Product Referral", "Outbound Enterprise", "Social Ads"]
CHANNEL_WEIGHTS = [0.30, 0.25, 0.20, 0.10, 0.15]

TIER_PRICING = {
    "Basic": 29.0,
    "Pro": 99.0,
    "Enterprise": 499.0
}

# Base monthly churn probabilities by tier
BASE_CHURN_RATES = {
    "Basic": 0.075,      # 7.5% monthly churn
    "Pro": 0.032,        # 3.2% monthly churn
    "Enterprise": 0.012  # 1.2% monthly churn
}

def generate_dataset(num_users=3000):
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "raw"), exist_ok=True)

    print(f"🚀 Generating synthetic SaaS data for {num_users} users from {START_DATE} to {END_DATE}...")

    users_records = []
    subscriptions_records = []
    activity_records = []

    sub_id_counter = 10001
    log_id_counter = 1000001

    for u_idx in range(1, num_users + 1):
        user_id = f"USR_{u_idx:05d}"

        # 1. Signup date with slight growth trend over time
        day_offset = int(np.random.beta(a=1.4, b=1.1) * TOTAL_DAYS)
        signup_date = START_DATE + timedelta(days=day_offset)

        country = np.random.choice(COUNTRIES, p=COUNTRY_WEIGHTS)
        channel = np.random.choice(CHANNELS, p=CHANNEL_WEIGHTS)

        # Plan tier distribution based on channel
        if channel == "Outbound Enterprise":
            plan_tier = np.random.choice(["Pro", "Enterprise"], p=[0.25, 0.75])
        elif channel in ["Organic Search", "Product Referral"]:
            plan_tier = np.random.choice(["Basic", "Pro", "Enterprise"], p=[0.55, 0.38, 0.07])
        else: # Paid Search / Social Ads
            plan_tier = np.random.choice(["Basic", "Pro", "Enterprise"], p=[0.70, 0.26, 0.04])

        users_records.append({
            "user_id": user_id,
            "signup_date": signup_date,
            "country": country,
            "acquisition_channel": channel,
            "initial_plan_tier": plan_tier
        })

        # 2. Subscription lifecycle (including upgrades/downgrades and churn)
        current_tier = plan_tier
        current_start = signup_date
        current_price = TIER_PRICING[current_tier]
        
        # Determine lifetime in months before potential churn
        monthly_churn_prob = BASE_CHURN_RATES[current_tier]
        if channel in ["Social Ads", "Paid Search"]:
            monthly_churn_prob *= 1.25
        elif channel == "Product Referral":
            monthly_churn_prob *= 0.80

        survived_months = 0
        will_churn = False
        churn_month = None

        max_possible_months = max(1, (END_DATE.year - current_start.year) * 12 + (END_DATE.month - current_start.month))
        for m in range(1, max_possible_months + 1):
            m_date = current_start + timedelta(days=m * 30)
            seasonal_factor = 1.35 if m_date.month in [11, 12] else 1.0

            if np.random.rand() < (monthly_churn_prob * seasonal_factor):
                will_churn = True
                churn_month = m
                break
            survived_months = m

        if will_churn:
            active_days = churn_month * 30 + random.randint(-10, 10)
            active_days = max(7, active_days)
            churn_date = current_start + timedelta(days=active_days)
            if churn_date > END_DATE:
                churn_date = None
                status = "active"
            else:
                status = "cancelled"
        else:
            churn_date = None
            status = "active"

        # Upgrades / Expansions / Contractions
        has_plan_change = False
        change_date = None
        new_tier = current_tier

        if (churn_date is None or (churn_date - current_start).days > 120) and ((END_DATE - current_start).days > 120):
            if current_tier == "Basic" and np.random.rand() < 0.14:
                has_plan_change = True
                new_tier = "Pro"
                change_date = current_start + timedelta(days=random.randint(60, 150))
            elif current_tier == "Pro" and np.random.rand() < 0.10:
                has_plan_change = True
                new_tier = "Enterprise"
                change_date = current_start + timedelta(days=random.randint(90, 210))
            elif current_tier == "Pro" and np.random.rand() < 0.04:
                has_plan_change = True
                new_tier = "Basic"
                change_date = current_start + timedelta(days=random.randint(90, 180))

        if has_plan_change and change_date and (churn_date is None or change_date < churn_date):
            # Phase 1 subscription (Initial)
            sub_id_1 = f"SUB_{sub_id_counter}"
            sub_id_counter += 1
            subscriptions_records.append({
                "subscription_id": sub_id_1,
                "user_id": user_id,
                "plan_tier": current_tier,
                "start_date": current_start,
                "end_date": change_date,
                "status": "expired",
                "monthly_price": current_price
            })

            # Phase 2 subscription (Upgraded / Downgraded)
            sub_id_2 = f"SUB_{sub_id_counter}"
            sub_id_counter += 1
            subscriptions_records.append({
                "subscription_id": sub_id_2,
                "user_id": user_id,
                "plan_tier": new_tier,
                "start_date": change_date,
                "end_date": churn_date,
                "status": status,
                "monthly_price": TIER_PRICING[new_tier]
            })
            effective_plan = new_tier
        else:
            sub_id = f"SUB_{sub_id_counter}"
            sub_id_counter += 1
            subscriptions_records.append({
                "subscription_id": sub_id,
                "user_id": user_id,
                "plan_tier": current_tier,
                "start_date": current_start,
                "end_date": churn_date,
                "status": status,
                "monthly_price": current_price
            })
            effective_plan = current_tier

        # 3. Generate Daily Activity Logs
        user_end_limit = churn_date if churn_date else END_DATE
        days_span = (user_end_limit - current_start).days

        if days_span > 0:
            base_engagement = {
                "Basic": 0.35,
                "Pro": 0.55,
                "Enterprise": 0.75
            }[effective_plan]

            sample_dates = [
                current_start + timedelta(days=d)
                for d in range(0, days_span + 1)
                if np.random.rand() < base_engagement
            ]

            if current_start not in sample_dates:
                sample_dates.insert(0, current_start)

            for act_date in sample_dates:
                days_until_churn = (churn_date - act_date).days if churn_date else 999

                # 30-day pre-churn engagement cliff
                if 0 <= days_until_churn <= 30:
                    decay = max(0.15, days_until_churn / 30.0)
                    daily_sessions = max(1, int(np.random.poisson(lam=1.5 * decay)))
                    feature_usage = int(np.random.poisson(lam=2.0 * decay))
                    support_tickets = np.random.choice([0, 1, 2, 3], p=[0.45, 0.35, 0.15, 0.05])
                    avg_duration = round(float(np.random.uniform(2.0, 8.0) * decay), 2)
                else:
                    if effective_plan == "Enterprise":
                        daily_sessions = int(np.random.poisson(lam=5.2)) + 1
                        feature_usage = int(np.random.poisson(lam=18.5)) + 2
                        support_tickets = np.random.choice([0, 1], p=[0.96, 0.04])
                        avg_duration = round(float(np.random.uniform(25.0, 75.0)), 2)
                    elif effective_plan == "Pro":
                        daily_sessions = int(np.random.poisson(lam=3.1)) + 1
                        feature_usage = int(np.random.poisson(lam=9.2)) + 1
                        support_tickets = np.random.choice([0, 1, 2], p=[0.91, 0.08, 0.01])
                        avg_duration = round(float(np.random.uniform(15.0, 45.0)), 2)
                    else: # Basic
                        daily_sessions = int(np.random.poisson(lam=1.8)) + 1
                        feature_usage = int(np.random.poisson(lam=3.8))
                        support_tickets = np.random.choice([0, 1, 2], p=[0.88, 0.10, 0.02])
                        avg_duration = round(float(np.random.uniform(5.0, 25.0)), 2)

                activity_records.append({
                    "log_id": log_id_counter,
                    "user_id": user_id,
                    "activity_date": act_date,
                    "daily_sessions": max(1, daily_sessions),
                    "feature_usage_count": feature_usage,
                    "support_tickets_logged": support_tickets,
                    "avg_session_duration_mins": avg_duration
                })
                log_id_counter += 1

    df_users = pd.DataFrame(users_records)
    df_subs = pd.DataFrame(subscriptions_records)
    df_activity = pd.DataFrame(activity_records)

    print(f"✅ Generated {len(df_users):,} users")
    print(f"✅ Generated {len(df_subs):,} subscription records")
    print(f"✅ Generated {len(df_activity):,} daily activity logs")

    df_users.to_csv(os.path.join(DATA_DIR, "raw", "raw_users.csv"), index=False)
    df_subs.to_csv(os.path.join(DATA_DIR, "raw", "raw_subscriptions.csv"), index=False)
    df_activity.to_csv(os.path.join(DATA_DIR, "raw", "raw_activity_logs.csv"), index=False)

    con = duckdb.connect(DB_PATH)
    con.execute("CREATE OR REPLACE TABLE raw_users AS SELECT * FROM df_users")
    con.execute("CREATE OR REPLACE TABLE raw_subscriptions AS SELECT * FROM df_subs")
    con.execute("CREATE OR REPLACE TABLE raw_activity_logs AS SELECT * FROM df_activity")
    con.close()

    print(f"💾 Successfully saved to DuckDB: {DB_PATH}")

if __name__ == "__main__":
    generate_dataset()
