"""
Unit tests for the Transform Phase of the Flight Analytics ETL Pipeline.
Uses pytest.
"""

import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

# Resolve paths to allow importing scripts
TEST_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = TEST_DIR.parent.resolve()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from transform import (
    clean_missing_values,
    clean_duplicates,
    validate_delay_columns,
    transform_flights_data
)

# Output paths
CLEANED_CSV_PATH = PROJECT_ROOT / "data" / "cleaned" / "flights_cleaned.csv"

def test_cleaned_file_exists():
    """Verify that the transformed output dataset has been successfully generated."""
    assert CLEANED_CSV_PATH.exists(), f"Cleaned output file is missing at {CLEANED_CSV_PATH}"
    df = pd.read_csv(CLEANED_CSV_PATH)
    assert not df.empty, "Cleaned dataset should not be empty."

def test_null_handling():
    """Verify that null handling logic correctly fills null values for numeric and categorical columns."""
    # Construct mock dataframe with missing values
    test_df = pd.DataFrame({
        "DEPARTURE_DELAY": [10.0, np.nan, 20.0, 15.0],
        "AIRLINE": ["UA", "AA", None, "DL"],
        "CANCELLED": [0, 0, 1, 0]
    })

    cleaned_df = clean_missing_values(test_df)
    
    # Assert no nulls are present in output
    assert cleaned_df["DEPARTURE_DELAY"].isnull().sum() == 0
    assert cleaned_df["AIRLINE"].isnull().sum() == 0

    # Numeric missing should be filled with median (median of [10.0, 20.0, 15.0] is 15.0)
    assert cleaned_df.loc[1, "DEPARTURE_DELAY"] == 15.0

    # Categorical missing should be filled with 'UNKNOWN'
    assert cleaned_df.loc[2, "AIRLINE"] == "UNKNOWN"

def test_clean_duplicates():
    """Verify that duplicate rows are correctly identified and removed."""
    test_df = pd.DataFrame({
        "YEAR": [2015, 2015, 2015, 2015],
        "MONTH": [1, 1, 1, 1],
        "DAY": [1, 1, 1, 1],
        "FLIGHT_NUMBER": [101, 101, 102, 101]
    })
    
    cleaned_df = clean_duplicates(test_df)
    
    # Check duplicate rows are dropped (first, second, and fourth rows are duplicates)
    assert len(cleaned_df) == 2
    # Check index reset
    assert list(cleaned_df.index) == [0, 1]

def test_validate_delay_columns():
    """Verify that delay columns are correctly formatted and cast to numeric."""
    test_df = pd.DataFrame({
        "DEPARTURE_DELAY": ["10", "  -15.5", "nan", "abc"],
        "ARRIVAL_DELAY": [5.0, 12.0, None, np.nan]
    })

    validated_df = validate_delay_columns(test_df)
    
    # Assert delay columns are cast to float
    assert np.issubdtype(validated_df["DEPARTURE_DELAY"].dtype, np.number)
    # Check non-numeric converted to NaN
    assert np.isnan(validated_df.loc[3, "DEPARTURE_DELAY"])

def test_cleaned_data_types():
    """Verify that the cleaned flights dataset contains correct types."""
    df = pd.read_csv(CLEANED_CSV_PATH)
    
    # YEAR, MONTH, DAY must be integer-like
    assert np.issubdtype(df["YEAR"].dtype, np.integer)
    assert np.issubdtype(df["MONTH"].dtype, np.integer)
    assert np.issubdtype(df["DAY"].dtype, np.integer)

    # Delay columns must be numeric
    delay_cols = ["DEPARTURE_DELAY", "ARRIVAL_DELAY", "AIR_SYSTEM_DELAY", "SECURITY_DELAY"]
    for col in delay_cols:
        if col in df.columns:
            assert np.issubdtype(df[col].dtype, np.number)
