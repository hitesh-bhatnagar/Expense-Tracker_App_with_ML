import pandas as pd
import plotly.express as px
from prophet import Prophet
import webbrowser
import os

# -----------------------------
# Load Data
# -----------------------------
csv_path = "expenses.csv"
data = pd.read_csv(csv_path, parse_dates=["Date"])

if data.empty:
    print(" No expense data found. Please add some expenses.")
    exit()

# -----------------------------
# Raw Transaction Chart
# -----------------------------
fig_transactions = px.bar(
    data,
    x="Date",
    y="Amount",
    color="Description",
    title=" All Transactions",
    labels={"Amount": "Expense Amount", "Date": "Transaction Date"},
    hover_data=["Description"],
)
fig_transactions.update_layout(bargap=0.3)

# -----------------------------
# Aggregate by Day for Forecast
# -----------------------------
daily_expenses = data.groupby("Date", as_index=False)["Amount"].sum()
daily_expenses = daily_expenses.rename(columns={"Date": "ds", "Amount": "y"})

if len(daily_expenses) < 2:
    print(" Not enough data for forecasting. Add more expenses on different dates.")
    # Save just the transactions chart
    out_path = os.path.abspath("trend.html")
    fig_transactions.write_html(out_path)
    webbrowser.open("file://" + out_path)
    exit()

# -----------------------------
# Prophet Forecast
# -----------------------------
model = Prophet()
model.fit(daily_expenses)

future = model.make_future_dataframe(periods=30)  # forecast next 30 days
forecast = model.predict(future)

fig_forecast = px.line(
    forecast,
    x="ds",
    y="yhat",
    title=" Forecast: Next 30 Days of Expenses",
    labels={"ds": "Date", "yhat": "Predicted Expense"},
)
fig_forecast.add_scatter(
    x=daily_expenses["ds"],
    y=daily_expenses["y"],
    mode="markers",
    name="Actual",
)

# -----------------------------
# Category / Item Analysis
# -----------------------------
fig_category = px.pie(
    data,
    names="Description",
    values="Amount",
    title=" Spending by Category/Item",
)

# -----------------------------
# Combine & Save Dashboard
# -----------------------------
from plotly.subplots import make_subplots
import plotly.graph_objects as go

fig_combined = make_subplots(
    rows=3, cols=1,
    subplot_titles=("All Transactions", "Forecasted Expenses", "Spending Breakdown"),
    vertical_spacing=0.15,
    specs=[
        [{"type": "xy"}],      # row 1: bar chart
        [{"type": "xy"}],      # row 2: forecast line chart
        [{"type": "domain"}]   # row 3: pie chart needs domain
    ]
)

# Add transactions chart (bar)
for trace in fig_transactions.data:
    fig_combined.add_trace(trace, row=1, col=1)

# Add forecast chart (line + scatter)
for trace in fig_forecast.data:
    fig_combined.add_trace(trace, row=2, col=1)

# Add category pie
for trace in fig_category.data:
    fig_combined.add_trace(trace, row=3, col=1)

fig_combined.update_layout(height=1200, showlegend=True)

# Save to HTML
out_path = os.path.abspath("trend.html")
fig_combined.write_html(out_path)
print(f"Analysis complete! Opening {out_path}")
webbrowser.open("file://" + out_path)
