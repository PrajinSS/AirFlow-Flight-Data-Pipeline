"""
Unit tests for the Analytics Phase of the Flight Analytics ETL Pipeline.
Uses pytest.
"""

import sys
from pathlib import Path
import pytest
import pandas as pd

# Resolve paths to allow importing scripts
TEST_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = TEST_DIR.parent.resolve()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Analytics output paths
ANALYTICS_DATA_DIR = PROJECT_ROOT / "data" / "analytics"
EXEC_SUMMARY_PATH = ANALYTICS_DATA_DIR / "executive_summary.csv"
AIRLINE_PERF_PATH = ANALYTICS_DATA_DIR / "daily_airline_performance.csv"
AIRPORT_TRAFFIC_PATH = ANALYTICS_DATA_DIR / "airport_traffic.csv"
DELAY_ANALYSIS_PATH = ANALYTICS_DATA_DIR / "delay_analysis.csv"

def test_analytics_files_exist():
    """Verify that all four required analytical summary CSV files exist."""
    assert EXEC_SUMMARY_PATH.exists(), "Missing executive_summary.csv"
    assert AIRLINE_PERF_PATH.exists(), "Missing daily_airline_performance.csv"
    assert AIRPORT_TRAFFIC_PATH.exists(), "Missing airport_traffic.csv"
    assert DELAY_ANALYSIS_PATH.exists(), "Missing delay_analysis.csv"

def test_executive_summary_content():
    """Verify that the executive summary contains expected columns and valid rows."""
    df = pd.read_csv(EXEC_SUMMARY_PATH)
    assert not df.empty, "executive_summary.csv is empty"
    assert len(df) == 1, "executive_summary.csv should contain exactly one row of statistics"
    
    expected_cols = [
        "TOTAL_FLIGHTS", "TOTAL_AIRLINES", "TOTAL_AIRPORTS", 
        "CANCELLATION_RATE", "DIVERSION_RATE", "AVG_DEPARTURE_DELAY", "AVG_ARRIVAL_DELAY"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Expected column '{col}' is missing in executive summary."

def test_airline_performance_content():
    """Verify that the airline performance dataset contains expected columns and non-empty records."""
    df = pd.read_csv(AIRLINE_PERF_PATH)
    assert not df.empty, "daily_airline_performance.csv is empty"
    
    expected_cols = [
        "AIRLINE_CODE", "FLIGHT_COUNT", "AVG_DEPARTURE_DELAY", 
        "AVG_ARRIVAL_DELAY", "CANCELLATION_RATE", "DIVERSION_RATE"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Expected column '{col}' is missing in airline performance."
        
    # Check flight count sorting is descending
    flight_counts = df["FLIGHT_COUNT"].tolist()
    assert all(flight_counts[i] >= flight_counts[i+1] for i in range(len(flight_counts)-1)), \
        "Airline performance should be sorted descending by FLIGHT_COUNT."

def test_airport_traffic_content():
    """Verify that the airport traffic dataset contains expected columns and non-empty records."""
    df = pd.read_csv(AIRPORT_TRAFFIC_PATH)
    assert not df.empty, "airport_traffic.csv is empty"
    
    expected_cols = ["AIRPORT_CODE", "ORIGIN_FLIGHTS", "DESTINATION_FLIGHTS", "TOTAL_TRAFFIC"]
    for col in expected_cols:
        assert col in df.columns, f"Expected column '{col}' is missing in airport traffic."
        
    # Check total traffic sorting is descending
    traffic = df["TOTAL_TRAFFIC"].tolist()
    assert all(traffic[i] >= traffic[i+1] for i in range(len(traffic)-1)), \
        "Airport traffic should be sorted descending by TOTAL_TRAFFIC."

def test_delay_analysis_content():
    """Verify that the delay analysis dataset contains expected columns and non-empty records."""
    df = pd.read_csv(DELAY_ANALYSIS_PATH)
    assert not df.empty, "delay_analysis.csv is empty"
    
    expected_cols = [
        "AIRLINE_CODE", "AVG_WEATHER_DELAY", "AVG_AIRLINE_DELAY", 
        "AVG_SECURITY_DELAY", "AVG_AIR_SYSTEM_DELAY", "AVG_LATE_AIRCRAFT_DELAY"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Expected column '{col}' is missing in delay analysis."
