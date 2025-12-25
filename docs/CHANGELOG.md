# CPUC AV Data Changelog

This document tracks changes to the CPUC reporting data across quarters, including schema changes, corrections, and notable data events.

## Format

Each entry includes:
- **Quarter**: Reporting period
- **Changes**: Schema or format changes
- **Corrections**: Data restatements or fixes
- **Notes**: Other notable observations

---

## 2024

### Q4 2024
- **Status**: Pending
- **Expected**: February 2025

### Q3 2024
- **Status**: Available
- **Companies reporting**: Waymo
- **Changes**: None noted
- **Notes**: Continued Waymo-only reporting

### Q2 2024
- **Status**: Available
- **Companies reporting**: Waymo
- **Changes**: None noted
- **Notes**: Continued Waymo-only reporting

### Q1 2024
- **Status**: Available
- **Companies reporting**: Waymo
- **Changes**: None noted
- **Notes**: First full quarter of Waymo-only reporting

---

## 2023

### Q4 2023
- **Status**: Available
- **Companies reporting**: Waymo, Cruise (partial)
- **Changes**: None noted
- **Corrections**: None noted
- **Notes**:
  - Cruise suspended operations October 24, 2023
  - Cruise data incomplete for quarter
  - Last quarter with multiple driverless deployment reporters

### Q3 2023 (August - September)
- **Status**: Available
- **Companies reporting**: Waymo, Cruise
- **Changes**:
  - Initial driverless deployment reporting period
  - New report types introduced
- **Notes**:
  - Driverless commercial service began August 2023
  - First public robotaxi data
  - Some initial column naming inconsistencies

---

## Earlier Periods (Pilot Data)

### 2019-2023 Pilot Reports
- **Status**: Available but lower priority
- **Companies**: Waymo, Cruise, Zoox, others
- **Notes**:
  - Pilot permits had different reporting requirements
  - Smaller scale operations
  - Different schema from deployment reports

---

## Known Data Corrections

The CPUC has issued the following corrections (noted on their website):

### January 3, 2023
> "Waymo's trip-level... updated to correct an error"
- Affected files: Trip-level reports
- Nature: Specific error not detailed
- Resolution: Download latest version of files

### [Additional corrections to be documented as discovered]

---

## Schema Mapping Changes

When column mappings are updated, they should be noted here:

### Initial Mappings (v1.0)
- Created comprehensive mappings for all report types
- Handled known variations: camelCase, snake_case, spacing

### [Future updates]

---

## Data Quality Observations

### Consistent REDACTED Fields
These fields are frequently or always REDACTED:
- Fare amounts (trip-level)
- Passenger counts (trip-level)
- Specific vehicle IDs

### Temporal Gaps
Known gaps in reporting:
- Cruise: No data after October 2023
- [Others to be documented]

### Outliers Noted
Significant outliers or anomalies:
- [To be documented during validation]

---

## Update Process

When new quarterly data is released:

1. Run `scripts/download.py` to fetch new files
2. Check for new column variations
3. Update `column_mappings.json` if needed
4. Run full pipeline
5. Document changes here
6. Update validation report

---

## Contributing

If you notice undocumented changes or corrections:
1. Open a GitHub issue with details
2. Include the affected quarter and report type
3. Reference the CPUC source if applicable
