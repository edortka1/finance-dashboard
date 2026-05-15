import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

st.set_page_config(page_title="Personal Finance Dashboard", layout="wide")

st.title("Personal Finance Dashboard")

rows = supabase.table("transactions").select("*").execute().data
df = pd.DataFrame(rows)

if df.empty:
    st.warning("No transactions found.")
    st.stop()

df["amount"] = pd.to_numeric(df["amount"])
df["date"] = pd.to_datetime(df["date"])

total_spent = df["amount"].sum()
transaction_count = len(df)
avg_transaction = df["amount"].mean()

col1, col2, col3 = st.columns(3)

col1.metric("Total Spending", f"${total_spent:,.2f}")
col2.metric("Transactions", transaction_count)
col3.metric("Average Transaction", f"${avg_transaction:,.2f}")

# -----------------------------
# Subscriptions Section
# -----------------------------

st.header("Subscriptions")

subs_rows = supabase.table("subscriptions").select("*").eq("active", True).execute().data
subs_df = pd.DataFrame(subs_rows)

if subs_df.empty:
    st.info("No active subscriptions found.")
else:
    subs_df["amount"] = pd.to_numeric(subs_df["amount"])
    subs_df["next_payment_date"] = pd.to_datetime(subs_df["next_payment_date"], errors="coerce")

    monthly_subscriptions = subs_df[subs_df["frequency"] == "monthly"]["amount"].sum()
    yearly_subscriptions = monthly_subscriptions * 12
    active_subscription_count = len(subs_df)

    sub_col1, sub_col2, sub_col3 = st.columns(3)

    sub_col1.metric("Monthly Subscriptions", f"${monthly_subscriptions:,.2f}")
    sub_col2.metric("Yearly Subscription Cost", f"${yearly_subscriptions:,.2f}")
    sub_col3.metric("Active Subscriptions", active_subscription_count)

    st.subheader("Upcoming Subscription Payments")

    upcoming_subs = subs_df.sort_values("next_payment_date")

    st.dataframe(
        upcoming_subs[
            ["name", "amount", "frequency", "next_payment_date", "category", "essential", "notes"]
        ],
        use_container_width=True
    )

    st.subheader("Subscriptions by Category")

    subs_by_category = subs_df.groupby("category")["amount"].sum().reset_index()

    fig_subs = px.bar(
        subs_by_category,
        x="category",
        y="amount",
        title="Monthly Subscriptions by Category"
    )

    st.plotly_chart(fig_subs, use_container_width=True)

st.subheader("Spending by Category")
category = df.groupby("category", dropna=False)["amount"].sum().reset_index()
fig = px.bar(category, x="category", y="amount")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Spending Over Time")
daily = df.groupby("date")["amount"].sum().reset_index()
fig2 = px.line(daily, x="date", y="amount")
st.plotly_chart(fig2, use_container_width=True)

st.subheader("Transactions")
st.dataframe(df.sort_values("date", ascending=False), use_container_width=True)
