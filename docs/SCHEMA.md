# CPUC AV Data Schema Documentation

This document describes the schema for each table in the processed dataset.

## Table of Contents

- [trips.parquet](#tripsparquet)
- [monthly_summary.parquet](#monthly_summaryparquet)
- [vmt_by_period.parquet](#vmt_by_periodparquet)
- [incidents.parquet](#incidentsparquet)
- [tract_pickups.parquet](#tract_pickupsparquet)
- [Metadata Columns](#metadata-columns)
- [Redaction Flags](#redaction-flags)

---

## trips.parquet

Trip-level data for individual AV rides.

| Field | Type | Description | Source | First Available | Known Issues |
|-------|------|-------------|--------|-----------------|--------------|
| `trip_id` | string | Unique trip identifier | Trip-level reports | Q3 2023 | Format varies by company |
| `trip_date` | datetime | Date of the trip | Trip-level reports | Q3 2023 | |
| `pickup_time` | datetime | Pickup timestamp | Trip-level reports | Q3 2023 | May be REDACTED |
| `dropoff_time` | datetime | Dropoff timestamp | Trip-level reports | Q3 2023 | May be REDACTED |
| `passenger_count` | float | Number of passengers | Trip-level reports | Q3 2023 | Often REDACTED |
| `trip_miles` | float | Distance traveled (miles) | Trip-level reports | Q3 2023 | |
| `trip_duration_minutes` | float | Trip duration in minutes | Trip-level reports | Q3 2023 | Derived from times |
| `fare_amount` | float | Fare charged (USD) | Trip-level reports | Q3 2023 | Often REDACTED |
| `pickup_tract` | string | Census tract of pickup | Trip-level reports | Q3 2023 | 11-digit FIPS code |
| `dropoff_tract` | string | Census tract of dropoff | Trip-level reports | Q3 2023 | 11-digit FIPS code |
| `vehicle_id` | string | AV vehicle identifier | Trip-level reports | Q3 2023 | May be REDACTED |

---

## monthly_summary.parquet

Month-level aggregate statistics.

| Field | Type | Description | Source | First Available | Known Issues |
|-------|------|-------------|--------|-----------------|--------------|
| `reporting_month` | datetime | First day of reporting month | Month-level reports | Q3 2023 | |
| `total_trips` | float | Total number of trips | Month-level reports | Q3 2023 | |
| `total_passengers` | float | Total passengers carried | Month-level reports | Q3 2023 | May be REDACTED |
| `total_passenger_miles` | float | Sum of passenger-miles | Month-level reports | Q3 2023 | |
| `total_vmt` | float | Total vehicle miles traveled | Month-level reports | Q3 2023 | |
| `total_vehicles` | float | Fleet size (active vehicles) | Month-level reports | Q3 2023 | Definition unclear |
| `avg_trip_length` | float | Average miles per trip | Month-level reports | Q3 2023 | |
| `avg_passengers_per_trip` | float | Average passengers per trip | Month-level reports | Q3 2023 | |

### Derived Fields (Monthly)

| Field | Type | Formula | Description |
|-------|------|---------|-------------|
| `derived_avg_passengers_per_trip` | float | total_passengers / total_trips | Computed average |
| `derived_avg_trip_length` | float | total_passenger_miles / total_trips | Computed average |
| `derived_trips_per_vehicle_per_day` | float | total_trips / (vehicles * 30) | Fleet utilization |
| `derived_trips_mom_growth` | float | % change from prior month | Month-over-month growth |
| `derived_passenger_miles_mom_growth` | float | % change from prior month | Month-over-month growth |

---

## vmt_by_period.parquet

Vehicle Miles Traveled broken out by operational period.

| Field | Type | Description | Source | First Available | Known Issues |
|-------|------|-------------|--------|-----------------|--------------|
| `reporting_period` | datetime | First day of reporting period | VMT reports | Q3 2023 | |
| `p0_vmt` | float | Period 0 VMT (with passenger) | VMT reports | Q3 2023 | See DATA_DICTIONARY |
| `p1_vmt` | float | Period 1 VMT (en route to pickup) | VMT reports | Q3 2023 | See DATA_DICTIONARY |
| `p2_vmt` | float | Period 2 VMT (repositioning) | VMT reports | Q3 2023 | See DATA_DICTIONARY |
| `p3_vmt` | float | Period 3 VMT (other) | VMT reports | Q3 2023 | See DATA_DICTIONARY |
| `total_vmt` | float | Sum of all periods | VMT reports | Q3 2023 | |
| `rider_only_vmt` | float | VMT with passengers (= P0) | VMT reports | Q3 2023 | |
| `empty_vmt` | float | VMT without passengers | VMT reports | Q3 2023 | = P1 + P2 + P3 |

### Derived Fields (VMT)

| Field | Type | Formula | Description |
|-------|------|---------|-------------|
| `derived_deadhead_pct` | float | (P1+P2+P3)/total * 100 | Percentage of empty miles |
| `derived_empty_ratio` | float | empty_vmt / rider_only_vmt | Empty to occupied ratio |

---

## incidents.parquet

Incident and complaint records.

| Field | Type | Description | Source | First Available | Known Issues |
|-------|------|-------------|--------|-----------------|--------------|
| `incident_id` | string | Unique incident identifier | Incidents reports | Q3 2023 | |
| `incident_date` | datetime | Date of incident | Incidents reports | Q3 2023 | |
| `incident_type` | string | Category of incident | Incidents reports | Q3 2023 | Taxonomy varies |
| `description` | string | Narrative description | Incidents reports | Q3 2023 | May be REDACTED |
| `location` | string | Location of incident | Incidents reports | Q3 2023 | Various formats |
| `injuries` | float | Number of injuries | Incidents reports | Q3 2023 | |
| `fatalities` | float | Number of fatalities | Incidents reports | Q3 2023 | |
| `vehicles_involved` | float | Number of vehicles | Incidents reports | Q3 2023 | |
| `was_av_at_fault` | string | AV fault determination | Incidents reports | Q3 2023 | Yes/No/Unknown |

---

## tract_pickups.parquet

Pickup and dropoff counts by census tract.

| Field | Type | Description | Source | First Available | Known Issues |
|-------|------|-------------|--------|-----------------|--------------|
| `reporting_month` | datetime | First day of month | Monthly-tract reports | Q3 2023 | |
| `census_tract` | string | 11-digit FIPS tract code | Monthly-tract reports | Q3 2023 | |
| `pickup_count` | float | Number of pickups in tract | Monthly-tract reports | Q3 2023 | May be REDACTED |
| `dropoff_count` | float | Number of dropoffs in tract | Monthly-tract reports | Q3 2023 | May be REDACTED |

---

## Metadata Columns

All tables include these metadata columns:

| Field | Type | Description |
|-------|------|-------------|
| `_source_file` | string | Original filename this row came from |
| `_company` | string | Company name (waymo, cruise, zoox, etc.) |
| `_year` | int | Reporting year |
| `_quarter` | int | Reporting quarter (1-4) |
| `_processed_at` | string | ISO timestamp of processing |

---

## Redaction Flags

For any field that may contain REDACTED values, a companion boolean column is created:

- Original field: `passenger_count`
- Redaction flag: `passenger_count_redacted`

When `passenger_count_redacted = True`:
- The `passenger_count` value will be `NaN`
- The original value was "REDACTED" or similar

This allows filtering and analysis of redaction patterns while preserving data integrity.

---

## Schema Evolution

### Q3 2023 (Initial)
- First driverless deployment reports
- All fields listed above available

### Q4 2023
- No schema changes noted
- Cruise data stops mid-quarter

### Q1 2024+
- Waymo only active reporter
- Additional detail in some VMT breakdowns

---

## Notes

1. **Data types**: Float types are used instead of int to accommodate NaN values
2. **Date handling**: All dates standardized to pandas datetime64[ns]
3. **Census tracts**: Use 11-digit FIPS codes (state + county + tract)
4. **Currency**: All monetary values in USD
5. **Distance**: All distances in miles
