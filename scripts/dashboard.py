"""
Enterprise Visualization and Dashboard Module for AirFlow ETL Pipeline.

This module handles the visualization phase (Phase 5) of the ETL pipeline:
- Validating the analytical datasets and database structures before execution
- Generating publication-ready static Matplotlib charts with statistical overlays
- Constructing interactive Plotly dashboards saved as responsive HTML pages
- Consolidating all views into a tabbed Master Dashboard
- Generating a detailed execution summary report
- Displaying a formatted terminal output summary

Author: Senior Analytics Engineer
Version: 1.0.0
"""

import datetime
import logging
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure UTF-8 encoding for stdout/stderr to support unicode characters on Windows
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ============================================================================
# CONFIGURATION & LOGGING SETUP
# ============================================================================


def _setup_logging() -> logging.Logger:
    """
    Initialize logging with idempotent stream handler configuration.

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    log = logging.getLogger("AirFlow.Visualization")

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

# Define project directories and paths
PROJECT_ROOT = Path(__file__).parent.parent
ANALYTICS_DATA_DIR = PROJECT_ROOT / "data" / "analytics"
DATABASE_PATH = PROJECT_ROOT / "database" / "airflow.db"
CHARTS_DIR = PROJECT_ROOT / "visualizations" / "charts"
DASHBOARDS_DIR = PROJECT_ROOT / "visualizations" / "dashboards"
EXPORTS_DIR = PROJECT_ROOT / "exports" / "html"
REPORTS_DIR = PROJECT_ROOT / "reports"
DASHBOARD_REPORT_PATH = REPORTS_DIR / "dashboard_report.txt"

# Ensure all target folders exist
CHARTS_DIR.mkdir(parents=True, exist_ok=True)
DASHBOARDS_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# VALIDATION FRAMEWORK
# ============================================================================


@dataclass
class DatasetSpec:
    """Specification of a required analytical CSV dataset."""
    name: str
    file_path: Path
    required_columns: List[str]


class VisualizationValidationError(Exception):
    """Exception raised when dataset validation fails."""
    pass


def validate_input_datasets(specs: List[DatasetSpec]) -> Dict[str, pd.DataFrame]:
    """
    Validate that required analytical datasets exist, are non-empty, and readable.

    Parameters
    ----------
    specs : List[DatasetSpec]
        List of dataset specifications containing required columns and file paths.

    Returns
    -------
    Dict[str, pd.DataFrame]
        Dictionary of loaded and validated pandas DataFrames.

    Raises
    ------
    VisualizationValidationError
        If any validation check fails.
    """
    logger.info("Executing analytical dataset validation checks...")
    loaded_data: Dict[str, pd.DataFrame] = {}

    for spec in specs:
        path = spec.file_path
        logger.info(f"Validating dataset '{spec.name}' at: {path}")

        # 1. Check file exists
        if not path.exists():
            raise VisualizationValidationError(f"Required dataset does not exist: {path}")

        # 2. Check readability and size
        try:
            df = pd.read_csv(path)
        except Exception as e:
            raise VisualizationValidationError(f"Dataset is not readable as CSV: {path}. Error: {e}")

        # 3. Check not empty
        if df.empty:
            raise VisualizationValidationError(f"Dataset is empty: {path}")

        # 4. Check required columns exist
        missing_cols = [col for col in spec.required_columns if col not in df.columns]
        if missing_cols:
            raise VisualizationValidationError(
                f"Missing required columns in '{spec.name}': {missing_cols}. Columns found: {list(df.columns)}"
            )

        loaded_data[spec.name] = df
        logger.info(f"✓ '{spec.name}' validated: {len(df)} rows, {len(df.columns)} columns.")

    # Validate database path for histograms
    logger.info(f"Validating database access at: {DATABASE_PATH}")
    if not DATABASE_PATH.exists():
        raise VisualizationValidationError(f"Database file not found at: {DATABASE_PATH}")

    # Check if we can connect and flights table exists
    try:
        with sqlite3.connect(str(DATABASE_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='flights';")
            if not cursor.fetchone():
                raise VisualizationValidationError("Table 'flights' does not exist in SQLite database.")
            cursor.execute("SELECT COUNT(*) FROM flights;")
            count = cursor.fetchone()[0]
            if count == 0:
                raise VisualizationValidationError("Table 'flights' is empty. Cannot extract delays distribution.")
            logger.info(f"✓ SQLite Database validated: '{count:,}' flights available.")
    except Exception as e:
        raise VisualizationValidationError(f"Database validation query failed: {e}")

    # Validate output directories are writable
    for directory in [CHARTS_DIR, DASHBOARDS_DIR, EXPORTS_DIR, REPORTS_DIR]:
        # Perform write check by creating a temp file
        temp_file = directory / ".write_check"
        try:
            temp_file.touch()
            temp_file.unlink()
        except Exception as e:
            raise VisualizationValidationError(f"Directory is not writable: {directory}. Error: {e}")

    logger.info("Validation framework completed successfully. All data pipelines clear.")
    return loaded_data


# ============================================================================
# SQL VERIFICATION (TASK 4: KPI AUDIT & VERIFICATION)
# ============================================================================

def verify_kpis_with_db(exec_summary: pd.DataFrame, db_path: Path) -> None:
    """
    Verify dashboard KPIs directly against SQLite queries to ensure integrity.
    (Production Dashboard Audit Requirement)
    """
    logger.info("Executing Dashboard KPI SQL Verification...")
    
    if not db_path.exists():
        raise VisualizationValidationError("Cannot perform SQL verification: Database missing.")

    row = exec_summary.iloc[0]
    csv_flights = int(row["TOTAL_FLIGHTS"])
    csv_airlines = int(row["TOTAL_AIRLINES"])
    csv_airports = int(row["TOTAL_AIRPORTS"])
    csv_cancellation = float(row["CANCELLATION_RATE"])
    csv_diversion = float(row["DIVERSION_RATE"])
    csv_avg_dep = float(row["AVG_DEPARTURE_DELAY"])
    csv_avg_arr = float(row["AVG_ARRIVAL_DELAY"])

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        
        # 1. Total Flights
        db_flights = cursor.execute("SELECT COUNT(*) FROM flights;").fetchone()[0]
        if db_flights != csv_flights:
            logger.error(f"SQL Verification Failed: CSV Flights ({csv_flights}) != DB Flights ({db_flights})")
            raise VisualizationValidationError("Total Flights metric mismatch between CSV and DB.")

        # 2. Total Airlines
        db_airlines = cursor.execute("SELECT COUNT(*) FROM airlines;").fetchone()[0]
        if db_airlines != csv_airlines:
            logger.error(f"SQL Verification Failed: CSV Airlines ({csv_airlines}) != DB Airlines ({db_airlines})")
            raise VisualizationValidationError("Total Airlines metric mismatch between CSV and DB.")

        # 3. Total Airports
        db_airports = cursor.execute("SELECT COUNT(*) FROM airports;").fetchone()[0]
        if db_airports != csv_airports:
            logger.error(f"SQL Verification Failed: CSV Airports ({csv_airports}) != DB Airports ({db_airports})")
            raise VisualizationValidationError("Total Airports metric mismatch between CSV and DB.")

        # 4. Cancellation Rate
        db_cancelled = cursor.execute("SELECT COUNT(*) FROM flights WHERE CANCELLED = 1;").fetchone()[0]
        db_cancellation_rate = round((db_cancelled / db_flights) * 100.0, 2) if db_flights > 0 else 0.0
        if abs(db_cancellation_rate - csv_cancellation) > 0.1:
            logger.error(f"SQL Verification Failed: CSV Cancellation Rate ({csv_cancellation}) != DB Rate ({db_cancellation_rate})")
            raise VisualizationValidationError("Cancellation Rate mismatch.")

        # 5. Diversion Rate
        db_diverted = cursor.execute("SELECT COUNT(*) FROM flights WHERE DIVERTED = 1;").fetchone()[0]
        db_diversion_rate = round((db_diverted / db_flights) * 100.0, 2) if db_flights > 0 else 0.0
        if abs(db_diversion_rate - csv_diversion) > 0.1:
            logger.error(f"SQL Verification Failed: CSV Diversion Rate ({csv_diversion}) != DB Rate ({db_diversion_rate})")
            raise VisualizationValidationError("Diversion Rate mismatch.")

        # 6. Avg Delays
        delays = cursor.execute("SELECT AVG(DEPARTURE_DELAY), AVG(ARRIVAL_DELAY) FROM flights;").fetchone()
        db_avg_dep = round(delays[0] or 0.0, 1)
        db_avg_arr = round(delays[1] or 0.0, 1)
        if abs(db_avg_dep - csv_avg_dep) > 0.1 or abs(db_avg_arr - csv_avg_arr) > 0.1:
            logger.error(f"SQL Verification Failed: Delays mismatch (DB: {db_avg_dep}, {db_avg_arr} vs CSV: {csv_avg_dep}, {csv_avg_arr})")
            raise VisualizationValidationError("Average Delay metrics mismatch.")
            
    logger.info("✓ SQL Verification PASSED: Dashboard metrics exactly match direct SQLite queries.")



# ============================================================================
# MATPLOTLIB STATIC CHARTS
# ============================================================================


def generate_static_charts(
    loaded_data: Dict[str, pd.DataFrame],
    db_path: Path
) -> List[str]:
    """
    Generate publication-ready static Matplotlib charts.

    Parameters
    ----------
    loaded_data : Dict[str, pd.DataFrame]
        Validated analytical DataFrames.
    db_path : Path
        Path to the SQLite database.

    Returns
    -------
    List[str]
        List of generated static chart file names.
    """
    logger.info("Generating high-quality static charts...")
    generated_charts: List[str] = []

    # Apply professional styling guidelines
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Helvetica", "Arial", "DejaVu Sans"]
    plt.rcParams["text.color"] = "#1e293b"
    plt.rcParams["axes.labelcolor"] = "#475569"
    plt.rcParams["xtick.color"] = "#475569"
    plt.rcParams["ytick.color"] = "#475569"

    # Color Palette definitions
    c_blue = "#2563eb"
    c_teal = "#0d9488"
    c_rose = "#e11d48"
    c_slate = "#475569"

    # ------------------------------------------------------------------------
    # Chart 1: Top 10 Airlines by Flight Count
    # ------------------------------------------------------------------------
    logger.info("Generating Chart 1: Top 10 Airlines by Flight Count")
    df_airline = loaded_data["airline_performance"]
    df_top_airlines = df_airline.head(10).sort_values(by="FLIGHT_COUNT", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    bars = ax.barh(
        df_top_airlines["AIRLINE_CODE"],
        df_top_airlines["FLIGHT_COUNT"],
        color=c_blue,
        edgecolor="none",
        height=0.6
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.xaxis.grid(True, linestyle="--", alpha=0.4, color="#cbd5e1")
    ax.set_axisbelow(True)

    # Add numeric labels to bars
    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + (width * 0.01),
            bar.get_y() + bar.get_height() / 2,
            f"{int(width):,}",
            va="center",
            ha="left",
            fontsize=9.5,
            color="#334155",
            fontweight="semibold"
        )

    ax.set_title("Top 10 Airlines by Flight Count", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Total Flights", fontsize=11, labelpad=10)
    ax.set_ylabel("Airline Code", fontsize=11, labelpad=10)
    plt.tight_layout()

    chart1_path = CHARTS_DIR / "top_airlines.png"
    plt.savefig(chart1_path, bbox_inches="tight")
    plt.close()
    generated_charts.append("top_airlines.png")

    # ------------------------------------------------------------------------
    # Chart 2: Top 10 Airports by Total Traffic
    # ------------------------------------------------------------------------
    logger.info("Generating Chart 2: Top 10 Airports by Total Traffic")
    df_airport = loaded_data["airport_traffic"]
    df_top_airports = df_airport.head(10).sort_values(by="TOTAL_TRAFFIC", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    bars = ax.barh(
        df_top_airports["AIRPORT_CODE"],
        df_top_airports["TOTAL_TRAFFIC"],
        color=c_teal,
        edgecolor="none",
        height=0.6
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.xaxis.grid(True, linestyle="--", alpha=0.4, color="#cbd5e1")
    ax.set_axisbelow(True)

    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + (width * 0.01),
            bar.get_y() + bar.get_height() / 2,
            f"{int(width):,}",
            va="center",
            ha="left",
            fontsize=9.5,
            color="#334155",
            fontweight="semibold"
        )

    ax.set_title("Top 10 Airports by Total Traffic (Origin + Destination)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Total Passenger Traffic", fontsize=11, labelpad=10)
    ax.set_ylabel("Airport Code", fontsize=11, labelpad=10)
    plt.tight_layout()

    chart2_path = CHARTS_DIR / "top_airports.png"
    plt.savefig(chart2_path, bbox_inches="tight")
    plt.close()
    generated_charts.append("top_airports.png")

    # ------------------------------------------------------------------------
    # Chart 3: Cancellation Rate by Airline
    # ------------------------------------------------------------------------
    logger.info("Generating Chart 3: Cancellation Rate by Airline")
    df_cancel = df_airline.sort_values(by="CANCELLATION_RATE", ascending=False)

    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
    bars = ax.bar(
        df_cancel["AIRLINE_CODE"],
        df_cancel["CANCELLATION_RATE"],
        color=c_rose,
        edgecolor="none",
        width=0.55
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, color="#cbd5e1")
    ax.set_axisbelow(True)

    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + 0.15,
            f"{height:.2f}%",
            va="bottom",
            ha="center",
            fontsize=8.5,
            color="#334155",
            fontweight="semibold"
        )

    ax.set_title("Cancellation Rate by Airline", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Airline Code", fontsize=11, labelpad=10)
    ax.set_ylabel("Cancellation Percentage (%)", fontsize=11, labelpad=10)
    plt.tight_layout()

    chart3_path = CHARTS_DIR / "cancellation_rate.png"
    plt.savefig(chart3_path, bbox_inches="tight")
    plt.close()
    generated_charts.append("cancellation_rate.png")

    # ------------------------------------------------------------------------
    # Chart 4: Delay Analysis Grouped Bar Chart
    # ------------------------------------------------------------------------
    logger.info("Generating Chart 4: Delay Analysis Grouped Bar Chart")
    df_delay = loaded_data["delay_analysis"]

    categories = [
        "AVG_WEATHER_DELAY", "AVG_AIRLINE_DELAY",
        "AVG_SECURITY_DELAY", "AVG_AIR_SYSTEM_DELAY",
        "AVG_LATE_AIRCRAFT_DELAY"
    ]
    colors = ["#f59e0b", "#3b82f6", "#10b981", "#6366f1", "#ec4899"]
    labels = ["Weather", "Airline", "Security", "Air System", "Late Aircraft"]

    x = np.arange(len(df_delay["AIRLINE_CODE"]))
    width = 0.15

    fig, ax = plt.subplots(figsize=(12, 6), dpi=150)

    for i, cat in enumerate(categories):
        ax.bar(
            x + i * width,
            df_delay[cat],
            width,
            color=colors[i],
            label=labels[i],
            edgecolor="none"
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, color="#cbd5e1")
    ax.set_axisbelow(True)

    ax.set_title("Average Delay Breakdown by Category per Airline", fontsize=14, fontweight="bold", pad=15)
    ax.set_xticks(x + width * 2)
    ax.set_xticklabels(df_delay["AIRLINE_CODE"])
    ax.set_xlabel("Airline Code", fontsize=11, labelpad=10)
    ax.set_ylabel("Average Delay (Minutes)", fontsize=11, labelpad=10)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cbd5e1")
    plt.tight_layout()

    chart4_path = CHARTS_DIR / "delay_analysis.png"
    plt.savefig(chart4_path, bbox_inches="tight")
    plt.close()
    generated_charts.append("delay_analysis.png")

    # ------------------------------------------------------------------------
    # Fetch Raw Flight Delays for Histograms
    # ------------------------------------------------------------------------
    logger.info("Fetching raw flights delay values for distribution analysis...")
    with sqlite3.connect(str(db_path)) as conn:
        df_raw_delays = pd.read_sql_query(
            "SELECT DEPARTURE_DELAY, ARRIVAL_DELAY FROM flights WHERE CANCELLED = 0 AND DIVERTED = 0;",
            conn
        )
    df_raw_delays = df_raw_delays.dropna()

    # ------------------------------------------------------------------------
    # Chart 5: Departure Delay Distribution Histogram
    # ------------------------------------------------------------------------
    logger.info("Generating Chart 5: Departure Delay Distribution")
    dep_delays = df_raw_delays["DEPARTURE_DELAY"]

    # Filter standard range for clean visualization, outliers handled gracefully
    dep_filtered = dep_delays[(dep_delays >= -20) & (dep_delays <= 180)]

    mean_dep = dep_delays.mean()
    median_dep = dep_delays.median()
    std_dep = dep_delays.std()
    p90_dep = dep_delays.quantile(0.90)

    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    n, bins, patches = ax.hist(
        dep_filtered,
        bins=50,
        color="#3b82f6",
        edgecolor="white",
        alpha=0.85
    )

    ax.axvline(mean_dep, color="#ef4444", linestyle="dashed", linewidth=1.5, label=f"Mean: {mean_dep:.2f}m")
    ax.axvline(median_dep, color="#10b981", linestyle="dashed", linewidth=1.5, label=f"Median: {median_dep:.2f}m")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, color="#cbd5e1")
    ax.set_axisbelow(True)

    stats_text = (
        f"Distribution Summary:\n"
        f"  Mean: {mean_dep:.2f} min\n"
        f"  Median: {median_dep:.2f} min\n"
        f"  Std Dev: {std_dep:.2f} min\n"
        f"  90th %tile: {p90_dep:.2f} min\n"
        f"  Total flights: {len(dep_delays):,}"
    )
    ax.text(
        0.95, 0.95,
        stats_text,
        transform=ax.transAxes,
        verticalalignment="top",
        horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor="#cbd5e1", alpha=0.95),
        fontsize=9.5,
        color="#334155"
    )

    ax.set_title("Departure Delay Distribution Analysis", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Departure Delay (Minutes)", fontsize=11, labelpad=10)
    ax.set_ylabel("Flight Frequency Count", fontsize=11, labelpad=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=True, edgecolor="#cbd5e1")
    plt.tight_layout()

    chart5_path = CHARTS_DIR / "departure_delay_distribution.png"
    plt.savefig(chart5_path, bbox_inches="tight")
    plt.close()
    generated_charts.append("departure_delay_distribution.png")

    # ------------------------------------------------------------------------
    # Chart 6: Arrival Delay Distribution Histogram
    # ------------------------------------------------------------------------
    logger.info("Generating Chart 6: Arrival Delay Distribution")
    arr_delays = df_raw_delays["ARRIVAL_DELAY"]
    arr_filtered = arr_delays[(arr_delays >= -20) & (arr_delays <= 180)]

    mean_arr = arr_delays.mean()
    median_arr = arr_delays.median()
    std_arr = arr_delays.std()
    p90_arr = arr_delays.quantile(0.90)

    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    n, bins, patches = ax.hist(
        arr_filtered,
        bins=50,
        color="#6366f1",
        edgecolor="white",
        alpha=0.85
    )

    ax.axvline(mean_arr, color="#ef4444", linestyle="dashed", linewidth=1.5, label=f"Mean: {mean_arr:.2f}m")
    ax.axvline(median_arr, color="#10b981", linestyle="dashed", linewidth=1.5, label=f"Median: {median_arr:.2f}m")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, color="#cbd5e1")
    ax.set_axisbelow(True)

    stats_text = (
        f"Distribution Summary:\n"
        f"  Mean: {mean_arr:.2f} min\n"
        f"  Median: {median_arr:.2f} min\n"
        f"  Std Dev: {std_arr:.2f} min\n"
        f"  90th %tile: {p90_arr:.2f} min\n"
        f"  Total flights: {len(arr_delays):,}"
    )
    ax.text(
        0.95, 0.95,
        stats_text,
        transform=ax.transAxes,
        verticalalignment="top",
        horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor="#cbd5e1", alpha=0.95),
        fontsize=9.5,
        color="#334155"
    )

    ax.set_title("Arrival Delay Distribution Analysis", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Arrival Delay (Minutes)", fontsize=11, labelpad=10)
    ax.set_ylabel("Flight Frequency Count", fontsize=11, labelpad=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=True, edgecolor="#cbd5e1")
    plt.tight_layout()

    chart6_path = CHARTS_DIR / "arrival_delay_distribution.png"
    plt.savefig(chart6_path, bbox_inches="tight")
    plt.close()
    generated_charts.append("arrival_delay_distribution.png")

    logger.info("✓ Matplotlib static charts generated successfully.")
    return generated_charts


# ============================================================================
# INTERACTIVE PLOTLY FIGURES GENERATION
# ============================================================================


def build_plotly_charts(
    loaded_data: Dict[str, pd.DataFrame],
    db_path: Path
) -> Tuple[go.Figure, go.Figure, go.Figure, go.Figure, go.Figure, go.Figure]:
    """
    Generate responsive and modern Plotly Figures.

    Parameters
    ----------
    loaded_data : Dict[str, pd.DataFrame]
        Validated analytical DataFrames.
    db_path : Path
        Path to the SQLite database.

    Returns
    -------
    Tuple[go.Figure, go.Figure, go.Figure, go.Figure, go.Figure, go.Figure]
        Tupel containing the generated interactive figures.
    """
    logger.info("Creating interactive Plotly visual figures...")

    # Chart 1: Top 10 Airlines
    df_airline = loaded_data["airline_performance"]
    df_top_airlines = df_airline.head(10).sort_values(by="FLIGHT_COUNT", ascending=True)
    fig_top_airlines = px.bar(
        df_top_airlines,
        x="FLIGHT_COUNT",
        y="AIRLINE_CODE",
        orientation="h",
        text="FLIGHT_COUNT",
        labels={"FLIGHT_COUNT": "Total Flights", "AIRLINE_CODE": "Airline Code"},
        color_discrete_sequence=["#2563eb"]
    )
    fig_top_airlines.update_traces(
        texttemplate="%{text:,}", textposition="outside",
        textfont=dict(size=13, color="#334155", family="Inter")
    )
    fig_top_airlines.update_layout(
        height=500, autosize=True,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=50, r=80, t=60, b=50),
        xaxis=dict(showgrid=True, gridcolor="#e2e8f0", title_font=dict(size=13), tickfont=dict(size=12)),
        yaxis=dict(tickfont=dict(size=12), title_font=dict(size=13)),
        font=dict(family="Inter, sans-serif")
    )

    # Chart 2: Top 10 Airports
    df_airport = loaded_data["airport_traffic"]
    df_top_airports = df_airport.head(10).sort_values(by="TOTAL_TRAFFIC", ascending=True)
    fig_top_airports = px.bar(
        df_top_airports,
        x="TOTAL_TRAFFIC",
        y="AIRPORT_CODE",
        orientation="h",
        text="TOTAL_TRAFFIC",
        labels={"TOTAL_TRAFFIC": "Total Traffic", "AIRPORT_CODE": "Airport Code"},
        color_discrete_sequence=["#0d9488"]
    )
    fig_top_airports.update_traces(
        texttemplate="%{text:,}", textposition="outside",
        textfont=dict(size=13, color="#334155", family="Inter")
    )
    fig_top_airports.update_layout(
        height=500, autosize=True,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=50, r=80, t=60, b=50),
        xaxis=dict(showgrid=True, gridcolor="#e2e8f0", title_font=dict(size=13), tickfont=dict(size=12)),
        yaxis=dict(tickfont=dict(size=12), title_font=dict(size=13)),
        font=dict(family="Inter, sans-serif")
    )

    # Chart 3: Cancellation Rate
    df_cancel = df_airline.sort_values(by="CANCELLATION_RATE", ascending=False)
    fig_cancellation = px.bar(
        df_cancel,
        x="AIRLINE_CODE",
        y="CANCELLATION_RATE",
        text="CANCELLATION_RATE",
        labels={"CANCELLATION_RATE": "Cancellation Rate (%)", "AIRLINE_CODE": "Airline"},
        color_discrete_sequence=["#e11d48"]
    )
    fig_cancellation.update_traces(
        texttemplate="%{text:.2f}%", textposition="outside",
        textfont=dict(size=12, color="#334155", family="Inter")
    )
    fig_cancellation.update_layout(
        height=500, autosize=True,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=50, r=30, t=60, b=50),
        yaxis=dict(showgrid=True, gridcolor="#e2e8f0", title_font=dict(size=13), tickfont=dict(size=12)),
        xaxis=dict(tickfont=dict(size=11), tickangle=-45, title_font=dict(size=13)),
        font=dict(family="Inter, sans-serif")
    )

    # Chart 4: Grouped Delay Analysis
    df_delay = loaded_data["delay_analysis"]
    delay_melted = df_delay.melt(
        id_vars=["AIRLINE_CODE"],
        value_vars=[
            "AVG_WEATHER_DELAY", "AVG_AIRLINE_DELAY",
            "AVG_SECURITY_DELAY", "AVG_AIR_SYSTEM_DELAY",
            "AVG_LATE_AIRCRAFT_DELAY"
        ],
        var_name="DelayType",
        value_name="Minutes"
    )
    delay_melted["DelayType"] = delay_melted["DelayType"].replace({
        "AVG_WEATHER_DELAY": "Weather",
        "AVG_AIRLINE_DELAY": "Airline",
        "AVG_SECURITY_DELAY": "Security",
        "AVG_AIR_SYSTEM_DELAY": "Air System",
        "AVG_LATE_AIRCRAFT_DELAY": "Late Aircraft"
    })
    fig_delays_grouped = px.bar(
        delay_melted,
        x="AIRLINE_CODE",
        y="Minutes",
        color="DelayType",
        barmode="group",
        labels={"Minutes": "Average Delay (Min)", "AIRLINE_CODE": "Airline", "DelayType": "Delay Category"},
        color_discrete_sequence=["#f59e0b", "#3b82f6", "#10b981", "#6366f1", "#ec4899"]
    )
    fig_delays_grouped.update_layout(
        height=500, autosize=True,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=50, r=30, t=60, b=50),
        yaxis=dict(showgrid=True, gridcolor="#e2e8f0", title_font=dict(size=13), tickfont=dict(size=12)),
        xaxis=dict(tickfont=dict(size=11), tickangle=-45, title_font=dict(size=13)),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
            font=dict(size=12), bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#e2e8f0", borderwidth=1
        ),
        font=dict(family="Inter, sans-serif")
    )

    # Load delay lists for distribution histograms
    with sqlite3.connect(str(db_path)) as conn:
        df_raw = pd.read_sql_query(
            "SELECT DEPARTURE_DELAY, ARRIVAL_DELAY FROM flights WHERE CANCELLED = 0 AND DIVERTED = 0;",
            conn
        )
    df_raw = df_raw.dropna()
    dep_filtered = df_raw[(df_raw["DEPARTURE_DELAY"] >= -20) & (df_raw["DEPARTURE_DELAY"] <= 180)]
    arr_filtered = df_raw[(df_raw["ARRIVAL_DELAY"] >= -20) & (df_raw["ARRIVAL_DELAY"] <= 180)]

    # Chart 5: Departure Delay Distribution
    fig_dep_dist = px.histogram(
        dep_filtered,
        x="DEPARTURE_DELAY",
        nbins=50,
        labels={"DEPARTURE_DELAY": "Departure Delay (Minutes)"},
        color_discrete_sequence=["#3b82f6"]
    )
    fig_dep_dist.update_layout(
        height=500, autosize=True,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=50, r=30, t=60, b=50),
        yaxis=dict(title="Flight Count", showgrid=True, gridcolor="#e2e8f0", title_font=dict(size=13), tickfont=dict(size=12)),
        xaxis=dict(title_font=dict(size=13), tickfont=dict(size=12)),
        font=dict(family="Inter, sans-serif")
    )

    # Chart 6: Arrival Delay Distribution
    fig_arr_dist = px.histogram(
        arr_filtered,
        x="ARRIVAL_DELAY",
        nbins=50,
        labels={"ARRIVAL_DELAY": "Arrival Delay (Minutes)"},
        color_discrete_sequence=["#6366f1"]
    )
    fig_arr_dist.update_layout(
        height=500, autosize=True,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=50, r=30, t=60, b=50),
        yaxis=dict(title="Flight Count", showgrid=True, gridcolor="#e2e8f0", title_font=dict(size=13), tickfont=dict(size=12)),
        xaxis=dict(title_font=dict(size=13), tickfont=dict(size=12)),
        font=dict(family="Inter, sans-serif")
    )

    return (
        fig_top_airlines,
        fig_top_airports,
        fig_cancellation,
        fig_delays_grouped,
        fig_dep_dist,
        fig_arr_dist
    )


# ============================================================================
# HTML TEMPLATE BUILDER
# ============================================================================


def build_kpi_section(exec_summary: pd.DataFrame) -> str:
    """
    Format executive KPI summary into structured HTML card layout.

    Parameters
    ----------
    exec_summary : pd.DataFrame
        Single row DataFrame containing executive metrics.

    Returns
    -------
    str
        HTML string of KPI cards.
    """
    row = exec_summary.iloc[0]
    total_flights = int(row["TOTAL_FLIGHTS"])
    total_airlines = int(row["TOTAL_AIRLINES"])
    total_airports = int(row["TOTAL_AIRPORTS"])
    cancellation_rate = float(row["CANCELLATION_RATE"])
    diversion_rate = float(row["DIVERSION_RATE"])
    avg_dep_delay = float(row["AVG_DEPARTURE_DELAY"])
    avg_arr_delay = float(row["AVG_ARRIVAL_DELAY"])

    # On-time rate derived
    on_time_rate = 100.0 - cancellation_rate - diversion_rate

    kpi_cards = [
        {
            "icon": "&#9992;",  # airplane
            "title": "Total Flights",
            "value": f"{total_flights:,}",
            "subtitle": "Tracked operations",
            "color": "#2563eb",
            "css_class": "",
        },
        {
            "icon": "&#9992;",
            "title": "Active Airlines",
            "value": str(total_airlines),
            "subtitle": "Carrier partners",
            "color": "#0d9488",
            "css_class": "",
        },
        {
            "icon": "&#127970;",  # office building
            "title": "Airport Hubs",
            "value": str(total_airports),
            "subtitle": "Network nodes",
            "color": "#6366f1",
            "css_class": "",
        },
        {
            "icon": "&#10003;",
            "title": "On-Time Rate",
            "value": f"{on_time_rate:.1f}%",
            "subtitle": "Completed flights",
            "color": "#059669",
            "css_class": "",
        },
        {
            "icon": "&#10007;",
            "title": "Cancellation Rate",
            "value": f"{cancellation_rate:.2f}%",
            "subtitle": "Cancelled flights",
            "color": "#e11d48",
            "css_class": "kpi-alert",
        },
        {
            "icon": "&#8634;",
            "title": "Diversion Rate",
            "value": f"{diversion_rate:.2f}%",
            "subtitle": "Diverted flights",
            "color": "#d97706",
            "css_class": "kpi-warn",
        },
        {
            "icon": "&#8595;",
            "title": "Avg Dep Delay",
            "value": f"{avg_dep_delay:.1f} min",
            "subtitle": "Departure average",
            "color": "#3b82f6",
            "css_class": "",
        },
        {
            "icon": "&#8593;",
            "title": "Avg Arr Delay",
            "value": f"{avg_arr_delay:.1f} min",
            "subtitle": "Arrival average",
            "color": "#8b5cf6",
            "css_class": "",
        },
    ]

    cards_html = ""
    for card in kpi_cards:
        cards_html += f"""
        <div class="kpi-card {card['css_class']}">
            <div class="kpi-icon" style="color:{card['color']}">{card['icon']}</div>
            <div class="kpi-label">{card['title']}</div>
            <div class="kpi-value" style="color:{card['color']}">{card['value']}</div>
            <div class="kpi-subtitle">{card['subtitle']}</div>
        </div>"""

    kpi_html = f"""
    <div class="section-header">
        <h2 class="section-title">Key Performance Indicators</h2>
        <p class="section-desc">Real-time operational metrics across the flight network</p>
    </div>
    <div class="kpi-grid">
        {cards_html}
    </div>
    """
    return kpi_html


def build_base_dashboard(
    title: str,
    subtitle: str,
    kpi_html: str,
    charts_content: str,
    extra_body: str = ""
) -> str:
    """
    Inject analytics content into the premium global HTML template.

    Parameters
    ----------
    title : str
        Dashboard page title.
    subtitle : str
        Dashboard subtitle description.
    kpi_html : str
        Pre-formatted KPI cards HTML block.
    charts_content : str
        Pre-formatted charts HTML block.
    extra_body : str, optional
        Any extra scripts or layout items.

    Returns
    -------
    str
        Full HTML string.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="AirFlow Enterprise Flight Analytics - {title}">
    <title>AirFlow Analytics - {title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        /* ===============================================================
           DESIGN TOKENS
           =============================================================== */
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #f1f5f9;
            --bg-page: #f8fafc;
            --card-bg: #ffffff;
            --text-primary: #0f172a;
            --text-secondary: #64748b;
            --text-muted: #94a3b8;
            --border-color: #e2e8f0;
            --border-light: #f1f5f9;
            --accent-blue: #2563eb;
            --accent-indigo: #4f46e5;
            --accent-teal: #0d9488;
            --accent-rose: #e11d48;
            --accent-amber: #d97706;
            --accent-emerald: #059669;
            --shadow-xs: 0 1px 2px rgba(0,0,0,0.04);
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05);
            --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.04);
            --shadow-xl: 0 20px 25px -5px rgba(0,0,0,0.08), 0 8px 10px -6px rgba(0,0,0,0.04);
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-xl: 20px;
            --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
            --transition-base: 250ms cubic-bezier(0.4, 0, 0.2, 1);
        }}

        /* ===============================================================
           RESET & BASE
           =============================================================== */
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        html {{
            font-size: 16px;
            scroll-behavior: smooth;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg-page);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }}

        /* ===============================================================
           HEADER
           =============================================================== */
        .dashboard-header {{
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
            border-bottom: 3px solid var(--accent-blue);
            padding: 0;
            position: sticky;
            top: 0;
            z-index: 100;
        }}

        .header-inner {{
            max-width: 1600px;
            margin: 0 auto;
            padding: 1.5rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }}

        .header-brand {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}

        .brand-logo {{
            width: 42px;
            height: 42px;
            background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-indigo) 100%);
            border-radius: var(--radius-sm);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.3rem;
            color: white;
            flex-shrink: 0;
        }}

        .brand-text h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.5rem;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: -0.03em;
            line-height: 1.2;
        }}

        .brand-text p {{
            color: var(--text-muted);
            font-size: 0.825rem;
            font-weight: 400;
            margin-top: 2px;
        }}

        .header-meta {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        .header-badge {{
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--accent-emerald);
            background: rgba(5,150,105,0.1);
            border: 1px solid rgba(5,150,105,0.2);
            padding: 0.35rem 0.75rem;
            border-radius: 9999px;
            letter-spacing: 0.02em;
        }}

        .header-timestamp {{
            font-size: 0.8rem;
            color: var(--text-muted);
            background: rgba(255,255,255,0.05);
            padding: 0.4rem 0.85rem;
            border-radius: 9999px;
            border: 1px solid rgba(255,255,255,0.08);
        }}

        /* ===============================================================
           MAIN CONTAINER
           =============================================================== */
        .dashboard-container {{
            max-width: 1600px;
            margin: 0 auto;
            padding: 2rem 2rem 1rem 2rem;
        }}

        /* ===============================================================
           SECTION HEADERS
           =============================================================== */
        .section-header {{
            margin-bottom: 1.25rem;
        }}

        .section-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.02em;
        }}

        .section-desc {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-top: 0.15rem;
        }}

        /* ===============================================================
           KPI GRID
           =============================================================== */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1rem;
            margin-bottom: 2.5rem;
        }}

        .kpi-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 1.5rem;
            box-shadow: var(--shadow-sm);
            transition: all var(--transition-base);
            position: relative;
            overflow: hidden;
        }}

        .kpi-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-indigo));
            opacity: 0;
            transition: opacity var(--transition-base);
        }}

        .kpi-card:hover {{
            transform: translateY(-3px);
            box-shadow: var(--shadow-lg);
        }}

        .kpi-card:hover::before {{
            opacity: 1;
        }}

        .kpi-card.kpi-alert::before {{
            background: var(--accent-rose);
            opacity: 1;
        }}

        .kpi-card.kpi-warn::before {{
            background: var(--accent-amber);
            opacity: 1;
        }}

        .kpi-icon {{
            font-size: 1.5rem;
            margin-bottom: 0.5rem;
            opacity: 0.85;
        }}

        .kpi-label {{
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-secondary);
            font-weight: 600;
            margin-bottom: 0.35rem;
        }}

        .kpi-value {{
            font-family: 'Outfit', sans-serif;
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 0.25rem;
        }}

        .kpi-subtitle {{
            font-size: 0.75rem;
            color: var(--text-muted);
            font-weight: 400;
        }}

        /* ===============================================================
           CHART GRID
           =============================================================== */
        .chart-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }}

        .chart-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 1.75rem;
            box-shadow: var(--shadow-sm);
            transition: box-shadow var(--transition-base);
            display: flex;
            flex-direction: column;
        }}

        .chart-card:hover {{
            box-shadow: var(--shadow-md);
        }}

        .chart-card-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.05rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 1rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid var(--border-light);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .chart-card-title::before {{
            content: '';
            width: 4px;
            height: 18px;
            border-radius: 2px;
            background: var(--accent-blue);
            flex-shrink: 0;
        }}

        /* Force Plotly charts to fill their card containers */
        .chart-card .js-plotly-plot,
        .chart-card .plotly,
        .chart-card .plot-container {{
            width: 100% !important;
        }}

        .chart-card .svg-container {{
            width: 100% !important;
        }}

        /* ===============================================================
           TABS (Master Dashboard)
           =============================================================== */
        .tabs-container {{
            margin-bottom: 2rem;
        }}

        .tabs {{
            display: inline-flex;
            gap: 0.25rem;
            background: #e2e8f0;
            padding: 0.3rem;
            border-radius: var(--radius-md);
        }}

        .tab-btn {{
            font-family: 'Inter', sans-serif;
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--text-secondary);
            background: transparent;
            border: none;
            padding: 0.6rem 1.4rem;
            border-radius: var(--radius-sm);
            cursor: pointer;
            transition: all var(--transition-fast);
            white-space: nowrap;
        }}

        .tab-btn:hover {{
            color: var(--text-primary);
            background: rgba(255,255,255,0.5);
        }}

        .tab-btn.active {{
            color: #ffffff;
            background: var(--accent-blue);
            box-shadow: var(--shadow-sm);
            font-weight: 600;
        }}

        .tab-content {{
            display: none;
            animation: fadeIn 0.3s ease-in-out;
        }}

        .tab-content.active {{
            display: block;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(4px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* ===============================================================
           FOOTER
           =============================================================== */
        .dashboard-footer {{
            max-width: 1600px;
            margin: 1rem auto 0 auto;
            padding: 1.5rem 2rem;
            text-align: center;
            border-top: 1px solid var(--border-color);
        }}

        .dashboard-footer p {{
            font-size: 0.78rem;
            color: var(--text-muted);
        }}

        .dashboard-footer .footer-brand {{
            font-weight: 600;
            color: var(--text-secondary);
        }}

        /* ===============================================================
           RESPONSIVE BREAKPOINTS
           =============================================================== */

        /* Tablet / small laptop */
        @media (max-width: 1200px) {{
            .kpi-grid {{
                grid-template-columns: repeat(4, minmax(0, 1fr));
            }}
            .chart-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        /* Narrow tablet */
        @media (max-width: 900px) {{
            .kpi-grid {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
            .header-inner {{
                padding: 1.25rem 1.25rem;
            }}
            .dashboard-container {{
                padding: 1.25rem;
            }}
        }}

        /* Mobile */
        @media (max-width: 600px) {{
            .kpi-grid {{
                grid-template-columns: 1fr;
            }}
            .chart-grid {{
                grid-template-columns: 1fr;
                gap: 1rem;
            }}
            .brand-text h1 {{
                font-size: 1.15rem;
            }}
            .header-meta {{
                flex-wrap: wrap;
            }}
            .tabs {{
                flex-wrap: wrap;
            }}
            .kpi-value {{
                font-size: 1.6rem;
            }}
        }}

        /* Large desktop (1920px) */
        @media (min-width: 1600px) {{
            .kpi-grid {{
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 1.25rem;
            }}
        }}
    </style>
</head>
<body>
    <header class="dashboard-header">
        <div class="header-inner">
            <div class="header-brand">
                <div class="brand-logo">&#9992;</div>
                <div class="brand-text">
                    <h1>{title}</h1>
                    <p>{subtitle}</p>
                </div>
            </div>
            <div class="header-meta">
                <span class="header-badge">&#9679; Last Pipeline Run</span>
                <span class="header-timestamp">{timestamp}</span>
            </div>
        </div>
    </header>

    <main class="dashboard-container">
        {kpi_html}
        {charts_content}
    </main>

    <footer class="dashboard-footer">
        <p><span class="footer-brand">AirFlow Analytics Platform</span> &copy; 2026 &mdash; Enterprise Flight Operations Intelligence Layer</p>
    </footer>

    {extra_body}
</body>
</html>"""
    return html


# ============================================================================
# INDIVIDUAL DASHBOARDS COMPILING
# ============================================================================


def generate_html_dashboards(
    loaded_data: Dict[str, pd.DataFrame],
    plotly_figs: Tuple[go.Figure, go.Figure, go.Figure, go.Figure, go.Figure, go.Figure]
) -> List[str]:
    """
    Construct and write the four requested HTML dashboards.

    Parameters
    ----------
    loaded_data : Dict[str, pd.DataFrame]
        Validated analytical DataFrames.
    plotly_figs : Tuple[go.Figure, go.Figure, go.Figure, go.Figure, go.Figure, go.Figure]
        Tupel containing the generated interactive figures.

    Returns
    -------
    List[str]
        List of generated HTML dashboard file names.
    """
    logger.info("Building interactive HTML dashboards...")
    generated_dashboards: List[str] = []

    fig_top_airlines, fig_top_airports, fig_cancellation, fig_delays, fig_dep_dist, fig_arr_dist = plotly_figs
    kpi_html = build_kpi_section(loaded_data["executive_summary"])

    # 1. Executive Dashboard
    logger.info("Generating: executive_dashboard.html")
    exec_charts = f"""
    <div class="chart-grid">
        <div class="chart-card">
            <div class="chart-card-title">Top 10 Airlines by Flight Operations Volume</div>
            {fig_top_airlines.to_html(full_html=False, include_plotlyjs='cdn')}
        </div>
        <div class="chart-card">
            <div class="chart-card-title">Top 10 Airport Infrastructure Operations Hubs</div>
            {fig_top_airports.to_html(full_html=False, include_plotlyjs='cdn')}
        </div>
    </div>
    """
    exec_html = build_base_dashboard(
        title="Executive Performance Summary",
        subtitle="Operational flight KPIs and key statistics overview.",
        kpi_html=kpi_html,
        charts_content=exec_charts
    )
    with open(EXPORTS_DIR / "executive_dashboard.html", "w", encoding="utf-8") as f:
        f.write(exec_html)
    generated_dashboards.append("executive_dashboard.html")

    # 2. Airline Dashboard
    logger.info("Generating: airline_dashboard.html")
    airline_charts = f"""
    <div class="chart-grid">
        <div class="chart-card">
            <div class="chart-card-title">Airlines Cancellation Percentage Comparison</div>
            {fig_cancellation.to_html(full_html=False, include_plotlyjs='cdn')}
        </div>
        <div class="chart-card">
            <div class="chart-card-title">Delay Metrics Analysis Breakdown</div>
            {fig_delays.to_html(full_html=False, include_plotlyjs='cdn')}
        </div>
    </div>
    """
    airline_html = build_base_dashboard(
        title="Airline Performance Dashboard",
        subtitle="Detailed airline operations, delay categories, and cancellation analysis.",
        kpi_html="",  # KPIs omitted or specialized
        charts_content=airline_charts
    )
    with open(EXPORTS_DIR / "airline_dashboard.html", "w", encoding="utf-8") as f:
        f.write(airline_html)
    generated_dashboards.append("airline_dashboard.html")

    # 3. Airport Dashboard
    logger.info("Generating: airport_dashboard.html")
    airport_charts = f"""
    <div class="chart-grid">
        <div class="chart-card">
            <div class="chart-card-title">Top Airports Operations Traffic Grid</div>
            {fig_top_airports.to_html(full_html=False, include_plotlyjs='cdn')}
        </div>
        <div class="chart-card">
            <div class="chart-card-title">Delay Frequency & Distibutions</div>
            {fig_dep_dist.to_html(full_html=False, include_plotlyjs='cdn')}
        </div>
    </div>
    """
    airport_html = build_base_dashboard(
        title="Airport Infrastructure Analytics",
        subtitle="Global airport traffic volumes, congestion analysis, and traffic distribution.",
        kpi_html="",
        charts_content=airport_charts
    )
    with open(EXPORTS_DIR / "airport_dashboard.html", "w", encoding="utf-8") as f:
        f.write(airport_html)
    generated_dashboards.append("airport_dashboard.html")

    # 4. Master Dashboard Portal (Tabbed Interface)
    logger.info("Generating: dashboard.html (Master Portal)")
    tabbed_content = f"""
    <div class="tabs-container">
        <div class="tabs">
            <button id="btn-exec" class="tab-btn active" onclick="switchTab('exec')">Executive Overview</button>
            <button id="btn-airline" class="tab-btn" onclick="switchTab('airline')">Airline Performance</button>
            <button id="btn-airport" class="tab-btn" onclick="switchTab('airport')">Airport Traffic</button>
            <button id="btn-delay" class="tab-btn" onclick="switchTab('delay')">Delay Analytics</button>
        </div>
    </div>

    <!-- Executive Tab -->
    <div id="tab-exec" class="tab-content active">
        <div class="section-header">
            <h2 class="section-title">Executive Overview</h2>
            <p class="section-desc">Top-level flight volume and airport operations metrics</p>
        </div>
        <div class="chart-grid">
            <div class="chart-card">
                <div class="chart-card-title">Top 10 Airlines by Flight Count</div>
                {fig_top_airlines.to_html(full_html=False, include_plotlyjs='cdn')}
            </div>
            <div class="chart-card">
                <div class="chart-card-title">Top 10 Airports by Total Traffic</div>
                {fig_top_airports.to_html(full_html=False, include_plotlyjs='cdn')}
            </div>
        </div>
    </div>

    <!-- Airline Tab -->
    <div id="tab-airline" class="tab-content">
        <div class="section-header">
            <h2 class="section-title">Airline Performance</h2>
            <p class="section-desc">Cancellation rates, delay categories, and carrier comparisons</p>
        </div>
        <div class="chart-grid">
            <div class="chart-card">
                <div class="chart-card-title">Cancellation Rate by Airline</div>
                {fig_cancellation.to_html(full_html=False, include_plotlyjs='cdn')}
            </div>
            <div class="chart-card">
                <div class="chart-card-title">Grouped Delay Breakdown by Category</div>
                {fig_delays.to_html(full_html=False, include_plotlyjs='cdn')}
            </div>
        </div>
    </div>

    <!-- Airport Tab -->
    <div id="tab-airport" class="tab-content">
        <div class="section-header">
            <h2 class="section-title">Airport Traffic Analysis</h2>
            <p class="section-desc">Hub traffic distribution across origin and destination airports</p>
        </div>
        <div class="chart-grid">
            <div class="chart-card" style="grid-column: 1 / -1;">
                <div class="chart-card-title">Top Airports Hub Traffic Distribution (Origin vs Destination)</div>
                {fig_top_airports.to_html(full_html=False, include_plotlyjs='cdn')}
            </div>
        </div>
    </div>

    <!-- Delay Tab -->
    <div id="tab-delay" class="tab-content">
        <div class="section-header">
            <h2 class="section-title">Delay Distribution Analytics</h2>
            <p class="section-desc">Statistical distribution of departure and arrival delays (-20m to 180m)</p>
        </div>
        <div class="chart-grid">
            <div class="chart-card">
                <div class="chart-card-title">Departure Delay Distribution</div>
                {fig_dep_dist.to_html(full_html=False, include_plotlyjs='cdn')}
            </div>
            <div class="chart-card">
                <div class="chart-card-title">Arrival Delay Distribution</div>
                {fig_arr_dist.to_html(full_html=False, include_plotlyjs='cdn')}
            </div>
        </div>
    </div>
    """

    tab_script = """
    <script>
        function switchTab(tabId) {
            // Hide all tab contents
            const contents = document.querySelectorAll('.tab-content');
            contents.forEach(c => c.classList.remove('active'));

            // Deactivate all buttons
            const buttons = document.querySelectorAll('.tab-btn');
            buttons.forEach(b => b.classList.remove('active'));

            // Show current tab and activate button
            const tab = document.getElementById('tab-' + tabId);
            tab.classList.add('active');
            document.getElementById('btn-' + tabId).classList.add('active');

            // Force Plotly to redraw charts to fill containers correctly
            setTimeout(function() {
                var plots = tab.querySelectorAll('.js-plotly-plot');
                plots.forEach(function(plot) {
                    if (window.Plotly) {
                        Plotly.Plots.resize(plot);
                    }
                });
                window.dispatchEvent(new Event('resize'));
            }, 50);
        }

        // On page load, resize all visible Plotly plots
        window.addEventListener('load', function() {
            setTimeout(function() {
                window.dispatchEvent(new Event('resize'));
            }, 200);
        });
    </script>
    """

    master_html = build_base_dashboard(
        title="Enterprise Flight Analytics Portal",
        subtitle="Consolidated flight performance, network bottlenecks, and analytical insights dashboard.",
        kpi_html=kpi_html,
        charts_content=tabbed_content,
        extra_body=tab_script
    )

    with open(EXPORTS_DIR / "dashboard.html", "w", encoding="utf-8") as f:
        f.write(master_html)
    generated_dashboards.append("dashboard.html")

    logger.info("✓ Plotly interactive HTML dashboards written successfully.")
    return generated_dashboards


# ============================================================================
# REPORT WRITING
# ============================================================================


def write_dashboard_report(
    charts: List[str],
    dashboards: List[str],
    row_count: int,
    execution_time_ms: float,
    output_path: Path
) -> None:
    """
    Generate and save a detailed dashboard execution text report.

    Parameters
    ----------
    charts : List[str]
        List of generated static chart files.
    dashboards : List[str]
        List of generated interactive HTML dashboard files.
    row_count : int
        Number of processed rows.
    execution_time_ms : float
        Execution runtime in milliseconds.
    output_path : Path
        Path to save the summary report file.
    """
    logger.info(f"Writing execution summary report to: {output_path}")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_lines = [
        "======================================================================",
        "                     AIRFLOW ETL PIPELINE - VISUALIZATION REPORT       ",
        "======================================================================",
        f"Execution Timestamp: {timestamp}",
        f"Execution Duration:  {execution_time_ms:.2f} ms ({execution_time_ms / 1000.0:.2f} seconds)",
        f"Flights Processed:   {row_count:,} flights",
        f"Files Created:       {len(charts) + len(dashboards) + 1} total files",
        "",
        "1. GENERATED STATIC CHARTS (visualizations/charts/)",
        "----------------------------------------------------------------------"
    ]

    for idx, chart in enumerate(charts, 1):
        report_lines.append(f"  {idx}. {chart}")

    report_lines.extend([
        "",
        "2. GENERATED INTERACTIVE DASHBOARDS (exports/html/)",
        "----------------------------------------------------------------------"
    ])

    for idx, db in enumerate(dashboards, 1):
        report_lines.append(f"  {idx}. {db}")

    report_lines.extend([
        "",
        "3. EXECUTION STATS",
        "----------------------------------------------------------------------",
        f"  ✓ Output charts folder verified: {CHARTS_DIR}",
        f"  ✓ Output html dashboards folder verified: {EXPORTS_DIR}",
        f"  ✓ Report file generated: {output_path}",
        "======================================================================"
    ])

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        logger.info("Visualization execution report written successfully.")
    except IOError as e:
        logger.error(f"Failed to write summary report to {output_path}: {e}")
        raise


# ============================================================================
# MAIN ENTRYPOINT
# ============================================================================


def main() -> int:
    """
    Orchestrate and execute the complete visualization pipeline.

    Steps:
    1. Define required datasets specifications.
    2. Validate inputs, columns, and directory write permissions.
    3. Generate 6 static charts using Matplotlib.
    4. Compile 6 interactive Plotly figures.
    5. Construct and output 4 HTML dashboards.
    6. Generate text report file.
    7. Print professional Phase 5 summary to stdout.

    Returns
    -------
    int
        0 if successful, 1 if validation fails or another error occurs.
    """
    logger.info("=" * 70)
    logger.info("AirFlow Visualization & Dashboard Layer - ETL Phase 5")
    logger.info("=" * 70)

    start_time = time.time()

    # Define validation rules
    specs = [
        DatasetSpec(
            name="executive_summary",
            file_path=ANALYTICS_DATA_DIR / "executive_summary.csv",
            required_columns=[
                "TOTAL_FLIGHTS", "TOTAL_AIRLINES", "TOTAL_AIRPORTS",
                "CANCELLATION_RATE", "DIVERSION_RATE",
                "AVG_DEPARTURE_DELAY", "AVG_ARRIVAL_DELAY"
            ]
        ),
        DatasetSpec(
            name="airline_performance",
            file_path=ANALYTICS_DATA_DIR / "daily_airline_performance.csv",
            required_columns=[
                "AIRLINE_CODE", "FLIGHT_COUNT", "AVG_DEPARTURE_DELAY",
                "AVG_ARRIVAL_DELAY", "CANCELLATION_RATE", "DIVERSION_RATE"
            ]
        ),
        DatasetSpec(
            name="airport_traffic",
            file_path=ANALYTICS_DATA_DIR / "airport_traffic.csv",
            required_columns=[
                "AIRPORT_CODE", "ORIGIN_FLIGHTS", "DESTINATION_FLIGHTS", "TOTAL_TRAFFIC"
            ]
        ),
        DatasetSpec(
            name="delay_analysis",
            file_path=ANALYTICS_DATA_DIR / "delay_analysis.csv",
            required_columns=[
                "AIRLINE_CODE", "AVG_WEATHER_DELAY", "AVG_AIRLINE_DELAY",
                "AVG_SECURITY_DELAY", "AVG_AIR_SYSTEM_DELAY",
                "AVG_LATE_AIRCRAFT_DELAY"
            ]
        )
    ]

    try:
        # 1. Validate datasets
        loaded_data = validate_input_datasets(specs)

        # 1.b. SQL Verification (TASK 4 Audit)
        verify_kpis_with_db(loaded_data["executive_summary"], DATABASE_PATH)

        # 2. Generate Matplotlib static charts
        charts = generate_static_charts(loaded_data, DATABASE_PATH)

        # 3. Build interactive figures
        plotly_figs = build_plotly_charts(loaded_data, DATABASE_PATH)

        # 4. Generate HTML dashboards
        dashboards = generate_html_dashboards(loaded_data, plotly_figs)

        # Calculate statistics for the report
        exec_summary_df = loaded_data["executive_summary"]
        row_count = int(exec_summary_df.at[0, "TOTAL_FLIGHTS"])

        end_time = time.time()
        execution_time_ms = (end_time - start_time) * 1000.0

        # 5. Write execution report file
        write_dashboard_report(
            charts=charts,
            dashboards=dashboards,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            output_path=DASHBOARD_REPORT_PATH
        )

        # 6. Print professional Phase 5 summary matching request format
        print("\n================================================================")
        print("DASHBOARD PHASE SUMMARY")
        print("================================================================")
        print("\nCharts Generated:")
        print("✓ Top Airlines")
        print("✓ Top Airports")
        print("✓ Cancellation Analysis")
        print("✓ Delay Analysis")
        print("✓ Departure Delay Distribution")
        print("✓ Arrival Delay Distribution")
        print("\nDashboards Generated:")
        print("✓ Executive Dashboard")
        print("✓ Airline Dashboard")
        print("✓ Airport Dashboard")
        print("✓ Master Dashboard")
        print("\nReports Generated:")
        print("✓ dashboard_report.txt")
        print("\nExecution Successful")
        print("================================================================\n")

        logger.info("Visualization and Dashboard Phase completed successfully.")
        return 0

    except VisualizationValidationError as e:
        logger.critical(f"Validation framework rejected inputs: {e}")
        return 1
    except Exception as e:
        logger.error(f"Visualization pipeline failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
