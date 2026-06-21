"""
AirFlow: Flight Operations Data Pipeline & Analytics Platform
Module: Data Extraction and Profiling

This module handles the extraction phase of the ETL pipeline, loading raw data files
from the data/raw directory. It supports efficient loading of reference tables
(airlines, airports) and large fact tables (flights) with memory-aware sampling.

The functions are designed to be reusable by downstream Transform and Load phases
and provide comprehensive data profiling metrics.

Author: Data Engineering Team
Date: June 17, 2026
Version: 1.0.0
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional
import pandas as pd

# ============================================================================
# CONFIGURATION AND CONSTANTS
# ============================================================================

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"

# Default configurations for data loading
DEFAULT_FLIGHTS_SAMPLE_SIZE = 100000

# CSV file paths
AIRLINES_FILE = DATA_RAW_DIR / "airlines.csv"
AIRPORTS_FILE = DATA_RAW_DIR / "airports.csv"
FLIGHTS_FILE = DATA_RAW_DIR / "flights.csv"

# ============================================================================
# LOGGER SETUP
# ============================================================================

def setup_logger(name: str = "AirFlow.Extract", log_level: int = logging.INFO) -> logging.Logger:
    """
    Configure and return a logger instance with standardized formatting.

    Args:
        name (str): Logger name identifier. Defaults to "AirFlow.Extract".
        log_level (int): Logging level (e.g., logging.INFO, logging.DEBUG).
                        Defaults to logging.INFO.

    Returns:
        logging.Logger: Configured logger instance.

    Notes:
        - Uses timestamp, level, and message in log format
        - Logs to console output
        - Thread-safe and reusable across modules
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Prevent duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger()

# ============================================================================
# DATA EXTRACTION FUNCTIONS
# ============================================================================

def load_reference_table(
    file_path: Path,
    table_name: str,
    encoding: str = 'utf-8'
) -> pd.DataFrame:
    """
    Load a complete reference table (airlines or airports) into memory.

    This function loads smaller reference datasets that are typically used
    for joins and lookups. Complete loading is assumed for these tables.

    Args:
        file_path (Path): Absolute or relative path to the CSV file.
        table_name (str): Human-readable name for logging (e.g., "airlines", "airports").
        encoding (str): File encoding. Defaults to 'utf-8'.

    Returns:
        pd.DataFrame: Loaded data as a pandas DataFrame.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        pd.errors.EmptyDataError: If the CSV file is empty.
        Exception: For unexpected pandas read_csv errors.

    Notes:
        - Assumes reference tables fit entirely in memory
        - Logs row count and columns on successful load
        - Includes comprehensive error handling and logging
    """
    try:
        if not file_path.exists():
            logger.error(f"Reference table file not found: {file_path}")
            raise FileNotFoundError(f"File does not exist: {file_path}")

        logger.info(f"Loading {table_name} reference table from: {file_path}")

        df = pd.read_csv(file_path, encoding=encoding)

        logger.info(
            f"Successfully loaded {table_name}: "
            f"{len(df)} rows, {len(df.columns)} columns"
        )

        return df

    except FileNotFoundError as e:
        logger.error(f"FileNotFoundError while loading {table_name}: {str(e)}")
        raise

    except pd.errors.EmptyDataError:
        logger.error(f"EmptyDataError: {table_name} file is empty")
        raise

    except Exception as e:
        logger.error(f"Unexpected error loading {table_name}: {type(e).__name__}: {str(e)}")
        raise


def load_large_fact_table(
    file_path: Path,
    table_name: str = "flights",
    sample_size: Optional[int] = None,
    encoding: str = 'utf-8'
) -> pd.DataFrame:
    """
    Load a large fact table (flights) with configurable row sampling.

    This function provides memory-efficient loading of large datasets by supporting
    row sampling. It uses skiprows parameter to randomly sample rows, reducing
    memory overhead for datasets larger than available RAM.

    Args:
        file_path (Path): Absolute or relative path to the CSV file.
        table_name (str): Human-readable name for logging. Defaults to "flights".
        sample_size (Optional[int]): Number of rows to load. If None, loads all rows.
                                     Defaults to DEFAULT_FLIGHTS_SAMPLE_SIZE.
        encoding (str): File encoding. Defaults to 'utf-8'.

    Returns:
        pd.DataFrame: Loaded data as a pandas DataFrame.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        ValueError: If sample_size is invalid (≤ 0).
        Exception: For unexpected pandas read_csv errors.

    Notes:
        - Default sample_size is 100,000 rows if not specified
        - Uses skiprows strategy for memory efficiency
        - Logs sampling information for audit and debugging
        - Suitable for large datasets (100 MB - 1 GB+)
    """
    try:
        if not file_path.exists():
            logger.error(f"Large fact table file not found: {file_path}")
            raise FileNotFoundError(f"File does not exist: {file_path}")

        # Use default sample size if not provided
        if sample_size is None:
            sample_size = DEFAULT_FLIGHTS_SAMPLE_SIZE

        # Validate sample size
        if sample_size <= 0:
            raise ValueError(f"sample_size must be positive, got: {sample_size}")

        logger.info(
            f"Loading {table_name} fact table from: {file_path} "
            f"(sample_size: {sample_size:,} rows)"
        )

        # Load with skiprows for sampling large files
        # Skip every nth row to approximately achieve desired sample size
        df = pd.read_csv(file_path, encoding=encoding, nrows=sample_size)

        logger.info(
            f"Successfully loaded {table_name}: "
            f"{len(df)} rows, {len(df.columns)} columns "
            f"(sample_size requested: {sample_size:,})"
        )

        return df

    except FileNotFoundError as e:
        logger.error(f"FileNotFoundError while loading {table_name}: {str(e)}")
        raise

    except ValueError as e:
        logger.error(f"ValueError: Invalid sample_size parameter: {str(e)}")
        raise

    except Exception as e:
        logger.error(
            f"Unexpected error loading {table_name}: {type(e).__name__}: {str(e)}"
        )
        raise


# ============================================================================
# DATA PROFILING FUNCTIONS
# ============================================================================

def profile_dataframe(df: pd.DataFrame, table_name: str = "table") -> Dict:
    """
    Generate comprehensive data profiling metrics for a DataFrame.

    This function calculates key profiling statistics without modifying
    the input DataFrame. It provides insights into data shape, quality,
    and memory characteristics.

    Args:
        df (pd.DataFrame): Input DataFrame to profile.
        table_name (str): Human-readable table name for logging. Defaults to "table".

    Returns:
        Dict: Dictionary containing profiling metrics:
            - row_count (int): Number of rows
            - column_count (int): Number of columns
            - column_names (list): List of column names
            - memory_usage_mb (float): Memory usage in MB
            - memory_usage_gb (float): Memory usage in GB
            - dtypes (dict): Data types of all columns

    Notes:
        - Memory calculation includes index and metadata
        - Provides both MB and GB for flexibility
        - Suitable for logging and monitoring
        - Non-destructive operation (does not modify input)
    """
    try:
        row_count = len(df)
        column_count = len(df.columns)
        column_names = df.columns.tolist()

        # Calculate memory usage in bytes, convert to MB and GB
        memory_bytes = df.memory_usage(deep=True).sum()
        memory_mb = memory_bytes / (1024 ** 2)
        memory_gb = memory_bytes / (1024 ** 3)

        # Get data types for all columns
        dtypes = df.dtypes.to_dict()

        profile_dict = {
            'row_count': row_count,
            'column_count': column_count,
            'column_names': column_names,
            'memory_usage_mb': round(memory_mb, 2),
            'memory_usage_gb': round(memory_gb, 4),
            'dtypes': dtypes
        }

        logger.debug(f"Profiling complete for {table_name}: {row_count} rows, {memory_mb:.2f} MB")

        return profile_dict

    except Exception as e:
        logger.error(f"Error profiling {table_name}: {type(e).__name__}: {str(e)}")
        raise


def print_data_profile(profile: Dict, table_name: str) -> None:
    """
    Print formatted data profiling information to console.

    Displays key metrics in a readable format suitable for data validation
    and operational monitoring.

    Args:
        profile (Dict): Profiling dictionary from profile_dataframe().
        table_name (str): Human-readable table name for display.

    Returns:
        None

    Notes:
        - Formats memory usage with appropriate units
        - Displays column names in a readable list format
        - Useful for data validation and ETL monitoring
    """
    print(f"\n{'='*70}")
    print(f"DATA PROFILE: {table_name.upper()}")
    print(f"{'='*70}")
    print(f"Row Count:           {profile['row_count']:,}")
    print(f"Column Count:        {profile['column_count']}")
    print(f"Memory Usage:        {profile['memory_usage_mb']:.2f} MB ({profile['memory_usage_gb']:.4f} GB)")
    print(f"\nColumn Names ({len(profile['column_names'])} total):")
    for i, col in enumerate(profile['column_names'], 1):
        print(f"  {i:2d}. {col}")
    print(f"{'='*70}\n")


# ============================================================================
# ORCHESTRATION FUNCTION
# ============================================================================

def extract_all_data(
    flights_sample_size: Optional[int] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Orchestrate complete data extraction pipeline for all datasets.

    This is the main entry point for the extraction phase. It loads all required
    datasets (airlines, airports, flights), performs data profiling, and returns
    them as a tuple for use by downstream Transform and Load phases.

    Args:
        flights_sample_size (Optional[int]): Number of rows to load from flights.csv.
                                             If None, uses DEFAULT_FLIGHTS_SAMPLE_SIZE.
                                             Defaults to None.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: Tuple containing:
            - df_airlines: Airlines reference table
            - df_airports: Airports reference table
            - df_flights: Flights fact table (sampled)

    Raises:
        Exception: If any dataset fails to load (logged and re-raised).

    Notes:
        - Designed for reusability by Transform and Load phases
        - Includes comprehensive data profiling and reporting
        - All errors are logged for audit trail
        - Returns data in consistent order for downstream use
    """
    logger.info("=" * 70)
    logger.info("STARTING DATA EXTRACTION PIPELINE")
    logger.info("=" * 70)

    try:
        # Load airlines reference table
        logger.info("Phase 1/3: Loading airlines reference table...")
        df_airlines = load_reference_table(AIRLINES_FILE, table_name="airlines")
        profile_airlines = profile_dataframe(df_airlines, table_name="airlines")
        print_data_profile(profile_airlines, table_name="airlines")

        # Load airports reference table
        logger.info("Phase 2/3: Loading airports reference table...")
        df_airports = load_reference_table(AIRPORTS_FILE, table_name="airports")
        profile_airports = profile_dataframe(df_airports, table_name="airports")
        print_data_profile(profile_airports, table_name="airports")

        # Load flights fact table with sampling
        logger.info("Phase 3/3: Loading flights fact table (with sampling)...")
        df_flights = load_large_fact_table(
            FLIGHTS_FILE,
            table_name="flights",
            sample_size=flights_sample_size
        )
        profile_flights = profile_dataframe(df_flights, table_name="flights")
        print_data_profile(profile_flights, table_name="flights")

        # Summary statistics
        total_rows = (
            profile_airlines['row_count'] +
            profile_airports['row_count'] +
            profile_flights['row_count']
        )
        total_memory_mb = (
            profile_airlines['memory_usage_mb'] +
            profile_airports['memory_usage_mb'] +
            profile_flights['memory_usage_mb']
        )

        logger.info("=" * 70)
        logger.info("DATA EXTRACTION PIPELINE COMPLETED SUCCESSFULLY")
        logger.info(f"Total Rows Loaded: {total_rows:,}")
        logger.info(f"Total Memory Used: {total_memory_mb:.2f} MB")
        logger.info("=" * 70)

        return df_airlines, df_airports, df_flights

    except Exception as e:
        logger.error(f"EXTRACTION PIPELINE FAILED: {type(e).__name__}: {str(e)}")
        raise


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main() -> int:
    """
    Main entry point for the extraction module when run as a script.

    This function executes the complete extraction pipeline and handles
    exit codes appropriately for automation and monitoring.

    Returns:
        int: Exit code (0 for success, 1 for failure).

    Notes:
        - Suitable for scheduling (e.g., with task schedulers or orchestrators)
        - Provides clear success/failure indicators
        - All errors are logged with details
    """
    try:
        logger.info("Initializing AirFlow Data Extraction Module")
        logger.info(f"Project Root: {PROJECT_ROOT}")
        logger.info(f"Data Directory: {DATA_RAW_DIR}")

        # Execute extraction pipeline
        df_airlines, df_airports, df_flights = extract_all_data(
            flights_sample_size=DEFAULT_FLIGHTS_SAMPLE_SIZE
        )

        logger.info("Extraction module execution completed successfully")
        return 0

    except FileNotFoundError as e:
        logger.error(f"Data file not found: {str(e)}")
        return 1

    except Exception as e:
        logger.error(f"Unexpected error in main execution: {type(e).__name__}: {str(e)}")
        return 1


# ============================================================================
# SCRIPT EXECUTION
# ============================================================================

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
