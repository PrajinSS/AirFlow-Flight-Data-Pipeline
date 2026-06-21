import sqlite3
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent
WH_DB = PROJECT_ROOT / "warehouse" / "warehouse.db"
REPORTS_DIR = PROJECT_ROOT / "reports"

def run_data_quality_check():
    report = []
    report.append("======================================================================")
    report.append("ENTERPRISE DATA QUALITY FRAMEWORK - STAR SCHEMA WAREHOUSE")
    report.append("======================================================================\n")

    with sqlite3.connect(WH_DB) as conn:
        cursor = conn.cursor()

        # 1. Row Counts
        report.append("1. ROW COUNTS")
        report.append("-------------")
        fact_flights = cursor.execute("SELECT COUNT(*) FROM fact_flights").fetchone()[0]
        dim_airline = cursor.execute("SELECT COUNT(*) FROM dim_airline").fetchone()[0]
        dim_airport = cursor.execute("SELECT COUNT(*) FROM dim_airport").fetchone()[0]
        dim_date = cursor.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0]
        
        report.append(f"fact_flights: {fact_flights:,}")
        report.append(f"dim_airline: {dim_airline:,}")
        report.append(f"dim_airport: {dim_airport:,}")
        report.append(f"dim_date: {dim_date:,}\n")

        # 2. Referential Integrity (Orphan Records)
        report.append("2. REFERENTIAL INTEGRITY (ORPHAN RECORDS)")
        report.append("-----------------------------------------")
        orphan_airlines = cursor.execute("SELECT COUNT(*) FROM fact_flights WHERE airline_key NOT IN (SELECT airline_key FROM dim_airline)").fetchone()[0]
        orphan_origins = cursor.execute("SELECT COUNT(*) FROM fact_flights WHERE origin_airport_key NOT IN (SELECT airport_key FROM dim_airport)").fetchone()[0]
        orphan_dests = cursor.execute("SELECT COUNT(*) FROM fact_flights WHERE dest_airport_key NOT IN (SELECT airport_key FROM dim_airport)").fetchone()[0]
        orphan_dates = cursor.execute("SELECT COUNT(*) FROM fact_flights WHERE date_key NOT IN (SELECT date_key FROM dim_date)").fetchone()[0]
        
        report.append(f"Orphan Airline Keys: {orphan_airlines}")
        report.append(f"Orphan Origin Airport Keys: {orphan_origins}")
        report.append(f"Orphan Dest Airport Keys: {orphan_dests}")
        report.append(f"Orphan Date Keys: {orphan_dates}\n")
        
        # 3. Null Checks in Fact Table
        report.append("3. CRITICAL NULL CHECKS (FACT_FLIGHTS)")
        report.append("--------------------------------------")
        null_airline = cursor.execute("SELECT COUNT(*) FROM fact_flights WHERE airline_key IS NULL").fetchone()[0]
        null_origin = cursor.execute("SELECT COUNT(*) FROM fact_flights WHERE origin_airport_key IS NULL").fetchone()[0]
        null_dest = cursor.execute("SELECT COUNT(*) FROM fact_flights WHERE dest_airport_key IS NULL").fetchone()[0]
        null_date = cursor.execute("SELECT COUNT(*) FROM fact_flights WHERE date_key IS NULL").fetchone()[0]
        
        report.append(f"Null Airline Keys: {null_airline}")
        report.append(f"Null Origin Airport Keys: {null_origin}")
        report.append(f"Null Dest Airport Keys: {null_dest}")
        report.append(f"Null Date Keys: {null_date}\n")

        # 4. Dimension Duplicates
        report.append("4. DIMENSION DUPLICATES")
        report.append("-----------------------")
        dup_airlines = cursor.execute("SELECT COUNT(*) FROM (SELECT airline_key FROM dim_airline GROUP BY airline_key HAVING COUNT(*) > 1)").fetchone()[0]
        dup_airports = cursor.execute("SELECT COUNT(*) FROM (SELECT airport_key FROM dim_airport GROUP BY airport_key HAVING COUNT(*) > 1)").fetchone()[0]
        dup_dates = cursor.execute("SELECT COUNT(*) FROM (SELECT date_key FROM dim_date GROUP BY date_key HAVING COUNT(*) > 1)").fetchone()[0]

        report.append(f"Duplicate Airline Keys: {dup_airlines}")
        report.append(f"Duplicate Airport Keys: {dup_airports}")
        report.append(f"Duplicate Date Keys: {dup_dates}\n")
        
        # Final Status
        total_issues = orphan_airlines + orphan_origins + orphan_dests + orphan_dates + null_airline + null_origin + null_dest + null_date + dup_airlines + dup_airports + dup_dates
        if total_issues == 0:
            report.append("OVERALL STATUS: SUCCESS (No Quality Issues Detected)\n")
        else:
            report.append(f"OVERALL STATUS: FAILED ({total_issues} Quality Issues Detected)\n")

    with open(REPORTS_DIR / "data_quality_report.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(report))

if __name__ == '__main__':
    run_data_quality_check()
