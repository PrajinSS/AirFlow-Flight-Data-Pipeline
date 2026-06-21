"""
Load Module for AirFlow ETL Pipeline.

This module handles the load phase of the ETL pipeline, providing:
- SQLite database initialization and table creation
- Data loading from cleaned CSV into normalized tables
- Referential integrity with foreign keys
- Row count validation
- Analytics metrics generation
- Professional reporting

Data Model:
- Dimension Table: airlines (airline reference data)
- Dimension Table: airports (airport reference data)
- Fact Table: flights (transactional flight data with foreign keys)

Author: Data Engineering Team
Version: 1.0.0
Last Updated: 2026-06-18
"""

import logging
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Tuple, Any, Optional

import pandas as pd

# ============================================================================
# CONFIGURATION & SETUP
# ============================================================================


def _setup_logging() -> logging.Logger:
    """
    Initialize logging with idempotent handler setup.

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    log = logging.getLogger(__name__)

    if not log.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        log.addHandler(handler)
        log.setLevel(logging.INFO)

    return log


logger = _setup_logging()

# Define project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_CLEANED_PATH = PROJECT_ROOT / "data" / "cleaned"
DATABASE_PATH = PROJECT_ROOT / "database"
REPORTS_PATH = PROJECT_ROOT / "reports"

# Ensure output directories exist
DATABASE_PATH.mkdir(parents=True, exist_ok=True)
REPORTS_PATH.mkdir(parents=True, exist_ok=True)

# Database configuration
DB_FILE = DATABASE_PATH / "airflow.db"
CLEANED_CSV = DATA_CLEANED_PATH / "flights_cleaned.csv"

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================


def create_database(db_path: Path) -> Path:
    """
    Create SQLite database file if it doesn't exist.

    Database is created with WAL (Write-Ahead Logging) mode for better
    concurrency and crash recovery.

    Parameters
    ----------
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    Path
        Path to the created database file.

    Raises
    ------
    IOError
        If database cannot be created.
    """
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.close()
        logger.debug(f"Database created/verified: {db_path}")
        return db_path
    except IOError as e:
        logger.error(f"Error creating database at {db_path}: {e}")
        raise


def create_tables(conn: sqlite3.Connection) -> None:
    """
    Create normalized dimension and fact tables in SQLite database.

    Tables:
    - airlines: Dimension table for airline reference data
    - airports: Dimension table for airport reference data
    - flights: Fact table with foreign keys to dimensions

    Existing tables are dropped and recreated (safe via transaction).

    Parameters
    ----------
    conn : sqlite3.Connection
        Active SQLite database connection.

    Raises
    ------
    sqlite3.Error
        If table creation fails.
    """
    cursor = conn.cursor()

    try:
        # Drop existing tables if they exist (idempotent)
        cursor.execute("DROP TABLE IF EXISTS flights;")
        cursor.execute("DROP TABLE IF EXISTS airports;")
        cursor.execute("DROP TABLE IF EXISTS airlines;")

        # Create airlines dimension table
        cursor.execute("""
            CREATE TABLE airlines (
                AIRLINE_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                AIRLINE TEXT UNIQUE NOT NULL,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create airports dimension table
        cursor.execute("""
            CREATE TABLE airports (
                AIRPORT_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                AIRPORT TEXT UNIQUE NOT NULL,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create flights fact table with all original columns
        # Foreign keys reference airline and airport dimensions
        # Columns based on typical flight data model with all common fields
        cursor.execute("""
            CREATE TABLE flights (
                FLIGHT_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                YEAR INTEGER,
                MONTH INTEGER,
                DAY INTEGER,
                DAY_OF_WEEK INTEGER,
                FLIGHT_NUMBER TEXT,
                AIRLINE_ID INTEGER NOT NULL,
                ORIGIN_AIRPORT_ID INTEGER NOT NULL,
                DESTINATION_AIRPORT_ID INTEGER NOT NULL,
                SCHEDULED_DEPARTURE INTEGER,
                DEPARTURE_TIME INTEGER,
                DEPARTURE_DELAY INTEGER,
                TAXI_OUT INTEGER,
                WHEELS_OFF INTEGER,
                SCHEDULED_TIME INTEGER,
                ELAPSED_TIME INTEGER,
                AIR_TIME INTEGER,
                DISTANCE INTEGER,
                WHEELS_ON INTEGER,
                TAXI_IN INTEGER,
                SCHEDULED_ARRIVAL INTEGER,
                ARRIVAL_TIME INTEGER,
                ARRIVAL_DELAY INTEGER,
                DIVERTED INTEGER,
                CANCELLED INTEGER,
                CANCELLATION_REASON TEXT,
                AIR_SYSTEM_DELAY INTEGER,
                SECURITY_DELAY INTEGER,
                AIRLINE_DELAY INTEGER,
                LATE_AIRCRAFT_DELAY INTEGER,
                WEATHER_DELAY INTEGER,
                AIRCRAFT_ID TEXT,
                AIRCRAFT_TYPE TEXT,
                MANUFACTURER TEXT,
                MODEL TEXT,
                TAIL_NUMBER TEXT,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (AIRLINE_ID) REFERENCES airlines(AIRLINE_ID),
                FOREIGN KEY (ORIGIN_AIRPORT_ID) REFERENCES airports(AIRPORT_ID),
                FOREIGN KEY (DESTINATION_AIRPORT_ID) REFERENCES airports(AIRPORT_ID)
            );
        """)

        # Create indices for common query patterns
        cursor.execute("CREATE INDEX idx_flights_airline_id ON flights(AIRLINE_ID);")
        cursor.execute("CREATE INDEX idx_flights_origin ON flights(ORIGIN_AIRPORT_ID);")
        cursor.execute("CREATE INDEX idx_flights_destination ON flights(DESTINATION_AIRPORT_ID);")
        cursor.execute("CREATE INDEX idx_flights_departure_delay ON flights(DEPARTURE_DELAY);")
        cursor.execute("CREATE INDEX idx_flights_arrival_delay ON flights(ARRIVAL_DELAY);")
        cursor.execute("CREATE INDEX idx_flights_cancelled ON flights(CANCELLED);")
        cursor.execute("CREATE INDEX idx_flights_diverted ON flights(DIVERTED);")
        cursor.execute("CREATE INDEX idx_flights_flight_number ON flights(FLIGHT_NUMBER);")

        conn.commit()
        logger.info("Database tables created successfully")

    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"Error creating tables: {e}")
        raise


# ============================================================================
# DATA EXTRACTION & LOADING
# ============================================================================


def extract_airlines(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract unique airlines from flights data and create dimension table.

    Parameters
    ----------
    df : pd.DataFrame
        Flights DataFrame with AIRLINE column.

    Returns
    -------
    pd.DataFrame
        Airlines dimension table with AIRLINE column.
        Index becomes AIRLINE_ID upon database insertion.

    Raises
    ------
    ValueError
        If AIRLINE column is missing or no airlines found.
    """
    if "AIRLINE" not in df.columns:
        raise ValueError("AIRLINE column not found in DataFrame")

    airlines_df = df[["AIRLINE"]].drop_duplicates().reset_index(drop=True)

    if airlines_df.empty:
        raise ValueError("No airlines found in data")

    logger.debug(f"Extracted {len(airlines_df)} unique airlines")

    return airlines_df


def extract_airports(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract unique airports from origin and destination columns.

    Airports can appear as both origin and destination, so deduplication
    is performed across both columns.

    Parameters
    ----------
    df : pd.DataFrame
        Flights DataFrame with ORIGIN_AIRPORT and DESTINATION_AIRPORT columns.

    Returns
    -------
    pd.DataFrame
        Airports dimension table with AIRPORT column.
        Index becomes AIRPORT_ID upon database insertion.

    Raises
    ------
    ValueError
        If airport columns are missing or no airports found.
    """
    required_cols = ["ORIGIN_AIRPORT", "DESTINATION_AIRPORT"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing airport columns: {missing_cols}")

    # Combine origin and destination airports, deduplicate
    origin_airports = df[["ORIGIN_AIRPORT"]].rename(
        columns={"ORIGIN_AIRPORT": "AIRPORT"}
    )
    dest_airports = df[["DESTINATION_AIRPORT"]].rename(
        columns={"DESTINATION_AIRPORT": "AIRPORT"}
    )

    airports_df = pd.concat(
        [origin_airports, dest_airports], ignore_index=True
    ).drop_duplicates().reset_index(drop=True)

    if airports_df.empty:
        raise ValueError("No airports found in data")

    logger.debug(f"Extracted {len(airports_df)} unique airports")

    return airports_df


def get_sqlite_table_schema(conn: sqlite3.Connection, table_name: str) -> Dict[str, str]:
    """
    Retrieve the schema (column names and types) from a SQLite table.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active SQLite database connection.
    table_name : str
        Name of the table to inspect.

    Returns
    -------
    Dict[str, str]
        Dictionary mapping column names to their data types.

    Raises
    ------
    sqlite3.Error
        If table doesn't exist or query fails.
    """
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    schema = {}
    for row in cursor.fetchall():
        column_name = row[1]
        column_type = row[2]
        schema[column_name] = column_type
    return schema


def validate_dataframe_schema(
    df: pd.DataFrame,
    conn: sqlite3.Connection,
    table_name: str = "flights",
    exclude_columns: Optional[list] = None
) -> Dict[str, Any]:
    """
    Validate that DataFrame columns match SQLite table schema.

    Compares DataFrame column names against SQLite table columns and identifies:
    - Missing columns (in DataFrame but not in table)
    - Extra columns (in table but not in DataFrame)
    - Column count differences

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to validate.
    conn : sqlite3.Connection
        Active SQLite database connection.
    table_name : str, optional
        Name of the SQLite table to compare against. Default is "flights".
    exclude_columns : list, optional
        List of columns to exclude from comparison (e.g., dimension FKs).
        Default is None.

    Returns
    -------
    Dict[str, Any]
        Validation result containing:
        - is_valid: Boolean indicating if validation passed
        - dataframe_columns: List of DataFrame columns
        - table_columns: List of SQLite table columns
        - missing_from_table: Columns in DataFrame but not in table
        - extra_in_table: Columns in table but not in DataFrame
        - column_count_df: Number of DataFrame columns
        - column_count_table: Number of SQLite table columns

    Raises
    ------
    ValueError
        If validation fails and critical columns are missing.
    """
    if exclude_columns is None:
        exclude_columns = []

    # Get DataFrame columns (excluding specified columns)
    df_columns = [col for col in df.columns if col not in exclude_columns]

    # Get SQLite table schema
    try:
        table_schema = get_sqlite_table_schema(conn, table_name)
        table_columns = [col for col in table_schema.keys() 
                        if col not in ["FLIGHT_ID", "CREATED_AT"]]  # Exclude auto-generated
    except sqlite3.Error as e:
        logger.error(f"Error retrieving table schema: {e}")
        raise ValueError(f"Cannot access table {table_name}: {e}")

    # Identify mismatches
    df_cols_set = set(df_columns)
    table_cols_set = set(table_columns)

    missing_from_table = df_cols_set - table_cols_set
    extra_in_table = table_cols_set - df_cols_set

    # Prepare result
    result = {
        "is_valid": len(missing_from_table) == 0,
        "dataframe_columns": sorted(df_columns),
        "table_columns": sorted(table_columns),
        "missing_from_table": sorted(missing_from_table),
        "extra_in_table": sorted(extra_in_table),
        "column_count_df": len(df_columns),
        "column_count_table": len(table_columns)
    }

    # Log validation results
    logger.info(f"Schema Validation for table '{table_name}':")
    logger.info(f"  DataFrame columns:    {result['column_count_df']}")
    logger.info(f"  SQLite table columns: {result['column_count_table']}")

    if missing_from_table:
        logger.warning(f"⚠ Columns in DataFrame but NOT in table: {sorted(missing_from_table)}")
        logger.debug(f"  These columns will be ignored during insert")

    if extra_in_table:
        logger.warning(f"⚠ Columns in table but NOT in DataFrame: {sorted(extra_in_table)}")
        logger.debug(f"  These columns will use NULL/default values")

    if result["is_valid"]:
        logger.info(f"✓ Schema validation PASSED - all DataFrame columns exist in table")
    else:
        logger.error(f"✗ Schema validation FAILED - {len(missing_from_table)} columns missing from table")
        logger.error(f"  Missing columns will cause INSERT to fail")

    return result


def select_compatible_columns(
    df: pd.DataFrame,
    conn: sqlite3.Connection,
    table_name: str = "flights",
    exclude_columns: Optional[list] = None
) -> pd.DataFrame:
    """
    Filter DataFrame to only include columns that exist in the SQLite table.

    This function ensures that only compatible columns are selected for insertion.
    Extra columns in the DataFrame are dropped; missing columns in the table
    are safely ignored.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to filter.
    conn : sqlite3.Connection
        Active SQLite database connection.
    table_name : str, optional
        Name of the SQLite table. Default is "flights".
    exclude_columns : list, optional
        List of columns to exclude from selection. Default is None.

    Returns
    -------
    pd.DataFrame
        DataFrame with only columns that exist in the SQLite table.

    Raises
    ------
    ValueError
        If no compatible columns are found.
    """
    if exclude_columns is None:
        exclude_columns = []

    # Get SQLite table schema
    table_schema = get_sqlite_table_schema(conn, table_name)
    table_columns = set(table_schema.keys()) - {"FLIGHT_ID", "CREATED_AT"}

    # Filter DataFrame to only include columns in the table
    available_columns = [col for col in df.columns 
                         if col in table_columns and col not in exclude_columns]

    if not available_columns:
        raise ValueError(f"No compatible columns found between DataFrame and {table_name} table")

    logger.debug(f"Selecting {len(available_columns)} compatible columns for insertion")

    return df[available_columns]


def load_data_to_sqlite(
    df: pd.DataFrame,
    conn: sqlite3.Connection,
    verbose: bool = False
) -> Dict[str, int]:
    """
    Load cleaned flight data into SQLite database with dimension tables.

    Process:
    1. Extract and load airlines dimension
    2. Extract and load airports dimension
    3. Map airline/airport codes to their IDs
    4. Validate schema compatibility
    5. Select only compatible columns
    6. Load flights fact table with foreign keys

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned flights DataFrame.
    conn : sqlite3.Connection
        Active SQLite database connection.
    verbose : bool, optional
        If True, log detailed progress. Default is False.

    Returns
    -------
    Dict[str, int]
        Dictionary with row counts for each table:
        - airlines: Number of airlines loaded
        - airports: Number of airports loaded
        - flights: Number of flights loaded

    Raises
    ------
    ValueError
        If required columns are missing or data is invalid.
    sqlite3.Error
        If database operations fail.
    """
    if df.empty:
        raise ValueError("Input DataFrame is empty")

    logger.info("Loading data into SQLite database...")

    try:
        # Step 1: Extract and load airlines
        logger.info("Step 1: Loading airlines dimension...")
        airlines_df = extract_airlines(df)
        airlines_df.to_sql(
            "airlines",
            conn,
            if_exists="append",
            index=False,
            index_label="AIRLINE_ID"
        )
        num_airlines = len(airlines_df)
        logger.info(f"  ✓ Loaded {num_airlines} airlines")

        # Step 2: Extract and load airports
        logger.info("Step 2: Loading airports dimension...")
        airports_df = extract_airports(df)
        airports_df.to_sql(
            "airports",
            conn,
            if_exists="append",
            index=False,
            index_label="AIRPORT_ID"
        )
        num_airports = len(airports_df)
        logger.info(f"  ✓ Loaded {num_airports} airports")

        # Step 3: Create lookup dictionaries for mapping codes to IDs
        logger.info("Step 3: Creating airline/airport ID mappings...")
        airlines_lookup_cursor = conn.execute(
            "SELECT AIRLINE_ID, AIRLINE FROM airlines;"
        )
        airlines_lookup = {row[1]: row[0] for row in airlines_lookup_cursor.fetchall()}

        airports_lookup_cursor = conn.execute(
            "SELECT AIRPORT_ID, AIRPORT FROM airports;"
        )
        airports_lookup = {row[1]: row[0] for row in airports_lookup_cursor.fetchall()}
        logger.info(f"  ✓ Created lookup dictionaries")

        # Step 4: Prepare flights data with foreign keys
        logger.info("Step 4: Preparing flights fact table...")
        df_flights = df.copy()

        # Map airline codes to IDs
        df_flights["AIRLINE_ID"] = df_flights["AIRLINE"].map(airlines_lookup)
        if df_flights["AIRLINE_ID"].isnull().any():
            null_airlines = df_flights[df_flights["AIRLINE_ID"].isnull()]["AIRLINE"].unique()
            logger.warning(f"Some airlines not found in lookup: {null_airlines}")

        # Map origin airport codes to IDs
        df_flights["ORIGIN_AIRPORT_ID"] = df_flights["ORIGIN_AIRPORT"].map(
            airports_lookup
        )
        if df_flights["ORIGIN_AIRPORT_ID"].isnull().any():
            null_origins = df_flights[df_flights["ORIGIN_AIRPORT_ID"].isnull()][
                "ORIGIN_AIRPORT"
            ].unique()
            logger.warning(f"Some origin airports not found: {null_origins}")

        # Map destination airport codes to IDs
        df_flights["DESTINATION_AIRPORT_ID"] = df_flights["DESTINATION_AIRPORT"].map(
            airports_lookup
        )
        if df_flights["DESTINATION_AIRPORT_ID"].isnull().any():
            null_dests = df_flights[df_flights["DESTINATION_AIRPORT_ID"].isnull()][
                "DESTINATION_AIRPORT"
            ].unique()
            logger.warning(f"Some destination airports not found: {null_dests}")

        logger.info(f"  ✓ Prepared {len(df_flights)} flights with foreign key mappings")

        # Step 5: Validate schema compatibility
        logger.info("Step 5: Validating schema compatibility...")
        exclude_cols = ["AIRLINE", "ORIGIN_AIRPORT", "DESTINATION_AIRPORT"]
        schema_result = validate_dataframe_schema(
            df_flights,
            conn,
            table_name="flights",
            exclude_columns=exclude_cols
        )

        # Step 6: Select only compatible columns
        logger.info("Step 6: Selecting compatible columns...")
        df_flights_final = select_compatible_columns(
            df_flights,
            conn,
            table_name="flights",
            exclude_columns=exclude_cols
        )
        logger.info(f"  ✓ Selected {len(df_flights_final.columns)} compatible columns for insertion")
        logger.debug(f"    Columns to insert: {list(df_flights_final.columns)}")

        # Step 7: Load flights fact table
        logger.info("Step 7: Loading flights fact table...")
        df_flights_final.to_sql(
            "flights",
            conn,
            if_exists="append",
            index=False
        )
        num_flights = len(df_flights_final)
        logger.info(f"  ✓ Loaded {num_flights:,} flights")

        conn.commit()
        logger.info("✓ Data loaded successfully into all tables")

        return {
            "airlines": num_airlines,
            "airports": num_airports,
            "flights": num_flights
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"✗ Error loading data: {e}", exc_info=True)
        raise


# ============================================================================
# VALIDATION
# ============================================================================


def validate_load(
    source_rows: int,
    loaded_counts: Dict[str, int],
    conn: sqlite3.Connection
) -> bool:
    """
    Validate that data was loaded correctly into database.

    Checks:
    - Flight counts match source CSV
    - All airlines are present
    - All airports are present
    - No NULL foreign key violations

    Parameters
    ----------
    source_rows : int
        Number of rows in source CSV.
    loaded_counts : Dict[str, int]
        Row counts from load_data_to_sqlite().
    conn : sqlite3.Connection
        Active SQLite database connection.

    Returns
    -------
    bool
        True if all validations pass.

    Raises
    ------
    ValueError
        If any validation fails.
    """
    logger.info("Validating data load...")

    cursor = conn.cursor()

    # Check flight counts
    flights_in_db = cursor.execute("SELECT COUNT(*) FROM flights;").fetchone()[0]
    if flights_in_db != source_rows:
        raise ValueError(
            f"Flight count mismatch: expected {source_rows}, got {flights_in_db}"
        )
    logger.debug(f"✓ Flight count validated: {flights_in_db:,} rows")

    # Check airlines count
    airlines_in_db = cursor.execute("SELECT COUNT(*) FROM airlines;").fetchone()[0]
    if airlines_in_db != loaded_counts["airlines"]:
        raise ValueError(
            f"Airlines count mismatch: expected {loaded_counts['airlines']}, "
            f"got {airlines_in_db}"
        )
    logger.debug(f"✓ Airlines count validated: {airlines_in_db} airlines")

    # Check airports count
    airports_in_db = cursor.execute("SELECT COUNT(*) FROM airports;").fetchone()[0]
    if airports_in_db != loaded_counts["airports"]:
        raise ValueError(
            f"Airports count mismatch: expected {loaded_counts['airports']}, "
            f"got {airports_in_db}"
        )
    logger.debug(f"✓ Airports count validated: {airports_in_db} airports")

    # Check for NULL foreign keys (data integrity)
    null_airlines = cursor.execute(
        "SELECT COUNT(*) FROM flights WHERE AIRLINE_ID IS NULL;"
    ).fetchone()[0]
    if null_airlines > 0:
        raise ValueError(f"Found {null_airlines} flights with NULL AIRLINE_ID")
    logger.debug("✓ No NULL airline IDs detected")

    null_origins = cursor.execute(
        "SELECT COUNT(*) FROM flights WHERE ORIGIN_AIRPORT_ID IS NULL;"
    ).fetchone()[0]
    if null_origins > 0:
        raise ValueError(f"Found {null_origins} flights with NULL ORIGIN_AIRPORT_ID")
    logger.debug("✓ No NULL origin airport IDs detected")

    null_destinations = cursor.execute(
        "SELECT COUNT(*) FROM flights WHERE DESTINATION_AIRPORT_ID IS NULL;"
    ).fetchone()[0]
    if null_destinations > 0:
        raise ValueError(f"Found {null_destinations} flights with NULL DESTINATION_AIRPORT_ID")
    logger.debug("✓ No NULL destination airport IDs detected")

    logger.info("Data validation completed successfully")

    return True


# ============================================================================
# ANALYTICS GENERATION
# ============================================================================


def calculate_analytics(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Calculate analytics metrics from loaded flight data.

    Metrics:
    - Total flights, airlines, airports
    - Top 10 airlines by flight count
    - Top 10 origin airports by flight count
    - Top 10 destination airports by flight count
    - Average departure and arrival delays
    - Cancellation rate
    - Diversion rate

    Parameters
    ----------
    conn : sqlite3.Connection
        Active SQLite database connection.

    Returns
    -------
    Dict[str, Any]
        Dictionary containing all calculated metrics.

    Raises
    ------
    sqlite3.Error
        If queries fail.
    """
    logger.info("Calculating analytics metrics...")

    cursor = conn.cursor()
    metrics = {}

    try:
        # Overall counts
        total_flights = cursor.execute(
            "SELECT COUNT(*) FROM flights;"
        ).fetchone()[0]
        metrics["total_flights"] = total_flights

        total_airlines = cursor.execute(
            "SELECT COUNT(*) FROM airlines;"
        ).fetchone()[0]
        metrics["total_airlines"] = total_airlines

        total_airports = cursor.execute(
            "SELECT COUNT(*) FROM airports;"
        ).fetchone()[0]
        metrics["total_airports"] = total_airports

        logger.debug(f"Counts: {total_flights:,} flights, "
                    f"{total_airlines} airlines, {total_airports} airports")

        # Top 10 airlines by flight count
        top_airlines_rows = cursor.execute("""
            SELECT a.AIRLINE, COUNT(f.FLIGHT_ID) as flight_count
            FROM flights f
            JOIN airlines a ON f.AIRLINE_ID = a.AIRLINE_ID
            GROUP BY f.AIRLINE_ID
            ORDER BY flight_count DESC
            LIMIT 10;
        """).fetchall()
        metrics["top_10_airlines"] = [
            {"airline": row[0], "flight_count": row[1]} for row in top_airlines_rows
        ]

        # Top 10 origin airports
        top_origins_rows = cursor.execute("""
            SELECT a.AIRPORT, COUNT(f.FLIGHT_ID) as flight_count
            FROM flights f
            JOIN airports a ON f.ORIGIN_AIRPORT_ID = a.AIRPORT_ID
            GROUP BY f.ORIGIN_AIRPORT_ID
            ORDER BY flight_count DESC
            LIMIT 10;
        """).fetchall()
        metrics["top_10_origin_airports"] = [
            {"airport": row[0], "flight_count": row[1]} for row in top_origins_rows
        ]

        # Top 10 destination airports
        top_destinations_rows = cursor.execute("""
            SELECT a.AIRPORT, COUNT(f.FLIGHT_ID) as flight_count
            FROM flights f
            JOIN airports a ON f.DESTINATION_AIRPORT_ID = a.AIRPORT_ID
            GROUP BY f.DESTINATION_AIRPORT_ID
            ORDER BY flight_count DESC
            LIMIT 10;
        """).fetchall()
        metrics["top_10_destination_airports"] = [
            {"airport": row[0], "flight_count": row[1]} for row in top_destinations_rows
        ]

        # Average delays (handle NULL values)
        avg_delays = cursor.execute("""
            SELECT 
                ROUND(AVG(DEPARTURE_DELAY), 2) as avg_departure_delay,
                ROUND(AVG(ARRIVAL_DELAY), 2) as avg_arrival_delay
            FROM flights
            WHERE DEPARTURE_DELAY IS NOT NULL
            AND ARRIVAL_DELAY IS NOT NULL;
        """).fetchone()
        metrics["avg_departure_delay"] = avg_delays[0] if avg_delays[0] is not None else 0.0
        metrics["avg_arrival_delay"] = avg_delays[1] if avg_delays[1] is not None else 0.0

        # Cancellation rate
        cancellation_stats = cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CANCELLED) as cancelled_count
            FROM flights;
        """).fetchone()
        cancelled_count = cancellation_stats[1] if cancellation_stats[1] is not None else 0
        total_count = cancellation_stats[0]
        metrics["cancellation_rate"] = (cancelled_count / total_count * 100) if total_count > 0 else 0.0
        metrics["cancellation_count"] = cancelled_count

        # Diversion rate
        diversion_stats = cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(DIVERTED) as diverted_count
            FROM flights;
        """).fetchone()
        diverted_count = diversion_stats[1] if diversion_stats[1] is not None else 0
        total_count = diversion_stats[0]
        metrics["diversion_rate"] = (diverted_count / total_count * 100) if total_count > 0 else 0.0
        metrics["diversion_count"] = diverted_count

        logger.info("Analytics metrics calculated successfully")

        return metrics

    except sqlite3.Error as e:
        logger.error(f"Error calculating analytics: {e}")
        raise


# ============================================================================
# REPORTING
# ============================================================================


def format_analytics_report(metrics: Dict[str, Any]) -> str:
    """
    Format analytics metrics into a readable report string.

    Parameters
    ----------
    metrics : Dict[str, Any]
        Metrics dictionary from calculate_analytics().

    Returns
    -------
    str
        Formatted report text.
    """
    report_lines = []

    # Header
    report_lines.append("="*70)
    report_lines.append("AIRFLOW - ANALYTICS REPORT")
    report_lines.append("="*70)
    report_lines.append("")

    # Summary section
    report_lines.append("SUMMARY METRICS")
    report_lines.append("-"*70)
    report_lines.append(f"Total Flights:           {metrics['total_flights']:,}")
    report_lines.append(f"Total Airlines:          {metrics['total_airlines']}")
    report_lines.append(f"Total Airports:          {metrics['total_airports']}")
    report_lines.append(f"Cancellation Rate:       {metrics['cancellation_rate']:.2f}% "
                       f"({metrics['cancellation_count']:,} flights)")
    report_lines.append(f"Diversion Rate:          {metrics['diversion_rate']:.2f}% "
                       f"({metrics['diversion_count']:,} flights)")
    report_lines.append("")

    # Delay analysis section
    report_lines.append("DELAY ANALYSIS")
    report_lines.append("-"*70)
    report_lines.append(f"Average Departure Delay: {metrics['avg_departure_delay']:.2f} minutes")
    report_lines.append(f"Average Arrival Delay:   {metrics['avg_arrival_delay']:.2f} minutes")
    report_lines.append("")

    # Top airlines section
    report_lines.append("TOP 10 AIRLINES BY FLIGHT COUNT")
    report_lines.append("-"*70)
    for idx, airline in enumerate(metrics["top_10_airlines"], 1):
        report_lines.append(f"{idx:2d}. {airline['airline']:5s} - {airline['flight_count']:,} flights")
    report_lines.append("")

    # Top origin airports section
    report_lines.append("TOP 10 ORIGIN AIRPORTS")
    report_lines.append("-"*70)
    for idx, airport in enumerate(metrics["top_10_origin_airports"], 1):
        report_lines.append(f"{idx:2d}. {airport['airport']:5s} - {airport['flight_count']:,} flights")
    report_lines.append("")

    # Top destination airports section
    report_lines.append("TOP 10 DESTINATION AIRPORTS")
    report_lines.append("-"*70)
    for idx, airport in enumerate(metrics["top_10_destination_airports"], 1):
        report_lines.append(f"{idx:2d}. {airport['airport']:5s} - {airport['flight_count']:,} flights")
    report_lines.append("")

    # Footer
    report_lines.append("="*70)
    report_lines.append("END OF REPORT")
    report_lines.append("="*70)

    return "\n".join(report_lines)


def save_analytics_report(report_text: str, report_path: Path) -> Path:
    """
    Save formatted analytics report to file.

    Parameters
    ----------
    report_text : str
        Formatted report text from format_analytics_report().
    report_path : Path
        Path to save report file.

    Returns
    -------
    Path
        Path to saved report file.

    Raises
    ------
    IOError
        If file cannot be written.
    """
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        logger.debug(f"Analytics report saved: {report_path}")
        return report_path
    except IOError as e:
        logger.error(f"Error writing analytics report to {report_path}: {e}")
        raise


# ============================================================================
# ORCHESTRATION
# ============================================================================


def load_flights_data(
    csv_path: Path,
    db_path: Path
) -> Dict[str, Any]:
    """
    Execute complete load pipeline: read CSV → create DB → load → validate → analytics.

    Pipeline Steps:
    1. Verify CSV file exists
    2. Read cleaned flight data
    3. Create SQLite database
    4. Create normalized tables
    5. Load data with foreign keys
    6. Validate row counts and integrity
    7. Calculate analytics metrics
    8. Generate and save report

    Parameters
    ----------
    csv_path : Path
        Path to cleaned flights CSV file.
    db_path : Path
        Path to SQLite database file.

    Returns
    -------
    Dict[str, Any]
        Metadata containing:
        - database_path: Path to created database
        - report_path: Path to analytics report
        - source_rows: Row count from CSV
        - loaded_rows: Row counts per table
        - metrics: Analytics metrics

    Raises
    ------
    FileNotFoundError
        If CSV file not found.
    Exception
        If any load step fails (wrapped in error logging).
    """
    logger.info("Starting load pipeline...")

    # Step 0: Verify source file
    if not csv_path.exists():
        raise FileNotFoundError(f"Cleaned CSV not found: {csv_path}")
    logger.info(f"Source CSV found: {csv_path}")

    try:
        # Step 1: Read cleaned data
        logger.info("Step 1: Reading cleaned flight data...")
        df_flights = pd.read_csv(csv_path)
        source_rows = len(df_flights)
        logger.info(f"Read {source_rows:,} rows from CSV")

        # Step 2: Create database
        logger.info("Step 2: Creating SQLite database...")
        create_database(db_path)

        # Step 3: Open connection and create tables
        logger.info("Step 3: Creating database tables...")
        conn = sqlite3.connect(str(db_path))
        create_tables(conn)

        # Step 4: Load data
        logger.info("Step 4: Loading data into database...")
        loaded_counts = load_data_to_sqlite(df_flights, conn, verbose=True)
        logger.info(f"Loaded: {loaded_counts['airlines']} airlines, "
                   f"{loaded_counts['airports']} airports, "
                   f"{loaded_counts['flights']:,} flights")

        # Step 5: Validate
        logger.info("Step 5: Validating data load...")
        validate_load(source_rows, loaded_counts, conn)

        # Step 6: Calculate analytics
        logger.info("Step 6: Calculating analytics metrics...")
        metrics = calculate_analytics(conn)

        # Step 7: Generate and save report
        logger.info("Step 7: Generating analytics report...")
        report_text = format_analytics_report(metrics)
        report_path = REPORTS_PATH / "analytics_report.txt"
        save_analytics_report(report_text, report_path)
        logger.info(f"Analytics report saved: {report_path}")

        # Close connection
        conn.close()

        # Compile metadata
        metadata = {
            "database_path": str(db_path),
            "report_path": str(report_path),
            "source_rows": source_rows,
            "loaded_rows": loaded_counts,
            "metrics": metrics
        }

        logger.info("Load pipeline completed successfully")

        return metadata

    except Exception as e:
        logger.error(f"Load pipeline failed: {e}", exc_info=True)
        raise


def main() -> int:
    """
    Main entry point for the load module.

    Workflow:
    1. Execute load pipeline
    2. Display execution summary
    3. Return success/failure exit code

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    logger.info("="*70)
    logger.info("AirFlow Load Phase - ETL Pipeline")
    logger.info("="*70)

    try:
        # Execute load pipeline
        metadata = load_flights_data(CLEANED_CSV, DB_FILE)

        # Display execution summary
        print("\n" + "="*70)
        print("LOAD PHASE SUMMARY")
        print("="*70)
        print(f"Source CSV:              {CLEANED_CSV}")
        print(f"Rows Loaded:             {metadata['source_rows']:,}")
        print(f"\nDatabase: {metadata['database_path']}")
        print(f"  - Airlines:            {metadata['loaded_rows']['airlines']}")
        print(f"  - Airports:            {metadata['loaded_rows']['airports']}")
        print(f"  - Flights:             {metadata['loaded_rows']['flights']:,}")
        print(f"\nAnalytics Report:        {metadata['report_path']}")
        print(f"\nTop Airline:             {metadata['metrics']['top_10_airlines'][0]['airline']} "
              f"({metadata['metrics']['top_10_airlines'][0]['flight_count']:,} flights)")
        print(f"Cancellation Rate:       {metadata['metrics']['cancellation_rate']:.2f}%")
        print(f"Avg Departure Delay:     {metadata['metrics']['avg_departure_delay']:.2f} min")
        print(f"Avg Arrival Delay:       {metadata['metrics']['avg_arrival_delay']:.2f} min")
        print("="*70 + "\n")

        logger.info("Load phase completed successfully!")

        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except Exception as e:
        logger.error(f"Load phase failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
