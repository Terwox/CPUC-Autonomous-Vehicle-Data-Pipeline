#!/usr/bin/env python3
"""
CPUC Autonomous Vehicle Data Cleaner

This script standardizes schemas across different quarters of CPUC data,
handles REDACTED cells, and prepares data for merging.

Usage:
    python scripts/clean.py [--input-dir RAW_DIR] [--output-dir PROCESSED_DIR]
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_column_mappings(mappings_path: Path) -> dict:
    """Load column name mappings from JSON file."""
    if not mappings_path.exists():
        logger.warning(f"Column mappings file not found: {mappings_path}")
        return {"trip_level": {}, "month_level": {}, "vmt": {}, "incidents": {}}

    with open(mappings_path, "r") as f:
        return json.load(f)


def detect_report_type(df: pd.DataFrame, filename: str) -> Optional[str]:
    """
    Detect the report type based on column names and filename.

    Args:
        df: DataFrame loaded from Excel
        filename: Original filename

    Returns:
        Report type string or None
    """
    columns_lower = [str(c).lower() for c in df.columns]
    filename_lower = filename.lower()

    # Check filename first
    if "trip" in filename_lower and "level" in filename_lower:
        return "trip_level"
    if "month" in filename_lower and "level" in filename_lower:
        return "month_level"
    if "tract" in filename_lower:
        return "tract_pickups"
    if "incident" in filename_lower and "location" in filename_lower:
        return "incidents_location"
    if "incident" in filename_lower or "complaint" in filename_lower:
        return "incidents"
    if "vmt" in filename_lower:
        return "vmt"

    # Check columns
    trip_indicators = ["trip", "passenger", "pickup", "dropoff", "fare"]
    month_indicators = ["month", "total_trips", "total_passengers"]
    vmt_indicators = ["vmt", "p0", "p1", "p2", "p3", "vehicle_miles"]
    incident_indicators = ["incident", "complaint", "collision", "contact"]

    trip_score = sum(1 for col in columns_lower if any(ind in col for ind in trip_indicators))
    month_score = sum(1 for col in columns_lower if any(ind in col for ind in month_indicators))
    vmt_score = sum(1 for col in columns_lower if any(ind in col for ind in vmt_indicators))
    incident_score = sum(1 for col in columns_lower if any(ind in col for ind in incident_indicators))

    scores = {
        "trip_level": trip_score,
        "month_level": month_score,
        "vmt": vmt_score,
        "incidents": incident_score,
    }

    max_score = max(scores.values())
    if max_score > 0:
        return max(scores, key=scores.get)

    return None


def normalize_column_name(name: str) -> str:
    """
    Normalize a column name to snake_case.

    Args:
        name: Original column name

    Returns:
        Normalized column name
    """
    # Convert to string and strip whitespace
    name = str(name).strip()

    # Replace common separators with underscores
    name = re.sub(r"[\s\-\.]+", "_", name)

    # Remove parentheses and their contents (units, etc.)
    name = re.sub(r"\([^)]*\)", "", name)

    # Convert camelCase to snake_case
    name = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)

    # Lowercase
    name = name.lower()

    # Remove special characters
    name = re.sub(r"[^a-z0-9_]", "", name)

    # Remove duplicate underscores
    name = re.sub(r"_+", "_", name)

    # Strip leading/trailing underscores
    name = name.strip("_")

    return name


def apply_column_mappings(df: pd.DataFrame, mappings: dict, report_type: str) -> pd.DataFrame:
    """
    Apply column name mappings to standardize schema.

    Args:
        df: DataFrame to process
        mappings: Column mappings dictionary
        report_type: Type of report for lookup

    Returns:
        DataFrame with standardized column names
    """
    if report_type not in mappings:
        logger.warning(f"No mappings found for report type: {report_type}")
        return df

    type_mappings = mappings[report_type]

    # First normalize all column names
    df.columns = [normalize_column_name(c) for c in df.columns]

    # Then apply specific mappings
    rename_map = {}
    for col in df.columns:
        if col in type_mappings:
            rename_map[col] = type_mappings[col]

    if rename_map:
        logger.info(f"Applying column renames: {rename_map}")
        df = df.rename(columns=rename_map)

    return df


def handle_redacted_values(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Handle REDACTED cells by replacing with NaN and creating flag columns.

    Args:
        df: DataFrame to process

    Returns:
        Tuple of (processed DataFrame, redaction statistics)
    """
    redaction_stats = {}

    for col in df.columns:
        if df[col].dtype == object:
            # Check for REDACTED values (case-insensitive)
            redacted_mask = df[col].astype(str).str.upper().str.contains(
                r"^REDACTED$|^\[REDACTED\]$|^N/A$|^CONFIDENTIAL$",
                regex=True,
                na=False,
            )

            redacted_count = redacted_mask.sum()
            if redacted_count > 0:
                # Create redaction flag column
                flag_col = f"{col}_redacted"
                df[flag_col] = redacted_mask

                # Replace REDACTED values with NaN
                df.loc[redacted_mask, col] = np.nan

                redaction_stats[col] = {
                    "redacted_count": int(redacted_count),
                    "total_count": len(df),
                    "redacted_pct": round(redacted_count / len(df) * 100, 2),
                }

                logger.info(
                    f"Column '{col}': {redacted_count} REDACTED values "
                    f"({redaction_stats[col]['redacted_pct']}%)"
                )

    return df, redaction_stats


def standardize_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize date columns to datetime format.

    Args:
        df: DataFrame to process

    Returns:
        DataFrame with standardized dates
    """
    date_patterns = ["date", "time", "day", "month", "year", "period"]

    for col in df.columns:
        col_lower = col.lower()

        # Skip flag columns
        if col.endswith("_redacted"):
            continue

        if any(pattern in col_lower for pattern in date_patterns):
            try:
                # Try to convert to datetime
                df[col] = pd.to_datetime(df[col], errors="coerce")
                logger.info(f"Converted column '{col}' to datetime")
            except Exception as e:
                logger.debug(f"Could not convert '{col}' to datetime: {e}")

    return df


def standardize_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize numeric columns (handle commas, currency symbols, etc.).

    Args:
        df: DataFrame to process

    Returns:
        DataFrame with standardized numeric values
    """
    numeric_patterns = [
        "count", "total", "sum", "amount", "miles", "vmt", "trips",
        "passengers", "fare", "rate", "pct", "percent", "avg", "mean",
        "p0", "p1", "p2", "p3",
    ]

    for col in df.columns:
        col_lower = col.lower()

        # Skip flag columns
        if col.endswith("_redacted"):
            continue

        if any(pattern in col_lower for pattern in numeric_patterns):
            if df[col].dtype == object:
                try:
                    # Remove currency symbols and commas
                    cleaned = df[col].astype(str).str.replace(r"[\$,]", "", regex=True)
                    cleaned = cleaned.str.strip()

                    # Convert to numeric
                    df[col] = pd.to_numeric(cleaned, errors="coerce")
                    logger.info(f"Converted column '{col}' to numeric")
                except Exception as e:
                    logger.debug(f"Could not convert '{col}' to numeric: {e}")

    return df


def add_source_metadata(
    df: pd.DataFrame,
    filename: str,
    company: str,
    year: int,
    quarter: int,
) -> pd.DataFrame:
    """
    Add source metadata columns to DataFrame.

    Args:
        df: DataFrame to process
        filename: Source filename
        company: Company name
        year: Reporting year
        quarter: Reporting quarter

    Returns:
        DataFrame with metadata columns
    """
    df["_source_file"] = filename
    df["_company"] = company
    df["_year"] = year
    df["_quarter"] = quarter
    df["_processed_at"] = datetime.now().isoformat()

    return df


def parse_metadata_from_filename(filename: str) -> dict:
    """
    Extract metadata from standardized filename.

    Args:
        filename: Filename in format {company}_{year}q{quarter}_{report_type}.xlsx

    Returns:
        Dictionary with extracted metadata
    """
    metadata = {
        "company": None,
        "year": None,
        "quarter": None,
        "report_type": None,
    }

    # Remove extension
    name = Path(filename).stem

    # Parse parts
    parts = name.split("_")

    if len(parts) >= 1:
        metadata["company"] = parts[0]

    if len(parts) >= 2:
        # Parse year and quarter from pattern like "2024q1"
        match = re.match(r"(\d{4})q(\d)", parts[1])
        if match:
            metadata["year"] = int(match.group(1))
            metadata["quarter"] = int(match.group(2))

    if len(parts) >= 3:
        # Join remaining parts for report type
        metadata["report_type"] = "_".join(parts[2:])

    return metadata


def inspect_excel_file(filepath: Path) -> dict:
    """
    Inspect an Excel file to understand its structure.

    Args:
        filepath: Path to Excel file

    Returns:
        Dictionary with file structure info
    """
    info = {
        "filepath": str(filepath),
        "sheets": [],
    }

    try:
        xl = pd.ExcelFile(filepath)
        for sheet_name in xl.sheet_names:
            df = xl.parse(sheet_name, nrows=5)
            info["sheets"].append({
                "name": sheet_name,
                "columns": list(df.columns),
                "row_count": len(xl.parse(sheet_name)),
            })
    except Exception as e:
        info["error"] = str(e)

    return info


def clean_excel_file(
    filepath: Path,
    mappings: dict,
    output_dir: Path,
) -> Optional[dict]:
    """
    Clean a single Excel file and return processing info.

    Args:
        filepath: Path to Excel file
        mappings: Column mappings dictionary
        output_dir: Directory for cleaned output

    Returns:
        Processing info dictionary or None if failed
    """
    filename = filepath.name
    logger.info(f"Processing: {filename}")

    # Parse metadata from filename
    metadata = parse_metadata_from_filename(filename)
    logger.info(f"  Metadata: {metadata}")

    processing_info = {
        "source_file": filename,
        "metadata": metadata,
        "sheets_processed": [],
        "errors": [],
    }

    try:
        xl = pd.ExcelFile(filepath)

        for sheet_name in xl.sheet_names:
            logger.info(f"  Processing sheet: {sheet_name}")

            try:
                # Read the sheet
                df = xl.parse(sheet_name)

                if df.empty:
                    logger.warning(f"    Sheet '{sheet_name}' is empty, skipping")
                    continue

                # Detect report type
                report_type = detect_report_type(df, filename)
                if report_type is None:
                    report_type = "unknown"
                logger.info(f"    Detected report type: {report_type}")

                # Apply column mappings
                df = apply_column_mappings(df, mappings, report_type)

                # Handle REDACTED values
                df, redaction_stats = handle_redacted_values(df)

                # Standardize dates
                df = standardize_dates(df)

                # Standardize numeric values
                df = standardize_numeric(df)

                # Add source metadata
                df = add_source_metadata(
                    df,
                    filename,
                    metadata["company"],
                    metadata["year"],
                    metadata["quarter"],
                )

                # Save cleaned data
                output_subdir = output_dir / "cleaned" / report_type
                output_subdir.mkdir(parents=True, exist_ok=True)

                # Create output filename
                sheet_suffix = f"_{sheet_name}" if len(xl.sheet_names) > 1 else ""
                output_filename = f"{Path(filename).stem}{sheet_suffix}.parquet"
                output_path = output_subdir / output_filename

                df.to_parquet(output_path, index=False)
                logger.info(f"    Saved to: {output_path}")

                processing_info["sheets_processed"].append({
                    "sheet_name": sheet_name,
                    "report_type": report_type,
                    "rows": len(df),
                    "columns": list(df.columns),
                    "redaction_stats": redaction_stats,
                    "output_path": str(output_path),
                })

            except Exception as e:
                error_msg = f"Error processing sheet '{sheet_name}': {e}"
                logger.error(f"    {error_msg}")
                processing_info["errors"].append(error_msg)

    except Exception as e:
        error_msg = f"Error reading file: {e}"
        logger.error(f"  {error_msg}")
        processing_info["errors"].append(error_msg)
        return processing_info

    return processing_info


def main():
    parser = argparse.ArgumentParser(
        description="Clean and standardize CPUC Autonomous Vehicle data"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(__file__).parent.parent / "raw",
        help="Directory containing raw Excel files (default: raw/)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "processed",
        help="Directory for cleaned output (default: processed/)",
    )
    parser.add_argument(
        "--mappings-file",
        type=Path,
        default=Path(__file__).parent.parent / "scripts" / "column_mappings.json",
        help="Path to column mappings JSON file",
    )
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Only inspect files without cleaning",
    )

    args = parser.parse_args()

    # Verify input directory exists
    if not args.input_dir.exists():
        logger.error(f"Input directory does not exist: {args.input_dir}")
        sys.exit(1)

    # Load column mappings
    mappings = load_column_mappings(args.mappings_file)

    # Find all Excel files
    excel_files = list(args.input_dir.glob("*.xlsx")) + list(args.input_dir.glob("*.xls"))
    logger.info(f"Found {len(excel_files)} Excel files")

    if not excel_files:
        logger.warning("No Excel files found in input directory")
        return

    if args.inspect_only:
        # Just inspect files
        inspection_results = []
        for filepath in excel_files:
            info = inspect_excel_file(filepath)
            inspection_results.append(info)
            print(json.dumps(info, indent=2))
        return

    # Process all files
    args.output_dir.mkdir(parents=True, exist_ok=True)

    processing_results = []
    success_count = 0
    error_count = 0

    for filepath in excel_files:
        result = clean_excel_file(filepath, mappings, args.output_dir)
        if result:
            processing_results.append(result)
            if result["errors"]:
                error_count += 1
            else:
                success_count += 1

    # Save processing report
    report = {
        "processed_at": datetime.now().isoformat(),
        "total_files": len(excel_files),
        "successful": success_count,
        "with_errors": error_count,
        "results": processing_results,
    }

    report_path = args.output_dir / "cleaning_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Cleaning report saved to: {report_path}")

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("Cleaning Summary")
    logger.info("=" * 50)
    logger.info(f"Total files processed: {len(excel_files)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"With errors: {error_count}")


if __name__ == "__main__":
    main()
