import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

st.set_page_config(page_title="Personal Finance Dashboard", layout="wide")
st.title("Personal Finance Dashboard")

# -----------------------------
# Load Transactions
# -----------------------------

rows = supabase.table("transactions").select("*").execute().data
df = pd.DataFrame(rows)

if df.empty:
    st.warning("No transactions found.")
    st.stop()

df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
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

monthly_subscriptions = 0

if subs_df.empty:
    st.info("No active subscriptions found.")
else:
    subs_df["amount"] = pd.to_numeric(subs_df["amount"], errors="coerce").fillna(0)
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

    subs_by_category = subs_df.groupby("category", dropna=False)["amount"].sum().reset_index()

    fig_subs = px.bar(
        subs_by_category,
        x="category",
        y="amount",
        title="Monthly Subscriptions by Category"
    )

    st.plotly_chart(
        fig_subs,
        use_container_width=True,
        key="subscriptions_by_category_chart"
    )

# -----------------------------
# Safe to Spend Section
# -----------------------------

st.header("Safe to Spend")

accounts_rows = supabase.table("accounts").select("*").execute().data
accounts_df = pd.DataFrame(accounts_rows)

goals_rows = supabase.table("financial_goals").select("*").eq("active", True).execute().data
goals_df = pd.DataFrame(goals_rows)

monthly_goals = 0
total_cash = 0

if accounts_df.empty:
    st.warning("No account balances found.")
else:
    accounts_df["current_balance"] = pd.to_numeric(
        accounts_df["current_balance"],
        errors="coerce"
    ).fillna(0)

    cash_accounts = accounts_df[
        accounts_df["subtype"].isin(["checking", "savings"])
    ]

    total_cash = cash_accounts["current_balance"].sum()

    if not goals_df.empty:
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
# Paycheck Runway
# -----------------------------

st.header("Paycheck Runway")

paycheck_rows = supabase.table("paychecks").select("*").eq("active", True).execute().data
paycheck_df = pd.DataFrame(paycheck_rows)

if paycheck_df.empty:
    st.info("No active paycheck information found.")
else:
    paycheck_df["expected_amount"] = pd.to_numeric(
        paycheck_df["expected_amount"],
        errors="coerce"
    ).fillna(0)

    paycheck_df["next_pay_date"] = pd.to_datetime(
        paycheck_df["next_pay_date"],
        errors="coerce"
    )

    next_paycheck = paycheck_df.sort_values("next_pay_date").iloc[0]

    today = pd.Timestamp.today().normalize()
    next_pay_date = next_paycheck["next_pay_date"]
    expected_paycheck = float(next_paycheck["expected_amount"])

    days_until_paycheck = max((next_pay_date - today).days, 0)

    monthly_obligations = monthly_subscriptions + monthly_goals + total_minimum_payment
    daily_obligation_rate = monthly_obligations / 30

    obligations_until_paycheck = daily_obligation_rate * days_until_paycheck

    safe_until_paycheck = total_cash - obligations_until_paycheck

    safe_per_day_until_paycheck = (
        safe_until_paycheck / days_until_paycheck
        if days_until_paycheck > 0
        else safe_until_paycheck
    )

    p1, p2, p3, p4 = st.columns(4)

    p1.metric("Days Until Paycheck", days_until_paycheck)
    p2.metric("Next Paycheck Amount", f"${expected_paycheck:,.2f}")
    p3.metric("Safe Until Paycheck", f"${safe_until_paycheck:,.2f}")
    p4.metric("Safe Per Day Until Paycheck", f"${safe_per_day_until_paycheck:,.2f}")

    st.caption(
        f"Next paycheck date: {next_pay_date.strftime('%b %d, %Y')}"
    )


# -----------------------------
# Credit Card Payment Pressure
# -----------------------------

st.header("Credit Card Payment Pressure")

cards_rows = supabase.table("credit_cards").select("*").eq("active", True).execute().data
cards_df = pd.DataFrame(cards_rows)

total_minimum_payment = 0

if cards_df.empty:
    st.info("No active credit cards found.")
else:
    cards_df["current_balance"] = pd.to_numeric(cards_df["current_balance"], errors="coerce").fillna(0)
    cards_df["statement_balance"] = pd.to_numeric(cards_df["statement_balance"], errors="coerce").fillna(0)
    cards_df["credit_limit"] = pd.to_numeric(cards_df["credit_limit"], errors="coerce").fillna(0)
    cards_df["minimum_payment"] = pd.to_numeric(cards_df["minimum_payment"], errors="coerce").fillna(0)
    cards_df["payment_due_date"] = pd.to_datetime(cards_df["payment_due_date"], errors="coerce")

    total_card_balance = cards_df["current_balance"].sum()
    total_statement_balance = cards_df["statement_balance"].sum()
    total_minimum_payment = cards_df["minimum_payment"].sum()
    total_credit_limit = cards_df["credit_limit"].sum()

    utilization = 0
    if total_credit_limit > 0:
        utilization = total_card_balance / total_credit_limit

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Card Balance", f"${total_card_balance:,.2f}")
    c2.metric("Statement Balance", f"${total_statement_balance:,.2f}")
    c3.metric("Minimum Payments", f"${total_minimum_payment:,.2f}")
    c4.metric("Utilization", f"{utilization:.1%}")

    st.subheader("Credit Cards")

    display_cards = cards_df.copy()
    display_cards["utilization"] = display_cards.apply(
        lambda row: row["current_balance"] / row["credit_limit"] if row["credit_limit"] > 0 else 0,
        axis=1
    )

    st.dataframe(
        display_cards[
            [
                "card_name",
                "current_balance",
                "statement_balance",
                "credit_limit",
                "utilization",
                "payment_due_date",
                "minimum_payment",
            ]
        ],
        use_container_width=True
    )

    if utilization >= 0.30:
        st.warning("Your credit utilization is above 30%. Consider paying cards down if credit score matters right now.")
    elif utilization >= 0.10:
        st.info("Your utilization is moderate. Under 10% is usually better for credit score optimization.")
    else:
        st.success("Your credit utilization is low.")

# -----------------------------
# Fixed vs Variable Spending
# -----------------------------

st.header("Fixed vs Variable Spending")

fixed_amount = monthly_subscriptions + monthly_goals + total_minimum_payment
variable_spending = total_spent - fixed_amount

fv1, fv2, fv3 = st.columns(3)
fv1.metric("Fixed Monthly Obligations", f"${fixed_amount:,.2f}")
fv2.metric("Variable Spending", f"${variable_spending:,.2f}")
fv3.metric("Total Spending Tracked", f"${total_spent:,.2f}")

fixed_variable_df = pd.DataFrame({
    "Type": ["Fixed Obligations", "Variable Spending"],
    "Amount": [fixed_amount, variable_spending]
})

fig_fixed_variable = px.pie(
    fixed_variable_df,
    names="Type",
    values="Amount",
    title="Fixed vs Variable Spending"
)

st.plotly_chart(
    fig_fixed_variable,
    use_container_width=True,
    key="fixed_vs_variable_chart"
)

if variable_spending > fixed_amount:
    st.warning("Your variable spending is higher than your fixed obligations.")
else:
    st.success("Your variable spending is currently lower than your fixed obligations.")



# -----------------------------
# Category Budgets
# -----------------------------

st.header("Category Budgets")

budget_rows = supabase.table("category_budgets").select("*").eq("active", True).execute().data
budget_df = pd.DataFrame(budget_rows)

if budget_df.empty:
    st.info("No category budgets found.")
else:
    budget_df["monthly_limit"] = pd.to_numeric(
        budget_df["monthly_limit"],
        errors="coerce"
    ).fillna(0)

    spending_by_category = df.groupby("category", dropna=False)["amount"].sum().reset_index()
    spending_by_category = spending_by_category.rename(
        columns={
            "category": "category_name",
            "amount": "spent"
        }
    )

    budget_status = budget_df.merge(
        spending_by_category,
        on="category_name",
        how="left"
    )

    budget_status["spent"] = budget_status["spent"].fillna(0)
    budget_status["remaining"] = budget_status["monthly_limit"] - budget_status["spent"]
    budget_status["used_percent"] = budget_status.apply(
        lambda row: row["spent"] / row["monthly_limit"] if row["monthly_limit"] > 0 else 0,
        axis=1
    )

    b1, b2, b3 = st.columns(3)

    b1.metric("Total Budget Limit", f"${budget_status['monthly_limit'].sum():,.2f}")
    b2.metric("Total Budget Spent", f"${budget_status['spent'].sum():,.2f}")
    b3.metric("Budget Remaining", f"${budget_status['remaining'].sum():,.2f}")

    st.subheader("Budget vs Actual")

    st.dataframe(
        budget_status[
            [
                "category_name",
                "monthly_limit",
                "spent",
                "remaining",
                "used_percent"
            ]
        ],
        use_container_width=True
    )

    fig_budget = px.bar(
        budget_status,
        x="category_name",
        y=["monthly_limit", "spent"],
        barmode="group",
        title="Budget vs Actual Spending"
    )

    st.plotly_chart(
        fig_budget,
        use_container_width=True,
        key="category_budget_chart"
    )

    over_budget = budget_status[budget_status["remaining"] < 0]

    if not over_budget.empty:
        st.warning("Some categories are over budget.")
        st.dataframe(
            over_budget[["category_name", "monthly_limit", "spent", "remaining"]],
            use_container_width=True
        )
    else:
        st.success("All tracked categories are within budget.")

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
    extra_needed = required_payment - fixed_payment

    l1, l2, l3, l4, l5 = st.columns(5)

    l1.metric("Current Loan Balance", f"${loan_balance:,.2f}")
    l2.metric("Required Monthly Payment", f"${required_payment:,.2f}")
    l3.metric("Your Planned Payment", f"${fixed_payment:,.2f}")

    if extra_needed > 0:
        l4.metric("Extra Needed / Month", f"${extra_needed:,.2f}")
    else:
        l4.metric("Ahead by / Month", f"${abs(extra_needed):,.2f}")

    l5.metric("Projected Payoff Date", projected_payoff_date.strftime("%b %Y"))

    if fixed_payment >= required_payment:
        st.success("You are on track to finish by your target payoff date.")
    else:
        st.warning("You are behind your target payoff pace. Increase monthly payment to finish by the target date.")

    st.caption(
        f"Target payoff date: {target_date.strftime('%b %Y')} | Months left: {months_left}"
    )

# -----------------------------
# Spending Charts
# -----------------------------

st.header("Spending Analysis")

st.subheader("Spending by Category")
category = df.groupby("category", dropna=False)["amount"].sum().reset_index()
fig = px.bar(category, x="category", y="amount")

st.plotly_chart(
    fig,
    use_container_width=True,
    key="spending_by_category_chart"
)

st.subheader("Spending Over Time")
daily = df.groupby("date")["amount"].sum().reset_index()
fig2 = px.line(daily, x="date", y="amount")

st.plotly_chart(
    fig2,
    use_container_width=True,
    key="spending_over_time_chart"
)

st.subheader("Transactions")
st.dataframe(df.sort_values("date", ascending=False), use_container_width=True)
