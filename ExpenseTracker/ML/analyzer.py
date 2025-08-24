# analyzer.py
# Produces a single dark, animated dashboard: Transactions (gradient bars),
# Forecast (neon glow line + confidence), and Spending Breakdown (pie).
# Safe legend handling (no duplicates) and cache-busting on open.

import os
import argparse
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from prophet import Prophet
import webbrowser

# ---------- CLI ----------
parser = argparse.ArgumentParser()
parser.add_argument("--open", action="store_true", help="Open the generated HTML in the default browser")
parser.add_argument("--out", default="trend.html", help="Output HTML file name")
args = parser.parse_args()

# ---------- Load Data ----------
csv_path = "expenses.csv"
if not os.path.exists(csv_path):
    print("No expenses.csv found. Export from the app first.")
    raise SystemExit(1)

data = pd.read_csv(csv_path, parse_dates=["Date"])
if data.empty:
    print("No expense data found. Please add some expenses.")
    raise SystemExit(0)

# Clean & sort
data["Date"] = pd.to_datetime(data["Date"])
data = data.sort_values("Date")

# ---------- DAILY AGG FOR FORECAST ----------
daily_expenses = (
    data.groupby("Date", as_index=False)["Amount"]
        .sum()
        .rename(columns={"Date": "ds", "Amount": "y"})
)

# ---------- Transactions (Bar, gradient, single legend) ----------
# Use continuous color by Amount to avoid one legend per description
fig_transactions = px.bar(
    data,
    x="Date",
    y="Amount",
    color="Amount",                # continuous -> one legend ramp, not many items
    color_continuous_scale="Electric",
    labels={"Amount": "Amount", "Date": "Date"},
)
# Rich hover with description
fig_transactions.update_traces(
    hovertemplate="<b>%{customdata}</b><br>Amount: ₹%{y:.2f}<br>Date: %{x|%d %b %Y}",
    customdata=data[["Description"]],
    marker_line=dict(color="rgba(255,255,255,0.6)", width=1.2),
    opacity=0.95,
    name="Transactions",           # single legend entry title
    legendgroup="transactions",
    showlegend=True
)
fig_transactions.update_layout(coloraxis_showscale=True, bargap=0.25)

# ---------- Forecast (Neon glow + CI) ----------
have_forecast = len(daily_expenses) >= 2
forecast = None
if have_forecast:
    model = Prophet()
    model.fit(daily_expenses)
    future = model.make_future_dataframe(periods=30)
    forecast = model.predict(future)

# Build with graph_objects for glow
fig_forecast = go.Figure()
if have_forecast:
    # Confidence band
    fig_forecast.add_trace(go.Scatter(
        x=forecast["ds"], y=forecast["yhat_upper"],
        mode="lines",
        line=dict(width=0),
        name="Upper",
        showlegend=False
    ))
    fig_forecast.add_trace(go.Scatter(
        x=forecast["ds"], y=forecast["yhat_lower"],
        mode="lines",
        fill="tonexty",
        fillcolor="rgba(0, 191, 255, 0.18)",
        line=dict(width=0),
        name="Confidence",
        showlegend=True
    ))
    # Glow layer (thick, transparent)
    fig_forecast.add_trace(go.Scatter(
        x=forecast["ds"], y=forecast["yhat"],
        mode="lines",
        line=dict(color="rgba(0,191,255,0.25)", width=16),
        name="",
        hoverinfo="skip",
        showlegend=False
    ))
    # Main neon line
    fig_forecast.add_trace(go.Scatter(
        x=forecast["ds"], y=forecast["yhat"],
        mode="lines+markers",
        line=dict(color="deepskyblue", width=4),
        marker=dict(size=7, color="white", line=dict(width=2, color="deepskyblue")),
        name="Forecast",
        hovertemplate="Predicted: ₹%{y:.2f}<br>Date: %{x|%d %b %Y}",
        legendgroup="forecast",
        showlegend=True
    ))
    # Actual points
    fig_forecast.add_trace(go.Scatter(
        x=daily_expenses["ds"], y=daily_expenses["y"],
        mode="markers",
        marker=dict(size=7, color="#9EEAF9", line=dict(width=0)),
        name="Actual",
        hovertemplate="Actual: ₹%{y:.2f}<br>Date: %{x|%d %b %Y}",
        legendgroup="forecast",
        showlegend=True
    ))
else:
    fig_forecast.add_annotation(text="Not enough distinct dates for forecasting.",
                                showarrow=False, font=dict(size=14))

# ---------- Category/Item Breakdown (Pie, no legend) ----------
category_totals = data.groupby("Description", as_index=True)["Amount"].sum().sort_values(ascending=False)
fig_category = go.Figure(go.Pie(
    labels=category_totals.index,
    values=category_totals.values,
    hole=0.45,
    textinfo="label+percent",
    marker=dict(line=dict(color="black", width=2)),
    pull=[0.06] * len(category_totals),
    showlegend=False  # prevents duplicate labels in the overall legend
))

# ---------- Combine Layout ----------
fig = make_subplots(
    rows=3, cols=1,
    subplot_titles=("All Transactions", "Forecasted Expenses", "Spending Breakdown"),
    specs=[
        [{"type": "xy"}],
        [{"type": "xy"}],
        [{"type": "domain"}]
    ],
    vertical_spacing=0.12
)

# row 1
for tr in fig_transactions.data:
    fig.add_trace(tr, row=1, col=1)

# row 2
for tr in fig_forecast.data:
    fig.add_trace(tr, row=2, col=1)

# row 3
for tr in fig_category.data:
    fig.add_trace(tr, row=3, col=1)

# ---------- Styling (dark, glossy-ish, smooth) ----------
fig.update_layout(
    title="Expense Analyzer Dashboard",
    template="plotly_dark",
    paper_bgcolor="rgba(10,10,24,1)",
    plot_bgcolor="rgba(20,20,40,1)",
    font=dict(size=14, color="white"),
    height=1200,
    transition_duration=600,
    hovermode="x unified",
    legend=dict(
        bgcolor="rgba(0,0,0,0.55)",
        bordercolor="rgba(255,255,255,0.25)",
        borderwidth=1
    )
)

# Axes polish
for rid in [1, 2]:
    fig.update_xaxes(
        row=rid, col=1,
        showgrid=True, gridwidth=0.3, gridcolor="rgba(255,255,255,0.08)",
        zeroline=False
    )
    fig.update_yaxes(
        row=rid, col=1,
        showgrid=True, gridwidth=0.3, gridcolor="rgba(255,255,255,0.08)"
    )

# Range slider on transactions
fig.update_xaxes(rangeslider=dict(visible=True), row=1, col=1)

# ---------- Write HTML (cache-bust) ----------
out_path = os.path.abspath(args.out)
fig.write_html(out_path, include_plotlyjs="cdn", auto_open=False)

print(f"Analysis complete: {out_path}")

# Optional open with a cache-busting query to avoid stale browser cache
if args.open:
    bust = f"?v={pd.Timestamp.now().timestamp()}"
    webbrowser.open("file://" + out_path + bust)
