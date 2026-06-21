"""
AirFlow Enterprise BI Portal - Unified Dash Application
=========================================================
A production-grade, multi-page analytics platform powered by Dash + Plotly.
ALL data sourced dynamically from warehouse/warehouse.db (Star Schema).
Zero mock data. Zero hardcoded values. Every metric from real Kaggle CSVs.

Launch:  python scripts/app.py
Access:  http://localhost:8050

Author: Senior BI Architect
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import dash
from dash import dcc, html, dash_table, Input, Output, callback
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
WH_DB = PROJECT_ROOT / "warehouse" / "warehouse.db"
ASSETS_DIR = PROJECT_ROOT / "exports" / "app" / "assets"

PLOTLY_TEMPLATE = "plotly_dark"
CHART_FONT = dict(family="Inter, Segoe UI, IBM Plex Sans, Helvetica Neue, sans-serif", color="#94a3b8", size=12)
CHART_GRID = "rgba(30,42,69,0.6)"

# Plotly modebar config: hide lasso/box select, show on hover, keep zoom/pan/reset/download
MODEBAR_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": True,
    "modeBarButtonsToRemove": ["select2d", "lasso2d"],
    "toImageButtonOptions": {"format": "png", "height": 600, "width": 1200, "scale": 2},
}

# App launch timestamp
APP_LAUNCH_TS = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Color palettes
COLORS = ["#3b82f6", "#6366f1", "#10b981", "#f59e0b", "#f43f5e",
          "#a855f7", "#06b6d4", "#14b8a6", "#ec4899", "#8b5cf6",
          "#22d3ee", "#facc15", "#fb923c", "#4ade80"]


def get_conn():
    """Return a fresh SQLite connection to the warehouse."""
    return sqlite3.connect(str(WH_DB))


def style_fig(fig, height=380):
    """Apply the unified dark theme to any Plotly figure."""
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=CHART_FONT,
        height=height,
        margin=dict(l=50, r=20, t=45, b=50),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#94a3b8")),
        xaxis=dict(gridcolor=CHART_GRID, zerolinecolor=CHART_GRID),
        yaxis=dict(gridcolor=CHART_GRID, zerolinecolor=CHART_GRID),
    )
    return fig


# ============================================================================
# DASH APP INIT
# ============================================================================

app = dash.Dash(
    __name__,
    assets_folder=str(ASSETS_DIR),
    suppress_callback_exceptions=True,
    title="AirFlow BI Portal",
    update_title="Loading...",
)
server = app.server


# ============================================================================
# REUSABLE COMPONENTS
# ============================================================================

def kpi_card(icon, label, value, subtitle, color_cls="blue"):
    """Build a single KPI metric card."""
    return html.Div(className=f"kpi-card {color_cls}", children=[
        html.Div(icon, className="kpi-icon"),
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className="kpi-value"),
        html.Div(subtitle, className="kpi-sub") if isinstance(subtitle, str)
        else html.Div(subtitle, className="kpi-sub"),
    ])


def chart_card(title, graph_id=None, children=None):
    """Wrap a Plotly graph or custom children inside a styled card."""
    inner = [html.Div(title, className="chart-card-title")]
    if children:
        inner += children if isinstance(children, list) else [children]
    elif graph_id:
        inner.append(dcc.Graph(id=graph_id, config=MODEBAR_CONFIG))
    return html.Div(className="chart-card", children=inner)


def dark_table(tid, **kwargs):
    """Styled dark-theme DataTable. Merges caller's style_data_conditional with base."""
    extra_cond = kwargs.pop("style_data_conditional", [])
    base_cond = [{"if": {"row_index": "odd"}, "backgroundColor": "#0f1629"}]
    return dash_table.DataTable(
        id=tid,
        style_table={"overflowX": "auto", "maxHeight": "500px", "overflowY": "auto"},
        style_header={
            "backgroundColor": "#0f1629", "color": "#94a3b8", "fontWeight": "600",
            "fontSize": "0.72rem", "textTransform": "uppercase", "letterSpacing": "0.06em",
            "border": "1px solid #1e2a45", "position": "sticky", "top": 0,
            "fontFamily": "Inter, Segoe UI, IBM Plex Sans, sans-serif",
        },
        style_cell={
            "backgroundColor": "#141b2d", "color": "#f1f5f9", "fontSize": "0.82rem",
            "border": "1px solid #1e2a45", "padding": "10px 12px", "textAlign": "left",
            "whiteSpace": "normal",
            "fontFamily": "Inter, Segoe UI, IBM Plex Sans, sans-serif",
        },
        style_data_conditional=base_cond + extra_cond,
        page_size=15,
        sort_action="native",
        filter_action="native",
        **kwargs,
    )


# ============================================================================
# SIDEBAR
# ============================================================================

NAV_ITEMS = [
    ("/",         "Executive Overview",  "\u2302"),
    ("/airline",  "Airline Analytics",   "\u2708"),
    ("/airport",  "Airport Analytics",   "\U0001F3E2"),
    ("/route",    "Route Intelligence",  "\u21C4"),
    ("/delay",    "Delay Analytics",     "\u23F1"),
    ("/trend",    "Trend Analytics",     "\U0001F4C8"),
    ("/quality",  "Data Quality",        "\u2714"),
]

sidebar = html.Div(id="sidebar", children=[
    html.Div(className="sidebar-brand", children=[
        html.Div("\u2708", className="sidebar-brand-icon"),
        html.Div(className="sidebar-brand-text", children=[
            html.Span("AirFlow", className="brand-name"),
            html.Span("BI Platform", className="brand-sub"),
        ]),
    ]),
    html.Nav(className="sidebar-nav", children=[
        html.Div("Analytics", className="sidebar-section-label"),
    ] + [
        dcc.Link(
            children=[html.Span(icon, className="nav-icon"), html.Span(label)],
            href=href,
            className="nav-link",
            id=f"nav-{href.strip('/') or 'home'}",
        )
        for href, label, icon in NAV_ITEMS
    ]),
    html.Div(className="sidebar-footer", children=[
        html.Div("Enterprise Analytics v9.0", className="sidebar-footer-text"),
    ]),
])


# ============================================================================
# PAGE: EXECUTIVE OVERVIEW
# ============================================================================

def page_executive():
    with get_conn() as conn:
        kpis = pd.read_sql("""
            SELECT
                COUNT(*)                                                                            AS total_flights,
                (SELECT COUNT(*) FROM dim_airline)                                                  AS total_airlines,
                (SELECT COUNT(*) FROM dim_airport)                                                  AS total_airports,
                ROUND(CAST(SUM(CASE WHEN CANCELLED=1 THEN 1 ELSE 0 END) AS FLOAT)/COUNT(*)*100, 2) AS cancel_rate,
                ROUND(CAST(SUM(CASE WHEN DIVERTED=1  THEN 1 ELSE 0 END) AS FLOAT)/COUNT(*)*100, 2) AS divert_rate,
                ROUND(AVG(DEPARTURE_DELAY), 1)                                                     AS avg_dep,
                ROUND(AVG(ARRIVAL_DELAY), 1)                                                       AS avg_arr
            FROM fact_flights
        """, conn).iloc[0]

    on_time = round(100 - kpis["cancel_rate"] - kpis["divert_rate"], 1)

    return html.Div([
        html.Div(className="page-header", children=[
            html.H1("Executive Overview", className="page-title"),
            html.P("Enterprise-wide KPIs and operational intelligence sourced from warehouse.db",
                   className="page-subtitle"),
        ]),
        # Phase G: Executive meta bar
        html.Div(className="meta-bar", children=[
            html.Div(className="meta-item", children=[
                html.Span("Warehouse:"),
                html.Span("warehouse.db", className="meta-value"),
            ]),
            html.Div(className="meta-item", children=[
                html.Span("Records Loaded:"),
                html.Span(f"{int(kpis['total_flights']):,}", className="meta-value"),
            ]),
            html.Div(className="meta-item", children=[
                html.Span("Last Refresh:"),
                html.Span(APP_LAUNCH_TS, className="meta-value"),
            ]),
            html.Span("v9.0", className="meta-badge"),
        ]),
        html.Div(className="kpi-row", children=[
            kpi_card("\u2708",  "Total Flights",     f"{int(kpis['total_flights']):,}",  "Tracked operations",  "blue"),
            kpi_card("\U0001F6E9", "Active Airlines", int(kpis["total_airlines"]),        "Carrier partners",    "purple"),
            kpi_card("\U0001F3E2", "Airport Hubs",    int(kpis["total_airports"]),         "Network nodes",       "blue"),
            kpi_card("\u2714",  "On-Time Rate",      f"{on_time}%",                       "Completed flights",   "emerald"),
            kpi_card("\u2716",  "Cancellation Rate", f"{kpis['cancel_rate']}%",            "Cancelled flights",   "rose"),
            kpi_card("\u21BA",  "Diversion Rate",    f"{kpis['divert_rate']}%",            "Diverted flights",    "amber"),
            kpi_card("\u2193",  "Avg Dep Delay",     f"{kpis['avg_dep']} min",             "Departure average",   "blue"),
            kpi_card("\u2191",  "Avg Arr Delay",     f"{kpis['avg_arr']} min",             "Arrival average",     "purple"),
        ]),
        html.Div(className="chart-row", children=[
            chart_card("Top 10 Airlines by Flight Volume", "exec-top-airlines"),
            chart_card("Top 10 Airports by Total Traffic", "exec-top-airports"),
        ]),
        html.Div(className="chart-row", children=[
            chart_card("Delay Category Overview (Delayed Flights)", "exec-delay-overview"),
            chart_card("US Airport Network Map", "exec-geo-map"),
        ]),
    ])


# ============================================================================
# PAGE: AIRLINE ANALYTICS
# ============================================================================

def page_airline():
    with get_conn() as conn:
        opts = pd.read_sql("SELECT airline_key, airline_name FROM dim_airline ORDER BY airline_name", conn)
    options = [{"label": r["airline_name"], "value": r["airline_key"]} for _, r in opts.iterrows()]

    return html.Div([
        html.Div(className="page-header", children=[
            html.H1("Airline Analytics", className="page-title"),
            html.P("Deep-dive into carrier performance, delays, and reliability", className="page-subtitle"),
        ]),
        html.Div(className="filter-bar", children=[
            html.Div(className="filter-group", children=[
                html.Label("Select Airline", className="filter-label"),
                dcc.Dropdown(id="airline-dropdown", options=options,
                             value=options[0]["value"], clearable=False,
                             className="dash-dropdown", style={"width": "340px"}),
            ]),
        ]),
        html.Div(className="kpi-row", id="airline-kpi-row"),
        html.Div(className="chart-row", children=[
            chart_card("Daily Flight Volume", "airline-daily"),
            chart_card("Departure Delay Distribution", "airline-delay-dist"),
        ]),
        html.Div(className="chart-row single", children=[
            chart_card("All Airlines - Reliability Comparison", "airline-comparison"),
        ]),
    ])


# ============================================================================
# PAGE: AIRPORT ANALYTICS
# ============================================================================

def page_airport():
    with get_conn() as conn:
        opts = pd.read_sql("""
            SELECT DISTINCT a.airport_key, a.airport_code || ' - ' || a.airport_name AS label
            FROM dim_airport a
            JOIN fact_flights f ON a.airport_key IN (f.origin_airport_key, f.dest_airport_key)
            ORDER BY label
        """, conn)
    options = [{"label": r["label"], "value": r["airport_key"]} for _, r in opts.iterrows()]

    return html.Div([
        html.Div(className="page-header", children=[
            html.H1("Airport Analytics", className="page-title"),
            html.P("Traffic volumes, delay distributions, and hub rankings", className="page-subtitle"),
        ]),
        html.Div(className="filter-bar", children=[
            html.Div(className="filter-group", children=[
                html.Label("Select Airport", className="filter-label"),
                dcc.Dropdown(id="airport-dropdown", options=options,
                             value=options[0]["value"] if options else None, clearable=False,
                             className="dash-dropdown", style={"width": "380px"}),
            ]),
        ]),
        html.Div(className="kpi-row", id="airport-kpi-row"),
        html.Div(className="chart-row", children=[
            chart_card("Departure Delay Distribution", "airport-delay-hist"),
            chart_card("Top Destination Airports from This Hub", "airport-top-dest"),
        ]),
        html.Div(className="chart-row single", children=[
            chart_card("Airport Rankings by Total Traffic (Top 25)", "airport-rankings"),
        ]),
    ])


# ============================================================================
# PAGE: ROUTE INTELLIGENCE
# ============================================================================

def page_route():
    return html.Div([
        html.Div(className="page-header", children=[
            html.H1("Route Intelligence", className="page-title"),
            html.P("Origin-destination analysis, reliability rankings, and risk assessment",
                   className="page-subtitle"),
        ]),
        html.Div(className="filter-bar", children=[
            html.Div(className="filter-group", children=[
                html.Label("Minimum Flights per Route", className="filter-label"),
                dcc.Slider(id="route-min-flights", min=5, max=100, step=5, value=20,
                           marks={i: str(i) for i in range(5, 101, 10)},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ]),
        ]),
        html.Div(className="chart-row", children=[
            chart_card("Top 20 Routes by Flight Volume", "route-top"),
            chart_card("Route Risk Matrix (Delay vs Cancellation)", "route-risk"),
        ]),
        html.Div(className="chart-row single", children=[
            chart_card("Route Reliability Rankings", children=[dark_table("route-table")]),
        ]),
    ])


# ============================================================================
# PAGE: DELAY ANALYTICS
# ============================================================================

def page_delay():
    with get_conn() as conn:
        airline_opts = pd.read_sql("SELECT airline_key, airline_name FROM dim_airline ORDER BY airline_name", conn)
    a_options = [{"label": "All Airlines", "value": "all"}] + \
                [{"label": r["airline_name"], "value": r["airline_key"]} for _, r in airline_opts.iterrows()]

    with get_conn() as conn:
        day_opts = pd.read_sql("SELECT DISTINCT date_key, full_date, day_name FROM dim_date ORDER BY date_key", conn)
    d_options = [{"label": "All Days", "value": "all"}] + \
                [{"label": f"{r['day_name']} ({r['full_date'][:10]})", "value": r["date_key"]}
                 for _, r in day_opts.iterrows()]

    return html.Div([
        html.Div(className="page-header", children=[
            html.H1("Delay Analytics", className="page-title"),
            html.P("Deep analysis of delay causes across the flight network", className="page-subtitle"),
        ]),
        html.Div(className="filter-bar", children=[
            html.Div(className="filter-group", children=[
                html.Label("Filter by Airline", className="filter-label"),
                dcc.Dropdown(id="delay-airline-filter", options=a_options, value="all", clearable=False,
                             className="dash-dropdown", style={"width": "280px"}),
            ]),
            html.Div(className="filter-group", children=[
                html.Label("Filter by Day", className="filter-label"),
                dcc.Dropdown(id="delay-day-filter", options=d_options, value="all", clearable=False,
                             className="dash-dropdown", style={"width": "260px"}),
            ]),
        ]),
        html.Div(className="chart-row", children=[
            chart_card("Delay Category Breakdown (Avg Minutes)", "delay-category"),
            chart_card("Average Delay by Airline", "delay-airline-bar"),
        ]),
        html.Div(className="chart-row", children=[
            chart_card("Weather Delay Distribution", "delay-weather-hist"),
            chart_card("Late Aircraft Delay Distribution", "delay-late-hist"),
        ]),
    ])


# ============================================================================
# PAGE: TREND ANALYTICS
# ============================================================================

def page_trend():
    return html.Div([
        html.Div(className="page-header", children=[
            html.H1("Trend Analytics", className="page-title"),
            html.P("Daily performance trends, traffic patterns, and operational analysis",
                   className="page-subtitle"),
        ]),
        html.Div(className="chart-row", children=[
            chart_card("Daily Flight Volume", "trend-flights"),
            chart_card("Daily Average Delay Trend", "trend-delay"),
        ]),
        html.Div(className="chart-row", children=[
            chart_card("Daily Cancellation Rate", "trend-cancel"),
            chart_card("Weekday vs Weekend Traffic", "trend-daytype"),
        ]),
        html.Div(className="chart-row single", children=[
            chart_card("Airline Performance Across Days", "trend-airline-daily"),
        ]),
    ])


# ============================================================================
# PAGE: ENTERPRISE DATA QUALITY COMMAND CENTER
# ============================================================================

def page_quality():
    """Enterprise Data Quality Command Center — all metrics from warehouse.db."""
    import json
    from datetime import datetime

    with get_conn() as conn:
        # ── Section 1: Core warehouse metrics ──
        total       = conn.execute("SELECT COUNT(*) FROM fact_flights").fetchone()[0]
        dim_airlines = conn.execute("SELECT COUNT(*) FROM dim_airline").fetchone()[0]
        dim_airports = conn.execute("SELECT COUNT(*) FROM dim_airport").fetchone()[0]
        dim_dates   = conn.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0]

        # ── Validation checks (12 rules, all live SQL) ──
        checks_sql = [
            ("Null Airline Keys",        total, "SELECT COUNT(*) FROM fact_flights WHERE airline_key IS NULL"),
            ("Null Origin Airport Keys", total, "SELECT COUNT(*) FROM fact_flights WHERE origin_airport_key IS NULL"),
            ("Null Dest Airport Keys",   total, "SELECT COUNT(*) FROM fact_flights WHERE dest_airport_key IS NULL"),
            ("Null Date Keys",           total, "SELECT COUNT(*) FROM fact_flights WHERE date_key IS NULL"),
            ("Orphan Airline Refs",      total, "SELECT COUNT(*) FROM fact_flights WHERE airline_key NOT IN (SELECT airline_key FROM dim_airline)"),
            ("Orphan Origin Refs",       total, "SELECT COUNT(*) FROM fact_flights WHERE origin_airport_key NOT IN (SELECT airport_key FROM dim_airport)"),
            ("Orphan Dest Refs",         total, "SELECT COUNT(*) FROM fact_flights WHERE dest_airport_key NOT IN (SELECT airport_key FROM dim_airport)"),
            ("Orphan Date Refs",         total, "SELECT COUNT(*) FROM fact_flights WHERE date_key NOT IN (SELECT date_key FROM dim_date)"),
            ("Duplicate Airline Keys",   dim_airlines, "SELECT COUNT(*) FROM (SELECT airline_key FROM dim_airline GROUP BY airline_key HAVING COUNT(*)>1)"),
            ("Duplicate Airport Keys",   dim_airports, "SELECT COUNT(*) FROM (SELECT airport_key FROM dim_airport GROUP BY airport_key HAVING COUNT(*)>1)"),
            ("Departure Delay Nulls",    total, "SELECT COUNT(*) FROM fact_flights WHERE DEPARTURE_DELAY IS NULL"),
            ("Arrival Delay Nulls",      total, "SELECT COUNT(*) FROM fact_flights WHERE ARRIVAL_DELAY IS NULL"),
        ]

        validation_results = []
        for name, checked, sql in checks_sql:
            failures = conn.execute(sql).fetchone()[0]
            status = "PASS" if failures == 0 else ("WARNING" if failures < 10 else "FAIL")
            validation_results.append({
                "rule": name,
                "records_checked": checked,
                "failures": failures,
                "status": status,
            })

        total_checks = len(validation_results)
        passed_checks = sum(1 for v in validation_results if v["status"] == "PASS")
        failed_checks = total_checks - passed_checks
        dq_score = round(100 - (failed_checks / total_checks * 100), 1)

        # ── ETL metadata ──
        has_etl_tables = False
        try:
            conn.execute("SELECT 1 FROM etl_run_history LIMIT 1")
            has_etl_tables = True
        except Exception:
            pass

        last_etl_time = None
        etl_status = "UNKNOWN"
        etl_duration = 0
        phase_data = []
        dq_trend_data = []

        if has_etl_tables:
            row = conn.execute("""
                SELECT run_timestamp, overall_status, total_duration
                FROM etl_run_history ORDER BY run_timestamp DESC LIMIT 1
            """).fetchone()
            if row:
                last_etl_time = row[0]
                etl_status = row[1]
                etl_duration = row[2]

            phase_data = conn.execute("""
                SELECT p.phase_name, p.status, p.duration_seconds, p.start_time, p.end_time
                FROM etl_phase_log p
                JOIN etl_run_history r ON p.run_id = r.run_id
                ORDER BY r.run_timestamp DESC, p.id ASC
            """).fetchall()

            dq_trend_data = conn.execute("""
                SELECT r.run_timestamp, r.dq_score, r.records_loaded
                FROM etl_run_history r
                ORDER BY r.run_timestamp ASC
            """).fetchall()

    # ── Freshness calculation ──
    freshness_label = "Unknown"
    freshness_color = "amber"
    if last_etl_time:
        try:
            etl_dt = datetime.fromisoformat(last_etl_time)
            delta = datetime.now() - etl_dt
            hours_ago = delta.total_seconds() / 3600
            if hours_ago < 24:
                freshness_label = f"{int(hours_ago)}h ago — Fresh"
                freshness_color = "emerald"
            elif hours_ago < 72:
                freshness_label = f"{int(hours_ago)}h ago — Aging"
                freshness_color = "amber"
            else:
                freshness_label = f"{int(hours_ago / 24)}d ago — Stale"
                freshness_color = "rose"
        except Exception:
            freshness_label = "Parse Error"

    # ── Pipeline health ──
    if etl_status == "SUCCESS":
        health_label = "HEALTHY"
        health_color = "emerald"
    elif etl_status == "WARNING":
        health_label = "WARNING"
        health_color = "amber"
    else:
        health_label = etl_status
        health_color = "blue"

    # ── DQ Score label ──
    if dq_score >= 95:
        score_label = "EXCELLENT"
    elif dq_score >= 80:
        score_label = "GOOD"
    elif dq_score >= 60:
        score_label = "FAIR"
    else:
        score_label = "CRITICAL"

    # ── Gauge figure ──
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=dq_score,
        number={"suffix": "%", "font": {"size": 54, "family": "Outfit, sans-serif", "color": "#f1f5f9"}},
        title={"text": f"<b>Data Quality Score</b><br><span style='font-size:0.8em;color:#94a3b8'>{score_label}</span>",
               "font": {"size": 16, "family": "Inter, sans-serif", "color": "#94a3b8"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#1e2a45",
                     "tickfont": {"color": "#64748b", "size": 11}},
            "bar": {"color": "#10b981" if dq_score >= 95 else "#f59e0b" if dq_score >= 80 else "#f43f5e"},
            "bgcolor": "rgba(20,27,45,0.5)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 60], "color": "rgba(244,63,94,0.15)"},
                {"range": [60, 80], "color": "rgba(245,158,11,0.15)"},
                {"range": [80, 95], "color": "rgba(250,204,21,0.1)"},
                {"range": [95, 100], "color": "rgba(16,185,129,0.15)"},
            ],
            "threshold": {
                "line": {"color": "#10b981", "width": 3},
                "thickness": 0.8,
                "value": dq_score,
            },
        },
    ))
    fig_gauge.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#94a3b8"),
        height=300,
        margin=dict(l=30, r=30, t=60, b=20),
    )

    # ── Pipeline Timeline figure ──
    if phase_data:
        phase_df = pd.DataFrame(phase_data, columns=["phase", "status", "duration", "start", "end"])
        phase_df["phase"] = phase_df["phase"].str.capitalize()
        colors_map = {"SUCCESS": "#10b981", "FAIL": "#f43f5e", "WARNING": "#f59e0b"}
        phase_df["color"] = phase_df["status"].map(colors_map).fillna("#3b82f6")

        fig_pipeline = go.Figure()
        fig_pipeline.add_trace(go.Bar(
            y=phase_df["phase"],
            x=phase_df["duration"],
            orientation="h",
            marker=dict(color=phase_df["color"], line=dict(width=0)),
            text=[f"{d:.1f}s — {s}" for d, s in zip(phase_df["duration"], phase_df["status"])],
            textposition="outside",
            textfont=dict(size=11, color="#94a3b8", family="Inter, sans-serif"),
            hovertemplate="<b>%{y}</b><br>Duration: %{x:.2f}s<br>Status: %{text}<extra></extra>",
        ))
        fig_pipeline.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", color="#94a3b8", size=12),
            height=280,
            margin=dict(l=80, r=80, t=20, b=20),
            xaxis=dict(title="Duration (seconds)", gridcolor="rgba(30,42,69,0.6)", zerolinecolor="rgba(30,42,69,0.6)"),
            yaxis=dict(autorange="reversed", gridcolor="rgba(30,42,69,0.6)"),
            showlegend=False,
        )
    else:
        fig_pipeline = go.Figure()
        fig_pipeline.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=280, margin=dict(l=20, r=20, t=40, b=20),
            annotations=[dict(text="No pipeline data available", x=0.5, y=0.5,
                              showarrow=False, font=dict(size=14, color="#64748b"))]
        )

    # ── DQ Trend figure ──
    if dq_trend_data and len(dq_trend_data) > 0:
        trend_df = pd.DataFrame(dq_trend_data, columns=["timestamp", "score", "records"])
        trend_df["label"] = pd.to_datetime(trend_df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=trend_df["label"], y=trend_df["score"],
            mode="lines+markers+text",
            text=[f"{s}%" for s in trend_df["score"]],
            textposition="top center",
            textfont=dict(size=11, color="#10b981", family="Inter, sans-serif"),
            line=dict(color="#10b981", width=3),
            marker=dict(size=10, color="#10b981", line=dict(color="#0a0e1a", width=2)),
            fill="tozeroy",
            fillcolor="rgba(16,185,129,0.08)",
            hovertemplate="<b>%{x}</b><br>DQ Score: %{y}%<extra></extra>",
        ))
        fig_trend.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", color="#94a3b8", size=12),
            height=260,
            margin=dict(l=50, r=20, t=20, b=40),
            xaxis=dict(gridcolor="rgba(30,42,69,0.6)", zerolinecolor="rgba(30,42,69,0.6)"),
            yaxis=dict(range=[0, 105], gridcolor="rgba(30,42,69,0.6)", zerolinecolor="rgba(30,42,69,0.6)",
                       title="Score %"),
            showlegend=False,
        )
    else:
        fig_trend = go.Figure()
        fig_trend.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=260, margin=dict(l=20, r=20, t=40, b=20),
            annotations=[dict(text="Trend data will appear after multiple ETL runs", x=0.5, y=0.5,
                              showarrow=False, font=dict(size=14, color="#64748b"))]
        )

    # ── Executive Insights (dynamically generated) ──
    insights = []
    insights.append(f"✓ {total:,} flight records validated across {dim_airlines} airlines and {dim_airports} airports.")
    null_total = sum(v["failures"] for v in validation_results if "Null" in v["rule"])
    if null_total == 0:
        insights.append("✓ Zero null foreign keys detected — referential integrity maintained.")
    else:
        insights.append(f"⚠ {null_total} null foreign key(s) detected.")
    orphan_total = sum(v["failures"] for v in validation_results if "Orphan" in v["rule"])
    if orphan_total == 0:
        insights.append("✓ No orphan records detected — all foreign keys resolve to valid dimensions.")
    else:
        insights.append(f"⚠ {orphan_total} orphan record(s) detected.")
    dup_total = sum(v["failures"] for v in validation_results if "Duplicate" in v["rule"])
    if dup_total == 0:
        insights.append("✓ No duplicate dimension keys found — dimension tables are clean.")
    else:
        insights.append(f"⚠ {dup_total} duplicate dimension key(s) found.")
    insights.append(f"✓ Data Quality Score: {dq_score}% — {score_label}")
    if last_etl_time:
        insights.append(f"✓ Last successful ETL: {last_etl_time[:19]} ({etl_duration}s total duration)")
    insights.append(f"✓ Warehouse coverage: {dim_dates} dates, {dim_airlines} airlines, {dim_airports} airports.")

    # ── Build the page ──
    return html.Div(className="dq-command-center", children=[
        # Header
        html.Div(className="page-header", children=[
            html.H1("Data Quality Command Center", className="page-title"),
            html.P("Enterprise-grade validation, pipeline health monitoring, and data governance",
                   className="page-subtitle"),
        ]),

        # Meta bar
        html.Div(className="meta-bar", children=[
            html.Div(className="meta-item", children=[
                html.Span("Source:"),
                html.Span("warehouse.db", className="meta-value"),
            ]),
            html.Div(className="meta-item", children=[
                html.Span("Records:"),
                html.Span(f"{total:,}", className="meta-value"),
            ]),
            html.Div(className="meta-item", children=[
                html.Span("Rules:"),
                html.Span(f"{passed_checks}/{total_checks} passed", className="meta-value"),
            ]),
            html.Span(f"DQ {dq_score}%", className="meta-badge"),
        ]),

        # Section 1: Executive KPIs
        html.Div(className="kpi-row", children=[
            kpi_card("📊", "Records Validated", f"{total:,}",
                     f"{dim_airlines} airlines · {dim_airports} airports", "blue"),
            kpi_card("🎯", "Data Quality Score", f"{dq_score}%",
                     score_label, "emerald" if dq_score >= 95 else "amber"),
            kpi_card("✅", "Rules Passed", f"{passed_checks} / {total_checks}",
                     "ALL PASS" if failed_checks == 0 else f"{failed_checks} FAILED",
                     "emerald" if failed_checks == 0 else "rose"),
            kpi_card("💚" if health_color == "emerald" else "⚠️", "Pipeline Health",
                     health_label, f"{etl_duration}s total runtime", health_color),
            kpi_card("🕐", "Last ETL Run",
                     last_etl_time[:16].replace("T", " ") if last_etl_time else "N/A",
                     etl_status, "blue"),
            kpi_card("📡", "Data Freshness", freshness_label,
                     "Monitoring active", freshness_color),
        ]),

        # Section 2: Gauge + Pipeline Timeline
        html.Div(className="chart-row", children=[
            chart_card("Data Quality Score Gauge", children=[
                dcc.Graph(figure=fig_gauge, config=MODEBAR_CONFIG),
            ]),
            chart_card("Pipeline Execution Timeline", children=[
                dcc.Graph(figure=fig_pipeline, config=MODEBAR_CONFIG),
            ]),
        ]),

        # Section 3: Validation Matrix
        html.Div(className="chart-row single", children=[
            chart_card("Validation Rule Matrix", children=[
                dark_table("quality-matrix-table",
                    columns=[
                        {"name": "Validation Rule", "id": "rule"},
                        {"name": "Records Checked", "id": "records_checked"},
                        {"name": "Failures", "id": "failures"},
                        {"name": "Status", "id": "status"},
                    ],
                    data=[{
                        "rule": v["rule"],
                        "records_checked": f"{v['records_checked']:,}",
                        "failures": str(v["failures"]),
                        "status": v["status"],
                    } for v in validation_results],
                    style_data_conditional=[
                        {"if": {"filter_query": '{status} = "PASS"', "column_id": "status"},
                         "color": "#10b981", "fontWeight": "700"},
                        {"if": {"filter_query": '{status} = "FAIL"', "column_id": "status"},
                         "color": "#f43f5e", "fontWeight": "700"},
                        {"if": {"filter_query": '{status} = "WARNING"', "column_id": "status"},
                         "color": "#f59e0b", "fontWeight": "700"},
                        {"if": {"filter_query": '{failures} = "0"', "column_id": "failures"},
                         "color": "#10b981"},
                    ],
                ),
            ]),
        ]),

        # Section 4 & 5: DQ Trend + Executive Insights
        html.Div(className="chart-row", children=[
            chart_card("Data Quality Score Trend", children=[
                dcc.Graph(figure=fig_trend, config=MODEBAR_CONFIG),
            ]),
            chart_card("Executive Insights", children=[
                html.Div(className="dq-insights", children=[
                    html.Div(className="dq-insight-item", children=[
                        html.Span(insight)
                    ]) for insight in insights
                ]),
            ]),
        ]),
    ])


# ============================================================================
# APP LAYOUT
# ============================================================================

app.layout = html.Div(id="app-container", children=[
    dcc.Location(id="url", refresh=False),
    sidebar,
    html.Div(id="page-content"),
])


# ============================================================================
# ROUTING
# ============================================================================

@callback(Output("page-content", "children"), Input("url", "pathname"))
def route_page(pathname):
    pages = {
        "/airline": page_airline,
        "/airport": page_airport,
        "/route":   page_route,
        "/delay":   page_delay,
        "/trend":   page_trend,
        "/quality": page_quality,
    }
    return pages.get(pathname, page_executive)()


@callback(
    [Output(f"nav-{href.strip('/') or 'home'}", "className") for href, _, _ in NAV_ITEMS],
    Input("url", "pathname"),
)
def update_nav_active(pathname):
    return ["nav-link active" if pathname == href else "nav-link" for href, _, _ in NAV_ITEMS]


# ============================================================================
# CALLBACKS: EXECUTIVE OVERVIEW
# ============================================================================

@callback(Output("exec-top-airlines", "figure"), Input("url", "pathname"))
def cb_exec_airlines(_):
    with get_conn() as conn:
        df = pd.read_sql("""
            SELECT a.airline_name, COUNT(*) AS flights
            FROM fact_flights f JOIN dim_airline a ON f.airline_key = a.airline_key
            GROUP BY a.airline_name ORDER BY flights DESC LIMIT 10
        """, conn)
    fig = px.bar(df, x="flights", y="airline_name", orientation="h",
                 color="flights", color_continuous_scale="Blues", text="flights")
    fig.update_traces(textposition="outside", textfont_size=11, marker_line_width=0,
                      texttemplate="%{text:,.0f}", hovertemplate="<b>%{y}</b><br>Flights: %{x:,.0f}<extra></extra>")
    fig.update_layout(showlegend=False, coloraxis_showscale=False,
                      yaxis=dict(autorange="reversed", title=""),
                      xaxis=dict(title="Flights", separatethousands=True))
    return style_fig(fig)


@callback(Output("exec-top-airports", "figure"), Input("url", "pathname"))
def cb_exec_airports(_):
    with get_conn() as conn:
        df = pd.read_sql("""
            SELECT a.airport_code,
                   COUNT(*) AS traffic
            FROM (
                SELECT origin_airport_key AS ak FROM fact_flights
                UNION ALL
                SELECT dest_airport_key AS ak FROM fact_flights
            ) t
            JOIN dim_airport a ON t.ak = a.airport_key
            GROUP BY a.airport_code
            ORDER BY traffic DESC LIMIT 10
        """, conn)
    fig = px.bar(df, x="traffic", y="airport_code", orientation="h",
                 color="traffic", color_continuous_scale="Teal", text="traffic")
    fig.update_traces(textposition="outside", textfont_size=11, marker_line_width=0,
                      texttemplate="%{text:,.0f}", hovertemplate="<b>%{y}</b><br>Traffic: %{x:,.0f}<extra></extra>")
    fig.update_layout(showlegend=False, coloraxis_showscale=False,
                      yaxis=dict(autorange="reversed", title=""),
                      xaxis=dict(title="Total Traffic", separatethousands=True))
    return style_fig(fig)


@callback(Output("exec-delay-overview", "figure"), Input("url", "pathname"))
def cb_exec_delays(_):
    with get_conn() as conn:
        df = pd.read_sql("""
            SELECT
                ROUND(AVG(WEATHER_DELAY), 2)        AS Weather,
                ROUND(AVG(AIRLINE_DELAY), 2)        AS Airline,
                ROUND(AVG(SECURITY_DELAY), 2)       AS Security,
                ROUND(AVG(AIR_SYSTEM_DELAY), 2)     AS "NAS",
                ROUND(AVG(LATE_AIRCRAFT_DELAY), 2)  AS "Late Aircraft"
            FROM fact_flights WHERE ARRIVAL_DELAY > 0
        """, conn)
    melted = df.melt(var_name="Category", value_name="Avg Minutes")
    fig = px.bar(melted, x="Category", y="Avg Minutes", color="Category",
                 color_discrete_sequence=COLORS, text="Avg Minutes")
    fig.update_traces(textposition="outside", textfont_size=12, marker_line_width=0)
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Average Minutes")
    return style_fig(fig, height=360)


@callback(Output("exec-geo-map", "figure"), Input("url", "pathname"))
def cb_exec_geo(_):
    with get_conn() as conn:
        df = pd.read_sql("""
            SELECT a.airport_code, a.airport_name, a.latitude, a.longitude,
                   COUNT(*) AS departures
            FROM fact_flights f
            JOIN dim_airport a ON f.origin_airport_key = a.airport_key
            WHERE a.latitude IS NOT NULL AND a.longitude IS NOT NULL
            GROUP BY a.airport_code, a.airport_name, a.latitude, a.longitude
        """, conn)
    fig = px.scatter_geo(
        df, lat="latitude", lon="longitude", size="departures",
        hover_name="airport_name",
        hover_data={"airport_code": True, "departures": True, "latitude": False, "longitude": False},
        scope="usa", color="departures", color_continuous_scale="Plasma",
        size_max=30,
    )
    fig.update_layout(
        geo=dict(bgcolor="rgba(0,0,0,0)", lakecolor="rgba(20,27,45,1)",
                 landcolor="rgba(20,27,45,1)", subunitcolor="#1e2a45",
                 showlakes=True, showcountries=False, showsubunits=True),
        coloraxis_showscale=False,
    )
    return style_fig(fig, height=400)


# ============================================================================
# CALLBACKS: AIRLINE ANALYTICS
# ============================================================================

@callback(
    [Output("airline-kpi-row", "children"),
     Output("airline-daily", "figure"),
     Output("airline-delay-dist", "figure"),
     Output("airline-comparison", "figure")],
    Input("airline-dropdown", "value"),
)
def cb_airline(akey):
    empty = style_fig(go.Figure())
    if akey is None:
        return [], empty, empty, empty

    with get_conn() as conn:
        stats = pd.read_sql(f"""
            SELECT COUNT(*) AS flights,
                   ROUND(AVG(DEPARTURE_DELAY),1)  AS avg_dep,
                   ROUND(AVG(ARRIVAL_DELAY),1)     AS avg_arr,
                   ROUND(CAST(SUM(CASE WHEN CANCELLED=1 THEN 1 ELSE 0 END) AS FLOAT)/COUNT(*)*100,2) AS cancel_rate
            FROM fact_flights WHERE airline_key = {akey}
        """, conn).iloc[0]

        name = pd.read_sql(f"SELECT airline_name FROM dim_airline WHERE airline_key={akey}", conn).iloc[0]["airline_name"]

        daily = pd.read_sql(f"""
            SELECT d.full_date, d.day_name, COUNT(*) AS flights
            FROM fact_flights f JOIN dim_date d ON f.date_key = d.date_key
            WHERE f.airline_key = {akey}
            GROUP BY d.full_date, d.day_name ORDER BY d.full_date
        """, conn)
        daily["date_label"] = daily["day_name"] + " (" + daily["full_date"].str[:10] + ")"

        delays = pd.read_sql(f"""
            SELECT DEPARTURE_DELAY FROM fact_flights
            WHERE airline_key = {akey} AND DEPARTURE_DELAY IS NOT NULL
              AND DEPARTURE_DELAY BETWEEN -30 AND 120
        """, conn)

        comp = pd.read_sql("""
            SELECT a.airline_name,
                   COUNT(*) AS flights,
                   ROUND(AVG(f.ARRIVAL_DELAY),1)  AS avg_delay,
                   ROUND(CAST(SUM(CASE WHEN f.CANCELLED=1 THEN 1 ELSE 0 END) AS FLOAT)/COUNT(*)*100,2) AS cancel_rate
            FROM fact_flights f JOIN dim_airline a ON f.airline_key = a.airline_key
            GROUP BY a.airline_name ORDER BY avg_delay
        """, conn)

    kpis = [
        kpi_card("\u2708", name, f"{int(stats['flights']):,}", "Total flights", "blue"),
        kpi_card("\u2193", "Avg Dep Delay", f"{stats['avg_dep']} min", "Departure", "amber"),
        kpi_card("\u2191", "Avg Arr Delay", f"{stats['avg_arr']} min", "Arrival", "purple"),
        kpi_card("\u2716", "Cancel Rate", f"{stats['cancel_rate']}%", "Cancellation", "rose"),
    ]

    fig_daily = px.bar(daily, x="date_label", y="flights", color_discrete_sequence=["#3b82f6"],
                       text="flights")
    fig_daily.update_traces(textposition="outside", textfont_size=11, marker_line_width=0)
    fig_daily.update_layout(xaxis_title="", yaxis_title="Flights")
    style_fig(fig_daily)

    fig_hist = px.histogram(delays, x="DEPARTURE_DELAY", nbins=50,
                            color_discrete_sequence=["#6366f1"])
    fig_hist.update_layout(xaxis_title="Departure Delay (min)", yaxis_title="Frequency")
    style_fig(fig_hist)

    fig_comp = px.scatter(comp, x="avg_delay", y="cancel_rate", text="airline_name",
                          size="flights", color="avg_delay", color_continuous_scale="RdYlGn_r",
                          size_max=40)
    fig_comp.update_traces(textposition="top center", textfont_size=10)
    fig_comp.update_layout(xaxis_title="Avg Arrival Delay (min)", yaxis_title="Cancellation Rate (%)",
                           coloraxis_showscale=False)
    style_fig(fig_comp, height=420)

    return kpis, fig_daily, fig_hist, fig_comp


# ============================================================================
# CALLBACKS: AIRPORT ANALYTICS
# ============================================================================

@callback(
    [Output("airport-kpi-row", "children"),
     Output("airport-delay-hist", "figure"),
     Output("airport-top-dest", "figure"),
     Output("airport-rankings", "figure")],
    Input("airport-dropdown", "value"),
)
def cb_airport(apkey):
    empty = style_fig(go.Figure())
    if apkey is None:
        return [], empty, empty, empty

    with get_conn() as conn:
        info = pd.read_sql(f"SELECT airport_code, airport_name, city, state FROM dim_airport WHERE airport_key={apkey}", conn).iloc[0]

        origin_cnt = conn.execute(f"SELECT COUNT(*) FROM fact_flights WHERE origin_airport_key={apkey}").fetchone()[0]
        dest_cnt   = conn.execute(f"SELECT COUNT(*) FROM fact_flights WHERE dest_airport_key={apkey}").fetchone()[0]
        avg_dep    = conn.execute(f"SELECT ROUND(AVG(DEPARTURE_DELAY),1) FROM fact_flights WHERE origin_airport_key={apkey}").fetchone()[0] or 0

        delays = pd.read_sql(f"""
            SELECT DEPARTURE_DELAY FROM fact_flights
            WHERE origin_airport_key={apkey} AND DEPARTURE_DELAY IS NOT NULL
              AND DEPARTURE_DELAY BETWEEN -30 AND 120
        """, conn)

        top_dest = pd.read_sql(f"""
            SELECT a.airport_code, a.airport_name, COUNT(*) AS flights
            FROM fact_flights f JOIN dim_airport a ON f.dest_airport_key = a.airport_key
            WHERE f.origin_airport_key = {apkey}
            GROUP BY a.airport_code, a.airport_name ORDER BY flights DESC LIMIT 10
        """, conn)

        rankings = pd.read_sql("""
            SELECT a.airport_code,
                   COUNT(*) AS total_traffic,
                   DENSE_RANK() OVER (ORDER BY COUNT(*) DESC) AS rank
            FROM (
                SELECT origin_airport_key AS ak FROM fact_flights
                UNION ALL SELECT dest_airport_key FROM fact_flights
            ) t
            JOIN dim_airport a ON t.ak = a.airport_key
            GROUP BY a.airport_code
            ORDER BY rank LIMIT 25
        """, conn)

    kpis = [
        kpi_card("\U0001F3E2", info["airport_code"], f"{info['airport_name']}", f"{info['city']}, {info['state']}", "blue"),
        kpi_card("\u2191", "Departures", f"{origin_cnt:,}", "Origin flights", "emerald"),
        kpi_card("\u2193", "Arrivals", f"{dest_cnt:,}", "Destination flights", "purple"),
        kpi_card("\u23F1", "Avg Dep Delay", f"{avg_dep} min", "Departure average", "amber"),
    ]

    fig_h = px.histogram(delays, x="DEPARTURE_DELAY", nbins=50, color_discrete_sequence=["#06b6d4"])
    fig_h.update_layout(xaxis_title="Departure Delay (min)", yaxis_title="Frequency")
    style_fig(fig_h)

    fig_d = px.bar(top_dest, x="flights", y="airport_code", orientation="h",
                   color="flights", color_continuous_scale="Teal", text="flights",
                   hover_data={"airport_name": True})
    fig_d.update_traces(textposition="outside", textfont_size=11, marker_line_width=0)
    fig_d.update_layout(showlegend=False, coloraxis_showscale=False,
                        yaxis=dict(autorange="reversed", title=""))
    style_fig(fig_d)

    fig_r = px.bar(rankings, x="airport_code", y="total_traffic",
                   color="total_traffic", color_continuous_scale="Plasma",
                   text="rank", hover_data={"total_traffic": True})
    fig_r.update_traces(texttemplate="#%{text}", textposition="outside", textfont_size=10,
                        marker_line_width=0)
    fig_r.update_layout(showlegend=False, coloraxis_showscale=False,
                        xaxis_title="Airport", yaxis_title="Total Traffic", xaxis_tickangle=-45)
    style_fig(fig_r, height=420)

    return kpis, fig_h, fig_d, fig_r


# ============================================================================
# CALLBACKS: ROUTE INTELLIGENCE
# ============================================================================

@callback(
    [Output("route-top", "figure"),
     Output("route-risk", "figure"),
     Output("route-table", "data"),
     Output("route-table", "columns")],
    Input("route-min-flights", "value"),
)
def cb_routes(min_f):
    min_f = min_f or 20
    with get_conn() as conn:
        df = pd.read_sql(f"""
            SELECT
                orig.airport_code AS origin,
                dest.airport_code AS destination,
                orig.airport_code || ' -> ' || dest.airport_code AS route,
                COUNT(*) AS flights,
                ROUND(AVG(f.ARRIVAL_DELAY), 1) AS avg_delay,
                ROUND(CAST(SUM(CASE WHEN f.CANCELLED=1 THEN 1 ELSE 0 END) AS FLOAT)/COUNT(*)*100, 2) AS cancel_rate,
                ROUND(AVG(f.DISTANCE), 0) AS avg_distance_mi
            FROM fact_flights f
            JOIN dim_airport orig ON f.origin_airport_key = orig.airport_key
            JOIN dim_airport dest ON f.dest_airport_key = dest.airport_key
            GROUP BY orig.airport_code, dest.airport_code
            HAVING COUNT(*) >= {min_f}
            ORDER BY flights DESC
        """, conn)

    top20 = df.head(20)
    fig_top = px.bar(top20, x="flights", y="route", orientation="h",
                     color="flights", color_continuous_scale="Blues", text="flights")
    fig_top.update_traces(textposition="outside", textfont_size=10, marker_line_width=0)
    fig_top.update_layout(showlegend=False, coloraxis_showscale=False,
                          yaxis=dict(autorange="reversed", title=""))
    style_fig(fig_top, height=520)

    fig_risk = px.scatter(df, x="avg_delay", y="cancel_rate", size="flights",
                          hover_data={"route": True, "flights": True, "avg_distance_mi": True},
                          color="avg_delay", color_continuous_scale="RdYlGn_r", size_max=30)
    fig_risk.update_layout(xaxis_title="Avg Arrival Delay (min)", yaxis_title="Cancellation Rate (%)",
                           coloraxis_showscale=False)
    style_fig(fig_risk, height=520)

    cols = [{"name": c, "id": c} for c in df.columns]
    return fig_top, fig_risk, df.to_dict("records"), cols


# ============================================================================
# CALLBACKS: DELAY ANALYTICS
# ============================================================================

@callback(
    [Output("delay-category", "figure"),
     Output("delay-airline-bar", "figure"),
     Output("delay-weather-hist", "figure"),
     Output("delay-late-hist", "figure")],
    [Input("delay-airline-filter", "value"),
     Input("delay-day-filter", "value")],
)
def cb_delays(airline_val, day_val):
    where_parts = ["f.ARRIVAL_DELAY > 0"]
    if airline_val != "all":
        where_parts.append(f"f.airline_key = {airline_val}")
    if day_val != "all":
        where_parts.append(f"f.date_key = {day_val}")
    where = " AND ".join(where_parts)

    with get_conn() as conn:
        cat = pd.read_sql(f"""
            SELECT
                ROUND(AVG(f.WEATHER_DELAY), 2)       AS Weather,
                ROUND(AVG(f.AIRLINE_DELAY), 2)       AS Airline,
                ROUND(AVG(f.SECURITY_DELAY), 2)      AS Security,
                ROUND(AVG(f.AIR_SYSTEM_DELAY), 2)    AS "NAS",
                ROUND(AVG(f.LATE_AIRCRAFT_DELAY), 2) AS "Late Aircraft"
            FROM fact_flights f WHERE {where}
        """, conn)

        where_all = "f.ARRIVAL_DELAY > 0"
        if day_val != "all":
            where_all += f" AND f.date_key = {day_val}"

        by_airline = pd.read_sql(f"""
            SELECT a.airline_name,
                   ROUND(AVG(f.ARRIVAL_DELAY), 1) AS avg_delay
            FROM fact_flights f
            JOIN dim_airline a ON f.airline_key = a.airline_key
            WHERE {where_all}
            GROUP BY a.airline_name ORDER BY avg_delay DESC
        """, conn)

        where_hist = []
        if airline_val != "all":
            where_hist.append(f"f.airline_key = {airline_val}")
        if day_val != "all":
            where_hist.append(f"f.date_key = {day_val}")
        hist_where = (" AND " + " AND ".join(where_hist)) if where_hist else ""

        weather = pd.read_sql(f"SELECT f.WEATHER_DELAY FROM fact_flights f WHERE f.WEATHER_DELAY > 0{hist_where}", conn)
        late    = pd.read_sql(f"SELECT f.LATE_AIRCRAFT_DELAY FROM fact_flights f WHERE f.LATE_AIRCRAFT_DELAY > 0{hist_where}", conn)

    melted = cat.melt(var_name="Category", value_name="Avg Minutes")
    fig_cat = px.pie(melted, names="Category", values="Avg Minutes",
                     color_discrete_sequence=COLORS, hole=0.45)
    fig_cat.update_traces(textinfo="label+percent", textfont_size=11)
    style_fig(fig_cat)

    fig_air = px.bar(by_airline, x="airline_name", y="avg_delay",
                     color="avg_delay", color_continuous_scale="OrRd", text="avg_delay")
    fig_air.update_traces(textposition="outside", textfont_size=10, marker_line_width=0)
    fig_air.update_layout(showlegend=False, coloraxis_showscale=False,
                          xaxis_tickangle=-45, xaxis_title="", yaxis_title="Avg Delay (min)")
    style_fig(fig_air)

    fig_w = px.histogram(weather, x="WEATHER_DELAY", nbins=40, color_discrete_sequence=["#3b82f6"])
    fig_w.update_layout(xaxis_title="Weather Delay (min)", yaxis_title="Frequency")
    style_fig(fig_w)

    fig_l = px.histogram(late, x="LATE_AIRCRAFT_DELAY", nbins=40, color_discrete_sequence=["#f59e0b"])
    fig_l.update_layout(xaxis_title="Late Aircraft Delay (min)", yaxis_title="Frequency")
    style_fig(fig_l)

    return fig_cat, fig_air, fig_w, fig_l


# ============================================================================
# CALLBACKS: TREND ANALYTICS
# ============================================================================

@callback(
    [Output("trend-flights", "figure"),
     Output("trend-delay", "figure"),
     Output("trend-cancel", "figure"),
     Output("trend-daytype", "figure"),
     Output("trend-airline-daily", "figure")],
    Input("url", "pathname"),
)
def cb_trends(_):
    with get_conn() as conn:
        daily = pd.read_sql("""
            SELECT d.full_date, d.day_name, d.is_weekend,
                   COUNT(*) AS flights,
                   ROUND(AVG(f.DEPARTURE_DELAY), 1) AS avg_dep_delay,
                   ROUND(AVG(f.ARRIVAL_DELAY), 1)   AS avg_arr_delay,
                   ROUND(CAST(SUM(CASE WHEN f.CANCELLED=1 THEN 1 ELSE 0 END) AS FLOAT)/COUNT(*)*100, 2) AS cancel_rate
            FROM fact_flights f
            JOIN dim_date d ON f.date_key = d.date_key
            GROUP BY d.full_date, d.day_name, d.is_weekend
            ORDER BY d.full_date
        """, conn)
        daily["label"] = daily["day_name"] + " " + daily["full_date"].str[5:10]

        airline_daily = pd.read_sql("""
            SELECT d.full_date, d.day_name, a.airline_name, COUNT(*) AS flights
            FROM fact_flights f
            JOIN dim_date d ON f.date_key = d.date_key
            JOIN dim_airline a ON f.airline_key = a.airline_key
            GROUP BY d.full_date, d.day_name, a.airline_name
            ORDER BY d.full_date
        """, conn)
        airline_daily["label"] = airline_daily["day_name"] + " " + airline_daily["full_date"].str[5:10]

        daytype = pd.read_sql("""
            SELECT
                CASE WHEN d.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END AS day_type,
                COUNT(*) AS flights,
                ROUND(AVG(f.DEPARTURE_DELAY), 1) AS avg_delay
            FROM fact_flights f
            JOIN dim_date d ON f.date_key = d.date_key
            GROUP BY day_type
        """, conn)

    fig_f = px.area(daily, x="label", y="flights", markers=True,
                    color_discrete_sequence=["#3b82f6"])
    fig_f.update_layout(xaxis_title="", yaxis_title="Flights")
    style_fig(fig_f)

    fig_d = px.line(daily, x="label", y=["avg_dep_delay", "avg_arr_delay"],
                    markers=True, color_discrete_sequence=["#f59e0b", "#a855f7"])
    fig_d.update_layout(xaxis_title="", yaxis_title="Avg Delay (min)", legend_title="Delay Type")
    style_fig(fig_d)

    fig_c = px.bar(daily, x="label", y="cancel_rate",
                   color="cancel_rate", color_continuous_scale="Reds", text="cancel_rate")
    fig_c.update_traces(textposition="outside", textfont_size=11, marker_line_width=0)
    fig_c.update_layout(xaxis_title="", yaxis_title="Cancellation Rate (%)",
                        showlegend=False, coloraxis_showscale=False)
    style_fig(fig_c)

    fig_dt = px.bar(daytype, x="day_type", y="flights", color="day_type",
                    color_discrete_sequence=["#3b82f6", "#06b6d4"], text="flights")
    fig_dt.update_traces(textposition="outside", textfont_size=12, marker_line_width=0)
    fig_dt.update_layout(xaxis_title="", yaxis_title="Flights", showlegend=False)
    style_fig(fig_dt)

    fig_ad = px.line(airline_daily, x="label", y="flights", color="airline_name",
                     markers=True, color_discrete_sequence=COLORS)
    fig_ad.update_layout(xaxis_title="", yaxis_title="Flights",
                         legend_title="Airline", legend=dict(font=dict(size=9)))
    style_fig(fig_ad, height=440)

    return fig_f, fig_d, fig_c, fig_dt, fig_ad


# ============================================================================
# LAUNCH
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  AirFlow Enterprise BI Portal")
    print("  http://localhost:8050")
    print("=" * 60 + "\n")
    app.run(debug=False, host="0.0.0.0", port=8050)
