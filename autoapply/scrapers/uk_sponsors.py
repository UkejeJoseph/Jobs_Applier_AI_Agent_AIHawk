"""
UK Sponsor List Scraper
=======================
Downloads and parses the UK Home Office Register of Licensed Sponsors.
This is the official list of UK employers approved to sponsor Skilled Worker visas.
"""

import csv
import io
from pathlib import Path
from typing import List, Optional, Any, Set
from datetime import datetime, timedelta

import requests

from .base import SponsorListScraper, ScraperResult
from autoapply.core.job_schema import Job, Country
from autoapply.config import DATA_DIR


class UKSponsorList(SponsorListScraper):
    """
    UK Home Office Register of Licensed Sponsors.

    Downloads the official CSV from gov.uk and caches it locally.
    Use is_sponsor() to check if a company is on the approved list.

    The register includes:
    - Organisation Name
    - Town/City
    - County
    - Type & Rating (A-rated, B-rated)
    - Route (Skilled Worker, etc.)
    """

    # The gov.uk page that links to the CSV
    GOV_UK_PAGE = "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"

    # Direct CSV download URL (may need updating if gov.uk changes it)
    # This is typically a spreadsheet download link
    CSV_URL = "https://assets.publishing.service.gov.uk/media/5e7c7f67e90e071e47e2ac76/2024-01-01_-_Worker_and_Temporary_Worker.csv"

    CACHE_FILE = "uk_sponsors.csv"
    CACHE_MAX_AGE_DAYS = 7  # Re-download weekly

    def __init__(self):
        super().__init__("UK Sponsor List", Country.UK, DATA_DIR)
        self.cache_path = self.cache_dir / self.CACHE_FILE

    def download_sponsor_list(self) -> bool:
        """
        Download the sponsor list from gov.uk.

        Returns:
            True if successful, False otherwise
        """
        # Check if cache is still valid
        if self._is_cache_valid():
            self.logger.info("Using cached UK sponsor list")
            return True

        self.logger.info("Downloading UK sponsor list from gov.uk...")

        try:
            # First, try to get the latest CSV URL from the gov.uk page
            csv_url = self._get_latest_csv_url()
            if not csv_url:
                csv_url = self.CSV_URL  # Fall back to hardcoded URL

            response = self._get(csv_url)
            if not response:
                self.logger.error("Failed to download sponsor list")
                return False

            # Save to cache
            with open(self.cache_path, "wb") as f:
                f.write(response.content)

            self.logger.info(f"Saved sponsor list to {self.cache_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error downloading sponsor list: {e}")
            return False

    def _get_latest_csv_url(self) -> Optional[str]:
        """
        Try to find the latest CSV download URL from the gov.uk page.

        Returns:
            URL string or None
        """
        try:
            response = self._get(self.GOV_UK_PAGE)
            if not response:
                return None

            soup = self._parse_html(response.text)

            # Look for CSV download links
            for link in soup.select("a[href*='.csv']"):
                href = link.get("href", "")
                if "Worker" in href or "sponsor" in href.lower():
                    # Make absolute URL if relative
                    if href.startswith("/"):
                        href = f"https://www.gov.uk{href}"
                    elif not href.startswith("http"):
                        href = f"https://assets.publishing.service.gov.uk{href}"
                    return href

            # Also check for ODS (spreadsheet) links that might have CSV alternative
            for link in soup.select("a[href*='.ods'], a[href*='.xlsx']"):
                href = link.get("href", "")
                csv_href = href.replace(".ods", ".csv").replace(".xlsx", ".csv")
                return csv_href

        except Exception as e:
            self.logger.warning(f"Could not find latest CSV URL: {e}")

        return None

    def _is_cache_valid(self) -> bool:
        """Check if the cached file exists and is recent enough."""
        if not self.cache_path.exists():
            return False

        # Check file age
        file_time = datetime.fromtimestamp(self.cache_path.stat().st_mtime)
        age = datetime.now() - file_time

        return age < timedelta(days=self.CACHE_MAX_AGE_DAYS)

    def load_sponsors(self) -> Set[str]:
        """
        Load sponsors from the cached CSV file.

        Returns:
            Set of normalized company names
        """
        sponsors = set()

        if not self.cache_path.exists():
            self.logger.warning("Sponsor list cache not found. Run download_sponsor_list() first.")
            return sponsors

        try:
            with open(self.cache_path, "r", encoding="utf-8-sig") as f:
                # Try to detect the CSV format
                sample = f.read(4096)
                f.seek(0)

                # Detect delimiter
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                reader = csv.DictReader(f, dialect=dialect)

                # Find the organisation name column
                org_column = None
                for col in reader.fieldnames or []:
                    col_lower = col.lower()
                    if "organisation" in col_lower or "company" in col_lower or "name" in col_lower:
                        org_column = col
                        break

                if not org_column and reader.fieldnames:
                    # Fall back to first column
                    org_column = reader.fieldnames[0]

                if not org_column:
                    self.logger.error("Could not find organisation name column in CSV")
                    return sponsors

                # Also find the route column to filter for Skilled Worker
                route_column = None
                for col in reader.fieldnames or []:
                    if "route" in col.lower() or "type" in col.lower():
                        route_column = col
                        break

                for row in reader:
                    org_name = row.get(org_column, "").strip().lower()

                    # Filter for Skilled Worker route if column exists
                    if route_column:
                        route = row.get(route_column, "").lower()
                        if "skilled worker" not in route and "worker" not in route:
                            continue

                    if org_name:
                        # Normalize company name
                        org_name = self._normalize_company(org_name)
                        sponsors.add(org_name)

            self.logger.info(f"Loaded {len(sponsors)} UK sponsors from cache")

        except Exception as e:
            self.logger.error(f"Error loading sponsors from CSV: {e}")

        return sponsors

    def _normalize_company(self, name: str) -> str:
        """Normalize company name for matching."""
        name = name.lower().strip()

        # Remove common suffixes
        suffixes = [
            " limited", " ltd", " ltd.", " plc", " inc", " inc.",
            " llp", " lp", " uk", " (uk)", " international"
        ]
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()

        return name

    def is_sponsor(self, company_name: str) -> bool:
        """
        Check if a company is on the UK sponsor list.

        Args:
            company_name: Company name to check

        Returns:
            True if company is a licensed sponsor
        """
        if not self._sponsors:
            self._sponsors = self.load_sponsors()

        normalized = self._normalize_company(company_name)

        # Exact match
        if normalized in self._sponsors:
            return True

        # Partial match (for variations in company names)
        for sponsor in self._sponsors:
            # Check if one contains the other (for abbreviated names)
            if len(normalized) > 3 and len(sponsor) > 3:
                if normalized in sponsor or sponsor in normalized:
                    return True

        return False

    def get_sponsors_in_city(self, city: str) -> List[str]:
        """
        Get all sponsors in a specific city.

        Args:
            city: City name to filter by

        Returns:
            List of sponsor names in that city
        """
        sponsors_in_city = []
        city_lower = city.lower()

        if not self.cache_path.exists():
            return sponsors_in_city

        try:
            with open(self.cache_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    # Find city column
                    for col in row:
                        if "city" in col.lower() or "town" in col.lower():
                            if city_lower in row[col].lower():
                                org_col = next(
                                    (c for c in row if "organisation" in c.lower() or "name" in c.lower()),
                                    None
                                )
                                if org_col:
                                    sponsors_in_city.append(row[org_col])
                            break

        except Exception as e:
            self.logger.error(f"Error searching sponsors by city: {e}")

        return sponsors_in_city
