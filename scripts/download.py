#!/usr/bin/env python3
"""
CPUC Autonomous Vehicle Data Downloader

This script scrapes the CPUC quarterly reporting page to find and download
all available Excel files containing autonomous vehicle operational data.

Usage:
    python scripts/download.py [--output-dir RAW_DIR] [--metadata-file METADATA_PATH]
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Constants
CPUC_BASE_URL = "https://www.cpuc.ca.gov"
CPUC_REPORTING_URL = (
    "https://www.cpuc.ca.gov/regulatory-services/licensing/"
    "transportation-licensing-and-analysis-branch/autonomous-vehicle-programs/"
    "quarterly-reporting"
)

# Known companies in the AV program
KNOWN_COMPANIES = ["waymo", "cruise", "zoox", "aurora", "nuro"]

# Report types based on CPUC file naming conventions
REPORT_TYPES = [
    "trip-level",
    "month-level",
    "monthly-tract",
    "incidents-complaints",
    "incidents-location",
    "vmt",
]

# Permit types
PERMIT_TYPES = [
    "drivered-pilot",
    "driverless-pilot",
    "drivered-deployment",
    "driverless-deployment",
]


def get_session() -> requests.Session:
    """Create a requests session with appropriate headers."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.5",
        }
    )
    return session


def fetch_with_retry(
    session: requests.Session,
    url: str,
    max_retries: int = 4,
    base_delay: float = 2.0,
    stream: bool = False,
) -> Optional[requests.Response]:
    """
    Fetch a URL with exponential backoff retry logic.

    Args:
        session: requests Session object
        url: URL to fetch
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles each retry)
        stream: Whether to stream the response

    Returns:
        Response object or None if all retries failed
    """
    for attempt in range(max_retries + 1):
        try:
            response = session.get(url, timeout=30, stream=stream)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                logger.error(f"All retry attempts failed for {url}: {e}")
                return None
    return None


def parse_filename_metadata(url: str, link_text: str) -> dict:
    """
    Extract metadata from a download URL and link text.

    Args:
        url: The download URL
        link_text: The text of the link element

    Returns:
        Dictionary with extracted metadata
    """
    metadata = {
        "original_url": url,
        "original_link_text": link_text,
        "company": None,
        "quarter": None,
        "year": None,
        "report_type": None,
        "permit_type": None,
    }

    # Normalize for matching
    url_lower = url.lower()
    text_lower = link_text.lower()
    combined = f"{url_lower} {text_lower}"

    # Extract company
    for company in KNOWN_COMPANIES:
        if company in combined:
            metadata["company"] = company
            break

    # Extract quarter (Q1, Q2, Q3, Q4 or similar patterns)
    quarter_patterns = [
        r"q([1-4])",
        r"quarter\s*([1-4])",
        r"(\d{4})[-_]?q([1-4])",
        r"q([1-4])[-_]?(\d{4})",
    ]
    for pattern in quarter_patterns:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 1:
                metadata["quarter"] = int(groups[0])
            elif len(groups) == 2:
                # Determine which group is year vs quarter
                if len(groups[0]) == 4:
                    metadata["year"] = int(groups[0])
                    metadata["quarter"] = int(groups[1])
                else:
                    metadata["quarter"] = int(groups[0])
                    metadata["year"] = int(groups[1])
            break

    # Extract year if not already found
    if metadata["year"] is None:
        year_match = re.search(r"20(1[9]|2[0-9])", combined)
        if year_match:
            metadata["year"] = int(f"20{year_match.group(1)}")

    # Extract report type
    for report_type in REPORT_TYPES:
        if report_type.replace("-", "").replace("_", "") in combined.replace(
            "-", ""
        ).replace("_", ""):
            metadata["report_type"] = report_type
            break

    # Try alternate report type patterns
    if metadata["report_type"] is None:
        if "trip" in combined and "level" in combined:
            metadata["report_type"] = "trip-level"
        elif "month" in combined and "level" in combined:
            metadata["report_type"] = "month-level"
        elif "tract" in combined:
            metadata["report_type"] = "monthly-tract"
        elif "incident" in combined and "location" in combined:
            metadata["report_type"] = "incidents-location"
        elif "incident" in combined or "complaint" in combined:
            metadata["report_type"] = "incidents-complaints"
        elif "vmt" in combined:
            metadata["report_type"] = "vmt"

    # Extract permit type
    for permit_type in PERMIT_TYPES:
        if permit_type.replace("-", "") in combined.replace("-", "").replace("_", ""):
            metadata["permit_type"] = permit_type
            break

    # Alternate permit type patterns
    if metadata["permit_type"] is None:
        if "driverless" in combined and "deployment" in combined:
            metadata["permit_type"] = "driverless-deployment"
        elif "drivered" in combined and "deployment" in combined:
            metadata["permit_type"] = "drivered-deployment"
        elif "driverless" in combined and "pilot" in combined:
            metadata["permit_type"] = "driverless-pilot"
        elif "drivered" in combined and "pilot" in combined:
            metadata["permit_type"] = "drivered-pilot"

    return metadata


def generate_filename(metadata: dict, original_filename: str) -> str:
    """
    Generate a standardized filename based on metadata.

    Format: {company}_{year}q{quarter}_{report_type}.xlsx

    Args:
        metadata: Extracted metadata dictionary
        original_filename: Original filename from URL

    Returns:
        Standardized filename
    """
    parts = []

    # Company
    if metadata["company"]:
        parts.append(metadata["company"])
    else:
        parts.append("unknown")

    # Year and quarter
    if metadata["year"] and metadata["quarter"]:
        parts.append(f"{metadata['year']}q{metadata['quarter']}")
    elif metadata["quarter"]:
        parts.append(f"q{metadata['quarter']}")
    else:
        # Use a hash of the original URL for uniqueness
        url_hash = hashlib.md5(metadata["original_url"].encode()).hexdigest()[:8]
        parts.append(url_hash)

    # Report type
    if metadata["report_type"]:
        parts.append(metadata["report_type"])

    # Permit type (if available and different from default)
    if metadata["permit_type"] and metadata["permit_type"] != "driverless-deployment":
        parts.append(metadata["permit_type"])

    # Get extension from original filename
    ext = Path(original_filename).suffix.lower()
    if ext not in [".xlsx", ".xls"]:
        ext = ".xlsx"

    return "_".join(parts) + ext


def scrape_download_links(session: requests.Session) -> list[dict]:
    """
    Scrape the CPUC quarterly reporting page for Excel file download links.

    Args:
        session: requests Session object

    Returns:
        List of dictionaries containing link info and metadata
    """
    logger.info(f"Fetching CPUC quarterly reporting page: {CPUC_REPORTING_URL}")

    response = fetch_with_retry(session, CPUC_REPORTING_URL)
    if response is None:
        logger.error("Failed to fetch CPUC reporting page")
        return []

    soup = BeautifulSoup(response.content, "lxml")

    # Find all links to Excel files
    excel_links = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        link_text = link.get_text(strip=True)

        # Check if this is an Excel file link
        if any(ext in href.lower() for ext in [".xlsx", ".xls"]):
            # Make absolute URL if relative
            if not href.startswith("http"):
                href = urljoin(CPUC_BASE_URL, href)

            # Parse metadata from the link
            metadata = parse_filename_metadata(href, link_text)

            # Get original filename from URL
            parsed_url = urlparse(href)
            original_filename = os.path.basename(parsed_url.path)

            # Generate standardized filename
            std_filename = generate_filename(metadata, original_filename)

            excel_links.append(
                {
                    "url": href,
                    "link_text": link_text,
                    "original_filename": original_filename,
                    "standardized_filename": std_filename,
                    "metadata": metadata,
                }
            )

    logger.info(f"Found {len(excel_links)} Excel file links")
    return excel_links


def download_file(
    session: requests.Session, url: str, output_path: Path
) -> Optional[dict]:
    """
    Download a file from URL to the specified path.

    Args:
        session: requests Session object
        url: URL to download from
        output_path: Path to save the file

    Returns:
        Dictionary with download info or None if failed
    """
    logger.info(f"Downloading: {url}")
    logger.info(f"  -> {output_path}")

    response = fetch_with_retry(session, url, stream=True)
    if response is None:
        return None

    # Get file size if available
    total_size = int(response.headers.get("content-length", 0))

    # Download and save
    output_path.parent.mkdir(parents=True, exist_ok=True)

    downloaded_size = 0
    hash_md5 = hashlib.md5()

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded_size += len(chunk)
                hash_md5.update(chunk)

    return {
        "path": str(output_path),
        "size_bytes": downloaded_size,
        "md5": hash_md5.hexdigest(),
        "download_timestamp": datetime.now().isoformat(),
        "content_type": response.headers.get("content-type"),
    }


def load_metadata(metadata_path: Path) -> dict:
    """Load existing metadata or create new."""
    if metadata_path.exists():
        with open(metadata_path, "r") as f:
            return json.load(f)
    return {
        "last_updated": None,
        "source_url": CPUC_REPORTING_URL,
        "files": {},
        "download_history": [],
    }


def save_metadata(metadata: dict, metadata_path: Path) -> None:
    """Save metadata to JSON file."""
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Download CPUC Autonomous Vehicle quarterly reports"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "raw",
        help="Directory to save downloaded files (default: raw/)",
    )
    parser.add_argument(
        "--metadata-file",
        type=Path,
        default=Path(__file__).parent.parent / "processed" / "metadata.json",
        help="Path to metadata JSON file (default: processed/metadata.json)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files even if they already exist",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without actually downloading",
    )
    parser.add_argument(
        "--filter-company",
        type=str,
        help="Only download files for specified company",
    )
    parser.add_argument(
        "--filter-year",
        type=int,
        help="Only download files for specified year",
    )
    parser.add_argument(
        "--priority-only",
        action="store_true",
        help="Only download driverless deployment reports from Aug 2023 onward",
    )

    args = parser.parse_args()

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load existing metadata
    metadata = load_metadata(args.metadata_file)

    # Create session and scrape links
    session = get_session()
    links = scrape_download_links(session)

    if not links:
        logger.error("No Excel files found on the CPUC page")
        sys.exit(1)

    # Apply filters
    filtered_links = links
    if args.filter_company:
        filtered_links = [
            link
            for link in filtered_links
            if link["metadata"]["company"] == args.filter_company.lower()
        ]
        logger.info(
            f"Filtered to {len(filtered_links)} files for company: {args.filter_company}"
        )

    if args.filter_year:
        filtered_links = [
            link
            for link in filtered_links
            if link["metadata"]["year"] == args.filter_year
        ]
        logger.info(
            f"Filtered to {len(filtered_links)} files for year: {args.filter_year}"
        )

    if args.priority_only:
        # Priority: Driverless Deployment from August 2023 onward
        priority_links = []
        for link in filtered_links:
            meta = link["metadata"]
            if meta["permit_type"] == "driverless-deployment":
                year = meta["year"]
                quarter = meta["quarter"]
                if year and quarter:
                    # Aug 2023 is Q3 2023
                    if year > 2023 or (year == 2023 and quarter >= 3):
                        priority_links.append(link)
        filtered_links = priority_links
        logger.info(
            f"Filtered to {len(filtered_links)} priority files "
            "(driverless deployment, Aug 2023+)"
        )

    # Download files
    downloaded = 0
    skipped = 0
    failed = 0

    download_run = {
        "timestamp": datetime.now().isoformat(),
        "files_found": len(links),
        "files_filtered": len(filtered_links),
        "files_downloaded": 0,
        "files_skipped": 0,
        "files_failed": 0,
    }

    for link in filtered_links:
        output_path = args.output_dir / link["standardized_filename"]

        # Check if file already exists
        if output_path.exists() and not args.force:
            logger.info(f"Skipping (already exists): {link['standardized_filename']}")
            skipped += 1
            continue

        if args.dry_run:
            logger.info(f"Would download: {link['url']}")
            logger.info(f"  -> {output_path}")
            logger.info(f"  Metadata: {json.dumps(link['metadata'], indent=4)}")
            continue

        # Download the file
        download_info = download_file(session, link["url"], output_path)

        if download_info:
            downloaded += 1
            # Update metadata
            metadata["files"][link["standardized_filename"]] = {
                **link,
                "download_info": download_info,
            }
        else:
            failed += 1
            logger.error(f"Failed to download: {link['url']}")

        # Be polite - add delay between downloads
        time.sleep(1)

    # Update download history
    download_run["files_downloaded"] = downloaded
    download_run["files_skipped"] = skipped
    download_run["files_failed"] = failed
    metadata["download_history"].append(download_run)
    metadata["last_updated"] = datetime.now().isoformat()

    # Save metadata
    if not args.dry_run:
        save_metadata(metadata, args.metadata_file)
        logger.info(f"Metadata saved to: {args.metadata_file}")

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("Download Summary")
    logger.info("=" * 50)
    logger.info(f"Total files found: {len(links)}")
    logger.info(f"Files after filtering: {len(filtered_links)}")
    logger.info(f"Downloaded: {downloaded}")
    logger.info(f"Skipped (existing): {skipped}")
    logger.info(f"Failed: {failed}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
