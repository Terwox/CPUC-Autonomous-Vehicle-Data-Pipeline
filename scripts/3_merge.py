#!/usr/bin/env python3
"""
CPUC Autonomous Vehicle Data Merger

This script combines cleaned quarterly data files into unified tables
and computes derived metrics.

Usage:
    python scripts/merge.py [--input-dir CLEANED_DIR] [--output-dir PROCESSED_DIR]
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# Canonical schema definitions for each table type
CANONICAL_SCHEMAS = {
    "trip_level": {
        "trip_id": "str",
        "trip_date": "datetime64[ns]",
        "pickup_time": "datetime64[ns]",
        "dropoff_time": "datetime64[ns]",
        "passenger_count": "float64",
        "trip_miles": "float64",
        "trip_duration_minutes": "float64",
        "fare_amount": "float64",
        "pickup_tract": "str",
        "dropoff_tract": "str",
        "vehicle_id": "str",
    },
    "month_level": {
        "reporting_month": "datetime64[ns]",
        "total_trips": "float64",
        "total_passengers": "float64",
        "total_passenger_miles": "float64",
        "total_vmt": "float64",
        "total_vehicles": "float64",
        "avg_trip_length": "float64",
        "avg_passengers_per_trip": "float64",
    },
    "vmt": {
        "reporting_period": "datetime64[ns]",
        "p0_vmt": "float64",  # Period 0: with passenger
        "p1_vmt": "float64",  # Period 1: en route to pickup
        "p2_vmt": "float64",  # Period 2: repositioning
        "p3_vmt": "float64",  # Period 3: other (charging, maintenance)
        "total_vmt": "float64",
        "rider_only_vmt": "float64",
        "empty_vmt": "float64",
    },
    "incidents": {
        "incident_id": "str",
        "incident_date": "datetime64[ns]",
        "incident_type": "str",
        "description": "str",
        "location": "str",
        "injuries": "float64",
        "fatalities": "float64",
        "vehicles_involved": "float64",
        "was_av_at_fault": "str",
    },
    "tract_pickups": {
        "reporting_month": "datetime64[ns]",
        "census_tract": "str",
        "pickup_count": "float64",
        "dropoff_count": "float64",
    },
}


def find_cleaned_files(input_dir: Path) -> dict[str, list[Path]]:
    """
    Find all cleaned data files (parquet and CSV) organized by report type.

    Args:
        input_dir: Base directory containing cleaned subdirectories

    Returns:
        Dictionary mapping report type to list of file paths
    """
    cleaned_dir = input_dir / "cleaned"
    if not cleaned_dir.exists():
        logger.warning(f"Cleaned directory not found: {cleaned_dir}")
        return {}

    files_by_type = {}
    for subdir in cleaned_dir.iterdir():
        if subdir.is_dir():
            report_type = subdir.name
            # Find both parquet and CSV files
            data_files = list(subdir.glob("*.parquet")) + list(subdir.glob("*.csv"))
            if data_files:
                files_by_type[report_type] = data_files
                logger.info(f"Found {len(data_files)} files for {report_type}")

    return files_by_type


def align_schema(df: pd.DataFrame, canonical_columns: dict) -> pd.DataFrame:
    """
    Align DataFrame to canonical schema, adding missing columns.

    Args:
        df: DataFrame to align
        canonical_columns: Dictionary of column name to dtype

    Returns:
        Aligned DataFrame
    """
    # Add missing columns with NaN
    for col, dtype in canonical_columns.items():
        if col not in df.columns:
            df[col] = np.nan
            logger.debug(f"Added missing column: {col}")

    return df


def merge_report_type(
    files: list[Path],
    report_type: str,
    canonical_schema: dict,
) -> Optional[pd.DataFrame]:
    """
    Merge all files of a given report type into a single DataFrame.

    Args:
        files: List of data file paths (parquet or CSV)
        report_type: Type of report
        canonical_schema: Expected schema for this report type

    Returns:
        Merged DataFrame or None
    """
    if not files:
        return None

    logger.info(f"Merging {len(files)} files for report type: {report_type}")

    dfs = []
    for filepath in files:
        try:
            # Read based on file extension
            if filepath.suffix.lower() == '.parquet':
                df = pd.read_parquet(filepath)
            elif filepath.suffix.lower() == '.csv':
                df = pd.read_csv(filepath, low_memory=False)
            else:
                logger.warning(f"  Skipping unknown file type: {filepath}")
                continue
            df = align_schema(df, canonical_schema)
            dfs.append(df)
            logger.debug(f"  Loaded: {filepath.name} ({len(df)} rows)")
        except Exception as e:
            logger.error(f"  Error loading {filepath.name}: {e}")

    if not dfs:
        return None

    # Concatenate all DataFrames
    merged = pd.concat(dfs, ignore_index=True)
    logger.info(f"  Merged total: {len(merged)} rows")

    # Sort by date if available
    date_cols = [c for c in merged.columns if "date" in c.lower() or "month" in c.lower() or "period" in c.lower()]
    if date_cols:
        primary_date_col = date_cols[0]
        if pd.api.types.is_datetime64_any_dtype(merged[primary_date_col]):
            merged = merged.sort_values(primary_date_col)
            logger.info(f"  Sorted by: {primary_date_col}")

    return merged


def compute_derived_metrics_trips(df: pd.DataFrame) -> pd.DataFrame:
    """Compute derived metrics for trip-level data."""
    if df is None or df.empty:
        return df

    # Average trip length
    if "trip_miles" in df.columns and "total_trips" in df.columns:
        df["derived_avg_trip_length"] = df["trip_miles"] / df["total_trips"]

    return df


def compute_derived_metrics_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Compute derived metrics for monthly summary data."""
    if df is None or df.empty:
        return df

    # Average passengers per trip
    if "total_passengers" in df.columns and "total_trips" in df.columns:
        df["derived_avg_passengers_per_trip"] = df["total_passengers"] / df["total_trips"]

    # Average trip length
    if "total_passenger_miles" in df.columns and "total_trips" in df.columns:
        df["derived_avg_trip_length"] = df["total_passenger_miles"] / df["total_trips"]

    # Trips per vehicle per day (assuming 30 days per month)
    if "total_trips" in df.columns and "total_vehicles" in df.columns:
        df["derived_trips_per_vehicle_per_day"] = df["total_trips"] / (df["total_vehicles"] * 30)

    # Month-over-month growth rates
    if "total_trips" in df.columns:
        df["derived_trips_mom_growth"] = df.groupby("_company")["total_trips"].pct_change() * 100

    if "total_passenger_miles" in df.columns:
        df["derived_passenger_miles_mom_growth"] = df.groupby("_company")["total_passenger_miles"].pct_change() * 100

    return df


def compute_derived_metrics_vmt(df: pd.DataFrame) -> pd.DataFrame:
    """Compute derived metrics for VMT data."""
    if df is None or df.empty:
        return df

    # Calculate total VMT if not present
    vmt_cols = ["p0_vmt", "p1_vmt", "p2_vmt", "p3_vmt"]
    available_vmt_cols = [c for c in vmt_cols if c in df.columns]

    if available_vmt_cols and "total_vmt" not in df.columns:
        df["total_vmt"] = df[available_vmt_cols].sum(axis=1)

    # Deadhead percentage: (P1 + P2 + P3) / total * 100
    if "total_vmt" in df.columns:
        deadhead_cols = ["p1_vmt", "p2_vmt", "p3_vmt"]
        available_deadhead = [c for c in deadhead_cols if c in df.columns]
        if available_deadhead:
            deadhead_vmt = df[available_deadhead].sum(axis=1)
            df["derived_deadhead_pct"] = (deadhead_vmt / df["total_vmt"]) * 100

    # Rider-only VMT (P0)
    if "p0_vmt" in df.columns:
        df["rider_only_vmt"] = df["p0_vmt"]

    # Empty VMT (P1 + P2 + P3)
    if available_vmt_cols:
        empty_cols = [c for c in ["p1_vmt", "p2_vmt", "p3_vmt"] if c in df.columns]
        if empty_cols:
            df["empty_vmt"] = df[empty_cols].sum(axis=1)

    # Empty ratio: empty_vmt / rider_only_vmt
    if "empty_vmt" in df.columns and "rider_only_vmt" in df.columns:
        df["derived_empty_ratio"] = df["empty_vmt"] / df["rider_only_vmt"]

    return df


def generate_schema_documentation(
    merged_data: dict[str, pd.DataFrame],
    output_path: Path,
) -> None:
    """
    Generate schema documentation from merged data.

    Args:
        merged_data: Dictionary of report type to DataFrame
        output_path: Path to save documentation
    """
    schema_doc = {
        "generated_at": datetime.now().isoformat(),
        "tables": {},
    }

    for report_type, df in merged_data.items():
        if df is not None and not df.empty:
            columns_info = []
            for col in df.columns:
                col_info = {
                    "name": col,
                    "dtype": str(df[col].dtype),
                    "non_null_count": int(df[col].notna().sum()),
                    "null_count": int(df[col].isna().sum()),
                    "null_pct": round(df[col].isna().mean() * 100, 2),
                }

                # Check for redaction flag
                if col.endswith("_redacted"):
                    col_info["is_redaction_flag"] = True
                    col_info["redacted_count"] = int(df[col].sum())

                # Add sample values for non-sensitive columns
                if not col.startswith("_") and df[col].notna().any():
                    sample = df[col].dropna().head(3).tolist()
                    col_info["sample_values"] = [str(v)[:50] for v in sample]

                columns_info.append(col_info)

            schema_doc["tables"][report_type] = {
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": columns_info,
            }

    with open(output_path, "w") as f:
        json.dump(schema_doc, f, indent=2)
    logger.info(f"Schema documentation saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Merge cleaned CPUC data into unified tables"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(__file__).parent.parent / "processed",
        help="Directory containing cleaned parquet files (default: processed/)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "processed",
        help="Directory for merged output (default: processed/)",
    )

    args = parser.parse_args()

    # Find cleaned files by type
    files_by_type = find_cleaned_files(args.input_dir)

    if not files_by_type:
        logger.error("No cleaned files found. Run clean.py first.")
        sys.exit(1)

    # Merge each report type
    merged_data = {}

    for report_type, files in files_by_type.items():
        canonical_schema = CANONICAL_SCHEMAS.get(report_type, {})
        merged_df = merge_report_type(files, report_type, canonical_schema)

        if merged_df is not None:
            merged_data[report_type] = merged_df

    # Compute derived metrics
    if "trip_level" in merged_data:
        merged_data["trip_level"] = compute_derived_metrics_trips(merged_data["trip_level"])

    if "month_level" in merged_data:
        merged_data["month_level"] = compute_derived_metrics_monthly(merged_data["month_level"])

    if "vmt" in merged_data:
        merged_data["vmt"] = compute_derived_metrics_vmt(merged_data["vmt"])

    # Save merged tables
    args.output_dir.mkdir(parents=True, exist_ok=True)

    output_mapping = {
        "trip_level": "trips.parquet",
        "month_level": "monthly_summary.parquet",
        "vmt": "vmt_by_period.parquet",
        "incidents": "incidents.parquet",
        "tract_pickups": "tract_pickups.parquet",
    }

    for report_type, df in merged_data.items():
        if df is not None and not df.empty:
            output_filename = output_mapping.get(report_type, f"{report_type}.parquet")
            output_path = args.output_dir / output_filename
            df.to_parquet(output_path, index=False)
            logger.info(f"Saved {report_type}: {output_path} ({len(df)} rows)")

    # Generate schema documentation
    schema_path = args.output_dir / "schema_info.json"
    generate_schema_documentation(merged_data, schema_path)

    # Update metadata
    metadata_path = args.output_dir / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
    else:
        metadata = {}

    metadata["merge_info"] = {
        "merged_at": datetime.now().isoformat(),
        "tables": {
            name: {
                "rows": len(df),
                "columns": len(df.columns),
                "output_file": output_mapping.get(name, f"{name}.parquet"),
            }
            for name, df in merged_data.items()
            if df is not None
        },
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Metadata updated: {metadata_path}")

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("Merge Summary")
    logger.info("=" * 50)
    for name, df in merged_data.items():
        if df is not None:
            logger.info(f"  {name}: {len(df)} rows, {len(df.columns)} columns")


if __name__ == "__main__":
    main()
