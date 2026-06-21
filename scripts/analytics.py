"""
Analytics Module for AirFlow ETL Pipeline.

This module reads cleaned data from SQLite, computes analytical datasets using
highly optimized SQL queries (CTEs, JOINs, CASE WHEN, COALESCE, GROUP BY),
saves them as CSV files, and generates a formatted text summary report.

Features:
- Validates database and table existence before running queries.
- Creates directories automatically if they do not exist.
- Implements comprehensive error handling and logging.
- Conforms to PEP8 style guidelines, NumPy-style docstrings, and strict type hints.
- Displays a professional summary of the execution phase.

Execution:
    python scripts/analytics.py
"""

import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd

# ============================================================================
# CONFIGURATION & LOGGING SETUP
# ============================================================================


def _setup_logging() -> logging.Logger:
    """
    Initialize logging with idempotent handler setup.

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    log = logging.getLogger("AirFlow.Analytics")

    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        log.addHandler(handler)
        log.setLevel(logging.INFO)

    return log


logger = _setup_logging()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "airflow.db"
ANALYTICS_DATA_DIR = PROJECT_ROOT / "data" / "analytics"
REPORTS_DIR = PROJECT_ROOT / "reports"
SUMMARY_REPORT_PATH = REPORTS_DIR / "analytics_summary.txt"

# Ensure output directories exist
if ANALYTICS_DATA_DIR.exists() and not ANALYTICS_DATA_DIR.is_dir():
    logger.warning(f"File exists at {ANALYTICS_DATA_DIR}. Removing it to create directory.")
    ANALYTICS_DATA_DIR.unlink()
ANALYTICS_DATA_DIR.mkdir(parents=True, exist_ok=True)

if REPORTS_DIR.exists() and not REPORTS_DIR.is_dir():
    logger.warning(f"File exists at {REPORTS_DIR}. Removing it to create directory.")
    REPORTS_DIR.unlink()
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# VALIDATION CHECKS
# ============================================================================


def validate_database_and_tables(db_path: Path) -> bool:
    """
    Validate that the database file exists and contains the required tables.

    Parameters
    ----------
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    bool
        True if the database is valid, False otherwise.
    """
    logger.info(f"Validating database file at: {db_path}")

    if not db_path.exists():
        logger.error(f"Database file not found: {db_path}")
        return False

    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            # Fetch all user tables in the database
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cursor.fetchall()}

            required_tables = {"airlines", "airports", "flights"}
            missing_tables = required_tables - tables

            if missing_tables:
                logger.error(f"Missing required tables in database: {missing_tables}")
                return False

            # Verify flights table has records
            cursor.execute("SELECT COUNT(*) FROM flights;")
            count = cursor.fetchone()[0]
            if count == 0:
                logger.warning("The 'flights' table is empty. Analytics will be based on empty data.")

            logger.info("Database and table validation checks passed successfully.")
            return True

    except sqlite3.Error as e:
        logger.error(f"SQLite connection or query failed during validation: {e}")
        return False


# ============================================================================
# ANALYTICS COMPILATION
# ============================================================================


def get_executive_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Generate the Executive Summary dataset using SQL aggregations.

    Calculates: Total Flights, Total Airlines, Total Airports, Cancellation Rate,
    Diversion Rate, Average Departure Delay, and Average Arrival Delay.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active connection to the SQLite database.

    Returns
    -------
    pd.DataFrame
        DataFrame containing a single row of executive summary statistics.
    """
    logger.info("Computing Executive Summary dataset...")
    query = """
    WITH stats AS (
        SELECT 
            COUNT(*) as TOTAL_FLIGHTS,
            SUM(CASE WHEN CANCELLED = 1 THEN 1 ELSE 0 END) as cancelled_count,
            SUM(CASE WHEN DIVERTED = 1 THEN 1 ELSE 0 END) as diverted_count,
            AVG(DEPARTURE_DELAY) as avg_dep_delay,
            AVG(ARRIVAL_DELAY) as avg_arr_delay
        FROM flights
    ),
    dims AS (
        SELECT
            (SELECT COUNT(*) FROM airlines) as TOTAL_AIRLINES,
            (SELECT COUNT(*) FROM airports) as TOTAL_AIRPORTS
    )
    SELECT 
        stats.TOTAL_FLIGHTS,
        dims.TOTAL_AIRLINES,
        dims.TOTAL_AIRPORTS,
        ROUND(COALESCE((stats.cancelled_count * 100.0) / stats.TOTAL_FLIGHTS, 0.0), 4) as CANCELLATION_RATE,
        ROUND(COALESCE((stats.diverted_count * 100.0) / stats.TOTAL_FLIGHTS, 0.0), 4) as DIVERSION_RATE,
        ROUND(COALESCE(stats.avg_dep_delay, 0.0), 2) as AVG_DEPARTURE_DELAY,
        ROUND(COALESCE(stats.avg_arr_delay, 0.0), 2) as AVG_ARRIVAL_DELAY
    FROM stats
    CROSS JOIN dims;
    """
    df = pd.read_sql_query(query, conn)
    if df.empty:
        logger.warning("Executive summary query returned empty results.")
    return df


def get_airline_performance(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Generate the Airline Performance dataset.

    Calculates metrics (flight count, delays, rates) grouped by airline,
    sorted descending by flight count.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active connection to the SQLite database.

    Returns
    -------
    pd.DataFrame
        DataFrame of airline performance.
    """
    logger.info("Computing Airline Performance dataset...")
    query = """
    SELECT 
        a.AIRLINE as AIRLINE_CODE,
        COUNT(f.FLIGHT_ID) as FLIGHT_COUNT,
        ROUND(COALESCE(AVG(f.DEPARTURE_DELAY), 0.0), 2) as AVG_DEPARTURE_DELAY,
        ROUND(COALESCE(AVG(f.ARRIVAL_DELAY), 0.0), 2) as AVG_ARRIVAL_DELAY,
        ROUND(COALESCE(SUM(CASE WHEN f.CANCELLED = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(f.FLIGHT_ID), 0.0), 4) as CANCELLATION_RATE,
        ROUND(COALESCE(SUM(CASE WHEN f.DIVERTED = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(f.FLIGHT_ID), 0.0), 4) as DIVERSION_RATE
    FROM flights f
    JOIN airlines a ON f.AIRLINE_ID = a.AIRLINE_ID
    GROUP BY a.AIRLINE
    ORDER BY FLIGHT_COUNT DESC;
    """
    df = pd.read_sql_query(query, conn)
    if df.empty:
        logger.warning("Airline performance query returned empty results.")
    return df


def get_airport_traffic(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Generate the Airport Traffic dataset.

    Calculates origin and destination flights, as well as total traffic
    for each airport, sorted descending by total traffic.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active connection to the SQLite database.

    Returns
    -------
    pd.DataFrame
        DataFrame of airport traffic statistics.
    """
    logger.info("Computing Airport Traffic dataset...")
    query = """
    WITH origin_counts AS (
        SELECT ORIGIN_AIRPORT_ID, COUNT(*) as origin_flights
        FROM flights
        GROUP BY ORIGIN_AIRPORT_ID
    ),
    dest_counts AS (
        SELECT DESTINATION_AIRPORT_ID, COUNT(*) as destination_flights
        FROM flights
        GROUP BY DESTINATION_AIRPORT_ID
    )
    SELECT 
        a.AIRPORT as AIRPORT_CODE,
        COALESCE(o.origin_flights, 0) as ORIGIN_FLIGHTS,
        COALESCE(d.destination_flights, 0) as DESTINATION_FLIGHTS,
        (COALESCE(o.origin_flights, 0) + COALESCE(d.destination_flights, 0)) as TOTAL_TRAFFIC
    FROM airports a
    LEFT JOIN origin_counts o ON a.AIRPORT_ID = o.ORIGIN_AIRPORT_ID
    LEFT JOIN dest_counts d ON a.AIRPORT_ID = d.DESTINATION_AIRPORT_ID
    WHERE o.origin_flights IS NOT NULL OR d.destination_flights IS NOT NULL
    ORDER BY TOTAL_TRAFFIC DESC;
    """
    df = pd.read_sql_query(query, conn)
    if df.empty:
        logger.warning("Airport traffic query returned empty results.")
    return df


def get_delay_analysis(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Generate the Delay Analysis dataset.

    Calculates average weather, airline, security, air system, and late aircraft
    delays grouped by airline code.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active connection to the SQLite database.

    Returns
    -------
    pd.DataFrame
        DataFrame of delay categories analysis.
    """
    logger.info("Computing Delay Analysis dataset...")
    query = """
    SELECT 
        a.AIRLINE as AIRLINE_CODE,
        ROUND(COALESCE(AVG(f.WEATHER_DELAY), 0.0), 2) as AVG_WEATHER_DELAY,
        ROUND(COALESCE(AVG(f.AIRLINE_DELAY), 0.0), 2) as AVG_AIRLINE_DELAY,
        ROUND(COALESCE(AVG(f.SECURITY_DELAY), 0.0), 2) as AVG_SECURITY_DELAY,
        ROUND(COALESCE(AVG(f.AIR_SYSTEM_DELAY), 0.0), 2) as AVG_AIR_SYSTEM_DELAY,
        ROUND(COALESCE(AVG(f.LATE_AIRCRAFT_DELAY), 0.0), 2) as AVG_LATE_AIRCRAFT_DELAY
    FROM flights f
    JOIN airlines a ON f.AIRLINE_ID = a.AIRLINE_ID
    GROUP BY a.AIRLINE
    ORDER BY a.AIRLINE ASC;
    """
    df = pd.read_sql_query(query, conn)
    if df.empty:
        logger.warning("Delay analysis query returned empty results.")
    return df


# ============================================================================
# REPORT GENERATION
# ============================================================================


def write_summary_report(
    exec_summary: pd.DataFrame,
    airline_perf: pd.DataFrame,
    airport_traffic: pd.DataFrame,
    delay_analysis: pd.DataFrame,
    output_path: Path
) -> None:
    """
    Generate and save a formatted analytics summary text report.

    Parameters
    ----------
    exec_summary : pd.DataFrame
        Executive summary statistics.
    airline_perf : pd.DataFrame
        Airline performance metrics.
    airport_traffic : pd.DataFrame
        Airport traffic metrics.
    delay_analysis : pd.DataFrame
        Delay breakdown analysis metrics.
    output_path : Path
        Path to save the summary report file.
    """
    logger.info(f"Writing textual summary report to: {output_path}")

    # Extract metrics safely from dataframes, handling potential empty results
    total_flights = 0
    total_airlines = 0
    total_airports = 0
    cancellation_rate = 0.0
    diversion_rate = 0.0
    avg_dep_delay = 0.0
    avg_arr_delay = 0.0

    if not exec_summary.empty:
        total_flights = exec_summary.at[0, "TOTAL_FLIGHTS"]
        total_airlines = exec_summary.at[0, "TOTAL_AIRLINES"]
        total_airports = exec_summary.at[0, "TOTAL_AIRPORTS"]
        cancellation_rate = exec_summary.at[0, "CANCELLATION_RATE"]
        diversion_rate = exec_summary.at[0, "DIVERSION_RATE"]
        avg_dep_delay = exec_summary.at[0, "AVG_DEPARTURE_DELAY"]
        avg_arr_delay = exec_summary.at[0, "AVG_ARRIVAL_DELAY"]

    report_lines = [
        "======================================================================",
        "                     AIRFLOW ETL PIPELINE - ANALYTICS SUMMARY         ",
        "======================================================================",
        f"Total Flights Analysed: {total_flights:,}",
        f"Total Airlines Represented: {total_airlines}",
        f"Total Airports Represented: {total_airports}",
        f"Cancellation Rate: {cancellation_rate:.2f}%",
        f"Diversion Rate: {diversion_rate:.2f}%",
        f"Average Departure Delay: {avg_dep_delay:.2f} minutes",
        f"Average Arrival Delay: {avg_arr_delay:.2f} minutes",
        "",
        "1. TOP 10 AIRLINES BY FLIGHT COUNT",
        "----------------------------------------------------------------------",
        f"{'Rank':<5}{'Code':<10}{'Flights':<12}{'Avg Dep Delay':<16}{'Avg Arr Delay':<16}{'Cancel %':<10}",
        "-" * 70
    ]

    for idx, (_, row) in enumerate(airline_perf.head(10).iterrows(), 1):
        report_lines.append(
            f"{idx:<5}{row['AIRLINE_CODE']:<10}{row['FLIGHT_COUNT']:<12,}"
            f"{row['AVG_DEPARTURE_DELAY']:<16.2f}{row['AVG_ARRIVAL_DELAY']:<16.2f}"
            f"{row['CANCELLATION_RATE']:<10.2f}"
        )

    report_lines.extend([
        "",
        "2. TOP 10 AIRPORTS BY TOTAL TRAFFIC",
        "----------------------------------------------------------------------",
        f"{'Rank':<5}{'Code':<10}{'Total Traffic':<15}{'Origin Flights':<18}{'Dest Flights':<18}",
        "-" * 70
    ])

    for idx, (_, row) in enumerate(airport_traffic.head(10).iterrows(), 1):
        report_lines.append(
            f"{idx:<5}{row['AIRPORT_CODE']:<10}{row['TOTAL_TRAFFIC']:<15,}"
            f"{row['ORIGIN_FLIGHTS']:<18,}{row['DESTINATION_FLIGHTS']:<18,}"
        )

    report_lines.extend([
        "",
        "3. DELAY STATISTICS BY CATEGORY (AVERAGE MINUTES)",
        "----------------------------------------------------------------------",
        f"{'Airline':<10}{'Weather':<12}{'Airline':<12}{'Security':<12}{'Air System':<14}{'Late Aircraft':<14}",
        "-" * 76
    ])

    for _, row in delay_analysis.iterrows():
        report_lines.append(
            f"{row['AIRLINE_CODE']:<10}{row['AVG_WEATHER_DELAY']:<12.2f}"
            f"{row['AVG_AIRLINE_DELAY']:<12.2f}{row['AVG_SECURITY_DELAY']:<12.2f}"
            f"{row['AVG_AIR_SYSTEM_DELAY']:<14.2f}{row['AVG_LATE_AIRCRAFT_DELAY']:<14.2f}"
        )

    report_lines.extend([
        "",
        "4. CANCELLATION STATISTICS",
        "----------------------------------------------------------------------",
        f"Overall Cancellation Rate: {cancellation_rate:.4f}%",
        f"Overall Diversion Rate: {diversion_rate:.4f}%",
        "======================================================================"
    ])

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        logger.info("Summary report generated and written successfully.")
    except IOError as e:
        logger.error(f"Failed to write summary report to {output_path}: {e}")
        raise


# ============================================================================
# MAIN EXECUTION ENTRYPOINT
# ============================================================================


def main() -> int:
    """
    Orchestrate and execute the complete analytics generation pipeline.

    Steps:
    1. Validate database connection and table structures.
    2. Establish a connection to SQLite database.
    3. Generate the four required analytical datasets.
    4. Save each dataset to a CSV file in `data/analytics/`.
    5. Generate the analytical text report at `reports/analytics_summary.txt`.
    6. Print a formatted execution summary to stdout.

    Returns
    -------
    int
        0 if successful, 1 if validation fails, or another error occurs.
    """
    logger.info("=" * 70)
    logger.info("AirFlow Analytics Layer - ETL Phase 4")
    logger.info("=" * 70)

    # Validate database integrity first
    if not validate_database_and_tables(DATABASE_PATH):
        logger.critical("Database validation failed. Aborting execution.")
        return 1

    try:
        with sqlite3.connect(str(DATABASE_PATH)) as conn:
            # Generate Datasets
            exec_summary = get_executive_summary(conn)
            airline_perf = get_airline_performance(conn)
            airport_traffic = get_airport_traffic(conn)
            delay_analysis = get_delay_analysis(conn)

            # Export datasets to CSV files
            exec_summary_file = ANALYTICS_DATA_DIR / "executive_summary.csv"
            airline_perf_file = ANALYTICS_DATA_DIR / "daily_airline_performance.csv"
            airport_traffic_file = ANALYTICS_DATA_DIR / "airport_traffic.csv"
            delay_analysis_file = ANALYTICS_DATA_DIR / "delay_analysis.csv"

            exec_summary.to_csv(exec_summary_file, index=False)
            airline_perf.to_csv(airline_perf_file, index=False)
            airport_traffic.to_csv(airport_traffic_file, index=False)
            delay_analysis.to_csv(delay_analysis_file, index=False)

            logger.info("All analytical CSV datasets successfully written.")

            # Generate and write summary report
            write_summary_report(
                exec_summary=exec_summary,
                airline_perf=airline_perf,
                airport_traffic=airport_traffic,
                delay_analysis=delay_analysis,
                output_path=SUMMARY_REPORT_PATH
            )

        # Print the exact professional execution summary requested
        print("\n================================================================")
        print("ANALYTICS PHASE SUMMARY")
        print("================================================================")
        print("Executive Dataset Created")
        print("Airline Performance Dataset Created")
        print("Airport Traffic Dataset Created")
        print("Delay Analysis Dataset Created")
        print("\nReports Generated")
        print("\nExecution Successful")
        print("================================================================\n")

        logger.info("Analytics Phase completed successfully.")
        return 0

    except Exception as e:
        logger.error(f"Analytics generation pipeline encountered an error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
