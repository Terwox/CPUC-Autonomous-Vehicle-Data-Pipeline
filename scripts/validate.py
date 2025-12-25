#!/usr/bin/env python3
"""
CPUC Autonomous Vehicle Data Validator

This script performs data quality checks on the merged CPUC data
and generates a validation report.

Usage:
    python scripts/validate.py [--input-dir PROCESSED_DIR] [--output REPORT_PATH]
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class ValidationResult:
    """Container for validation check results."""

    def __init__(self, name: str, passed: bool, message: str, details: dict = None):
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
        }


def check_temporal_continuity(df: pd.DataFrame, date_col: str, company_col: str = "_company") -> ValidationResult:
    """
    Check for missing months in time series data.

    Args:
        df: DataFrame to check
        date_col: Name of date column
        company_col: Name of company column

    Returns:
        ValidationResult
    """
    if df is None or df.empty:
        return ValidationResult(
            "temporal_continuity",
            False,
            "No data to validate",
        )

    if date_col not in df.columns:
        return ValidationResult(
            "temporal_continuity",
            False,
            f"Date column '{date_col}' not found",
        )

    missing_periods = {}
    total_gaps = 0

    for company in df[company_col].unique():
        company_df = df[df[company_col] == company].copy()

        if company_df[date_col].isna().all():
            continue

        # Convert to period and find gaps
        company_df[date_col] = pd.to_datetime(company_df[date_col])
        dates = company_df[date_col].dropna().sort_values()

        if len(dates) < 2:
            continue

        # Create expected monthly range
        date_range = pd.date_range(
            start=dates.min(),
            end=dates.max(),
            freq="MS",  # Month start
        )

        actual_months = set(dates.dt.to_period("M"))
        expected_months = set(date_range.to_period("M"))
        gaps = expected_months - actual_months

        if gaps:
            missing_periods[company] = [str(p) for p in sorted(gaps)]
            total_gaps += len(gaps)

    passed = total_gaps == 0
    message = f"Found {total_gaps} missing periods" if not passed else "No gaps in temporal coverage"

    return ValidationResult(
        "temporal_continuity",
        passed,
        message,
        {"missing_periods": missing_periods},
    )


def check_cross_table_consistency(
    monthly_df: pd.DataFrame,
    trips_df: pd.DataFrame,
    tolerance: float = 0.05,
) -> ValidationResult:
    """
    Check if monthly aggregates match trip-level sums.

    Args:
        monthly_df: Monthly summary DataFrame
        trips_df: Trip-level DataFrame
        tolerance: Allowed percentage difference

    Returns:
        ValidationResult
    """
    if monthly_df is None or monthly_df.empty or trips_df is None or trips_df.empty:
        return ValidationResult(
            "cross_table_consistency",
            True,  # Skip if data not available
            "Skipped: insufficient data for comparison",
        )

    inconsistencies = []

    # Group trips by month and company
    if "_company" in trips_df.columns and "trip_date" in trips_df.columns:
        trips_df["_month"] = pd.to_datetime(trips_df["trip_date"]).dt.to_period("M")
        trip_counts = trips_df.groupby(["_company", "_month"]).size()

        # Compare with monthly totals
        if "total_trips" in monthly_df.columns and "reporting_month" in monthly_df.columns:
            monthly_df["_month"] = pd.to_datetime(monthly_df["reporting_month"]).dt.to_period("M")

            for (company, month), trip_count in trip_counts.items():
                mask = (monthly_df["_company"] == company) & (monthly_df["_month"] == month)
                if mask.any():
                    monthly_total = monthly_df.loc[mask, "total_trips"].iloc[0]
                    if pd.notna(monthly_total):
                        diff_pct = abs(trip_count - monthly_total) / monthly_total
                        if diff_pct > tolerance:
                            inconsistencies.append({
                                "company": company,
                                "month": str(month),
                                "trip_level_count": int(trip_count),
                                "monthly_total": float(monthly_total),
                                "diff_pct": round(diff_pct * 100, 2),
                            })

    passed = len(inconsistencies) == 0
    message = (
        f"Found {len(inconsistencies)} inconsistencies"
        if not passed
        else "Trip counts match monthly totals"
    )

    return ValidationResult(
        "cross_table_consistency",
        passed,
        message,
        {"inconsistencies": inconsistencies[:10]},  # Limit to first 10
    )


def check_monotonicity(df: pd.DataFrame, cumulative_cols: list[str]) -> ValidationResult:
    """
    Check that cumulative metrics don't decrease over time.

    Args:
        df: DataFrame to check
        cumulative_cols: List of column names that should be monotonic

    Returns:
        ValidationResult
    """
    if df is None or df.empty:
        return ValidationResult(
            "monotonicity",
            True,
            "Skipped: no data to validate",
        )

    violations = []

    for col in cumulative_cols:
        if col not in df.columns:
            continue

        for company in df.get("_company", pd.Series(["all"])).unique():
            if "_company" in df.columns:
                subset = df[df["_company"] == company][col].dropna()
            else:
                subset = df[col].dropna()

            if len(subset) < 2:
                continue

            # Check for decreases
            diffs = subset.diff()
            decreases = diffs[diffs < 0]

            if len(decreases) > 0:
                violations.append({
                    "column": col,
                    "company": company,
                    "decrease_count": len(decreases),
                    "max_decrease": float(decreases.min()),
                })

    passed = len(violations) == 0
    message = (
        f"Found {len(violations)} monotonicity violations"
        if not passed
        else "All cumulative metrics are monotonic"
    )

    return ValidationResult(
        "monotonicity",
        passed,
        message,
        {"violations": violations},
    )


def check_outliers(
    df: pd.DataFrame,
    numeric_cols: list[str],
    threshold_sd: float = 3.0,
) -> ValidationResult:
    """
    Flag values more than threshold standard deviations from the mean.

    Args:
        df: DataFrame to check
        numeric_cols: List of numeric column names
        threshold_sd: Number of standard deviations for outlier threshold

    Returns:
        ValidationResult
    """
    if df is None or df.empty:
        return ValidationResult(
            "outlier_detection",
            True,
            "Skipped: no data to validate",
        )

    outliers = []

    for col in numeric_cols:
        if col not in df.columns:
            continue

        values = df[col].dropna()
        if len(values) < 3:
            continue

        mean = values.mean()
        std = values.std()

        if std == 0:
            continue

        z_scores = (values - mean) / std
        outlier_mask = abs(z_scores) > threshold_sd
        outlier_count = outlier_mask.sum()

        if outlier_count > 0:
            outliers.append({
                "column": col,
                "outlier_count": int(outlier_count),
                "outlier_pct": round(outlier_count / len(values) * 100, 2),
                "threshold_sd": threshold_sd,
                "mean": round(float(mean), 2),
                "std": round(float(std), 2),
            })

    passed = len(outliers) == 0
    message = (
        f"Found outliers in {len(outliers)} columns"
        if not passed
        else "No significant outliers detected"
    )

    return ValidationResult(
        "outlier_detection",
        passed if len(outliers) == 0 else None,  # None = warning
        message,
        {"outliers": outliers},
    )


def check_completeness(df: pd.DataFrame, table_name: str) -> ValidationResult:
    """
    Calculate completeness metrics and REDACTED percentages.

    Args:
        df: DataFrame to check
        table_name: Name of the table for reporting

    Returns:
        ValidationResult
    """
    if df is None or df.empty:
        return ValidationResult(
            f"completeness_{table_name}",
            True,
            "Skipped: no data to validate",
        )

    column_stats = []

    for col in df.columns:
        # Skip metadata columns
        if col.startswith("_"):
            continue

        total = len(df)
        null_count = df[col].isna().sum()
        null_pct = round(null_count / total * 100, 2)

        stat = {
            "column": col,
            "total_rows": total,
            "null_count": int(null_count),
            "null_pct": null_pct,
        }

        # Check for redaction flag
        redacted_col = f"{col}_redacted"
        if redacted_col in df.columns:
            redacted_count = df[redacted_col].sum()
            stat["redacted_count"] = int(redacted_count)
            stat["redacted_pct"] = round(redacted_count / total * 100, 2)

        column_stats.append(stat)

    # Overall completeness
    data_cols = [s for s in column_stats if not s["column"].endswith("_redacted")]
    avg_null_pct = np.mean([s["null_pct"] for s in data_cols]) if data_cols else 0

    passed = avg_null_pct < 50  # Arbitrary threshold
    message = f"Average null percentage: {round(avg_null_pct, 2)}%"

    return ValidationResult(
        f"completeness_{table_name}",
        passed,
        message,
        {"column_stats": column_stats, "avg_null_pct": round(avg_null_pct, 2)},
    )


def check_data_types(df: pd.DataFrame, expected_schema: dict) -> ValidationResult:
    """
    Verify data types match expected schema.

    Args:
        df: DataFrame to check
        expected_schema: Dictionary of column name to expected dtype

    Returns:
        ValidationResult
    """
    if df is None or df.empty:
        return ValidationResult(
            "data_types",
            True,
            "Skipped: no data to validate",
        )

    mismatches = []

    for col, expected_dtype in expected_schema.items():
        if col not in df.columns:
            continue

        actual_dtype = str(df[col].dtype)

        # Flexible matching
        expected_base = expected_dtype.split("[")[0]
        actual_base = actual_dtype.split("[")[0]

        if expected_base != actual_base:
            mismatches.append({
                "column": col,
                "expected": expected_dtype,
                "actual": actual_dtype,
            })

    passed = len(mismatches) == 0
    message = (
        f"Found {len(mismatches)} data type mismatches"
        if not passed
        else "All data types match expected schema"
    )

    return ValidationResult(
        "data_types",
        passed,
        message,
        {"mismatches": mismatches},
    )


def generate_validation_report(results: list[ValidationResult], output_path: Path) -> None:
    """
    Generate markdown validation report.

    Args:
        results: List of ValidationResult objects
        output_path: Path to save report
    """
    lines = [
        "# CPUC AV Data Validation Report",
        "",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Summary",
        "",
    ]

    passed = sum(1 for r in results if r.passed is True)
    failed = sum(1 for r in results if r.passed is False)
    warnings = sum(1 for r in results if r.passed is None)

    lines.extend([
        f"- **Passed**: {passed}",
        f"- **Failed**: {failed}",
        f"- **Warnings**: {warnings}",
        "",
        "## Detailed Results",
        "",
    ])

    for result in results:
        status = "✅ PASS" if result.passed is True else "❌ FAIL" if result.passed is False else "⚠️ WARNING"
        lines.extend([
            f"### {result.name}",
            "",
            f"**Status**: {status}",
            "",
            f"**Message**: {result.message}",
            "",
        ])

        if result.details:
            lines.append("**Details**:")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(result.details, indent=2, default=str)[:2000])
            lines.append("```")
            lines.append("")

    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    logger.info(f"Validation report saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Validate CPUC Autonomous Vehicle data quality"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(__file__).parent.parent / "processed",
        help="Directory containing processed parquet files (default: processed/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent / "docs" / "VALIDATION_REPORT.md",
        help="Path for validation report (default: docs/VALIDATION_REPORT.md)",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Optional path for JSON validation results",
    )

    args = parser.parse_args()

    # Load data
    data = {}
    parquet_files = {
        "trips": "trips.parquet",
        "monthly": "monthly_summary.parquet",
        "vmt": "vmt_by_period.parquet",
        "incidents": "incidents.parquet",
        "tracts": "tract_pickups.parquet",
    }

    for name, filename in parquet_files.items():
        filepath = args.input_dir / filename
        if filepath.exists():
            data[name] = pd.read_parquet(filepath)
            logger.info(f"Loaded {name}: {len(data[name])} rows")
        else:
            data[name] = None
            logger.warning(f"File not found: {filepath}")

    # Run validation checks
    results = []

    # Temporal continuity checks
    if data["monthly"] is not None:
        results.append(check_temporal_continuity(data["monthly"], "reporting_month"))

    if data["trips"] is not None:
        results.append(check_temporal_continuity(data["trips"], "trip_date"))

    # Cross-table consistency
    results.append(check_cross_table_consistency(data["monthly"], data["trips"]))

    # Monotonicity (for cumulative metrics if any)
    # Skip for now as we don't have clearly cumulative columns

    # Outlier detection
    if data["monthly"] is not None:
        numeric_cols = ["total_trips", "total_passengers", "total_passenger_miles", "total_vmt"]
        results.append(check_outliers(data["monthly"], numeric_cols))

    if data["vmt"] is not None:
        vmt_cols = ["p0_vmt", "p1_vmt", "p2_vmt", "p3_vmt", "total_vmt"]
        results.append(check_outliers(data["vmt"], vmt_cols))

    # Completeness checks
    for name, df in data.items():
        if df is not None:
            results.append(check_completeness(df, name))

    # Generate report
    generate_validation_report(results, args.output)

    # Save JSON results if requested
    if args.json_output:
        json_results = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "passed": sum(1 for r in results if r.passed is True),
                "failed": sum(1 for r in results if r.passed is False),
                "warnings": sum(1 for r in results if r.passed is None),
            },
            "results": [r.to_dict() for r in results],
        }
        with open(args.json_output, "w") as f:
            json.dump(json_results, f, indent=2, default=str)
        logger.info(f"JSON results saved to: {args.json_output}")

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("Validation Summary")
    logger.info("=" * 50)

    passed = sum(1 for r in results if r.passed is True)
    failed = sum(1 for r in results if r.passed is False)
    warnings = sum(1 for r in results if r.passed is None)

    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Warnings: {warnings}")

    # Exit with error code if any failures
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
