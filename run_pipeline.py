#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPUC AV Data Pipeline Runner

Executes the full ETL pipeline in order:
1. Download - Fetch raw files from CPUC
2. Clean - Standardize schemas, handle REDACTED
3. Merge - Combine quarters into unified tables
4. Validate - Run data quality checks
"""

import subprocess
import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

# Define the scripts to run in order
SCRIPTS = [
    ("scripts/1_download.py", "Fetching raw files from CPUC"),
    ("scripts/2_clean.py", "Standardizing schemas and handling REDACTED values"),
    ("scripts/3_merge.py", "Combining quarters into unified tables"),
    ("scripts/4_validate.py", "Running data quality checks"),
]

def run_script(script_path: str, description: str) -> bool:
    """
    Run a single script and return True if successful.

    Args:
        script_path: Path to the Python script
        description: Human-readable description of what the script does

    Returns:
        True if script completed successfully, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"Step {SCRIPTS.index((script_path, description)) + 1}/{len(SCRIPTS)}: {description}")
    print(f"Running: {script_path}")
    print(f"{'='*60}\n")

    try:
        # Run the script and capture output in real-time
        result = subprocess.run(
            [sys.executable, script_path],
            check=True,
            text=True
        )

        try:
            print(f"\n[OK] {script_path} completed successfully")
        except UnicodeEncodeError:
            print(f"\n[SUCCESS] {script_path} completed successfully")
        return True

    except subprocess.CalledProcessError as e:
        try:
            print(f"\n[X] {script_path} failed with exit code {e.returncode}")
        except UnicodeEncodeError:
            print(f"\n[FAILED] {script_path} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        try:
            print(f"\n[X] Script not found: {script_path}")
        except UnicodeEncodeError:
            print(f"\n[ERROR] Script not found: {script_path}")
        return False

def main():
    """Run the complete pipeline."""
    print("="*60)
    print("CPUC AV Data Pipeline")
    print("="*60)

    # Track which scripts succeeded
    results = []

    # Run each script in order
    for script_path, description in SCRIPTS:
        success = run_script(script_path, description)
        results.append((script_path, success))

        # Continue to next step even if this one failed
        if not success:
            print(f"\nWarning: {script_path} failed, but continuing to next step...\n")

    # Check if all scripts completed successfully
    all_success = all(success for _, success in results)

    print(f"\n{'='*60}")
    if all_success:
        print("Pipeline COMPLETED SUCCESSFULLY")
    else:
        print("Pipeline COMPLETED WITH ERRORS")
    print(f"{'='*60}\n")

    print("All steps completed:")
    for i, (script_path, success) in enumerate(results, 1):
        status = "[OK]" if success else "[X]"
        try:
            print(f"  {status} Step {i}: {script_path}")
        except UnicodeEncodeError:
            print(f"  {'SUCCESS' if success else 'FAILED'} Step {i}: {script_path}")

    if all_success:
        print("\nProcessed data is available in the processed/ directory.")
    else:
        print("\nSome steps failed. Check the output above for details.")
        print("Processed data (if any) is available in the processed/ directory.")
        sys.exit(1)

if __name__ == "__main__":
    main()
