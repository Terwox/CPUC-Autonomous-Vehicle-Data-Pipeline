# CPUC AV Data Dictionary

This document provides detailed definitions for variables in the CPUC Autonomous Vehicle dataset, including concepts that may not be immediately obvious from field names alone.

## Table of Contents

- [VMT Periods (P0-P3)](#vmt-periods-p0-p3)
- [Passenger-Miles](#passenger-miles)
- [Incidents and Complaints](#incidents-and-complaints)
- [Derived Metrics](#derived-metrics)
- [REDACTED Values](#redacted-values)
- [Census Tracts](#census-tracts)
- [Companies](#companies)
- [Permit Types](#permit-types)

---

## VMT Periods (P0-P3)

Vehicle Miles Traveled (VMT) is broken into four periods based on the vehicle's operational state:

### P0 (Period 0) - With Passenger
- **Definition**: Miles driven with one or more passengers in the vehicle
- **Also called**: Rider VMT, Occupied VMT
- **Example**: Driving from pickup location to dropoff location

### P1 (Period 1) - En Route to Pickup
- **Definition**: Miles driven to reach a passenger who has requested a ride
- **Also called**: Dispatch VMT, Pickup VMT
- **Example**: Driving from previous dropoff to new pickup location
- **Note**: This is "empty" miles but necessary for service

### P2 (Period 2) - Repositioning
- **Definition**: Miles driven to reposition for anticipated demand
- **Also called**: Repositioning VMT, Cruising
- **Example**: Moving to a high-demand area before a request comes in
- **Note**: Strategic movement without a specific passenger assignment

### P3 (Period 3) - Other
- **Definition**: Miles driven for non-service purposes
- **Includes**:
  - Traveling to/from charging stations
  - Traveling to/from maintenance facilities
  - Testing or calibration drives
  - Other operational needs
- **Note**: Not directly related to passenger service

### Key VMT Relationships

```
Total VMT = P0 + P1 + P2 + P3

Rider VMT = P0
Empty VMT = P1 + P2 + P3
Deadhead % = (Empty VMT / Total VMT) * 100
```

---

## Passenger-Miles

### Definition
Passenger-miles represent the sum of miles traveled by all passengers. It accounts for both distance and ridership.

### Calculation
```
Passenger-Miles = Σ (trip_miles × passenger_count)
```

### Example
- Trip A: 5 miles, 2 passengers = 10 passenger-miles
- Trip B: 3 miles, 1 passenger = 3 passenger-miles
- Total: 13 passenger-miles

### Why It Matters
- Better measure of service delivery than trip count
- Accounts for shared rides
- Standard transit industry metric
- Used by Our World in Data for AV comparisons

---

## Incidents and Complaints

### Incident Types

**Collision**
- Any contact between the AV and another vehicle, object, or person
- Includes minor fender-benders and serious accidents
- Must be reported regardless of fault

**Near-Miss**
- Situation requiring emergency intervention
- AV or other party takes sudden evasive action
- No physical contact occurred

**Traffic Violation**
- AV commits a traffic violation (real or alleged)
- May be reported by third party or law enforcement

**Complaint**
- Report from passenger, other road user, or public
- May or may not involve safety issue
- Includes service quality complaints

### Severity Indicators

| Field | Description |
|-------|-------------|
| `injuries` | Number of people injured (any severity) |
| `fatalities` | Number of deaths |
| `vehicles_involved` | Total vehicles in incident |

### Fault Determination

The `was_av_at_fault` field contains:
- **Yes**: AV determined to be at fault
- **No**: AV not at fault
- **Unknown**: Fault not determined or disputed
- **Pending**: Investigation ongoing

**Note**: Fault determination may be contested or revised.

---

## Derived Metrics

These fields are computed by the pipeline, not from CPUC source data.

### derived_deadhead_pct
```
derived_deadhead_pct = ((P1 + P2 + P3) / Total_VMT) * 100
```
- **Interpretation**: Percentage of miles driven without passengers
- **Context**: Traditional taxis typically have 30-40% deadhead
- **Lower is better**: More efficient use of vehicle miles

### derived_avg_trip_length
```
derived_avg_trip_length = total_passenger_miles / total_trips
```
- **Units**: Miles per trip
- **Note**: Includes all trips, including short ones

### derived_trips_per_vehicle_per_day
```
derived_trips_per_vehicle_per_day = total_trips / (total_vehicles × 30)
```
- **Assumption**: 30 days per month
- **Interpretation**: Fleet utilization measure
- **Note**: Vehicles may not all be active every day

### derived_empty_ratio
```
derived_empty_ratio = empty_vmt / rider_only_vmt
```
- **Interpretation**: Empty miles per occupied mile
- **Context**: Ratio > 1 means more empty than occupied

### derived_*_mom_growth
- Month-over-month percentage change
- Computed separately by company
- `NaN` for first month of each company's data

---

## REDACTED Values

### What Gets REDACTED

Companies can claim confidentiality for certain data elements. Commonly REDACTED:

| Field | Typical Reason |
|-------|---------------|
| Fare amounts | Competitive pricing information |
| Passenger counts | Demand patterns |
| Vehicle IDs | Fleet composition |
| Specific times | Service patterns |

### How We Handle It

1. Original REDACTED text replaced with `NaN`
2. Companion `{field}_redacted` column set to `True`
3. No imputation or estimation performed

### Analyzing Redaction

```python
# Find redaction rates by field
redacted_cols = [c for c in df.columns if c.endswith('_redacted')]
for col in redacted_cols:
    rate = df[col].mean() * 100
    print(f"{col}: {rate:.1f}% redacted")
```

---

## Census Tracts

### Format
Census tracts are identified by 11-digit FIPS codes:
```
SSCCCTTTTTT
│ │   │
│ │   └── 6-digit tract number
│ └────── 3-digit county code
└──────── 2-digit state code (06 = California)
```

### Example
`06075010100` = California (06), San Francisco County (075), Tract 0101.00

### Uses
- Geographic analysis of service patterns
- Equity analysis (join with demographic data)
- Comparison with transit coverage

### Data Source
Census tracts from 2020 Census geography.

---

## Companies

### Currently Active

**Waymo**
- Subsidiary of Alphabet (Google)
- Active driverless deployment since August 2023
- Operating in San Francisco, Los Angeles, Phoenix
- Only active reporter as of late 2024

### Previously Active

**Cruise**
- Subsidiary of General Motors
- Driverless deployment suspended October 24, 2023
- Following incident involving a pedestrian
- CPUC permit revoked/suspended

**Zoox**
- Subsidiary of Amazon
- Currently in pilot phase (drivered operations)
- Not yet reporting driverless deployment data

### Others
Various companies hold pilot permits but are not in driverless deployment.

---

## Permit Types

### Driverless Deployment
- Commercial passenger service
- No safety driver in vehicle
- Can charge fares
- Subject to quarterly reporting
- **This is the main dataset focus**

### Drivered Deployment
- Commercial passenger service
- Safety driver present
- Can charge fares
- Different reporting requirements

### Driverless Pilot
- Testing without safety driver
- Cannot charge fares
- Cannot carry passengers (generally)

### Drivered Pilot
- Testing with safety driver present
- Cannot charge fares
- May carry passengers for testing

---

## Additional Resources

- [CPUC Autonomous Vehicle Programs](https://www.cpuc.ca.gov/regulatory-services/licensing/transportation-licensing-and-analysis-branch/autonomous-vehicle-programs/)
- [CPUC Decision 20-11-046](https://docs.cpuc.ca.gov/PublishedDocs/Published/G000/M351/K470/351470674.PDF) - Original reporting requirements
- [Census Bureau TIGER/Line Shapefiles](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) - For tract geometries
