import os   
import argparse
import pandas as pd
import numpy as np
from prophet import Prophet
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import webbrowser
from datetime import timedelta

parser = argparse.ArgumentParser()
parser.add_argument("--open", action="store_true", help="Open the generated HTML in browser")
parser.add_argument("--out", default="trend.html", help="Output HTML file name")
args = parser.parse_args()

#   Helpers 
def safe_read_csv(path):
    if not os.path.exists(path):
        print("No expenses.csv found. Export from the app first.")
        raise SystemExit(1)
    df = pd.read_csv(path, parse_dates=["Date"])
    if df.empty:
        print("No expense data found. Please add some expenses.")
        raise SystemExit(0)
    return df

def money(x):
    try:
        return "₹{:,.2f}".format(x)
    except:
        return str(x)

#       Load Data
csv_path = "expenses.csv"
data = safe_read_csv(csv_path)

# ensure numeric Amount and valid Date
data["Amount"] = pd.to_numeric(data["Amount"], errors="coerce")
data = data.dropna(subset=["Amount", "Date"]).copy()
if "Description" not in data.columns:
    data["Description"] = "Other"
data["Description"] = data["Description"].fillna("Other").astype(str)
data["Date"] = pd.to_datetime(data["Date"])
data = data.sort_values("Date")

# Quick key performance indicators
total_spend = data["Amount"].sum()
first_date = data["Date"].min()
last_date = data["Date"].max()
days_span = max(1, (last_date - first_date).days + 1)
avg_per_day = total_spend / days_span
top_cat = data.groupby("Description")["Amount"].sum().sort_values(ascending=False)
top1 = top_cat.index[0] if not top_cat.empty else "N/A"
top1_amount = top_cat.iloc[0] if not top_cat.empty else 0.0

# Aggregate for bar chart: top categories + Others 
cat_sums = data.groupby("Description", as_index=True)["Amount"].sum().sort_values(ascending=False)


#   choose top N categories to show separately
TOP_N = 6
top_categories = list(cat_sums.index[:TOP_N])
others = cat_sums.index[TOP_N:]

#  daily totals per top-category + others aggregated


data["Day"] = data["Date"].dt.normalize()
daily_cat = (data.groupby(["Day", "Description"])["Amount"]
             .sum()
             .reset_index())



pivot = daily_cat.pivot(index="Day", columns="Description", values="Amount").fillna(0)

# ensure top columns order
for c in top_categories:
    if c not in pivot.columns:
        pivot[c] = 0.0


# compute Others as sum of small categories
pivot["Others"] = pivot[[c for c in pivot.columns if c not in top_categories]].sum(axis=1)


# keep only top_categories + Others
bar_cols = top_categories + ["Others"]
pivot = pivot.reindex(columns=bar_cols).fillna(0)

#   create a daily totals series
daily_totals = pivot.sum(axis=1).rename("DailyTotal").reset_index()
daily_totals["Day"] = pd.to_datetime(daily_totals["Day"])

#   Outlier handling 
cap_pct = 0.98
if len(daily_totals) >= 1:
    cap_val = float(daily_totals["DailyTotal"].quantile(cap_pct))
    cap_top = max(cap_val * 1.5, daily_totals["DailyTotal"].max())
else:
    cap_top = daily_totals["DailyTotal"].max() if not daily_totals.empty else 0.0

#   Forecast using Prophet on daily totals 
daily_prophet = daily_totals.rename(columns={"Day": "ds", "DailyTotal": "y"}).dropna(subset=["y"])
have_forecast = len(daily_prophet) >= 2
forecast_df = None
forecast_next_30_sum = None

if have_forecast:
    m = Prophet()
    m.fit(daily_prophet)
    future = m.make_future_dataframe(periods=30)
    forecast_df = m.predict(future)
    # compute next-30-days predicted sum 
    last_known = daily_prophet["ds"].max()
    future_only = forecast_df[forecast_df["ds"] > last_known]
    forecast_next_30_sum = float(future_only["yhat"].sum())

#   Build figures 
#        Transactions: stacked bar for top categories + Others, and small scatter for raw transactions
transactions_fig = go.Figure()
colors = ["#2EC4B6", "#3D8DF0", "#8E44AD", "#FF7A59", "#FFC857", "#6D9886", "#999999"]  

for i, col in enumerate(bar_cols):
    transactions_fig.add_trace(go.Bar(
        x=pivot.index,
        y=pivot[col],
        name=col if col != "Others" else "Others (small categories)",
        marker=dict(color=colors[i % len(colors)], line=dict(width=0.3, color="rgba(255,255,255,0.06)")),
        hovertemplate="Day: %{x|%d %b %Y}<br>Category: " + str(col) + "<br>Amount: ₹%{y:.2f}<extra></extra>",
    ))


np.random.seed(2)
jitter = (np.random.rand(len(data)) - 0.5) * 0.6  
txn_x = data["Date"] + pd.to_timedelta(jitter, unit="D")
transactions_fig.add_trace(go.Scatter(
    x=txn_x,
    y=data["Amount"],
    mode="markers",
    marker=dict(size=6, color="rgba(255,255,255,0.65)", line=dict(width=0.3, color="rgba(0,0,0,0.1)")),
    name="Transactions (individual)",
    hovertemplate="<b>%{text}</b><br>Amount: ₹%{y:.2f}<br>Date: %{x|%d %b %Y}<extra></extra>",
    text=data["Description"]
))

#   outlier annotation: if daily total > cap_top show marker/annotation

outlier_days = daily_totals[daily_totals["DailyTotal"] > cap_top]
if not outlier_days.empty:
    transactions_fig.add_trace(go.Scatter(
        x=outlier_days["Day"],
        y=outlier_days["DailyTotal"],
        mode="markers+text",
        marker=dict(size=12, color="gold"),
        text=[f"Outlier: {money(v)}" for v in outlier_days["DailyTotal"]],
        textposition="top center",
        name="Outliers",
        hovertemplate="Day: %{x|%d %b %Y}<br>Daily total: ₹%{y:.2f}<extra></extra>"
    ))

transactions_fig.update_layout(barmode="stack")

#   Forecast figure
forecast_fig = go.Figure()
if have_forecast:
    forecast_fig.add_trace(go.Scatter(x=forecast_df["ds"], y=forecast_df["yhat_upper"], mode="lines", line=dict(width=0), showlegend=False))
    forecast_fig.add_trace(go.Scatter(x=forecast_df["ds"], y=forecast_df["yhat_lower"], mode="lines", fill="tonexty", fillcolor="rgba(14,165,233,0.12)", line=dict(width=0), name="Confidence"))
    forecast_fig.add_trace(go.Scatter(x=forecast_df["ds"], y=forecast_df["yhat"], mode="lines", line=dict(color="#0ea5e9", width=3), name="Forecast"))
    forecast_fig.add_trace(go.Scatter(x=daily_prophet["ds"], y=daily_prophet["y"], mode="markers", marker=dict(size=6, color="#9EEAF9"), name="Actual"))

#  Pie chart

# Limit pie to top 8 labels, group the rest in Others 
pie_labels = list(cat_sums.index[:TOP_N]) + (["Others (other categories)"] if len(cat_sums) > TOP_N else [])
pie_values = [cat_sums.get(l, 0.0) for l in pie_labels]



if "Others" in pivot.columns:
   
    others_val = cat_sums[~cat_sums.index.isin(top_categories)].sum()
    if others_val > 0 and len(cat_sums) > TOP_N:
        pie_values = [cat_sums.get(l, 0.0) for l in top_categories] + [others_val]

pie_fig = go.Figure(go.Pie(labels=pie_labels, values=pie_values, hole=0.45, textinfo="percent+label",
                           insidetextorientation="radial", marker=dict(line=dict(color="rgba(255,255,255,0.25)", width=0.8))))

#Cosmetic layout & KPI HTML assembly 

kpis = {
    "Total Spend": money(total_spend),
    "Avg / day": money(avg_per_day),
    "Top category": f"{top1} ({money(top1_amount)})" if top1 != "N/A" else "N/A",
    "Forecast next 30d": money(forecast_next_30_sum) if forecast_next_30_sum is not None else "N/A"
}

common_layout = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(14,14,30,1)",
    plot_bgcolor="rgba(18,18,40,0.94)",
    font=dict(color="white", family="Segoe UI, Roboto, Arial"),
    margin=dict(t=60, b=40, l=60, r=30)
)

transactions_fig.update_layout(
    title="All Transactions (stacked by top categories)",
    xaxis=dict(title="Date"),
    yaxis=dict(title="Amount (₹)"),
    hovermode="x unified",
    **common_layout
)


if cap_top > 0:
    transactions_fig.update_yaxes(range=[0, cap_top * 1.05])

forecast_fig.update_layout(title="Forecasted Expenses (next 30 days)", xaxis=dict(title="Date"), yaxis=dict(title="Amount (₹)"), hovermode="x unified", **common_layout)
pie_fig.update_layout(title="Spending Breakdown (top categories)", **common_layout)

transactions_div = transactions_fig.to_html(full_html=False, include_plotlyjs="cdn", default_height=350)
forecast_div = forecast_fig.to_html(full_html=False, include_plotlyjs=False, default_height=420)
pie_div = pie_fig.to_html(full_html=False, include_plotlyjs=False, default_height=300)


#                            Compose final HTML 

html_template = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Expense Analyzer</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    /* Dark, clean UI */
    body {{
      margin: 0;
      background: linear-gradient(180deg, #0f1226 0%, #0b0d18 100%);
      color: #dbeafe;
      font-family: "Segoe UI", Roboto, Arial, sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    .container {{ max-width: 1200px; margin: 20px auto; padding: 20px; }}
    header {{ display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:18px; }}
    .title {{ font-size:20px; font-weight:600; color:#e6eef8; display:flex; align-items:center; gap:10px; }}
    .kpi-row {{ display:flex; gap:12px; flex-wrap:wrap; }}
    .kpi {{
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.03);
      padding: 12px 16px;
      border-radius: 10px;
      min-width: 180px;
      box-shadow: 0 6px 18px rgba(2,6,23,0.6);
    }}
    .kpi .label {{ font-size:12px; color:#98a8c7; }}
    .kpi .value {{ font-size:18px; font-weight:700; margin-top:4px; color:#ffffff; }}
    .charts {{ display:block; margin-top:18px; }}
    .chart-row {{ margin-bottom:18px; background: rgba(255,255,255,0.02); padding:10px; border-radius:10px; }}
    footer {{ margin-top:18px; color:#9aa7c7; font-size:13px; text-align:center; }}
    .btns {{ display:flex; gap:8px; }}
    .hint {{ font-size:13px; color:#9aa7c7; margin-top:8px; }}
    @media (max-width: 880px) {{
      .container {{ padding:10px; }}
      .kpi {{ min-width: 140px; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title">Expense Analyzer — dashboard</div>
      <div class="btns">
        <button onclick="downloadPNG('transactions')">Download Transactions PNG</button>
        <button onclick="downloadPNG('forecast')">Download Forecast PNG</button>
        <button onclick="downloadPNG('pie')">Download Breakdown PNG</button>
      </div>
    </header>

    <div class="kpi-row">
      <div class="kpi"><div class="label">Total Spend</div><div class="value">{kpis['Total Spend']}</div></div>
      <div class="kpi"><div class="label">Average / day</div><div class="value">{kpis['Avg / day']}</div></div>
      <div class="kpi"><div class="label">Top category</div><div class="value">{kpis['Top category']}</div></div>
      <div class="kpi"><div class="label">Forecast (30d)</div><div class="value">{kpis['Forecast next 30d']}</div></div>
    </div>

    <div class="charts">
      <div class="chart-row" id="transactions">{transactions_div}</div>
      <div class="chart-row" id="forecast">{forecast_div}</div>
      <div class="chart-row" id="pie">{pie_div}</div>
      <div class="hint">Tip: click a slice in the Spending Breakdown to isolate that category in the Transactions chart.</div>
    </div>

    <footer>Generated by ExpenseTracker · {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</footer>
  </div>

  <!-- JS: Plotly is loaded via CDN in transactions_div; use Plotly.* for actions -->
  <script>
    // Helper to download PNG of a specific div's plotly graph
    function downloadPNG(which) {{
      let el;
      if (which === 'transactions') el = document.querySelector('#transactions .plotly-graph-div');
      else if (which === 'forecast') el = document.querySelector('#forecast .plotly-graph-div');
      else el = document.querySelector('#pie .plotly-graph-div');
      if (!el) return alert('Chart not found');
      Plotly.toImage(el, {{format:'png', width:1200, height:600}}).then(function(uri) {{
        var link = document.createElement('a');
        link.href = uri;
        link.download = which + '.png';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }});
    }}

    // When user clicks on a pie slice, isolate the corresponding bar trace(s)
    document.addEventListener('DOMContentLoaded', function() {{
      try {{
        let pieDiv = document.querySelector('#pie .plotly-graph-div');
        let txDiv = document.querySelector('#transactions .plotly-graph-div');
        if (!pieDiv || !txDiv) return;

        pieDiv.on('plotly_click', function(data) {{
          // clicked label
          const label = data.points[0].label;
          // Map labels to bar traces by name
          let barTraces = txDiv.data.filter(d => d.type === 'bar');
          // compute visibility array: only show traces whose name matches label OR show all when label == 'Others'
          let update = {{visible: []}};
          for (let i = 0; i < barTraces.length; i++) {{
            let name = barTraces[i].name;
            if (label === 'Others (other categories)') {{
              // show Others trace only
              update.visible.push(name.toLowerCase().includes('others') ? true : 'legendonly');
            }} else {{
              update.visible.push(name === label ? true : 'legendonly');
            }}
          }}
          // apply
          Plotly.restyle(txDiv, update);
        }});

        // allow double-click on pie area to restore all (double click triggers 'plotly_doubleclick')
        pieDiv.on('plotly_doubleclick', function() {{
          // make all traces visible
          let barTraces = txDiv.data.filter(d => d.type === 'bar');
          let update = {{visible: []}};
          for (let i = 0; i < barTraces.length; i++) update.visible.push(true);
          Plotly.restyle(txDiv, update);
        }});
      }} catch (e) {{
        console.warn('JS isolation wiring failed:', e);
      }}
    }});
  </script>
</body>
</html>
"""



out_path = os.path.abspath(args.out)
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html_template)

print("Dashboard written to:", out_path)

if args.open:

    webbrowser.open("file://" + out_path + "?v=" + str(pd.Timestamp.now().timestamp()))
