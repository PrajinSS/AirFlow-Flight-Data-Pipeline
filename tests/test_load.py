"""
Unit tests for the Load Phase of the Flight Analytics ETL Pipeline.
Uses pytest.
"""

import sys
import sqlite3
from pathlib import Path
import pytest
import pandas as pd

# Resolve paths to allow importing scripts
TEST_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = TEST_DIR.parent.resolve()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from load import DB_FILE, CLEANED_CSV

def test_database_exists():
    """Verify that the SQLite database file exists on the filesystem."""
    assert DB_FILE.exists(), f"Database file is missing at {DB_FILE}"

def test_database_tables():
    """Verify that all required normalized tables were created in the database."""
    with sqlite3.connect(str(DB_FILE)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        
        expected_tables = {"airlines", "airports", "flights"}
        for table in expected_tables:
            assert table in tables, f"Expected table '{table}' is missing in SQLite database."

def test_database_schema():
    """Verify the columns of each table in the database schema."""
    with sqlite3.connect(str(DB_FILE)) as conn:
        cursor = conn.cursor()
        
        # Verify airlines schema
        cursor.execute("PRAGMA table_info(airlines);")
        airlines_cols = {row[1] for row in cursor.fetchall()}
        assert "AIRLINE_ID" in airlines_cols
        assert "AIRLINE" in airlines_cols
        
        # Verify airports schema
        cursor.execute("PRAGMA table_info(airports);")
        airports_cols = {row[1] for row in cursor.fetchall()}
        assert "AIRPORT_ID" in airports_cols
        assert "AIRPORT" in airports_cols

        # Verify flights schema
        cursor.execute("PRAGMA table_info(flights);")
        flights_cols = {row[1] for row in cursor.fetchall()}
        assert "FLIGHT_ID" in flights_cols
        assert "AIRLINE_ID" in flights_cols
        assert "ORIGIN_AIRPORT_ID" in flights_cols
        assert "DESTINATION_AIRPORT_ID" in flights_cols

def test_row_counts_match():
    """Verify that the loaded flight rows match the cleaned source CSV count."""
    assert CLEANED_CSV.exists()
    df_cleaned = pd.read_csv(CLEANED_CSV)
    expected_rows = len(df_cleaned)

    with sqlite3.connect(str(DB_FILE)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM flights;")
        db_rows = cursor.fetchone()[0]
        
        assert db_rows == expected_rows, f"Row count mismatch: CSV has {expected_rows} rows, DB has {db_rows} rows"

def test_database_integrity_constraints():
    """Verify that there are no orphaned flight records (referential integrity check)."""
    with sqlite3.connect(str(DB_FILE)) as conn:
        cursor = conn.cursor()
        
        # Orphaned airline check
        cursor.execute("""
            SELECT COUNT(*) FROM flights 
            WHERE AIRLINE_ID NOT IN (SELECT AIRLINE_ID FROM airlines);
        """)
        orphaned_airlines = cursor.fetchone()[0]
        assert orphaned_airlines == 0, f"Found {orphaned_airlines} flight records referencing non-existent airlines."

        # Orphaned airports checks
        cursor.execute("""
            SELECT COUNT(*) FROM flights 
            WHERE ORIGIN_AIRPORT_ID NOT IN (SELECT AIRPORT_ID FROM airports);
        """)
        orphaned_origins = cursor.fetchone()[0]
        assert orphaned_origins == 0, f"Found {orphaned_origins} flight records referencing non-existent origin airports."

        cursor.execute("""
            SELECT COUNT(*) FROM flights 
            WHERE DESTINATION_AIRPORT_ID NOT IN (SELECT AIRPORT_ID FROM airports);
        """)
        orphaned_dests = cursor.fetchone()[0]
        assert orphaned_dests == 0, f"Found {orphaned_dests} flight records referencing non-existent destination airports."
