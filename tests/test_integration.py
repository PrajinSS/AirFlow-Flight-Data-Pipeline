"""
End-to-End Integration Tests for the AirFlow Flight Analytics ETL Pipeline.
Uses pytest to validate the full pipeline flow:
Extract -> Transform -> Load -> Analytics -> Dashboard
"""

import sys
import sqlite3
import os
from pathlib import Path
import pytest
import pandas as pd

# Resolve paths to allow importing scripts
TEST_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = TEST_DIR.parent.resolve()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Import main execution functions from ETL phases
import extract
import transform
import load
import analytics
import dashboard

def test_full_pipeline_integration():
    """
    Execute the entire pipeline in sequence and validate phase-to-phase transitions.
    
    Validates:
    1. Extract -> Transform (Data format, column layouts)
    2. Transform -> Load (Dimension lookups, foreign keys, row counts)
    3. Load -> Analytics (SQL CTEs aggregations, analytical datasets)
    4. Analytics -> Dashboard (Plotly charts, responsive CSS layout HTML dashboards)
    """
    # -------------------------------------------------------------------------
    # PHASE 1 & 2: Extract -> Transform
    # -------------------------------------------------------------------------
    # Run extract of small sample size for integration testing speed
    sample_size = 1000
    df_airlines, df_airports, df_flights = extract.extract_all_data(flights_sample_size=sample_size)
    
    assert isinstance(df_airlines, pd.DataFrame)
    assert isinstance(df_airports, pd.DataFrame)
    assert isinstance(df_flights, pd.DataFrame)
    assert len(df_flights) == sample_size
    
    # Pass raw output to transform module pipeline
    df_cleaned, transform_meta = transform.transform_flights_data(df_flights, verbose=False)
    
    assert isinstance(df_cleaned, pd.DataFrame)
    assert len(df_cleaned) == sample_size, "Cleaned flights count should match raw flights count."
    assert "DEPARTURE_DELAY" in df_cleaned.columns
    assert "ARRIVAL_DELAY" in df_cleaned.columns
    assert df_cleaned["DEPARTURE_DELAY"].isnull().sum() == 0, "All nulls in departure delay should be resolved."
    assert df_cleaned["ARRIVAL_DELAY"].isnull().sum() == 0, "All nulls in arrival delay should be resolved."

    # -------------------------------------------------------------------------
    # PHASE 2 & 3: Transform -> Load
    # -------------------------------------------------------------------------
    # Create SQLite database and run loading logic
    test_db_path = PROJECT_ROOT / "database" / "airflow.db"
    
    # Save transformed data to intermediate cleaned CSV
    transform.save_cleaned_dataset(df_cleaned)
    
    # Connect and recreate tables
    with sqlite3.connect(str(test_db_path)) as conn:
        load.create_tables(conn)
        loaded_counts = load.load_data_to_sqlite(df_cleaned, conn)
        
        # Verify load validations pass
        load_valid = load.validate_load(len(df_cleaned), loaded_counts, conn)
        assert load_valid is True, "Database load validation failed."
        
        # Verify db counts match source cleaned dataframe size
        cursor = conn.cursor()
        db_count = cursor.execute("SELECT COUNT(*) FROM flights;").fetchone()[0]
        assert db_count == sample_size, f"Orphaned row counts: expected {sample_size}, got {db_count} in DB."

    # -------------------------------------------------------------------------
    # PHASE 3 & 4: Load -> Analytics
    # -------------------------------------------------------------------------
    # Generate analytical tables and textual reports using database connection
    with sqlite3.connect(str(test_db_path)) as conn:
        exec_summary = analytics.get_executive_summary(conn)
        airline_perf = analytics.get_airline_performance(conn)
        airport_traffic = analytics.get_airport_traffic(conn)
        delay_analysis = analytics.get_delay_analysis(conn)
        
        # Ensure analytical tables correspond to correct counts
        assert not exec_summary.empty
        assert exec_summary.at[0, "TOTAL_FLIGHTS"] == sample_size
        
        # Export summaries
        exec_summary.to_csv(analytics.ANALYTICS_DATA_DIR / "executive_summary.csv", index=False)
        airline_perf.to_csv(analytics.ANALYTICS_DATA_DIR / "daily_airline_performance.csv", index=False)
        airport_traffic.to_csv(analytics.ANALYTICS_DATA_DIR / "airport_traffic.csv", index=False)
        delay_analysis.to_csv(analytics.ANALYTICS_DATA_DIR / "delay_analysis.csv", index=False)
        
        analytics.write_summary_report(
            exec_summary, airline_perf, airport_traffic, delay_analysis, analytics.SUMMARY_REPORT_PATH
        )
        assert analytics.SUMMARY_REPORT_PATH.exists()

    # -------------------------------------------------------------------------
    # PHASE 4 & 5: Analytics -> Dashboard
    # -------------------------------------------------------------------------
    # Generate charts and dashboards based on analytics CSV outputs
    dashboard_status = dashboard.main()
    assert dashboard_status == 0, "Dashboard creation phase failed."
    
    # Validate visual assets exist on filesystem
    charts_dir = PROJECT_ROOT / "visualizations" / "charts"
    exports_dir = PROJECT_ROOT / "exports" / "html"
    
    # Check matplotlib charts exist
    assert (charts_dir / "top_airlines.png").exists()
    assert (charts_dir / "top_airports.png").exists()
    
    # Check plotly HTML dashboards exist
    assert (exports_dir / "dashboard.html").exists()
    assert (exports_dir / "executive_dashboard.html").exists()
    assert (exports_dir / "airline_dashboard.html").exists()
    assert (exports_dir / "airport_dashboard.html").exists()
