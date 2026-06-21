# Star Schema Warehouse Design

The Enterprise Data Warehouse (`warehouse.db`) is structured using a dimensional modeling approach (Star Schema) to optimize query performance and simplify analytics.

## 1. Fact Table
### `fact_flights`
Granularity: One row per flight transaction.
- **Surrogate Keys**: `airline_key`, `origin_airport_key`, `dest_airport_key`, `date_key`
- **Measures**: `DEPARTURE_DELAY`, `ARRIVAL_DELAY`, `AIR_TIME`, `DISTANCE`, `WEATHER_DELAY`, `SECURITY_DELAY`, `AIRLINE_DELAY`, `LATE_AIRCRAFT_DELAY`
- **Degenerate Dimensions**: `FLIGHT_NUMBER`, `TAIL_NUMBER`, `CANCELLED`, `DIVERTED`

## 2. Dimension Tables
### `dim_airline`
Stores airline reference data.
- **Attributes**: `airline_key` (PK), `airline_code` (IATA), `airline_name`

### `dim_airport`
Stores geographical and naming data for network hubs.
- **Attributes**: `airport_key` (PK), `airport_code`, `airport_name`, `city`, `state`, `country`, `latitude`, `longitude`

### `dim_date`
Provides robust temporal slicing capabilities.
- **Attributes**: `date_key` (PK, YYYYMMDD), `full_date`, `year`, `quarter`, `month`, `month_name`, `week`, `day`, `day_name`, `is_weekend`

## Benefits
- **Query Performance**: Heavy use of surrogate integer keys and indices dramatically reduces JOIN overhead compared to the normalized ETL layer.
- **Geospatial Compatibility**: `dim_airport` supports direct Plotly map rendering.
- **Temporal Analysis**: `dim_date` natively supports YoY, QoQ, and MoM trend analytics without complex string parsing.
