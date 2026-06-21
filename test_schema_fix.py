#!/usr/bin/env python3
"""
Test Script: Validate Schema Mismatch Fix

This script tests the schema validation functions to ensure the fix works correctly.
Run after transform.py has generated flights_cleaned.csv

Usage:
    python test_schema_fix.py
"""

import sys
import sqlite3
from pathlib import Path

# Add scripts to path
scripts_dir = Path(__file__).parent / "scripts"
sys.path.insert(0, str(scripts_dir))

import pandas as pd
from load import (
    create_database,
    create_tables,
    get_sqlite_table_schema,
    validate_dataframe_schema,
    select_compatible_columns,
    load_data_to_sqlite,
)


def test_schema_retrieval():
    """Test getting SQLite table schema."""
    print("\n" + "=" * 70)
    print("TEST 1: Schema Retrieval")
    print("=" * 70)

    conn = sqlite3.connect(":memory:")
    create_tables(conn)

    schema = get_sqlite_table_schema(conn, "flights")

    print(f"✓ Retrieved schema for flights table")
    print(f"  Total columns: {len(schema)}")
    print(f"  Columns: {', '.join(sorted(schema.keys())[:5])}... (showing first 5)")

    # Check for critical columns
    critical_cols = ["FLIGHT_NUMBER", "AIRLINE_ID", "ORIGIN_AIRPORT_ID", "DESTINATION_AIRPORT_ID"]
    missing = [col for col in critical_cols if col not in schema]

    if missing:
        print(f"✗ FAILED: Missing critical columns: {missing}")
        return False
    else:
        print(f"✓ All critical columns present: {critical_cols}")

    conn.close()
    return True


def test_schema_validation():
    """Test schema validation function."""
    print("\n" + "=" * 70)
    print("TEST 2: Schema Validation")
    print("=" * 70)

    conn = sqlite3.connect(":memory:")
    create_tables(conn)

    # Create test DataFrame with FLIGHT_NUMBER
    df = pd.DataFrame({
        "YEAR": [2015, 2015],
        "MONTH": [1, 1],
        "DAY": [1, 2],
        "DAY_OF_WEEK": [4, 5],
        "FLIGHT_NUMBER": ["AA001", "AA002"],
        "AIRLINE": ["AA", "AA"],
        "ORIGIN_AIRPORT": ["LAX", "LAX"],
        "DESTINATION_AIRPORT": ["JFK", "JFK"],
        "SCHEDULED_DEPARTURE": [600, 700],
        "DEPARTURE_TIME": [605, 710],
        "DEPARTURE_DELAY": [5, 10],
        "ARRIVAL_DELAY": [15, 20],
        "CANCELLED": [0, 0],
        "DIVERTED": [0, 0],
    })

    print(f"Created test DataFrame with {len(df.columns)} columns")
    print(f"  Columns: {list(df.columns)}")

    # Validate schema
    result = validate_dataframe_schema(
        df,
        conn,
        table_name="flights",
        exclude_columns=["AIRLINE", "ORIGIN_AIRPORT", "DESTINATION_AIRPORT"],
    )

    print(f"\nValidation Result:")
    print(f"  Is Valid: {result['is_valid']}")
    print(f"  DataFrame columns: {result['column_count_df']}")
    print(f"  Table columns: {result['column_count_table']}")

    if result["missing_from_table"]:
        print(f"  ✗ Missing from table: {result['missing_from_table']}")
        return False
    else:
        print(f"  ✓ All DataFrame columns exist in table")

    if result["is_valid"]:
        print(f"✓ Schema validation PASSED")
    else:
        print(f"✗ Schema validation FAILED")
        return False

    conn.close()
    return True


def test_column_filtering():
    """Test compatible column selection."""
    print("\n" + "=" * 70)
    print("TEST 3: Compatible Column Filtering")
    print("=" * 70)

    conn = sqlite3.connect(":memory:")
    create_tables(conn)

    # Create test DataFrame with extra columns
    df = pd.DataFrame({
        "YEAR": [2015, 2015],
        "MONTH": [1, 1],
        "FLIGHT_NUMBER": ["AA001", "AA002"],
        "AIRLINE": ["AA", "AA"],
        "ORIGIN_AIRPORT": ["LAX", "LAX"],
        "DESTINATION_AIRPORT": ["JFK", "JFK"],
        "DEPARTURE_DELAY": [5, 10],
        "ARRIVAL_DELAY": [15, 20],
        "EXTRA_COLUMN_1": [100, 200],  # Extra column not in table
        "EXTRA_COLUMN_2": [300, 400],  # Extra column not in table
    })

    print(f"Original DataFrame: {len(df.columns)} columns")
    print(f"  Including extra columns: EXTRA_COLUMN_1, EXTRA_COLUMN_2")

    # Filter to compatible columns
    df_filtered = select_compatible_columns(
        df,
        conn,
        table_name="flights",
        exclude_columns=["AIRLINE", "ORIGIN_AIRPORT", "DESTINATION_AIRPORT"],
    )

    print(f"\nFiltered DataFrame: {len(df_filtered.columns)} columns")
    print(f"  Extra columns removed: {set(df.columns) - set(df_filtered.columns)}")

    # Check that FLIGHT_NUMBER is included
    if "FLIGHT_NUMBER" in df_filtered.columns:
        print(f"✓ FLIGHT_NUMBER included in filtered DataFrame")
    else:
        print(f"✗ FLIGHT_NUMBER NOT in filtered DataFrame")
        return False

    # Check that extra columns are removed
    if "EXTRA_COLUMN_1" not in df_filtered.columns and "EXTRA_COLUMN_2" not in df_filtered.columns:
        print(f"✓ Extra columns removed successfully")
    else:
        print(f"✗ Extra columns not properly removed")
        return False

    conn.close()
    return True


def test_full_load_flow():
    """Test the complete load flow with schema validation."""
    print("\n" + "=" * 70)
    print("TEST 4: Full Load Flow (Schema Validation + Insertion)")
    print("=" * 70)

    # Read cleaned data if available
    cleaned_csv = Path("data") / "cleaned" / "flights_cleaned.csv"

    if not cleaned_csv.exists():
        print(f"⚠ Skipping full load test: {cleaned_csv} not found")
        print(f"  (Run transform.py first to generate cleaned data)")
        return None

    try:
        df = pd.read_csv(cleaned_csv)
        print(f"✓ Loaded flights_cleaned.csv")
        print(f"  Rows: {len(df):,}")
        print(f"  Columns: {len(df.columns)}")

        # Create in-memory database
        conn = sqlite3.connect(":memory:")
        create_database(conn)
        create_tables(conn)

        # Load data with schema validation
        print(f"\nLoading data with schema validation...")
        counts = load_data_to_sqlite(df, conn, verbose=False)

        print(f"\n✓ Data loaded successfully:")
        print(f"  Airlines: {counts['airlines']:,}")
        print(f"  Airports: {counts['airports']:,}")
        print(f"  Flights: {counts['flights']:,}")

        # Verify FLIGHT_NUMBER in database
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM flights WHERE FLIGHT_NUMBER IS NOT NULL;")
        count_with_flight_number = cursor.fetchone()[0]

        print(f"\n✓ FLIGHT_NUMBER verification:")
        print(f"  Flights with FLIGHT_NUMBER: {count_with_flight_number:,}")

        cursor.execute("SELECT COUNT(*) FROM flights;")
        total_flights = cursor.fetchone()[0]

        if count_with_flight_number > 0:
            pct = (count_with_flight_number / total_flights) * 100
            print(f"  Percentage with FLIGHT_NUMBER: {pct:.1f}%")

        conn.close()
        return True

    except Exception as e:
        print(f"✗ Full load test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "Schema Mismatch Fix - Test Suite" + " " * 20 + "║")
    print("╚" + "=" * 68 + "╝")

    tests = [
        ("Schema Retrieval", test_schema_retrieval),
        ("Schema Validation", test_schema_validation),
        ("Column Filtering", test_column_filtering),
        ("Full Load Flow", test_full_load_flow),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r is None)

    for test_name, result in results:
        if result is True:
            status = "✓ PASSED"
        elif result is False:
            status = "✗ FAILED"
        else:
            status = "⊘ SKIPPED"
        print(f"{status:12} {test_name}")

    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")

    if failed == 0:
        print("\n✓ All tests passed! Schema fix is working correctly.")
        return 0
    else:
        print(f"\n✗ {failed} test(s) failed. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
