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


# -----------------------------
# Safe to Spend Section
# -----------------------------

st.header("Safe to Spend")

accounts_rows = supabase.table("accounts").select("*").execute().data
accounts_df = pd.DataFrame(accounts_rows)

goals_rows = supabase.table("financial_goals").select("*").eq("active", True).execute().data
goals_df = pd.DataFrame(goals_rows)

if accounts_df.empty:
    st.warning("No account balances found.")
else:
    accounts_df["current_balance"] = pd.to_numeric(accounts_df["current_balance"], errors="coerce").fillna(0)

    # For now, use all account balances as cash.
    # Later we can separate checking/savings vs credit cards/loans.
    cash_accounts = accounts_df[
        accounts_df["subtype"].isin(["checking", "savings"])
    ]

    total_cash = cash_accounts["current_balance"].sum()

    if goals_df.empty:
        monthly_goals = 0
    else:
        goals_df["amount"] = pd.to_numeric(goals_df["amount"], errors="coerce").fillna(0)
        monthly_goals = goals_df[goals_df["frequency"] == "monthly"]["amount"].sum()

    safe_to_spend_month = total_cash - monthly_subscriptions - monthly_goals
    safe_to_spend_week = safe_to_spend_month / 4
    safe_to_spend_day = safe_to_spend_month / 30

    s1, s2, s3, s4 = st.columns(4)

    s1.metric("Cash Balance", f"${total_cash:,.2f}")
    s2.metric("Safe This Month", f"${safe_to_spend_month:,.2f}")
    s3.metric("Safe Per Week", f"${safe_to_spend_week:,.2f}")
    s4.metric("Safe Per Day", f"${safe_to_spend_day:,.2f}")

    st.subheader("Monthly Obligations")

    obligations = []

    if not subs_df.empty:
        obligations.append({
            "Name": "Subscriptions",
            "Amount": monthly_subscriptions
        })

    if not goals_df.empty:
        for _, row in goals_df.iterrows():
            obligations.append({
                "Name": row["goal_name"],
                "Amount": row["amount"]
            })

    obligations_df = pd.DataFrame(obligations)

    st.dataframe(obligations_df, use_container_width=True)


# -----------------------------
# Loan Payoff Planner
# -----------------------------

st.header("Loan Payoff Planner")

loans_rows = supabase.table("loans").select("*").eq("active", True).execute().data
loans_df = pd.DataFrame(loans_rows)

if loans_df.empty:
    st.info("No active loans found.")
else:
    loan = loans_df.iloc[0]

    loan_balance = float(loan["current_balance"])
    annual_rate = float(loan["interest_rate"]) / 100
    monthly_rate = annual_rate / 12
    minimum_payment = float(loan["minimum_payment"])
    target_date = pd.to_datetime(loan["target_payoff_date"])

    today = pd.Timestamp.today().normalize()
    months_left = max((target_date.year - today.year) * 12 + (target_date.month - today.month), 1)

    if monthly_rate > 0:
        required_payment = loan_balance * monthly_rate / (1 - (1 + monthly_rate) ** (-months_left))
    else:
        required_payment = loan_balance / months_left

    fixed_payment = st.number_input(
        "Monthly payment you plan to make",
        min_value=0.0,
        value=float(minimum_payment),
        step=50.0
    )

    balance = loan_balance
    months = 0

    while balance > 0 and months < 600:
        interest = balance * monthly_rate
        principal = fixed_payment - interest

        if principal <= 0:
            months = 600
            break

        balance -= principal
        months += 1

    projected_payoff_date = today + pd.DateOffset(months=months)

    l1, l2, l3, l4 = st.columns(4)

    l1.metric("Current Loan Balance", f"${loan_balance:,.2f}")
    l2.metric("Required Monthly Payment", f"${required_payment:,.2f}")
    l3.metric("Your Planned Payment", f"${fixed_payment:,.2f}")
    l4.metric("Projected Payoff Date", projected_payoff_date.strftime("%b %Y"))

    if fixed_payment >= required_payment:
        st.success("You are on track to finish by your target payoff date.")
    else:
        st.warning("You are behind your target payoff pace. Increase monthly payment to finish by the target date.")

    st.caption(
        f"Target payoff date: {target_date.strftime('%b %Y')} | Months left: {months_left}"
    )

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
