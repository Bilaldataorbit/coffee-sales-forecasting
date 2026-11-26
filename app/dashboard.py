"""Coffee Sales Forecasting dashboard (Streamlit).

Run from the repo root:  streamlit run app/dashboard.py
Needs the data and the tables made by notebooks 01-05.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "Coffe_sales.csv"
DAILY = ROOT / "data" / "processed" / "daily_sales.csv"
TAB = ROOT / "outputs" / "tables"

BROWN, RED, GREEN, GREY, BLUE = "#6F4E37", "#C1272D", "#2A7F62", "#9AA0A6", "#3B6EA5"
WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
RECENT_DAYS = 49   # last 7 full weeks, after the jump in volume (starts Mon 3 Feb 2025)

st.set_page_config(page_title="Coffee Sales Forecasting", page_icon="☕", layout="wide")


# ---------- data ----------
@st.cache_data
def load_raw() -> pd.DataFrame:
    df = pd.read_csv(RAW, parse_dates=["Date"])
    df["Weekday"] = pd.Categorical(df["Date"].dt.strftime("%a"), categories=WEEK, ordered=True)
    return df


@st.cache_data
def load_daily(df: pd.DataFrame) -> pd.DataFrame:
    if DAILY.exists():
        d = pd.read_csv(DAILY, parse_dates=["date"], index_col="date")
    else:  # rebuild if notebook 01 has not been run
        cal = pd.date_range(df["Date"].min(), df["Date"].max())
        g = df.groupby("Date").agg(revenue=("money", "sum"), transactions=("money", "size")).reindex(cal)
        d = g.rename_axis("date")
        d["reported"] = d["transactions"].notna()
        d = d.fillna({"revenue": 0, "transactions": 0})
        d["revenue_ma7"] = d["revenue"].where(d["reported"]).rolling(7, min_periods=4).mean()
    d["weekday"] = pd.Categorical(d.index.strftime("%a"), categories=WEEK, ordered=True)
    return d


def read_table(name: str, **kw):
    p = TAB / name
    return pd.read_csv(p, **kw) if p.exists() else None


def need(df, what: str):
    if df is None:
        st.info(f"{what} not found. Run notebooks 01 to 05 first, then reload this page.")
        return False
    return True


if not RAW.exists():
    st.error(f"Data file not found: {RAW}. Put Coffe_sales.csv in data/raw/.")
    st.stop()

df, daily = load_raw(), load_daily(load_raw())
LAST = df["Date"].max()

# ---------- header and sidebar ----------
st.title("☕ Coffee Sales Forecasting")
st.caption(
    f"Data: {df['Date'].min():%d %b %Y} to {LAST:%d %b %Y} · {len(df):,} card transactions · "
    "**Historical exercise**: the forecast window lies in the past, so this is not a live forecast. "
    "Currency is not stated in the data."
)

with st.sidebar:
    st.header("Filters")
    d0, d1 = st.date_input("Date range", (daily.index.min().date(), daily.index.max().date()),
                           min_value=daily.index.min().date(), max_value=daily.index.max().date())
    products = sorted(df["coffee_name"].unique())
    sel_products = st.multiselect("Products", products, default=products)
    st.markdown("---")
    st.caption("Filters apply to Overview and Patterns. Forecast, Backtest and Recommendations use the full data.")

mask = (df["Date"].dt.date >= d0) & (df["Date"].dt.date <= d1) & df["coffee_name"].isin(sel_products)
dff = df[mask]
# Daily table that follows the product filter (shop days with no sale of the chosen product count as 0)
dsel = daily
if set(sel_products) != set(products):
    per_day = df[df["coffee_name"].isin(sel_products)].groupby("Date").agg(
        revenue=("money", "sum"), transactions=("money", "size"))
    dsel = daily.copy()
    dsel["revenue"] = per_day["revenue"].reindex(dsel.index).fillna(0)
    dsel["transactions"] = per_day["transactions"].reindex(dsel.index).fillna(0)
    dsel["revenue_ma7"] = dsel["revenue"].where(dsel["reported"]).rolling(7, min_periods=4).mean()
dd = dsel.loc[str(d0):str(d1)]

tab_over, tab_pat, tab_fc, tab_bt, tab_rec = st.tabs(
    ["Overview", "Patterns", "Forecast", "Backtest", "Recommendations"])

# ---------- Overview ----------
with tab_over:
    rep = dd[dd["reported"]]
    c = st.columns(4)
    c[0].metric("Total revenue", f"{dff['money'].sum():,.0f}")
    c[1].metric("Transactions", f"{len(dff):,}")
    c[2].metric("Avg revenue per day with sales", f"{(dff['money'].sum() / max(len(rep), 1)):,.0f}")
    c[3].metric("Avg price per sale", f"{dff['money'].mean():,.2f}" if len(dff) else "-")

    fig = go.Figure()
    fig.add_scatter(x=rep.index, y=rep["revenue"], name="Daily revenue", line=dict(color="#C9B8A8", width=1))
    fig.add_scatter(x=dd.index, y=dd["revenue_ma7"], name="7-day average", line=dict(color=BROWN, width=3))
    gaps = dd[~dd["reported"]]
    if len(gaps):
        fig.add_scatter(x=gaps.index, y=[0] * len(gaps), mode="markers", name="No data that day",
                        marker=dict(color=RED, size=8, symbol="x"))
    fig.update_layout(title="Daily revenue", height=380, margin=dict(t=50, b=10), legend=dict(orientation="h", y=-0.15),
                      yaxis_title="Revenue per day")
    st.plotly_chart(fig, width="stretch")

    wk = rep.resample("W-SUN").agg(avg_revenue=("revenue", "mean"), avg_transactions=("transactions", "mean"))
    f2 = go.Figure()
    f2.add_scatter(x=wk.index, y=wk["avg_revenue"], name="Revenue per day", line=dict(color=BROWN, width=3))
    f2.add_scatter(x=wk.index, y=wk["avg_transactions"], name="Sales per day", line=dict(color=RED, width=3), yaxis="y2")
    f2.update_layout(title="Weekly averages: revenue and number of sales", height=330, margin=dict(t=50, b=10),
                     yaxis=dict(title="Revenue per day"), yaxis2=dict(title="Sales per day", overlaying="y", side="right"),
                     legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(f2, width="stretch")
    st.caption("Early 2025 shows a large jump. It comes from more sales per day, not from higher prices. "
               "The data cannot say why, so forecasts must be tested on recent days.")

# ---------- Patterns ----------
with tab_pat:
    scope = st.radio("Period for weekday and hour charts", ["Selected date range", "Last 7 weeks"], horizontal=True)
    base = dff if scope == "Selected date range" else df[(df["Date"] > LAST - pd.Timedelta(days=RECENT_DAYS))
                                                          & df["coffee_name"].isin(sel_products)]
    if base.empty:
        st.warning("No sales for this selection.")
    else:
        # Count every shop day (any product sold), so a day without the chosen product counts as zero
        if scope == "Selected date range":
            days_all = df[(df["Date"].dt.date >= d0) & (df["Date"].dt.date <= d1)]
        else:
            days_all = df[df["Date"] > LAST - pd.Timedelta(days=RECENT_DAYS)]
        n_days = days_all.groupby("Weekday", observed=True)["Date"].nunique().reindex(WEEK)
        col1, col2 = st.columns(2)
        wk_rev = (base.groupby("Weekday", observed=True)["money"].sum().reindex(WEEK) / n_days)
        col1.plotly_chart(px.bar(x=WEEK, y=wk_rev.values, title="Average revenue by weekday",
                                 labels={"x": "", "y": "Revenue per day"}, color_discrete_sequence=[BROWN]), width="stretch")
        hr = base.groupby("hour_of_day")["money"].sum()
        col2.plotly_chart(px.bar(x=hr.index, y=hr.values, title="Revenue by hour",
                                 labels={"x": "Hour", "y": "Revenue"}, color_discrete_sequence=[BROWN]), width="stretch")

        heat = base.pivot_table(index="Weekday", columns="hour_of_day", values="money", aggfunc="size",
                                fill_value=0, observed=False).reindex(WEEK)
        heat = heat.div(n_days, axis=0)
        st.plotly_chart(px.imshow(heat.round(1), text_auto=".1f", aspect="auto", color_continuous_scale="YlOrBr",
                                  title="Average cups per hour, by weekday", labels=dict(x="Hour", y="", color="Cups")),
                        width="stretch")

        col3, col4 = st.columns(2)
        prod = base.groupby("coffee_name")["money"].sum().sort_values()
        col3.plotly_chart(px.bar(x=prod.values, y=prod.index, orientation="h", title="Revenue by product",
                                 labels={"x": "Revenue", "y": ""}, color_discrete_sequence=[BROWN]), width="stretch")
        tod = base.pivot_table(index="coffee_name", columns="Time_of_Day", values="money", aggfunc="sum", fill_value=0)
        tod = tod.reindex(columns=[c_ for c_ in ["Morning", "Afternoon", "Night"] if c_ in tod.columns])
        tod = tod.div(tod.sum())
        col4.plotly_chart(px.imshow(tod.mul(100).round(0), text_auto=".0f", aspect="auto", color_continuous_scale="YlOrBr",
                                    title="Share of each period's revenue (%)", labels=dict(x="", y="", color="%")),
                          width="stretch")

# ---------- Forecast ----------
with tab_fc:
    fut = read_table("forecast_next_30_days_all_models.csv", parse_dates=["date"], index_col="date")
    if need(fut, "Forecast table (notebook 04)"):
        st.write("Each method forecasts the next 30 days from the full history. The range between good methods "
                 "shows how uncertain the forecast is.")
        methods = [m for m in fut.columns if m != "naive_last"]
        default = [m for m in ["combo", "HW_no_trend", "ARIMA_011", "weekday_avg_4w", "mean_7d"] if m in methods]
        chosen = st.multiselect("Methods to show", methods, default=default)
        hist_days = st.slider("Days of history to show", 30, 200, 90)
        hist = daily[daily["reported"]].iloc[-hist_days:]

        fig = go.Figure()
        if chosen:
            lo, hi = fut[chosen].min(axis=1), fut[chosen].max(axis=1)
            fig.add_scatter(x=list(fut.index) + list(fut.index[::-1]), y=list(hi) + list(lo[::-1]), fill="toself",
                            fillcolor="rgba(193,39,45,0.12)", line=dict(width=0), name="Range of chosen methods", hoverinfo="skip")
        fig.add_scatter(x=hist.index, y=hist["revenue"], name="Actual", line=dict(color="black", width=2))
        palette = [RED, GREEN, BLUE, BROWN, GREY, "#B5651D", "#7B4FA3"]
        for m, colr in zip(chosen, palette * 2):
            fig.add_scatter(x=fut.index, y=fut[m], name=m, line=dict(color=colr, width=2, dash="dash"))
        fig.update_layout(height=430, title="Actual revenue and 30-day forecasts", yaxis_title="Revenue per day",
                          margin=dict(t=50, b=10), legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, width="stretch")

        last30 = daily["revenue"].iloc[-30:].sum()
        tot = fut[methods].sum().rename("30-day total").to_frame()
        tot["vs last 30 days"] = tot["30-day total"] / last30 - 1
        c = st.columns(3)
        c[0].metric("Last 30 days (actual)", f"{last30:,.0f}")
        c[1].metric("Forecast range, all methods", f"{tot['30-day total'].min():,.0f} to {tot['30-day total'].max():,.0f}")
        c[2].metric("Combo (average of 3 forecasts)", f"{tot.loc['combo', '30-day total']:,.0f}" if "combo" in tot.index else "-")
        st.dataframe(tot.style.format({"30-day total": "{:,.0f}", "vs last 30 days": "{:+.0%}"}), width="stretch")
        st.caption("Forecast window: 24 Mar to 22 Apr 2025, which is in the past. There are no actuals to check it "
                   "against, so the Backtest tab is the real evidence of accuracy.")

# ---------- Backtest ----------
with tab_bt:
    comp = read_table("final_model_comparison.csv", index_col=0)
    if need(comp, "Model comparison table (notebook 04)"):
        st.write("Every method was tested on **35 rolling origins**: at each start date it saw only earlier days and "
                 "forecast the next 30. Lower MAE and WAPE are better.")
        show = comp[["family", "MAE", "WAPE", "SMAPE", "Bias"]].sort_values("MAE")
        st.dataframe(show.style.format({"MAE": "{:.1f}", "WAPE": "{:.0%}", "SMAPE": "{:.0%}", "Bias": "{:+.1f}"})
                     .background_gradient(subset=["MAE"], cmap="YlOrBr_r"), width="stretch")
        fam = {"baseline": GREY, "Holt-Winters": RED, "ARIMA": BLUE, "average": GREEN}
        fig = px.bar(show.reset_index(names="model"), x="MAE", y="model", color="family", orientation="h",
                     color_discrete_map=fam, title="Average miss per day (MAE), 30-day forecasts")
        fig.update_layout(yaxis=dict(autorange="reversed"), height=420, margin=dict(t=50, b=10))
        st.plotly_chart(fig, width="stretch")

        po = read_table("per_origin_mae.csv", index_col=0, parse_dates=True)
        if po is not None:
            pick = st.multiselect("Compare MAE by start date", list(po.columns),
                                  default=[c_ for c_ in ["seasonal_naive", "mean_7d", "weekday_avg_4w", "HW_no_trend"] if c_ in po.columns])
            f2 = go.Figure()
            for m in pick:
                f2.add_scatter(x=po.index, y=po[m], name=m, mode="lines")
            f2.update_layout(title="MAE of 30-day forecasts by starting date", height=360, margin=dict(t=50, b=10),
                             yaxis_title="MAE", legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(f2, width="stretch")
        st.warning(
            "Reading this: Holt-Winters, ARIMA and the combination are about 16-17% better than 'same weekday last week' "
            "but only 2-3% better than a plain 7-day average. In the last 30 days alone a weekday average wins by a wide "
            "margin, so no single window should decide the model. Daily SMAPE is inflated by very low-sales days.")

# ---------- Recommendations ----------
with tab_rec:
    pf = read_table("product_forecast.csv", index_col=0)
    guide = read_table("prep_guide.csv", index_col=0)
    slots = read_table("peak_slots.csv")
    if need(pf, "Product forecast (notebook 05)"):
        st.subheader("Product forecast, next 30 days")
        body = pf.drop("TOTAL", errors="ignore")
        fig = go.Figure(go.Bar(
            x=body["cups forecast (central)"], y=body.index, orientation="h", marker_color=BROWN,
            error_x=dict(type="data", symmetric=False,
                         array=body["cups high"] - body["cups forecast (central)"],
                         arrayminus=body["cups forecast (central)"] - body["cups low"])))
        fig.update_layout(title="Expected cups (bar = central forecast, line = range between methods)",
                          yaxis=dict(autorange="reversed"), height=380, margin=dict(t=50, b=10))
        st.plotly_chart(fig, width="stretch")
        st.caption("The product split uses each product's revenue share over the last 7 weeks. The product mix is not "
                   "stable, so treat it as a rough guide.")
        st.dataframe(pf.style.format("{:,.2f}"), width="stretch")
    if guide is not None:
        st.subheader("Daily prep guide (cups per day)")
        st.write("**Median** = a normal day. **p80** = the level reached or beaten on about 1 day in 5: prepare for this "
                 "to run out only occasionally.")
        st.dataframe(guide.style.format("{:.1f}"), width="stretch")
    if slots is not None:
        st.subheader("Busiest weekday and hour slots")
        st.dataframe(slots.style.format({"avg cups": "{:.1f}"}), width="stretch", hide_index=True)
    st.info("Based on 13 months of data with one big level jump in Feb 2025 and no stock or waste data. "
            "Use these as starting points and re-check every month.")
