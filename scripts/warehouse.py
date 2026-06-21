import sqlite3
import pandas as pd
from pathlib import Path
import logging
import sys

def setup_logging():
    log = logging.getLogger("WarehouseBuilder")
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    return log

logger = setup_logging()

PROJECT_ROOT = Path(__file__).parent.parent
DB_SOURCE = PROJECT_ROOT / "database" / "airflow.db"
WH_DEST = PROJECT_ROOT / "warehouse" / "warehouse.db"
RAW_AIRPORTS = PROJECT_ROOT / "data" / "raw" / "airports.csv"
RAW_AIRLINES = PROJECT_ROOT / "data" / "raw" / "airlines.csv"

def build_warehouse():
    logger.info("Connecting to source and destination databases...")
    
    # 1. Load Raw CSVs for richer dimensions
    airports_raw = pd.read_csv(RAW_AIRPORTS)
    airlines_raw = pd.read_csv(RAW_AIRLINES)
    
    # 2. Extract facts and keys from airflow.db
    with sqlite3.connect(DB_SOURCE) as src_conn:
        flights_df = pd.read_sql("SELECT * FROM flights", src_conn)
        db_airlines = pd.read_sql("SELECT AIRLINE_ID, AIRLINE FROM airlines", src_conn)
        db_airports = pd.read_sql("SELECT AIRPORT_ID, AIRPORT FROM airports", src_conn)
    
    # --- DIM AIRPORT ---
    logger.info("Building dim_airport...")
    dim_airport = pd.merge(db_airports, airports_raw, left_on='AIRPORT', right_on='IATA_CODE', how='left')
    dim_airport = dim_airport.rename(columns={
        'AIRPORT_ID': 'airport_key',
        'IATA_CODE': 'airport_code',
        'AIRPORT_y': 'airport_name',
        'CITY': 'city',
        'STATE': 'state',
        'COUNTRY': 'country',
        'LATITUDE': 'latitude',
        'LONGITUDE': 'longitude'
    })[['airport_key', 'airport_code', 'airport_name', 'city', 'state', 'country', 'latitude', 'longitude']]
    
    # --- DIM AIRLINE ---
    logger.info("Building dim_airline...")
    dim_airline = pd.merge(db_airlines, airlines_raw, left_on='AIRLINE', right_on='IATA_CODE', how='left')
    dim_airline = dim_airline.rename(columns={
        'AIRLINE_ID': 'airline_key',
        'IATA_CODE': 'airline_code',
        'AIRLINE_y': 'airline_name'
    })[['airline_key', 'airline_code', 'airline_name']]
    
    # --- DIM DATE ---
    logger.info("Building dim_date...")
    # Create dates from flights to cover the required range
    flights_df['date_str'] = flights_df['YEAR'].astype(str) + '-' + flights_df['MONTH'].astype(str).str.zfill(2) + '-' + flights_df['DAY'].astype(str).str.zfill(2)
    dates = pd.to_datetime(flights_df['date_str'].unique())
    
    dim_date = pd.DataFrame({'full_date': sorted(dates)})
    dim_date['date_key'] = dim_date['full_date'].dt.strftime('%Y%m%d').astype(int)
    dim_date['year'] = dim_date['full_date'].dt.year
    dim_date['quarter'] = dim_date['full_date'].dt.quarter
    dim_date['month'] = dim_date['full_date'].dt.month
    dim_date['month_name'] = dim_date['full_date'].dt.month_name()
    dim_date['week'] = dim_date['full_date'].dt.isocalendar().week
    dim_date['day'] = dim_date['full_date'].dt.day
    dim_date['day_name'] = dim_date['full_date'].dt.day_name()
    dim_date['is_weekend'] = dim_date['full_date'].dt.dayofweek >= 5
    
    # --- FACT FLIGHTS ---
    logger.info("Building fact_flights...")
    fact_flights = flights_df.copy()
    fact_flights['date_key'] = pd.to_datetime(fact_flights['date_str']).dt.strftime('%Y%m%d').astype(int)
    
    # Rename columns to match star schema standard (lowercase, explicit keys)
    fact_flights = fact_flights.rename(columns={
        'AIRLINE_ID': 'airline_key',
        'ORIGIN_AIRPORT_ID': 'origin_airport_key',
        'DESTINATION_AIRPORT_ID': 'dest_airport_key'
    })
    
    # Drop redundant columns
    cols_to_drop = ['YEAR', 'MONTH', 'DAY', 'DAY_OF_WEEK', 'CREATED_AT', 'date_str', 'FLIGHT_ID']
    fact_flights = fact_flights.drop(columns=[c for c in cols_to_drop if c in fact_flights.columns])
    
    # Write to Warehouse
    logger.info("Loading Data into warehouse.db...")
    if WH_DEST.exists():
        WH_DEST.unlink()
    
    with sqlite3.connect(WH_DEST) as wh_conn:
        dim_airport.to_sql('dim_airport', wh_conn, index=False)
        dim_airline.to_sql('dim_airline', wh_conn, index=False)
        dim_date.to_sql('dim_date', wh_conn, index=False)
        fact_flights.to_sql('fact_flights', wh_conn, index=False)
        
        # Add Indexes for Performance Optimization
        wh_conn.execute("CREATE INDEX idx_fact_date ON fact_flights(date_key);")
        wh_conn.execute("CREATE INDEX idx_fact_airline ON fact_flights(airline_key);")
        wh_conn.execute("CREATE INDEX idx_fact_origin ON fact_flights(origin_airport_key);")
        wh_conn.execute("CREATE INDEX idx_fact_dest ON fact_flights(dest_airport_key);")
        
    logger.info("✓ Enterprise Data Warehouse built successfully!")

if __name__ == '__main__':
    build_warehouse()
