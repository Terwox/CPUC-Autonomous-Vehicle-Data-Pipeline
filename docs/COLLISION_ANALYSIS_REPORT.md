# CPUC Autonomous Vehicle Collision Analysis Report

**Analysis Date:** December 26, 2025
**Data Period:** 2022-2023
**Geographic Focus:** San Francisco, California

## Executive Summary

This report analyzes collision rates for commercial autonomous vehicle (robotaxi) operations in San Francisco compared to human drivers, using data from the California Public Utilities Commission (CPUC) quarterly reports.

### Key Findings

- **Cruise**: 10.1 collisions per million miles (1.98M miles driven, 20 collisions)
- **Waymo**: 59.5 collisions per million miles (34K miles driven, 2 collisions)
- **Human Drivers (SF)**: 5.55 injury-causing collisions per million miles

**Important Note**: Direct comparison is challenging due to different reporting standards. Robotaxi data includes ALL collisions (including minor incidents), while human driver benchmarks typically measure only injury-causing crashes.

---

## Data Sources

### CPUC Deployment Program Data (2022-2023)

Only two companies reported complete deployment program data with VMT (vehicle miles traveled):

| Company | TCPID | Total Miles | Total Trips | Total Collisions |
|---------|-------|-------------|-------------|------------------|
| Cruise | PSG0038152 | 1,982,132 | 26,207 | 20 |
| Waymo | PSG0039080 | 33,587 | 3,507 | 2 |

### Human Driver Benchmark

According to Waymo's December 2023 study (published in collaboration with NHTSA data):
- **San Francisco injury-causing crash rate**: 5.55 per million miles
- This rate is approximately 3x higher than the national average
- Data source: NHTSA Standing General Order (SGO) reports

---

## Collision Rate Analysis

### Collisions Per Million Miles

| Driver Type | Rate | Period | Notes |
|-------------|------|--------|-------|
| **Human Drivers (SF)** | 5.55 | 2022-2023 | Injury-causing crashes only |
| **Cruise (Robotaxi)** | 10.1 | 2022-2023 | ALL collisions reported to CPUC |
| **Waymo (CPUC data)** | 59.5 | 2022-2023 | ALL collisions, limited sample (34K miles) |
| **Waymo (self-reported)** | 0.41 | 2023 | Injury-causing only, multi-city combined |

### Statistical Considerations

1. **Reporting Methodology Differences**
   - CPUC requires reporting of ALL collisions, including minor incidents
   - Human driver benchmarks typically track only injury-causing or police-reported crashes
   - This creates an upward bias in robotaxi collision counts

2. **Sample Size Issues**
   - Waymo's CPUC data (34K miles) is too limited for robust statistical conclusions
   - Cruise's data (1.98M miles) provides more reliable estimates
   - Human driver baseline is based on much larger population samples

3. **Geographic and Temporal Context**
   - All robotaxi operations occurred in San Francisco
   - Data covers 2022-2023 period
   - Human benchmark is contemporaneous (same time period)

---

## Detailed Findings

### Cruise Performance

**Overall Rate**: 10.1 collisions per million miles

- Driven nearly 2 million miles in commercial deployment
- Recorded 20 total collisions
- Rate is approximately **1.8x higher** than human injury-causing crash rate
- However, this includes ALL collisions (minor and major), while human rate includes only injury-causing

**Interpretation**: Cruise appears to have a slightly higher collision rate than human drivers in San Francisco, though the comparison is complicated by different reporting standards. If minor, non-injury collisions were excluded, Cruise's rate would likely be closer to or below the human baseline.

### Waymo Performance

**CPUC Data Rate**: 59.5 collisions per million miles (limited data)
**Self-Reported Study Rate**: 0.41 injury-causing collisions per million miles

- Only 34K miles reported to CPUC (insufficient for reliable estimates)
- 2 collisions recorded
- Self-reported multi-city study shows much better performance
- Large discrepancy suggests reporting methodology differences

**Interpretation**: CPUC data is too limited to draw conclusions. Waymo's self-reported study (0.41 per million miles for injury-causing crashes) suggests significantly better performance than human drivers, but this comes from Waymo's own analysis and covers multiple cities.

---

## Data Quality & Limitations

### CPUC Data Limitations

1. **Redacted VMT Values**
   - 2024-2025 data has 565K trips from Cruise with redacted VMT
   - Analysis limited to 2022-2023 period with non-redacted data
   - Cannot assess most recent performance

2. **Limited Company Coverage**
   - Only Cruise and Waymo reported deployment program VMT data
   - Other companies (Zoox, Argo AI, etc.) only have pilot program data
   - Pilot programs excluded from this analysis

3. **Inconsistent Reporting**
   - Some Excel files contained only data dictionary templates
   - VMT columns were initially mis-parsed as datetime values (fixed in analysis)
   - Missing TCPID values in some records

### Comparison Challenges

1. **Definitional Differences**
   - "Collision" definition varies between CPUC reports and traffic safety studies
   - Severity thresholds differ (all vs. injury-causing vs. police-reported)
   - Makes direct comparison problematic

2. **Operating Context**
   - Robotaxis operate 24/7 in all weather conditions
   - Human driver baseline includes mix of experience levels and conditions
   - San Francisco has unique traffic patterns (hills, fog, dense urban environment)

3. **Reporting Bias**
   - Robotaxis may be more likely to report minor incidents
   - Human drivers may not report minor collisions to authorities
   - Self-reporting by AV companies creates potential conflicts of interest

---

## Conclusions

### Primary Findings

1. **Cruise vs. Human Drivers**: Cruise's collision rate of 10.1 per million miles is approximately 1.8x the human injury-causing crash rate of 5.55. However, this comparison is confounded by:
   - Cruise data includes ALL collisions (minor + major)
   - Human baseline includes only injury-causing crashes
   - Adjusted for severity, rates are likely comparable

2. **Limited Waymo Data**: Waymo's CPUC deployment data (34K miles) is insufficient for reliable rate estimation. Their self-reported study suggests superior performance to humans, but requires independent verification.

3. **Data Availability**: Analysis is constrained by:
   - Only 2 companies with deployment VMT data
   - Redacted recent data (2024-2025)
   - Inconsistent reporting standards

### Recommendations

1. **Standardize Reporting**: CPUC should mandate consistent collision severity classifications to enable apples-to-apples comparisons with human driver benchmarks.

2. **Require VMT Disclosure**: Companies should not be allowed to redact VMT data, as it prevents public safety analysis.

3. **Independent Verification**: Self-reported safety studies should be independently verified using CPUC data.

4. **Expand Coverage**: More companies should report deployment program data to increase sample size and competitive benchmarking.

---

## Methodology

### Data Processing Pipeline

1. **Download**: Raw CPUC quarterly reports downloaded from official CPUC website (ZIP archives containing Excel/CSV files)

2. **Clean**:
   - Filtered out template/reference files
   - Standardized column names and data types
   - Fixed VMT columns (prevented incorrect datetime conversion)
   - Handled REDACTED values
   - Mapped TCPIDs to company names

3. **Merge**: Combined quarterly reports by type (trips, VMT, incidents)

4. **Analyze**:
   - Calculated total VMT and collisions by company
   - Computed collision rates per million miles
   - Compared to human driver benchmarks from published studies

### Company Identification

TCPID to company mapping:
- `PSG0038152` = Cruise
- `PSG0039080` = Waymo

### Files Generated

Analysis outputs saved in `processed/` directory:
- `FINAL_collisions_by_company_deployment.csv` - Robotaxi collision rates
- `FINAL_robotaxi_vs_human_comparison.csv` - Comparison with human drivers
- `incidents_combined.csv` - All incident records
- `vmt_combined.csv` - All VMT records

---

## References

### Data Sources

- California Public Utilities Commission (CPUC) Quarterly Reporting: https://www.cpuc.ca.gov/regulatory-services/licensing/transportation-licensing-and-analysis-branch/autonomous-vehicle-programs/quarterly-reporting
- CPUC Decision 20-11-046 (defines reporting requirements)
- CPUC Decision 24-11-002 (recent updates to requirements)

### Human Driver Benchmarks

- Waymo. (2023, December). "Waymo significantly outperforms comparable human benchmarks over 7+ million miles of rider-only driving." https://waymo.com/blog/2023/12/waymo-significantly-outperforms-comparable-human-benchmarks-over-7-million
- Full peer-reviewed study: https://www.tandfonline.com/doi/full/10.1080/15389588.2024.2380786

### Additional Context

- San Francisco Vision Zero Traffic Fatalities Report (2023)
- SFMTA Traffic Crashes Report (2017-2022)

---

## Appendix: Technical Notes

### Data Quality Issues Resolved

1. **VMT DateTime Conversion Bug**: Initial data cleaning incorrectly converted VMT columns (e.g., `total_vmtperiod1`) to datetime because they contained the word "period". Fixed by excluding numeric columns from date parsing.

2. **Template File Contamination**: Excel files containing data dictionaries were initially processed as data. Fixed by filtering filenames and sheet names for "template", "reference", "narrative" patterns.

3. **Missing Company Names**: Many records lacked explicit company identifiers. Resolved by mapping TCPIDs and extracting company names from source filenames.

### Pipeline Tools

- Python 3.12
- pandas 2.3.3
- pyarrow 22.0.0
- Data stored in Parquet format for efficiency

### Reproducibility

All analysis code is available in the repository:
- `scripts/1_download.py` - Fetch raw CPUC data
- `scripts/2_clean.py` - Standardize and clean
- `scripts/3_merge.py` - Combine quarters
- `scripts/4_validate.py` - Data quality checks
- `run_pipeline.py` - Execute full pipeline

Run `python run_pipeline.py` to reproduce the analysis.

---

**Report Generated by**: CPUC AV Data Pipeline
**Last Updated**: December 26, 2025
