import sqlite3
import pandas as pd
from pathlib import Path
import logging
import sys

def setup_logging():
    log = logging.getLogger("BI_Analytics")
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
REPORTS_DIR = PROJECT_ROOT / "reports"

def run_bi_analytics():
    logger.info("Starting Enterprise BI Analytics Engine...")
    
    with sqlite3.connect(WH_DB) as conn:
        
        # 1. kpi_airline_reliability.csv
        logger.info("Generating Airline Reliability KPIs...")
        airline_reliability = pd.read_sql("""
            WITH AirlineStats AS (
                SELECT 
                    a.airline_name,
                    COUNT(f.airline_key) as total_flights,
                    SUM(CASE WHEN f.CANCELLED = 1 THEN 1 ELSE 0 END) as cancelled_flights,
                    SUM(CASE WHEN f.DIVERTED = 1 THEN 1 ELSE 0 END) as diverted_flights,
                    AVG(f.ARRIVAL_DELAY) as avg_delay
                FROM fact_flights f
                JOIN dim_airline a ON f.airline_key = a.airline_key
                GROUP BY a.airline_name
            )
            SELECT 
                airline_name,
                total_flights,
                cancelled_flights,
                ROUND((CAST(cancelled_flights AS FLOAT) / total_flights) * 100, 2) as cancellation_rate,
                ROUND((CAST(diverted_flights AS FLOAT) / total_flights) * 100, 2) as diversion_rate,
                ROUND(avg_delay, 2) as avg_delay_mins,
                RANK() OVER (ORDER BY (CAST(cancelled_flights AS FLOAT) / total_flights) ASC, avg_delay ASC) as reliability_rank
            FROM AirlineStats
            ORDER BY reliability_rank;
        """, conn)
        airline_reliability.to_csv(BI_DIR / "kpi_airline_reliability.csv", index=False)
        
        # 2. kpi_airport_efficiency.csv
        logger.info("Generating Airport Efficiency KPIs...")
        airport_efficiency = pd.read_sql("""
            SELECT 
                ap.airport_code,
                ap.airport_name,
                COUNT(f.origin_airport_key) as total_departures,
                ROUND(AVG(f.DEPARTURE_DELAY), 2) as avg_dep_delay,
                SUM(CASE WHEN f.DEPARTURE_DELAY > 15 THEN 1 ELSE 0 END) as delayed_departures,
                ROUND((CAST(SUM(CASE WHEN f.DEPARTURE_DELAY > 15 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(f.origin_airport_key)) * 100, 2) as delay_rate,
                DENSE_RANK() OVER (ORDER BY AVG(f.DEPARTURE_DELAY) ASC) as efficiency_rank
            FROM fact_flights f
            JOIN dim_airport ap ON f.origin_airport_key = ap.airport_key
            GROUP BY ap.airport_code, ap.airport_name
            HAVING COUNT(f.origin_airport_key) > 50
            ORDER BY efficiency_rank;
        """, conn)
        airport_efficiency.to_csv(BI_DIR / "kpi_airport_efficiency.csv", index=False)
        
        # 3. kpi_route_reliability.csv (Route Intelligence)
        logger.info("Generating Route Intelligence KPIs...")
        route_reliability = pd.read_sql("""
            SELECT 
                orig.airport_code as origin,
                dest.airport_code as destination,
                orig.airport_code || ' \u2192 ' || dest.airport_code as route,
                COUNT(*) as flights,
                ROUND(AVG(f.ARRIVAL_DELAY), 2) as avg_arr_delay,
                ROUND((CAST(SUM(CASE WHEN f.CANCELLED = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*)) * 100, 2) as cancellation_rate
            FROM fact_flights f
            JOIN dim_airport orig ON f.origin_airport_key = orig.airport_key
            JOIN dim_airport dest ON f.dest_airport_key = dest.airport_key
            GROUP BY orig.airport_code, dest.airport_code
            HAVING COUNT(*) > 20
            ORDER BY flights DESC;
        """, conn)
        route_reliability.to_csv(BI_DIR / "route_intelligence.csv", index=False)
        
        # 4. Monthly Trend Analytics
        logger.info("Generating Monthly Trends...")
        monthly_trends = pd.read_sql("""
            SELECT 
                d.month_name,
                d.month,
                COUNT(*) as total_flights,
                ROUND(AVG(f.DEPARTURE_DELAY), 2) as avg_delay,
                ROUND((CAST(SUM(CASE WHEN f.CANCELLED = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*)) * 100, 2) as cancellation_rate,
                SUM(COUNT(*)) OVER (ORDER BY d.month) as running_total_flights
            FROM fact_flights f
            JOIN dim_date d ON f.date_key = d.date_key
            GROUP BY d.month_name, d.month
            ORDER BY d.month;
        """, conn)
        monthly_trends.to_csv(TRENDS_DIR / "monthly_trends.csv", index=False)

        # 5. kpi_delay_risk.csv
        delay_risk = pd.read_sql("""
            SELECT 
                a.airline_name,
                ROUND(AVG(f.WEATHER_DELAY), 2) as weather_risk,
                ROUND(AVG(f.SECURITY_DELAY), 2) as security_risk,
                ROUND(AVG(f.LATE_AIRCRAFT_DELAY), 2) as late_aircraft_risk,
                ROUND(AVG(f.AIR_SYSTEM_DELAY), 2) as nas_risk
            FROM fact_flights f
            JOIN dim_airline a ON f.airline_key = a.airline_key
            WHERE f.ARRIVAL_DELAY > 0
            GROUP BY a.airline_name;
        """, conn)
        delay_risk.to_csv(BI_DIR / "kpi_delay_risk.csv", index=False)
        
        # 6. Generate Executive Scorecard
        logger.info("Writing Executive Scorecard...")
        best_airline = airline_reliability.iloc[0]['airline_name']
        worst_airline = airline_reliability.iloc[-1]['airline_name']
        best_airport = airport_efficiency.iloc[0]['airport_name']
        worst_airport = airport_efficiency.iloc[-1]['airport_name']
        
        route_rel_sorted = route_reliability.sort_values(by='cancellation_rate')
        best_route = route_rel_sorted.iloc[0]['route']
        worst_route = route_rel_sorted.iloc[-1]['route']
        
        scorecard = f"""======================================================================
EXECUTIVE SCORECARD - FLIGHT ANALYTICS BI
======================================================================

AIRLINE PERFORMANCE
-------------------
🏆 Best Performing Airline: {best_airline}
⚠️ Worst Performing Airline: {worst_airline}

AIRPORT PERFORMANCE
-------------------
🏆 Best Airport (Least Delays): {best_airport}
⚠️ Worst Airport (Most Delays): {worst_airport}

ROUTE INTELLIGENCE
------------------
⭐ Most Reliable Route: {best_route}
🚫 Highest Risk Route: {worst_route}
======================================================================"""
        with open(REPORTS_DIR / "executive_scorecard.txt", "w", encoding='utf-8') as f:
            f.write(scorecard)
            
        # 7. Generate Business Insights
        logger.info("Generating Business Insight Engine...")
        busiest_airline = airline_reliability.sort_values(by='total_flights', ascending=False).iloc[0]['airline_name']
        busiest_airport = airport_efficiency.sort_values(by='total_departures', ascending=False).iloc[0]['airport_name']
        
        insights = f"""AUTOMATED BUSINESS INSIGHTS
---------------------------
- Volume Insight: {busiest_airline} handled the highest number of flights in the network.
- Hub Insight: {busiest_airport} was the busiest airport by departure volume.
- Performance Insight: {best_airline} holds the #1 Reliability Rank among all carriers.
- Risk Insight: The {worst_route} route exhibits the highest cancellation risk.
"""
        with open(REPORTS_DIR / "business_insights.txt", "w", encoding='utf-8') as f:
            f.write(insights)

        logger.info("✓ Enterprise BI Analytics Engine completed successfully!")

if __name__ == '__main__':
    run_bi_analytics()
