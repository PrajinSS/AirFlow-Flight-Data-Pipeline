import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import logging
import sys

def setup_logging():
    log = logging.getLogger("BI_Portal")
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    return log

logger = setup_logging()

PROJECT_ROOT = Path(__file__).parent.parent
WH_DB = PROJECT_ROOT / "warehouse" / "warehouse.db"
BI_DIR = PROJECT_ROOT / "data" / "bi"
TRENDS_DIR = PROJECT_ROOT / "data" / "trends"
MAPS_DIR = PROJECT_ROOT / "exports" / "maps"
EXPORTS_DIR = PROJECT_ROOT / "exports" / "html"

def generate_maps():
    logger.info("Generating Geospatial Analytics Maps...")
    with sqlite3.connect(WH_DB) as conn:
        # Flight Density Map
        airport_traffic = pd.read_sql("""
            SELECT 
                a.airport_code,
                a.airport_name,
                a.city,
                a.state,
                a.latitude,
                a.longitude,
                COUNT(f.origin_airport_key) as total_departures
            FROM fact_flights f
            JOIN dim_airport a ON f.origin_airport_key = a.airport_key
            GROUP BY a.airport_code, a.airport_name, a.city, a.state, a.latitude, a.longitude
            HAVING a.latitude IS NOT NULL AND a.longitude IS NOT NULL
        """, conn)

    fig = px.scatter_geo(
        airport_traffic,
        lat='latitude',
        lon='longitude',
        size='total_departures',
        hover_name='airport_name',
        hover_data={'city': True, 'state': True, 'total_departures': True, 'latitude': False, 'longitude': False},
        title='US Airport Flight Density',
        scope='usa',
        template='plotly_dark',
        color='total_departures',
        color_continuous_scale=px.colors.sequential.Plasma
    )
    fig.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
    map_path = MAPS_DIR / "flight_density_map.html"
    fig.write_html(str(map_path))
    logger.info(f"Saved Map: {map_path}")
    
    return fig

def build_bi_portal():
    logger.info("Building Enterprise BI Portal HTML...")
    
    # Read BI Datasets
    airline_rel = pd.read_csv(BI_DIR / "kpi_airline_reliability.csv")
    airport_eff = pd.read_csv(BI_DIR / "kpi_airport_efficiency.csv")
    route_rel = pd.read_csv(BI_DIR / "route_intelligence.csv")
    monthly_trends = pd.read_csv(TRENDS_DIR / "monthly_trends.csv")
    
    # Read Exec Scorecard and Business Insights
    with open(PROJECT_ROOT / "reports" / "executive_scorecard.txt", "r", encoding='utf-8') as f:
        scorecard = f.read()
        
    with open(PROJECT_ROOT / "reports" / "business_insights.txt", "r", encoding='utf-8') as f:
        insights = f.read()

    # Generate Plotly Chart HTML Divs
    # 1. Airline Reliability Bar Chart
    fig_airline = px.bar(
        airline_rel.sort_values(by='cancellation_rate'), 
        x='airline_name', y='cancellation_rate', 
        title='Airline Cancellation Rates',
        color='cancellation_rate',
        color_continuous_scale='Reds'
    )
    airline_html = fig_airline.to_html(full_html=False, include_plotlyjs='cdn')

    # 2. Airport Efficiency Scatter
    fig_airport = px.scatter(
        airport_eff, 
        x='total_departures', y='avg_dep_delay',
        size='delayed_departures', hover_name='airport_name',
        title='Airport Efficiency Matrix',
        color='avg_dep_delay',
        color_continuous_scale='Turbo'
    )
    airport_html = fig_airport.to_html(full_html=False, include_plotlyjs=False)

    # 3. Monthly Trends Line
    fig_trend = px.line(
        monthly_trends,
        x='month_name', y='total_flights',
        title='Monthly Flight Volume Trends',
        markers=True
    )
    trend_html = fig_trend.to_html(full_html=False, include_plotlyjs=False)
    
    # 4. Generate Geospatial Map
    fig_map = generate_maps()
    map_html = fig_map.to_html(full_html=False, include_plotlyjs=False)

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AirFlow BI Portal</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent: #3b82f6;
        }}
        body {{
            font-family: 'Segoe UI', system-ui, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            margin: 0;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 20px 0;
            border-bottom: 1px solid #334155;
            margin-bottom: 30px;
        }}
        h1, h2, h3 {{ color: #e2e8f0; }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .card {{
            background: var(--card-bg);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }}
        .full-width {{ grid-column: 1 / -1; }}
        pre {{
            white-space: pre-wrap;
            background: #0f172a;
            padding: 15px;
            border-radius: 6px;
            color: #10b981;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>AirFlow Enterprise BI Portal</h1>
        <p>Phase 9: Star Schema Warehouse & Advanced SQL Analytics</p>
    </div>

    <div class="grid">
        <!-- Executive Intelligence -->
        <div class="card">
            <h2>Executive Scorecard</h2>
            <pre>{scorecard}</pre>
        </div>
        <div class="card">
            <h2>Business Insight Engine</h2>
            <pre>{insights}</pre>
        </div>

        <!-- Trend Intelligence -->
        <div class="card full-width">
            <h2>Trend Intelligence</h2>
            {trend_html}
        </div>

        <!-- Airline & Airport Intelligence -->
        <div class="card">
            <h2>Airline Intelligence</h2>
            {airline_html}
        </div>
        <div class="card">
            <h2>Airport Intelligence</h2>
            {airport_html}
        </div>

        <!-- Geospatial Intelligence -->
        <div class="card full-width">
            <h2>Geospatial Intelligence</h2>
            {map_html}
        </div>
    </div>
</body>
</html>"""

    portal_path = EXPORTS_DIR / "bi_portal.html"
    with open(portal_path, "w", encoding='utf-8') as f:
        f.write(html_template)
    logger.info(f"✓ BI Portal generated successfully at: {portal_path}")

if __name__ == '__main__':
    build_bi_portal()
