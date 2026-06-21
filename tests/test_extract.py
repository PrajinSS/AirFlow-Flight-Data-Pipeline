"""
Unit tests for the Extract Phase of the Flight Analytics ETL Pipeline.
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

from extract import load_reference_table, load_large_fact_table, extract_all_data

# Expected file paths
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
AIRLINES_FILE = DATA_RAW_DIR / "airlines.csv"
AIRPORTS_FILE = DATA_RAW_DIR / "airports.csv"
FLIGHTS_FILE = DATA_RAW_DIR / "flights.csv"

def test_raw_files_exist():
    """Verify that all required raw data source files exist on the filesystem."""
    assert AIRLINES_FILE.exists(), f"Missing raw airlines file at {AIRLINES_FILE}"
    assert AIRPORTS_FILE.exists(), f"Missing raw airports file at {AIRPORTS_FILE}"
    assert FLIGHTS_FILE.exists(), f"Missing raw flights file at {FLIGHTS_FILE}"

def test_load_airlines():
    """Verify that the airlines reference table loads correctly and contains expected columns."""
    df = load_reference_table(AIRLINES_FILE, "airlines")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty, "Airlines DataFrame should not be empty."
    assert "IATA_CODE" in df.columns, "Missing 'IATA_CODE' in airlines columns."
    assert "AIRLINE" in df.columns, "Missing 'AIRLINE' in airlines columns."

def test_load_airports():
    """Verify that the airports reference table loads correctly and contains expected columns."""
    df = load_reference_table(AIRPORTS_FILE, "airports")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty, "Airports DataFrame should not be empty."
    assert "IATA_CODE" in df.columns, "Missing 'IATA_CODE' in airports columns."
    assert "AIRPORT" in df.columns, "Missing 'AIRPORT' in airports columns."

def test_load_flights_sample():
    """Verify that the large flights fact table loads correctly using memory-aware sampling."""
    sample_size = 1000
    df = load_large_fact_table(FLIGHTS_FILE, table_name="flights", sample_size=sample_size)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == sample_size, f"Flights DataFrame size {len(df)} does not match sample size {sample_size}"
    
    # Check for core columns
    expected_cols = ["YEAR", "MONTH", "DAY", "AIRLINE", "FLIGHT_NUMBER", "ORIGIN_AIRPORT", "DESTINATION_AIRPORT"]
    for col in expected_cols:
        assert col in df.columns, f"Expected column '{col}' is missing in raw flights schema."

def test_extract_all_data():
    """Verify the orchestrator function runs successfully and returns all three dataframes."""
    sample_size = 500
    df_airlines, df_airports, df_flights = extract_all_data(flights_sample_size=sample_size)
    
    assert isinstance(df_airlines, pd.DataFrame)
    assert isinstance(df_airports, pd.DataFrame)
    assert isinstance(df_flights, pd.DataFrame)
    
    assert not df_airlines.empty
    assert not df_airports.empty
    assert len(df_flights) == sample_size
