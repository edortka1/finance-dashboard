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
