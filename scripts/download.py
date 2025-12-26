#!/usr/bin/env python3
"""
CPUC Autonomous Vehicle Data Downloader

This script scrapes the CPUC quarterly reporting page to find and download
all available ZIP archives containing autonomous vehicle operational data,
then extracts the Excel files.

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
import zipfile
from datetime import datetime
from io import BytesIO
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
KNOWN_COMPANIES = [
    "waymo", "cruise", "zoox", "aurora", "nuro", "autox",
    "pony", "argo", "motional", "ghost", "deeproute", "voyage",
    "weride", "tensor"
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
    """
    for attempt in range(max_retries + 1):
        try:
            response = session.get(url, timeout=60, stream=stream)
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


def parse_zip_metadata(url: str, link_text: str) -> dict:
    """
    Extract metadata from a ZIP download URL and link text.
    """
    metadata = {
        "original_url": url,
        "original_link_text": link_text,
        "program_type": None,  # deployment or pilot
        "year": None,
        "quarter": None,
        "start_month": None,
        "end_month": None,
        "companies": [],
    }

    url_lower = url.lower()
    text_lower = link_text.lower()
    combined = f"{url_lower} {text_lower}"

    # Detect program type
    if "deployment" in combined:
        metadata["program_type"] = "deployment"
    elif "pilot" in combined:
        metadata["program_type"] = "pilot"

    # Extract year
    year_match = re.search(r"20(1[89]|2[0-9])", combined)
    if year_match:
        metadata["year"] = int(f"20{year_match.group(1)}")

    # Extract quarter (Q1, Q2, Q3, Q4)
    quarter_match = re.search(r"q([1-4])", combined, re.IGNORECASE)
    if quarter_match:
        metadata["quarter"] = int(quarter_match.group(1))

    # Extract month range patterns like "0601-0831" or "jun-aug"
    month_range = re.search(r"(\d{2})01[-_](\d{2})\d{2}", url_lower)
    if month_range:
        metadata["start_month"] = int(month_range.group(1))
        metadata["end_month"] = int(month_range.group(2))

    # Extract companies from link text
    for company in KNOWN_COMPANIES:
        if company in combined:
            metadata["companies"].append(company)

    return metadata


def generate_zip_filename(metadata: dict, original_url: str) -> str:
    """Generate a standardized filename for downloaded ZIP."""
    parts = []

    # Program type
    if metadata["program_type"]:
        parts.append(metadata["program_type"])
    else:
        parts.append("unknown")

    # Year
    if metadata["year"]:
        parts.append(str(metadata["year"]))

    # Quarter or month range
    if metadata["quarter"]:
        parts.append(f"q{metadata['quarter']}")
    elif metadata["start_month"] and metadata["end_month"]:
        parts.append(f"m{metadata['start_month']:02d}-{metadata['end_month']:02d}")

    # Use hash if we couldn't parse much
    if len(parts) <= 1:
        url_hash = hashlib.md5(original_url.encode()).hexdigest()[:8]
        parts.append(url_hash)

    return "_".join(parts) + ".zip"


def scrape_zip_links(session: requests.Session) -> list[dict]:
    """
    Scrape the CPUC quarterly reporting page for ZIP file download links.
    """
    logger.info(f"Fetching CPUC quarterly reporting page: {CPUC_REPORTING_URL}")

    response = fetch_with_retry(session, CPUC_REPORTING_URL)
    if response is None:
        logger.error("Failed to fetch CPUC reporting page")
        return []

    soup = BeautifulSoup(response.content, "lxml")

    zip_links = []
    seen_urls = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        link_text = link.get_text(strip=True)

        # Check if this is a ZIP file link
        if ".zip" in href.lower():
            # Make absolute URL if relative
            if not href.startswith("http"):
                href = urljoin(CPUC_BASE_URL, href)

            # Skip duplicates
            if href in seen_urls:
                continue
            seen_urls.add(href)

            # Parse metadata
            metadata = parse_zip_metadata(href, link_text)

            # Generate standardized filename
            std_filename = generate_zip_filename(metadata, href)

            zip_links.append({
                "url": href,
                "link_text": link_text,
                "standardized_filename": std_filename,
                "metadata": metadata,
            })

    logger.info(f"Found {len(zip_links)} ZIP file links")
    return zip_links


def download_and_extract_zip(
    session: requests.Session,
    url: str,
    output_dir: Path,
    zip_filename: str,
    metadata: dict,
) -> list[dict]:
    """
    Download a ZIP file and extract Excel files from it.

    Returns list of extracted file info.
    """
    logger.info(f"Downloading: {url}")

    response = fetch_with_retry(session, url)
    if response is None:
        return []

    extracted_files = []

    try:
        # Open ZIP from memory
        zip_buffer = BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            # List contents
            file_list = zf.namelist()
            excel_files = [f for f in file_list if f.lower().endswith(('.xlsx', '.xls'))]

            logger.info(f"  ZIP contains {len(excel_files)} Excel files")

            for excel_file in excel_files:
                # Skip hidden files and temp files
                basename = os.path.basename(excel_file)
                if basename.startswith('.') or basename.startswith('~'):
                    continue

                # Generate output filename with metadata prefix
                prefix_parts = []
                if metadata.get("program_type"):
                    prefix_parts.append(metadata["program_type"])
                if metadata.get("year"):
                    prefix_parts.append(str(metadata["year"]))
                if metadata.get("quarter"):
                    prefix_parts.append(f"q{metadata['quarter']}")
                elif metadata.get("start_month"):
                    prefix_parts.append(f"m{metadata['start_month']:02d}")

                # Clean up the original filename
                clean_basename = re.sub(r'[^\w\-\.]', '_', basename)

                if prefix_parts:
                    output_filename = f"{'_'.join(prefix_parts)}_{clean_basename}"
                else:
                    output_filename = clean_basename

                output_path = output_dir / output_filename

                # Extract file
                with zf.open(excel_file) as src:
                    content = src.read()
                    with open(output_path, 'wb') as dst:
                        dst.write(content)

                file_hash = hashlib.md5(content).hexdigest()

                extracted_files.append({
                    "original_name": excel_file,
                    "output_name": output_filename,
                    "output_path": str(output_path),
                    "size_bytes": len(content),
                    "md5": file_hash,
                    "source_zip": url,
                    "extracted_at": datetime.now().isoformat(),
                })

                logger.info(f"    Extracted: {output_filename}")

    except zipfile.BadZipFile as e:
        logger.error(f"  Invalid ZIP file: {e}")
    except Exception as e:
        logger.error(f"  Error extracting ZIP: {e}")

    return extracted_files


def load_metadata(metadata_path: Path) -> dict:
    """Load existing metadata or create new."""
    if metadata_path.exists():
        with open(metadata_path, "r") as f:
            return json.load(f)
    return {
        "last_updated": None,
        "source_url": CPUC_REPORTING_URL,
        "files": {},
        "zip_archives": {},
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
        "--deployment-only",
        action="store_true",
        help="Only download deployment program data (not pilot)",
    )
    parser.add_argument(
        "--pilot-only",
        action="store_true",
        help="Only download pilot program data (not deployment)",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        default=None,
        help="Only download data from this year onward",
    )

    args = parser.parse_args()

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load existing metadata
    metadata = load_metadata(args.metadata_file)

    # Create session and scrape links
    session = get_session()
    zip_links = scrape_zip_links(session)

    if not zip_links:
        logger.error("No ZIP files found on the CPUC page")
        sys.exit(1)

    # Apply filters
    filtered_links = zip_links

    if args.deployment_only:
        filtered_links = [
            link for link in filtered_links
            if link["metadata"]["program_type"] == "deployment"
        ]
        logger.info(f"Filtered to {len(filtered_links)} deployment files")

    if args.pilot_only:
        filtered_links = [
            link for link in filtered_links
            if link["metadata"]["program_type"] == "pilot"
        ]
        logger.info(f"Filtered to {len(filtered_links)} pilot files")

    if args.min_year:
        filtered_links = [
            link for link in filtered_links
            if link["metadata"]["year"] and link["metadata"]["year"] >= args.min_year
        ]
        logger.info(f"Filtered to {len(filtered_links)} files from {args.min_year}+")

    # Download and extract files
    total_zips = 0
    total_extracted = 0
    failed = 0

    download_run = {
        "timestamp": datetime.now().isoformat(),
        "zips_found": len(zip_links),
        "zips_filtered": len(filtered_links),
        "zips_downloaded": 0,
        "files_extracted": 0,
        "failed": 0,
    }

    for link in filtered_links:
        if args.dry_run:
            logger.info(f"Would download: {link['url']}")
            logger.info(f"  Program: {link['metadata']['program_type']}")
            logger.info(f"  Year: {link['metadata']['year']}, Q{link['metadata'].get('quarter', '?')}")
            continue

        # Check if we already have files from this ZIP
        zip_key = link["standardized_filename"]
        if zip_key in metadata.get("zip_archives", {}) and not args.force:
            logger.info(f"Skipping (already processed): {zip_key}")
            continue

        # Download and extract
        extracted = download_and_extract_zip(
            session,
            link["url"],
            args.output_dir,
            link["standardized_filename"],
            link["metadata"],
        )

        if extracted:
            total_zips += 1
            total_extracted += len(extracted)

            # Update metadata
            metadata["zip_archives"][zip_key] = {
                **link,
                "extracted_files": extracted,
                "downloaded_at": datetime.now().isoformat(),
            }

            for file_info in extracted:
                metadata["files"][file_info["output_name"]] = file_info
        else:
            failed += 1
            logger.error(f"Failed to process: {link['url']}")

        # Be polite - add delay between downloads
        time.sleep(1)

    # Update download history
    download_run["zips_downloaded"] = total_zips
    download_run["files_extracted"] = total_extracted
    download_run["failed"] = failed
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
    logger.info(f"Total ZIP archives found: {len(zip_links)}")
    logger.info(f"ZIP archives after filtering: {len(filtered_links)}")
    logger.info(f"ZIP archives downloaded: {total_zips}")
    logger.info(f"Excel files extracted: {total_extracted}")
    logger.info(f"Failed: {failed}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
