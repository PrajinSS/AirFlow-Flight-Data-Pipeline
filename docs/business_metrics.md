# Business Intelligence Metrics Definition

This document outlines the standard enterprise KPIs computed by the Business Intelligence Engine.

## 1. Airline Reliability Score
- **Definition**: Ranks airlines based on lowest cancellation rates combined with lowest average arrival delays.
- **Formula**: `RANK() OVER (ORDER BY (cancelled/total) ASC, avg_arrival_delay ASC)`
- **Output**: `kpi_airline_reliability.csv`

## 2. Airport Efficiency Score
- **Definition**: Identifies the most efficient departure hubs.
- **Formula**: `DENSE_RANK() OVER (ORDER BY avg_departure_delay ASC)`
- **Thresholds**: Evaluated only for airports with > 50 tracked departures.
- **Output**: `kpi_airport_efficiency.csv`

## 3. Route Reliability Risk
- **Definition**: Evaluates Origin-Destination pairs to identify highest risk segments.
- **Metrics**: Flight Volume, Average Arrival Delay, Cancellation Rate.
- **Output**: `route_intelligence.csv`

## 4. Delay Severity Index
- **Definition**: Segregates raw delay minutes into distinct categories to assign risk profiles to carriers.
- **Categories**: Weather, Security, Late Aircraft, NAS (National Airspace System).
- **Output**: `kpi_delay_risk.csv`

## 5. Temporal Trends
- **Definition**: Identifies seasonal fluctuations in network capacity and disruption events.
- **Metrics**: Moving Averages, Running Totals, Monthly Aggregations.
- **Output**: `monthly_trends.csv`
