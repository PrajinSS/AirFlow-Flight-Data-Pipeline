# Advanced SQL Analytics

The BI Layer heavily relies on advanced SQL capabilities built into the engine to execute complex, multi-dimensional queries directly inside SQLite.

## 1. Common Table Expressions (CTEs)
CTEs are used to modularize complex subqueries before applying ranking functions.
```sql
WITH AirlineStats AS (
    SELECT airline_name, COUNT(*) as total, AVG(ARRIVAL_DELAY) as delay
    FROM fact_flights f
    JOIN dim_airline a ON f.airline_key = a.airline_key
    GROUP BY airline_name
)
SELECT * FROM AirlineStats;
```

## 2. Window Functions
Window functions are employed to calculate rankings and running totals without collapsing the dataset granularity.

**Ranking Example:**
```sql
DENSE_RANK() OVER (ORDER BY AVG(DEPARTURE_DELAY) ASC) as efficiency_rank
```

**Running Total Example:**
```sql
SUM(COUNT(*)) OVER (ORDER BY d.month) as running_total_flights
```

## 3. Advanced Aggregations
Conditional aggregations using `CASE WHEN` allow pivoting metrics within a single query pass.
```sql
SUM(CASE WHEN CANCELLED = 1 THEN 1 ELSE 0 END) as cancelled_flights
```

## 4. Cross-Dimensional Joins
Route intelligence is gathered by joining the `dim_airport` dimension table twice to resolve Origin and Destination codes simultaneously.
```sql
JOIN dim_airport orig ON f.origin_airport_key = orig.airport_key
JOIN dim_airport dest ON f.dest_airport_key = dest.airport_key
```
