"""
Transform Module for AirFlow ETL Pipeline.

This module handles the transform phase of the ETL pipeline, providing:
- Data quality analysis and scoring
- Data cleaning and validation
- Business metrics generation
- Quality reporting and output dataset generation

Enterprise ETL Patterns Used:
- Immutable transformations (no inplace operations)
- Centralized logging (single logger instance)
- Separation of concerns (analysis, cleaning, metrics, reporting)
- Type hints for clarity and IDE support
- Comprehensive error handling with structured logging
- Memory optimization for large datasets

Author: Data Engineering Team
Version: 1.0.1
Last Updated: 2026-06-18
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Tuple, Any
from datetime import datetime

import pandas as pd

# ============================================================================
# CONFIGURATION & SETUP
# ============================================================================

# Configure logging (ensure idempotent setup for module imports)
def _setup_logging() -> logging.Logger:
    """
    Initialize logging with idempotent handler setup.
    
    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    log = logging.getLogger(__name__)
    
    # Only configure if handlers not already present
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
REPORTS_PATH = PROJECT_ROOT / "reports"

# Ensure output directories exist
DATA_CLEANED_PATH.mkdir(parents=True, exist_ok=True)
REPORTS_PATH.mkdir(parents=True, exist_ok=True)

# Business-critical delay columns
# TODO: Move to configuration file for environment-specific customization
DELAY_COLUMNS = [
    "DEPARTURE_DELAY",
    "ARRIVAL_DELAY",
    "AIR_SYSTEM_DELAY",
    "SECURITY_DELAY",
    "AIRLINE_DELAY",
    "LATE_AIRCRAFT_DELAY",
    "WEATHER_DELAY"
]

# Quality scoring thresholds (configurable for business rules)
# TODO: Implement scoring rules from business requirements
QUALITY_SCORE_THRESHOLDS = {
    "excellent": 90,
    "good": 75,
    "fair": 60,
    "poor": 0
}

# Deduction multipliers for quality score calculation
# TODO: Adjust based on business priorities
QUALITY_DEDUCTIONS = {
    "missing_values_multiplier": 0.5,  # Points per 1% missing
    "missing_values_max": 30,
    "duplicates_multiplier": 0.5,      # Points per 1% duplicates
    "duplicates_max": 20,
    "data_type_issues_max": 10
}

# ============================================================================
# PHASE 1: DATA QUALITY ANALYSIS
# ============================================================================


def analyze_missing_values(df: pd.DataFrame, verbose: bool = False) -> Dict[str, Any]:
    """
    Analyze missing values in a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame to analyze.
    verbose : bool, optional
        If True, log analysis details. Default is False (logged at orchestration level).

    Returns
    -------
    Dict[str, Any]
        Dictionary containing:
        - 'missing_count': Count of missing values per column
        - 'missing_percentage': Percentage of missing values per column
        - 'total_missing': Total count of missing values
        - 'total_missing_percentage': Overall percentage of missing values

    Raises
    ------
    ValueError
        If input DataFrame is empty.
    """
    if df.empty:
        raise ValueError("Input DataFrame is empty")

    if verbose:
        logger.debug("Analyzing missing values...")

    missing_count = df.isnull().sum()
    missing_percentage = (missing_count / len(df)) * 100
    total_missing = missing_count.sum()
    total_missing_percentage = (total_missing / (len(df) * len(df.columns))) * 100

    return {
        "missing_count": missing_count,
        "missing_percentage": missing_percentage,
        "total_missing": total_missing,
        "total_missing_percentage": total_missing_percentage
    }


def analyze_duplicates(df: pd.DataFrame, verbose: bool = False) -> Dict[str, Any]:
    """
    Analyze duplicate rows in a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame to analyze.
    verbose : bool, optional
        If True, log analysis details. Default is False (logged at orchestration level).

    Returns
    -------
    Dict[str, Any]
        Dictionary containing:
        - 'duplicate_count': Number of duplicate rows
        - 'duplicate_percentage': Percentage of duplicate rows
        - 'unique_rows': Count of unique rows

    Raises
    ------
    ValueError
        If input DataFrame is empty.
    """
    if df.empty:
        raise ValueError("Input DataFrame is empty")

    if verbose:
        logger.debug("Analyzing duplicates...")

    duplicate_count = df.duplicated().sum()
    duplicate_percentage = (duplicate_count / len(df)) * 100
    unique_rows = len(df) - duplicate_count

    return {
        "duplicate_count": duplicate_count,
        "duplicate_percentage": duplicate_percentage,
        "unique_rows": unique_rows
    }


def analyze_dtypes(df: pd.DataFrame, verbose: bool = False) -> Dict[str, str]:
    """
    Analyze data types in a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame to analyze.
    verbose : bool, optional
        If True, log analysis details. Default is False (logged at orchestration level).

    Returns
    -------
    Dict[str, str]
        Dictionary mapping column names to their data types.

    Raises
    ------
    ValueError
        If input DataFrame is empty.
    """
    if df.empty:
        raise ValueError("Input DataFrame is empty")

    if verbose:
        logger.debug("Analyzing data types...")

    return df.dtypes.astype(str).to_dict()


def get_dataframe_metrics(df: pd.DataFrame) -> Dict[str, int]:
    """
    Get basic DataFrame metrics (row count, column count).

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.

    Returns
    -------
    Dict[str, int]
        Dictionary containing:
        - 'row_count': Number of rows
        - 'column_count': Number of columns

    Raises
    ------
    ValueError
        If input DataFrame is empty.
    """
    if df.empty:
        raise ValueError("Input DataFrame is empty")

    return {
        "row_count": len(df),
        "column_count": len(df.columns)
    }


# ============================================================================
# PHASE 2: DATA QUALITY SCORE
# ============================================================================


def calculate_quality_score(
    df: pd.DataFrame,
    missing_analysis: Dict[str, Any],
    duplicates_analysis: Dict[str, Any]
) -> Tuple[int, str]:
    """
    Calculate a data quality score from 0 to 100.

    Scoring Logic:
    - Start at 100 points
    - Deduct points for missing values (configurable multiplier, max capped)
    - Deduct points for duplicate rows (configurable multiplier, max capped)
    - Deduct points for data type validation issues (max capped)
    - Final score: clipped to [0, 100]

    Business Rules:
    - TODO: Implement domain-specific quality rules
    - TODO: Add critical column weighting (e.g., DEPARTURE_DELAY more important)
    - TODO: Add configurable penalty thresholds

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.
    missing_analysis : Dict[str, Any]
        Result from analyze_missing_values().
    duplicates_analysis : Dict[str, Any]
        Result from analyze_duplicates().

    Returns
    -------
    Tuple[int, str]
        Quality score (0-100) and quality grade.

    Raises
    ------
    ValueError
        If inputs are invalid.
    """
    if df.empty:
        raise ValueError("Input DataFrame is empty")

    logger.debug("Calculating quality score...")

    score = 100.0

    # Deduct for missing values (configurable)
    missing_percentage = missing_analysis["total_missing_percentage"]
    missing_deduction = min(
        QUALITY_DEDUCTIONS["missing_values_max"],
        missing_percentage * QUALITY_DEDUCTIONS["missing_values_multiplier"]
    )
    score -= missing_deduction

    # Deduct for duplicates (configurable)
    duplicate_percentage = duplicates_analysis["duplicate_percentage"]
    duplicate_deduction = min(
        QUALITY_DEDUCTIONS["duplicates_max"],
        duplicate_percentage * QUALITY_DEDUCTIONS["duplicates_multiplier"]
    )
    score -= duplicate_deduction

    # Deduct for data type issues
    dtype_deduction = 0.0
    for col in df.columns:
        if col in DELAY_COLUMNS and df[col].dtype == "object":
            # Check if delay column has non-numeric values
            numeric_convert = pd.to_numeric(df[col], errors="coerce")
            non_numeric_count = numeric_convert.isna().sum()
            if non_numeric_count > 0:
                penalty = (non_numeric_count / len(df)) * 10
                dtype_deduction += min(2.0, penalty)

    dtype_deduction = min(QUALITY_DEDUCTIONS["data_type_issues_max"], dtype_deduction)
    score -= dtype_deduction

    # Clip score to valid range [0, 100]
    final_score = int(max(0, min(100, score)))

    # Determine quality grade based on configurable thresholds
    if final_score >= QUALITY_SCORE_THRESHOLDS["excellent"]:
        grade = "Excellent"
    elif final_score >= QUALITY_SCORE_THRESHOLDS["good"]:
        grade = "Good"
    elif final_score >= QUALITY_SCORE_THRESHOLDS["fair"]:
        grade = "Fair"
    else:
        grade = "Poor"

    logger.info(f"Quality Score: {final_score}/100 ({grade})")

    return final_score, grade


def generate_quality_summary(
    quality_score: int,
    grade: str,
    missing_analysis: Dict[str, Any],
    duplicates_analysis: Dict[str, Any],
    df_metrics: Dict[str, int]
) -> str:
    """
    Generate a readable quality summary report.

    Parameters
    ----------
    quality_score : int
        Data quality score (0-100).
    grade : str
        Quality grade (Excellent/Good/Fair/Poor).
    missing_analysis : Dict[str, Any]
        Result from analyze_missing_values().
    duplicates_analysis : Dict[str, Any]
        Result from analyze_duplicates().
    df_metrics : Dict[str, int]
        Result from get_dataframe_metrics().

    Returns
    -------
    str
        Formatted quality summary text.
    """
    summary = (
        f"\n{'='*70}\n"
        f"DATA QUALITY SUMMARY\n"
        f"{'='*70}\n\n"
        f"Overall Quality Score: {quality_score}/100 ({grade})\n\n"
        f"Dataset Metrics:\n"
        f"  - Total Rows:          {df_metrics['row_count']:,}\n"
        f"  - Total Columns:       {df_metrics['column_count']}\n\n"
        f"Missing Values Analysis:\n"
        f"  - Total Missing Values: {missing_analysis['total_missing']:,}\n"
        f"  - Total Missing %:      {missing_analysis['total_missing_percentage']:.2f}%\n\n"
        f"Duplicate Analysis:\n"
        f"  - Duplicate Rows:      {duplicates_analysis['duplicate_count']:,}\n"
        f"  - Duplicate %:         {duplicates_analysis['duplicate_percentage']:.2f}%\n"
        f"  - Unique Rows:         {duplicates_analysis['unique_rows']:,}\n\n"
        f"{'='*70}\n"
    )

    return summary


# ============================================================================
# PHASE 3: DATA CLEANING
# ============================================================================


def clean_missing_values(df: pd.DataFrame, verbose: bool = False) -> pd.DataFrame:
    """
    Clean missing values in DataFrame with assignment-safe operations.

    Strategy:
    - Numeric columns: Fill with median value
    - Categorical columns: Fill with "UNKNOWN"

    This function uses immutable transformations (no inplace operations)
    to avoid Pandas SettingWithCopyWarning and ensure thread-safe behavior.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame with potential missing values.
    verbose : bool, optional
        If True, log column-level fill operations. Default is False.

    Returns
    -------
    pd.DataFrame
        Cleaned DataFrame with missing values handled.

    Raises
    ------
    ValueError
        If input DataFrame is empty.
    """
    if df.empty:
        raise ValueError("Input DataFrame is empty")

    # Create explicit copy to avoid SettingWithCopyWarning
    df_cleaned = df.copy()
    columns_with_nulls = df_cleaned.columns[df_cleaned.isnull().any()].tolist()
    
    if not columns_with_nulls:
        logger.debug("No missing values found in DataFrame")
        return df_cleaned

    logger.info(f"Cleaning missing values in {len(columns_with_nulls)} columns")

    # Process numeric columns with median fill
    numeric_cols_with_nulls = [
        col for col in columns_with_nulls 
        if df_cleaned[col].dtype in ["int64", "float64"]
    ]
    for col in numeric_cols_with_nulls:
        median_value = df_cleaned[col].median()
        df_cleaned[col] = df_cleaned[col].fillna(median_value)
        if verbose:
            logger.debug(f"Filled {col} with median: {median_value}")

    # Process categorical columns with "UNKNOWN" fill
    categorical_cols_with_nulls = [
        col for col in columns_with_nulls 
        if col not in numeric_cols_with_nulls
    ]
    for col in categorical_cols_with_nulls:
        df_cleaned[col] = df_cleaned[col].fillna("UNKNOWN")
        if verbose:
            logger.debug(f"Filled {col} with 'UNKNOWN'")

    logger.debug("Missing values cleaned successfully")
    return df_cleaned


def clean_duplicates(
    df: pd.DataFrame, 
    subset: Tuple[str, ...] = None, 
    verbose: bool = False
) -> pd.DataFrame:
    """
    Remove duplicate rows from DataFrame.

    Strategy:
    - Keep first occurrence of duplicate rows
    - TODO: Implement business rule for duplicate handling (e.g., latest timestamp)
    - TODO: Add configurable keep strategy (first/last/all)

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame with potential duplicates.
    subset : Tuple[str, ...], optional
        Column names to consider for identifying duplicates.
        If None, all columns are considered. Default is None.
    verbose : bool, optional
        If True, log removal statistics. Default is False.

    Returns
    -------
    pd.DataFrame
        DataFrame with duplicates removed (reset index).

    Raises
    ------
    ValueError
        If input DataFrame is empty.
    """
    if df.empty:
        raise ValueError("Input DataFrame is empty")

    initial_rows = len(df)
    df_cleaned = df.drop_duplicates(subset=subset, keep="first").reset_index(drop=True)
    removed_rows = initial_rows - len(df_cleaned)

    if verbose or removed_rows > 0:
        logger.debug(f"Removed {removed_rows} duplicate rows")

    return df_cleaned


def validate_delay_columns(df: pd.DataFrame, verbose: bool = False) -> pd.DataFrame:
    """
    Validate and convert delay columns to numeric format.

    Delay columns (defined in DELAY_COLUMNS):
    - DEPARTURE_DELAY, ARRIVAL_DELAY, AIR_SYSTEM_DELAY
    - SECURITY_DELAY, AIRLINE_DELAY, LATE_AIRCRAFT_DELAY, WEATHER_DELAY

    Strategy:
    - Convert all delay columns to numeric
    - Invalid values become NaN for subsequent imputation
    - Log conversion statistics for audit trail

    This function uses assignment-safe operations to avoid Pandas warnings
    when working with potentially derived DataFrames.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame with delay columns.
    verbose : bool, optional
        If True, log per-column conversion details. Default is False.

    Returns
    -------
    pd.DataFrame
        DataFrame with validated delay columns (numeric type).

    Raises
    ------
    ValueError
        If input DataFrame is empty.
    """
    if df.empty:
        raise ValueError("Input DataFrame is empty")

    df_validated = df.copy()
    
    # Check for missing expected columns
    present_delay_cols = [col for col in DELAY_COLUMNS if col in df_validated.columns]
    missing_delay_cols = [col for col in DELAY_COLUMNS if col not in df_validated.columns]
    
    if missing_delay_cols:
        logger.warning(f"Missing expected delay columns: {missing_delay_cols}")
    
    if not present_delay_cols:
        logger.warning("No delay columns found in DataFrame")
        return df_validated

    logger.info(f"Validating {len(present_delay_cols)} delay columns to numeric format")

    # Convert each delay column to numeric, capturing invalid values as NaN
    invalid_count_total = 0
    for col in present_delay_cols:
        # Track invalid values before conversion for audit purposes
        # TODO: Implement business rule for handling specific invalid delay codes
        invalid_mask = ~df_validated[col].astype(str).str.strip().apply(
            lambda x: (isinstance(x, str) and (x.lstrip('-').replace('.', '', 1).isdigit() or x == 'nan')) or pd.isna(x)
        )
        invalid_count = invalid_mask.sum()
        invalid_count_total += invalid_count
        
        # Perform numeric conversion (invalid values → NaN)
        df_validated[col] = pd.to_numeric(df_validated[col], errors="coerce")
        
        if verbose and invalid_count > 0:
            logger.debug(
                f"Column {col}: {invalid_count} invalid values converted to NaN"
            )

    if invalid_count_total > 0:
        logger.info(f"Total invalid delay values converted to NaN: {invalid_count_total}")
    
    logger.debug("Delay columns validated successfully")
    return df_validated


# ============================================================================
# PHASE 4: BUSINESS METRICS
# ============================================================================


def generate_business_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Generate analytics-ready business metrics from flights data.

    Metrics Generated:
    - total_flights: Total number of flight records
    - cancelled_flights: Count and percentage of cancelled flights
    - diverted_flights: Count and percentage of diverted flights
    - avg_departure_delay: Average departure delay (minutes)
    - avg_arrival_delay: Average arrival delay (minutes)
    - on_time_flights: Count and percentage of on-time flights

    Business Rules (TODO):
    - TODO: Define SLA thresholds (on-time vs. late)
    - TODO: Implement airline-specific metrics
    - TODO: Add seasonal adjustments
    - TODO: Calculate delay root cause distribution

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned flights DataFrame.

    Returns
    -------
    Dict[str, Any]
        Dictionary containing all calculated business metrics.

    Raises
    ------
    ValueError
        If input DataFrame is empty or required columns missing.
    KeyError
        If required columns are missing.
    """
    if df.empty:
        raise ValueError("Input DataFrame is empty")

    logger.debug("Generating business metrics...")

    required_cols = [
        "CANCELLED", "DIVERTED", "DEPARTURE_DELAY", "ARRIVAL_DELAY"
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise KeyError(f"Missing required columns: {missing_cols}")

    total_flights = len(df)
    
    # Calculate flight disposition metrics
    cancelled_flights = int(df["CANCELLED"].sum())
    diverted_flights = int(df["DIVERTED"].sum())

    # Calculate delay metrics (robust to NaN values)
    avg_departure_delay = df["DEPARTURE_DELAY"].mean()
    avg_arrival_delay = df["ARRIVAL_DELAY"].mean()

    # Calculate on-time performance (both departure and arrival on-time)
    on_time_mask = (df["DEPARTURE_DELAY"] <= 0) & (df["ARRIVAL_DELAY"] <= 0)
    on_time_flights = int(on_time_mask.sum())

    metrics = {
        "total_flights": total_flights,
        "cancelled_flights": cancelled_flights,
        "cancelled_percentage": (cancelled_flights / total_flights * 100)
        if total_flights > 0 else 0,
        "diverted_flights": diverted_flights,
        "diverted_percentage": (diverted_flights / total_flights * 100)
        if total_flights > 0 else 0,
        "avg_departure_delay": round(avg_departure_delay, 2),
        "avg_arrival_delay": round(avg_arrival_delay, 2),
        "on_time_flights": on_time_flights,
        "on_time_percentage": (on_time_flights / total_flights * 100)
        if total_flights > 0 else 0
    }

    logger.debug("Business metrics generated successfully")

    return metrics


def format_business_metrics(metrics: Dict[str, Any]) -> str:
    """
    Format business metrics for reporting.

    Parameters
    ----------
    metrics : Dict[str, Any]
        Business metrics dictionary from generate_business_metrics().

    Returns
    -------
    str
        Formatted metrics text.
    """
    formatted = (
        f"\nBUSINESS METRICS\n"
        f"{'-'*70}\n"
        f"Total Flights:           {metrics['total_flights']:,}\n"
        f"Cancelled Flights:       {metrics['cancelled_flights']:,} "
        f"({metrics['cancelled_percentage']:.2f}%)\n"
        f"Diverted Flights:        {metrics['diverted_flights']:,} "
        f"({metrics['diverted_percentage']:.2f}%)\n"
        f"On-Time Flights:         {metrics['on_time_flights']:,} "
        f"({metrics['on_time_percentage']:.2f}%)\n"
        f"Avg Departure Delay:     {metrics['avg_departure_delay']:.2f} minutes\n"
        f"Avg Arrival Delay:       {metrics['avg_arrival_delay']:.2f} minutes\n"
    )

    return formatted


# ============================================================================
# PHASE 5: REPORTING
# ============================================================================


def save_quality_report(
    quality_score: int,
    grade: str,
    quality_summary: str,
    missing_analysis: Dict[str, Any],
    duplicates_analysis: Dict[str, Any],
    business_metrics: Dict[str, Any],
    dtypes_analysis: Dict[str, str]
) -> Path:
    """
    Generate and save comprehensive data quality report.

    Report Contents:
    - Header with generation timestamp
    - Quality score and grade
    - Dataset metrics (row count, column count)
    - Missing values breakdown by column
    - Data types by column
    - Business metrics summary

    Parameters
    ----------
    quality_score : int
        Data quality score (0-100).
    grade : str
        Quality grade (Excellent/Good/Fair/Poor).
    quality_summary : str
        Quality summary text.
    missing_analysis : Dict[str, Any]
        Missing values analysis from analyze_missing_values().
    duplicates_analysis : Dict[str, Any]
        Duplicates analysis from analyze_duplicates().
    business_metrics : Dict[str, Any]
        Business metrics from generate_business_metrics().
    dtypes_analysis : Dict[str, str]
        Data types analysis from analyze_dtypes().

    Returns
    -------
    Path
        Path to the generated report file.

    Raises
    ------
    IOError
        If report cannot be written.
    """
    report_path = REPORTS_PATH / "transform_report.txt"

    try:
        with open(report_path, "w", encoding="utf-8") as f:
            # Report header
            f.write("="*70 + "\n")
            f.write("AIRFLOW - DATA QUALITY REPORT\n")
            f.write("="*70 + "\n")
            f.write(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*70 + "\n\n")

            # Quality summary section
            f.write(quality_summary)

            # Missing values breakdown section
            f.write("MISSING VALUES BREAKDOWN BY COLUMN\n")
            f.write("-"*70 + "\n")
            for col, count in missing_analysis["missing_count"].items():
                percentage = missing_analysis["missing_percentage"][col]
                f.write(f"{col:30s}: {count:8,} ({percentage:6.2f}%)\n")
            f.write("\n")

            # Data types section
            f.write("DATA TYPES BY COLUMN\n")
            f.write("-"*70 + "\n")
            for col, dtype in dtypes_analysis.items():
                f.write(f"{col:30s}: {dtype}\n")
            f.write("\n")

            # Business metrics section
            f.write(format_business_metrics(business_metrics))

            # Report footer
            f.write("\n" + "="*70 + "\n")
            f.write("END OF REPORT\n")
            f.write("="*70 + "\n")

        logger.debug(f"Quality report saved: {report_path}")
        return report_path

    except IOError as e:
        logger.error(f"Error writing report to {report_path}: {e}")
        raise


# ============================================================================
# PHASE 6: OUTPUT DATASET
# ============================================================================


def save_cleaned_dataset(
    df: pd.DataFrame, 
    output_filename: str = "flights_cleaned.csv"
) -> Path:
    """
    Save cleaned dataset to CSV file.

    Output Format:
    - CSV with UTF-8 encoding
    - No index column
    - TODO: Implement Parquet export for better compression
    - TODO: Add data validation before export

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned DataFrame to save.
    output_filename : str, optional
        Output filename. Default is "flights_cleaned.csv".

    Returns
    -------
    Path
        Path to the saved file.

    Raises
    ------
    IOError
        If file cannot be written.
    ValueError
        If DataFrame is empty.
    """
    if df.empty:
        raise ValueError("Input DataFrame is empty")

    output_path = DATA_CLEANED_PATH / output_filename

    try:
        df.to_csv(output_path, index=False, encoding="utf-8")
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.debug(
            f"Cleaned dataset saved: {output_path} "
            f"({file_size_mb:.2f} MB, {len(df):,} rows)"
        )
        return output_path

    except IOError as e:
        logger.error(f"Error saving dataset to {output_path}: {e}")
        raise


# ============================================================================
# ORCHESTRATION
# ============================================================================


def transform_flights_data(
    df: pd.DataFrame, 
    verbose: bool = False
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Execute complete transformation pipeline on flights data.

    Pipeline Phases:
    1. Analyze data quality (Phase 1)
    2. Calculate quality score (Phase 2)
    3. Clean missing values and duplicates (Phase 3)
    4. Validate delay columns (Phase 3)
    5. Generate business metrics (Phase 4)
    6. Save quality report (Phase 5)
    7. Save cleaned dataset (Phase 6)

    This is the main orchestration function that coordinates all
    transformation stages. Verbose logging can be controlled per stage.

    Parameters
    ----------
    df : pd.DataFrame
        Raw flights DataFrame.
    verbose : bool, optional
        If True, enable detailed per-function logging. Default is False.

    Returns
    -------
    Tuple[pd.DataFrame, Dict[str, Any]]
        - Transformed DataFrame (cleaned and validated)
        - Transformation metadata containing:
          - quality_score: Data quality score (0-100)
          - quality_grade: Quality grade
          - initial_rows: Row count before cleaning
          - final_rows: Row count after cleaning
          - rows_removed: Number of rows removed
          - report_path: Path to quality report
          - output_path: Path to cleaned dataset
          - business_metrics: Analytics-ready metrics
          - missing_values: Count of missing values handled
          - duplicates_removed: Count of duplicates removed

    Raises
    ------
    ValueError
        If input DataFrame is invalid.
    Exception
        If any transformation step fails (wrapped in logger.error).
    """
    logger.info("Starting transformation pipeline...")

    if df.empty:
        raise ValueError("Input DataFrame is empty")

    try:
        # PHASE 1: Data Quality Analysis
        logger.info("PHASE 1: Analyzing data quality...")
        df_metrics = get_dataframe_metrics(df)
        missing_analysis = analyze_missing_values(df, verbose=verbose)
        duplicates_analysis = analyze_duplicates(df, verbose=verbose)
        dtypes_analysis = analyze_dtypes(df, verbose=verbose)

        logger.info(
            f"Initial dataset: {df_metrics['row_count']:,} rows, "
            f"{df_metrics['column_count']} columns"
        )

        # PHASE 2: Data Quality Scoring
        logger.info("PHASE 2: Calculating quality score...")
        quality_score, grade = calculate_quality_score(
            df, missing_analysis, duplicates_analysis
        )
        quality_summary = generate_quality_summary(
            quality_score, grade, missing_analysis, duplicates_analysis, df_metrics
        )

        # PHASE 3: Data Cleaning
        logger.info("PHASE 3: Cleaning data...")
        df_cleaned = clean_missing_values(df, verbose=verbose)
        df_cleaned = clean_duplicates(df_cleaned, verbose=verbose)
        df_cleaned = validate_delay_columns(df_cleaned, verbose=verbose)

        logger.info(
            f"Cleaned dataset: {len(df_cleaned):,} rows, "
            f"{len(df_cleaned.columns)} columns"
        )

        # PHASE 4: Business Metrics
        logger.info("PHASE 4: Generating business metrics...")
        business_metrics = generate_business_metrics(df_cleaned)

        # PHASE 5: Reporting
        logger.info("PHASE 5: Generating quality report...")
        report_path = save_quality_report(
            quality_score,
            grade,
            quality_summary,
            missing_analysis,
            duplicates_analysis,
            business_metrics,
            dtypes_analysis
        )

        # PHASE 6: Output Dataset
        logger.info("PHASE 6: Saving cleaned dataset...")
        output_path = save_cleaned_dataset(df_cleaned)

        # Compile transformation metadata
        metadata = {
            "quality_score": quality_score,
            "quality_grade": grade,
            "initial_rows": df_metrics["row_count"],
            "final_rows": len(df_cleaned),
            "rows_removed": df_metrics["row_count"] - len(df_cleaned),
            "report_path": str(report_path),
            "output_path": str(output_path),
            "business_metrics": business_metrics,
            "missing_values": missing_analysis["total_missing"],
            "duplicates_removed": duplicates_analysis["duplicate_count"]
        }

        logger.info("Transformation pipeline completed successfully")

        return df_cleaned, metadata

    except Exception as e:
        logger.error(f"Transformation pipeline failed: {e}", exc_info=True)
        raise


def main(verbose: bool = False) -> int:
    """
    Main entry point for the transform module.

    Workflow:
    1. Load raw datasets (airlines, airports, flights) via extract module
    2. Execute transformation pipeline on flights data
    3. Display transformation summary to console
    4. Return success/failure status code

    Parameters
    ----------
    verbose : bool, optional
        If True, enable detailed per-function logging. Default is False.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    logger.info("="*70)
    logger.info("AirFlow Transform Phase - ETL Pipeline")
    logger.info("="*70)

    try:
        # Dynamically import extract module to load raw data
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from extract import extract_all_data

        logger.info("Loading raw datasets...")
        airlines_df, airports_df, flights_df = extract_all_data()

        logger.info(
            f"Loaded datasets: Airlines={len(airlines_df):,} rows, "
            f"Airports={len(airports_df):,} rows, Flights={len(flights_df):,} rows"
        )

        # Execute transformation pipeline
        flights_cleaned, metadata = transform_flights_data(flights_df, verbose=verbose)

        # Display transformation summary to console (always show, regardless of log level)
        print("\n" + "="*70)
        print("TRANSFORMATION SUMMARY")
        print("="*70)
        print(f"Quality Score:       {metadata['quality_score']}/100 "
              f"({metadata['quality_grade']})")
        print(f"Initial Rows:        {metadata['initial_rows']:,}")
        print(f"Final Rows:          {metadata['final_rows']:,}")
        print(f"Rows Removed:        {metadata['rows_removed']:,}")
        print(f"Missing Values:      {metadata['missing_values']:,}")
        print(f"Duplicates Removed:  {metadata['duplicates_removed']:,}")
        print(f"\nReport:              {metadata['report_path']}")
        print(f"Cleaned Data:        {metadata['output_path']}")
        print("="*70 + "\n")

        logger.info("Transform phase completed successfully!")

        return 0

    except ModuleNotFoundError:
        logger.error(
            "Extract module not found. Ensure extract.py exists in scripts/ directory"
        )
        return 1
    except Exception as e:
        logger.error(f"Transform phase failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    # TODO: Add command-line argument parsing for --verbose flag
    exit_code = main(verbose=False)
    sys.exit(exit_code)
