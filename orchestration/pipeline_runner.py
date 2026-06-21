"""
AirFlow Flight Analytics Platform - Pipeline Orchestration & Automation.

This module implements Phase 6 of the ETL pipeline: a production-style
central orchestrator that executes all pipeline phases in sequence with:

- YAML-driven configuration management
- Enterprise logging (console + rotating file)
- Per-phase timing and status metadata (JSON)
- Health check / pre-flight validation framework
- Fail-fast execution with structured error reporting
- Pipeline run summary report generation
- Professional terminal output

Usage:
    python orchestration/pipeline_runner.py

Author: Principal Data Engineering Team
Version: 1.0.0
"""

import datetime
import json
import logging
import logging.handlers
import os
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# ============================================================================
# RESOLVE PATHS
# ============================================================================

ORCHESTRATION_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = ORCHESTRATION_DIR.parent.resolve()
CONFIG_PATH = PROJECT_ROOT / "config" / "pipeline_config.yaml"

# Ensure the scripts directory is on sys.path for phase imports
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ============================================================================
# CONFIGURATION LOADER
# ============================================================================


def load_config(config_path: Path) -> Dict[str, Any]:
    """
    Load and validate the YAML pipeline configuration.

    Parameters
    ----------
    config_path : Path
        Absolute path to pipeline_config.yaml.

    Returns
    -------
    Dict[str, Any]
        Parsed configuration dictionary.

    Raises
    ------
    FileNotFoundError
        If the configuration file does not exist.
    yaml.YAMLError
        If the YAML is malformed.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Pipeline configuration not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    if not isinstance(config, dict):
        raise ValueError("Pipeline configuration must be a YAML mapping (dict).")

    return config


# ============================================================================
# LOGGING SETUP
# ============================================================================


def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """
    Configure enterprise-grade logging with console and rotating file handlers.

    Parameters
    ----------
    config : Dict[str, Any]
        Full pipeline configuration dictionary.

    Returns
    -------
    logging.Logger
        Configured root pipeline logger.
    """
    log_cfg = config.get("logging", {})
    log_level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    log_format = log_cfg.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    date_fmt = log_cfg.get("date_format", "%Y-%m-%d %H:%M:%S")
    log_dir = PROJECT_ROOT / log_cfg.get("log_dir", "logs")
    log_file = PROJECT_ROOT / log_cfg.get("log_file", "logs/pipeline.log")
    max_bytes = log_cfg.get("max_bytes", 10_485_760)
    backup_count = log_cfg.get("backup_count", 5)

    # Ensure log directory exists
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("AirFlow.Pipeline")
    logger.setLevel(log_level)

    # Prevent duplicate handlers on re-import
    if logger.handlers:
        return logger

    formatter = logging.Formatter(log_format, datefmt=date_fmt)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# ============================================================================
# DATA MODELS
# ============================================================================


class PhaseStatus(str, Enum):
    """Enumeration of possible phase execution outcomes."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class PhaseResult:
    """Captures the execution result of a single pipeline phase."""
    phase_name: str
    status: str = PhaseStatus.PENDING.value
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: float = 0.0
    error_message: Optional[str] = None


@dataclass
class PipelineMetadata:
    """Aggregate execution metadata for the full pipeline run."""
    pipeline_name: str = "AirFlow Flight Analytics Pipeline"
    pipeline_version: str = "1.0.0"
    run_id: str = ""
    run_timestamp: str = ""
    total_duration_seconds: float = 0.0
    overall_status: str = PhaseStatus.PENDING.value
    phases: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise metadata to a plain dictionary."""
        return {
            "pipeline_name": self.pipeline_name,
            "pipeline_version": self.pipeline_version,
            "run_id": self.run_id,
            "run_timestamp": self.run_timestamp,
            "total_duration_seconds": round(self.total_duration_seconds, 3),
            "overall_status": self.overall_status,
            "phases": self.phases,
        }


# ============================================================================
# HEALTH CHECK FRAMEWORK
# ============================================================================


def run_health_checks(config: Dict[str, Any], logger: logging.Logger) -> bool:
    """
    Execute pre-flight validation before the pipeline runs.

    Checks performed:
    - Input CSV files exist and are readable.
    - All required output directories exist (created if missing).
    - Database directory exists (created if missing).

    Parameters
    ----------
    config : Dict[str, Any]
        Pipeline configuration.
    logger : logging.Logger
        Logger instance.

    Returns
    -------
    bool
        True if all health checks pass.
    """
    logger.info("Running pre-flight health checks...")
    all_ok = True
    actions_taken: List[str] = []

    # 1. Validate input files
    input_files = [
        config.get("inputs", {}).get("airlines_csv", "data/raw/airlines.csv"),
        config.get("inputs", {}).get("airports_csv", "data/raw/airports.csv"),
        config.get("inputs", {}).get("flights_csv", "data/raw/flights.csv"),
    ]

    for rel_path in input_files:
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            logger.error(f"HEALTH CHECK FAILED: Input file missing -> {full_path}")
            all_ok = False
        else:
            logger.info(f"  [OK] Input file exists: {rel_path}")

    # 2. Ensure required directories exist
    required_dirs = [
        config.get("outputs", {}).get("cleaned_data_dir", "data/cleaned"),
        config.get("outputs", {}).get("analytics_data_dir", "data/analytics"),
        config.get("database", {}).get("directory", "database"),
        config.get("reports", {}).get("directory", "reports"),
        config.get("visualizations", {}).get("charts_dir", "visualizations/charts"),
        config.get("visualizations", {}).get("dashboards_dir", "visualizations/dashboards"),
        config.get("visualizations", {}).get("exports_html_dir", "exports/html"),
        config.get("logging", {}).get("log_dir", "logs"),
        config.get("metadata", {}).get("directory", "metadata"),
    ]

    for rel_dir in required_dirs:
        dir_path = PROJECT_ROOT / rel_dir
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            msg = f"  [CREATED] Directory did not exist, created: {rel_dir}"
            logger.warning(msg)
            actions_taken.append(msg)
        else:
            logger.info(f"  [OK] Directory exists: {rel_dir}")

    if actions_taken:
        logger.info(f"  Health checks created {len(actions_taken)} missing directories.")

    if all_ok:
        logger.info("Pre-flight health checks PASSED.")
    else:
        logger.error("Pre-flight health checks FAILED. Cannot proceed.")

    return all_ok


# ============================================================================
# PHASE EXECUTOR
# ============================================================================


# Map of phase name -> (module_name, function_name, extra_kwargs)
PHASE_REGISTRY = {
    "extract":   ("extract",   "main", {}),
    "transform": ("transform", "main", {}),
    "load":      ("load",      "main", {}),
    "analytics": ("analytics", "main", {}),
    "dashboard": ("dashboard", "main", {}),
}

# Human-readable labels for terminal output
PHASE_LABELS = {
    "extract":   "Extract Phase",
    "transform": "Transform Phase",
    "load":      "Load Phase",
    "analytics": "Analytics Phase",
    "dashboard": "Dashboard Phase",
}


def execute_phase(
    phase_name: str,
    logger: logging.Logger,
) -> PhaseResult:
    """
    Import and execute a single pipeline phase module's main() function.

    Parameters
    ----------
    phase_name : str
        Registered phase identifier (e.g. 'extract', 'transform').
    logger : logging.Logger
        Logger instance.

    Returns
    -------
    PhaseResult
        Execution result with timing and status.
    """
    result = PhaseResult(phase_name=phase_name)

    if phase_name not in PHASE_REGISTRY:
        result.status = PhaseStatus.FAILED.value
        result.error_message = f"Unknown phase: {phase_name}"
        logger.error(result.error_message)
        return result

    module_name, func_name, kwargs = PHASE_REGISTRY[phase_name]

    result.status = PhaseStatus.RUNNING.value
    result.start_time = datetime.datetime.now().isoformat()

    start = time.perf_counter()

    try:
        logger.info(f"Importing module: scripts.{module_name}")
        module = __import__(module_name)
        entry_func = getattr(module, func_name)

        logger.info(f"Executing {phase_name}.{func_name}()...")
        exit_code = entry_func(**kwargs)

        elapsed = time.perf_counter() - start
        result.end_time = datetime.datetime.now().isoformat()
        result.duration_seconds = round(elapsed, 3)

        if exit_code == 0:
            result.status = PhaseStatus.SUCCESS.value
            logger.info(
                f"Phase '{phase_name}' completed successfully "
                f"in {result.duration_seconds:.1f}s."
            )
        else:
            result.status = PhaseStatus.FAILED.value
            result.error_message = f"Phase returned non-zero exit code: {exit_code}"
            logger.error(
                f"Phase '{phase_name}' FAILED with exit code {exit_code} "
                f"after {result.duration_seconds:.1f}s."
            )

    except Exception as exc:
        elapsed = time.perf_counter() - start
        result.end_time = datetime.datetime.now().isoformat()
        result.duration_seconds = round(elapsed, 3)
        result.status = PhaseStatus.FAILED.value
        result.error_message = f"{type(exc).__name__}: {exc}"
        logger.error(
            f"Phase '{phase_name}' raised an exception after "
            f"{result.duration_seconds:.1f}s: {exc}",
            exc_info=True,
        )

    return result


# ============================================================================
# METADATA PERSISTENCE
# ============================================================================


def save_metadata(metadata: PipelineMetadata, config: Dict[str, Any]) -> Path:
    """
    Persist pipeline execution metadata to JSON.

    Parameters
    ----------
    metadata : PipelineMetadata
        Completed pipeline metadata object.
    config : Dict[str, Any]
        Pipeline configuration.

    Returns
    -------
    Path
        Path to the written metadata JSON file.
    """
    meta_file = PROJECT_ROOT / config.get("metadata", {}).get(
        "pipeline_metadata_file", "metadata/pipeline_metadata.json"
    )
    meta_file.parent.mkdir(parents=True, exist_ok=True)

    with open(meta_file, "w", encoding="utf-8") as fh:
        json.dump(metadata.to_dict(), fh, indent=2, ensure_ascii=False)

    return meta_file


# ============================================================================
# PIPELINE RUN REPORT
# ============================================================================


def generate_run_report(
    metadata: PipelineMetadata,
    config: Dict[str, Any],
) -> Path:
    """
    Generate a human-readable pipeline run summary report.

    Parameters
    ----------
    metadata : PipelineMetadata
        Completed pipeline metadata.
    config : Dict[str, Any]
        Pipeline configuration.

    Returns
    -------
    Path
        Path to the generated report file.
    """
    report_path = PROJECT_ROOT / config.get("reports", {}).get(
        "pipeline_run_report", "reports/pipeline_run_report.txt"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)

    total_phases = len(metadata.phases)
    success_count = sum(1 for p in metadata.phases if p["status"] == PhaseStatus.SUCCESS.value)
    failed_count = sum(1 for p in metadata.phases if p["status"] == PhaseStatus.FAILED.value)
    skipped_count = sum(1 for p in metadata.phases if p["status"] == PhaseStatus.SKIPPED.value)
    success_rate = (success_count / total_phases * 100) if total_phases > 0 else 0.0

    lines = [
        "=" * 72,
        "  AIRFLOW FLIGHT ANALYTICS PLATFORM - PIPELINE RUN REPORT",
        "=" * 72,
        "",
        f"  Run ID:              {metadata.run_id}",
        f"  Execution Timestamp: {metadata.run_timestamp}",
        f"  Pipeline Version:    {metadata.pipeline_version}",
        "",
        "-" * 72,
        "  PHASE EXECUTION SUMMARY",
        "-" * 72,
        "",
        f"  {'Phase':<25}{'Status':<12}{'Duration':<15}{'Error':<20}",
        f"  {'-'*25:<25}{'-'*12:<12}{'-'*15:<15}{'-'*20:<20}",
    ]

    for phase in metadata.phases:
        duration_str = f"{phase['duration_seconds']:.1f} sec"
        error_str = phase.get("error_message", "") or ""
        if len(error_str) > 18:
            error_str = error_str[:18] + ".."
        lines.append(
            f"  {phase['phase_name']:<25}{phase['status']:<12}{duration_str:<15}{error_str:<20}"
        )

    lines.extend([
        "",
        "-" * 72,
        "  AGGREGATE STATISTICS",
        "-" * 72,
        "",
        f"  Total Phases Executed: {total_phases}",
        f"  Successful:            {success_count}",
        f"  Failed:                {failed_count}",
        f"  Skipped:               {skipped_count}",
        f"  Success Rate:          {success_rate:.1f}%",
        "",
        f"  Total Pipeline Runtime: {metadata.total_duration_seconds:.1f} seconds",
        f"  Pipeline Status:        {metadata.overall_status}",
        "",
        "=" * 72,
    ])

    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    return report_path


# ============================================================================
# TERMINAL OUTPUT
# ============================================================================


def print_banner() -> None:
    """Display the pipeline startup banner."""
    print()
    print("=" * 64)
    print("  AIRFLOW FLIGHT ANALYTICS PLATFORM")
    print("  Pipeline Orchestration & Automation Layer")
    print("=" * 64)
    print()


def print_phase_result(index: int, total: int, result: PhaseResult) -> None:
    """
    Print a single phase's result in the professional terminal format.

    Parameters
    ----------
    index : int
        1-based phase index.
    total : int
        Total number of phases.
    result : PhaseResult
        The phase execution result.
    """
    label = PHASE_LABELS.get(result.phase_name, result.phase_name)
    status_icon = "OK" if result.status == PhaseStatus.SUCCESS.value else "FAIL"
    status_color = result.status

    print(f"  [{index}/{total}] {label}")
    print(f"        Status:   {status_color}")
    print(f"        Duration: {result.duration_seconds:.1f} sec")

    if result.error_message:
        print(f"        Error:    {result.error_message}")

    print()


def print_summary(metadata: PipelineMetadata, meta_path: Path, report_path: Path) -> None:
    """
    Print the final pipeline execution summary.

    Parameters
    ----------
    metadata : PipelineMetadata
        Completed pipeline metadata.
    meta_path : Path
        Path to saved metadata JSON.
    report_path : Path
        Path to generated run report.
    """
    print("-" * 64)
    print()
    print(f"  TOTAL PIPELINE RUNTIME: {metadata.total_duration_seconds:.1f} sec")
    print()
    print(f"  PIPELINE STATUS: {metadata.overall_status}")
    print()
    print(f"  Metadata Updated:  {meta_path}")
    print(f"  Logs Written:      {PROJECT_ROOT / 'logs' / 'pipeline.log'}")
    print(f"  Report Generated:  {report_path}")
    print()
    print("=" * 64)
    print()


# ============================================================================
# MAIN PIPELINE RUNNER
# ============================================================================


def run_pipeline() -> int:
    """
    Execute the complete AirFlow ETL pipeline end-to-end.

    Workflow:
    1. Load YAML configuration.
    2. Initialise enterprise logging.
    3. Run health checks.
    4. Execute each phase sequentially with fail-fast semantics.
    5. Persist metadata to JSON.
    6. Generate run report.
    7. Print professional terminal summary.

    Returns
    -------
    int
        Exit code: 0 = full success, 1 = one or more phases failed.
    """
    # Configure UTF-8 for Windows console
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    pipeline_start = time.perf_counter()
    run_timestamp = datetime.datetime.now()

    # ------------------------------------------------------------------
    # 1. Load configuration
    # ------------------------------------------------------------------
    try:
        config = load_config(CONFIG_PATH)
    except Exception as exc:
        print(f"[FATAL] Cannot load configuration: {exc}", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # 2. Initialise logging
    # ------------------------------------------------------------------
    logger = setup_logging(config)
    logger.info("=" * 70)
    logger.info("AirFlow Pipeline Orchestrator - Starting execution")
    logger.info(f"Configuration loaded from: {CONFIG_PATH}")
    logger.info(f"Project root: {PROJECT_ROOT}")
    logger.info("=" * 70)

    # ------------------------------------------------------------------
    # 3. Prepare metadata
    # ------------------------------------------------------------------
    run_id = run_timestamp.strftime("%Y%m%d_%H%M%S")
    metadata = PipelineMetadata(
        pipeline_name=config.get("project", {}).get("name", "AirFlow Pipeline"),
        pipeline_version=config.get("project", {}).get("version", "1.0.0"),
        run_id=run_id,
        run_timestamp=run_timestamp.isoformat(),
    )

    # ------------------------------------------------------------------
    # 4. Health checks
    # ------------------------------------------------------------------
    print_banner()

    if not run_health_checks(config, logger):
        metadata.overall_status = PhaseStatus.FAILED.value
        metadata.total_duration_seconds = round(time.perf_counter() - pipeline_start, 3)

        meta_path = save_metadata(metadata, config)
        report_path = generate_run_report(metadata, config)

        print("  [ABORT] Pre-flight health checks failed.")
        print("          Fix the issues above and re-run.\n")
        print_summary(metadata, meta_path, report_path)
        return 1

    print("  Pre-flight health checks: PASSED\n")

    # ------------------------------------------------------------------
    # 5. Execute phases
    # ------------------------------------------------------------------
    phases_to_run: List[str] = config.get("execution", {}).get(
        "phases", ["extract", "transform", "load", "analytics", "dashboard"]
    )
    stop_on_failure: bool = config.get("execution", {}).get("stop_on_failure", True)

    total_phases = len(phases_to_run)
    all_results: List[PhaseResult] = []
    pipeline_failed = False

    for idx, phase_name in enumerate(phases_to_run, start=1):
        if pipeline_failed and stop_on_failure:
            # Mark remaining phases as skipped
            skipped = PhaseResult(
                phase_name=phase_name,
                status=PhaseStatus.SKIPPED.value,
            )
            all_results.append(skipped)
            metadata.phases.append(asdict(skipped))
            logger.warning(f"Phase '{phase_name}' SKIPPED due to prior failure.")
            print(f"  [{idx}/{total_phases}] {PHASE_LABELS.get(phase_name, phase_name)}")
            print(f"        Status:   SKIPPED")
            print()
            continue

        logger.info(f"--- Starting phase {idx}/{total_phases}: {phase_name} ---")
        result = execute_phase(phase_name, logger)
        all_results.append(result)
        metadata.phases.append(asdict(result))

        print_phase_result(idx, total_phases, result)

        if result.status == PhaseStatus.FAILED.value:
            pipeline_failed = True
            logger.error(
                f"Phase '{phase_name}' failed. "
                f"{'Halting pipeline.' if stop_on_failure else 'Continuing...'}"
            )

    # ------------------------------------------------------------------
    # 6. Finalise metadata
    # ------------------------------------------------------------------
    pipeline_end = time.perf_counter()
    metadata.total_duration_seconds = round(pipeline_end - pipeline_start, 3)
    metadata.overall_status = (
        PhaseStatus.FAILED.value if pipeline_failed else PhaseStatus.SUCCESS.value
    )

    meta_path = save_metadata(metadata, config)
    logger.info(f"Pipeline metadata saved to: {meta_path}")

    # ------------------------------------------------------------------
    # 7. Generate run report
    # ------------------------------------------------------------------
    report_path = generate_run_report(metadata, config)
    logger.info(f"Pipeline run report saved to: {report_path}")

    # ------------------------------------------------------------------
    # 8. Terminal summary
    # ------------------------------------------------------------------
    print_summary(metadata, meta_path, report_path)

    logger.info(
        f"Pipeline execution completed: {metadata.overall_status} "
        f"in {metadata.total_duration_seconds:.1f}s"
    )

    return 0 if not pipeline_failed else 1


# ============================================================================
# ENTRYPOINT
# ============================================================================


if __name__ == "__main__":
    sys.exit(run_pipeline())
