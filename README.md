# CPUC Autonomous Vehicle Data Pipeline

A reproducible data pipeline that downloads, cleans, and unifies California Public Utilities Commission (CPUC) quarterly autonomous vehicle reports into a single, well-documented dataset suitable for research use.

## Overview

The CPUC requires AV passenger service operators (currently Waymo, formerly Cruise) to submit quarterly reports containing trip-level data, VMT, incidents, and operational metrics. These reports are public but exist as separate Excel files with no official schema documentation, occasional column name changes across quarters, and REDACTED cells where companies claimed confidentiality.

This pipeline creates the first public, reproducible version of this dataset.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/cpuc-av-data.git
cd cpuc-av-data

# Install dependencies
pip install -r requirements.txt

# Run the pipeline
python scripts/download.py    # Fetch raw files from CPUC
python scripts/clean.py       # Standardize schemas, handle REDACTED
python scripts/merge.py       # Combine quarters into unified tables
python scripts/validate.py    # Run data quality checks
```

## Output Files

After running the pipeline, you'll find these files in `processed/`:

| File | Description |
|------|-------------|
| `trips.parquet` | All trip-level data with unified schema |
| `monthly_summary.parquet` | Month-level aggregates |
| `vmt_by_period.parquet` | VMT broken out by P0/P1/P2/P3 periods |
| `incidents.parquet` | Incidents and complaints |
| `tract_pickups.parquet` | Census tract pickup locations |
| `metadata.json` | Schema docs, source URLs, processing notes |

## Data Source

**URL**: https://www.cpuc.ca.gov/regulatory-services/licensing/transportation-licensing-and-analysis-branch/autonomous-vehicle-programs/quarterly-reporting

The page contains links to quarterly Excel files organized by:
- Reporting period (quarters from 2019 to present)
- Company (Waymo, Cruise, Zoox, others)
- Permit type (Drivered Pilot, Driverless Pilot, Drivered Deployment, Driverless Deployment)
- Report type (trip-level, month-level, monthly-tract, incidents-complaints, incidents-location, VMT)

**Priority focus**: Driverless Deployment reports from August 2023 onward (when commercial robotaxi service began).

## Project Structure

```
cpuc-av-data/
├── raw/                          # Original downloaded files, untouched
├── processed/                    # Cleaned, standardized data
├── docs/
│   ├── SCHEMA.md                 # Field definitions, known issues
│   ├── CHANGELOG.md              # What changed between quarters
│   ├── DATA_DICTIONARY.md        # Variable descriptions
│   └── VALIDATION_REPORT.md      # Data quality check results
├── scripts/
│   ├── download.py               # Fetch raw files from CPUC
│   ├── clean.py                  # Standardize schemas, handle REDACTED
│   ├── merge.py                  # Combine quarters into unified tables
│   ├── validate.py               # Data quality checks
│   └── column_mappings.json      # Schema reconciliation mappings
├── notebooks/
│   └── exploratory.ipynb         # Basic EDA, sanity checks
├── requirements.txt
└── README.md
```

## Handling REDACTED Values

When companies claim confidentiality for certain fields, the CPUC reports show "REDACTED". This pipeline:

1. Preserves REDACTED as `NaN` in the data
2. Creates a companion `{field}_redacted` boolean column
3. Documents redaction rates in the validation report

This allows researchers to:
- See which data is available vs. withheld
- Filter or analyze redaction patterns
- Maintain data integrity without imputation

## Derived Metrics

The pipeline computes these additional metrics (prefixed with `derived_`):

| Metric | Formula | Description |
|--------|---------|-------------|
| `derived_deadhead_pct` | (P1+P2+P3)/total_vmt * 100 | Percentage of VMT without passengers |
| `derived_avg_trip_length` | passenger_miles / trips | Average miles per trip |
| `derived_trips_per_vehicle_per_day` | trips / (vehicles * days) | Fleet utilization |
| `derived_empty_ratio` | empty_vmt / rider_vmt | Empty to occupied ratio |
| `derived_*_mom_growth` | month-over-month % change | Growth rates |

## Requirements

- Python 3.10+
- See `requirements.txt` for full dependencies

Core libraries:
- pandas (data manipulation)
- openpyxl (Excel reading)
- requests + BeautifulSoup (web scraping)
- pyarrow (parquet output)

## Known Limitations

1. **REDACTED data**: Some fields are consistently withheld by operators
2. **Schema changes**: Column names vary across quarters (handled by mappings)
3. **Cruise data gap**: Cruise stopped reporting after late 2023
4. **No imputation**: Missing values are preserved as-is
5. **Quarterly lag**: New data appears ~1-2 months after quarter end

## Citation

If you use this dataset in research, please cite:

```bibtex
@misc{cpuc_av_data,
  title = {CPUC Autonomous Vehicle Data Pipeline},
  author = {Your Name},
  year = {2024},
  url = {https://github.com/yourusername/cpuc-av-data},
  note = {Data sourced from California Public Utilities Commission}
}
```

## License

This project is licensed under CC-BY-4.0. The underlying data is public government data from the California Public Utilities Commission.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Run the validation checks
4. Submit a pull request

## References

- [CPUC Quarterly Reporting Page](https://www.cpuc.ca.gov/regulatory-services/licensing/transportation-licensing-and-analysis-branch/autonomous-vehicle-programs/quarterly-reporting)
- CPUC Decision 20-11-046 (defines reporting requirements)
- CPUC Decision 24-11-002 (recent updates to requirements)
- [Our World in Data - Self-Driving Taxis](https://ourworldindata.org/grapher/passenger-miles-traveled-self-driving-taxis)

## Contact

For questions or issues, please open a GitHub issue or contact [your email].
