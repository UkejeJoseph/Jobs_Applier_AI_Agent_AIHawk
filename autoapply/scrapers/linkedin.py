"""
LinkedIn Scraper
================
Scraper for LinkedIn Jobs using the guest API (no login required).
"""

import re
import json
from typing import List, Optional, Any, Dict
from urllib.parse import urlencode, quote

from .base import BaseScraper, ScraperResult
from autoapply.core.job_schema import (
    Job, Country, WorkType, JobStatus,
    detect_visa_sponsorship, extract_salary
)
from autoapply.config import VISA


class LinkedInScraper(BaseScraper):
    """
    LinkedIn Jobs scraper using the guest API.

    This uses LinkedIn's internal API that powers the public job search page,
    which doesn't require authentication.

    Note: LinkedIn rate-limits aggressively. Use with care.
    """

    # LinkedIn guest jobs API
    BASE_API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    # LinkedIn job view URL
    JOB_VIEW_URL = "https://www.linkedin.com/jobs/view"

    # Geographic IDs for countries
    GEO_IDS = {
        Country.US: "103644278",
        Country.UK: "101165590",
        Country.CANADA: "101174742",
        Country.NIGERIA: "105365761",
    }

    # Work type filters
    REMOTE_FILTER = "f_WT=2"  # Remote jobs

    def __init__(self, country: Country = Country.US):
        super().__init__(f"LinkedIn {country.value}", country)
        self.geo_id = self.GEO_IDS.get(country, self.GEO_IDS[Country.US])

    def scrape(self, search_terms: List[str] = None, max_jobs: int = 100) -> ScraperResult:
        """
        Scrape jobs from LinkedIn.

        Args:
            search_terms: Job titles to search for
            max_jobs: Maximum jobs to return

        Returns:
            ScraperResult with found jobs
        """
        from autoapply.config import JOB_PREFS

        if search_terms is None:
            search_terms = JOB_PREFS.target_titles

        result = ScraperResult(source=self.name)
        seen_ids = set()

        for search_term in search_terms:
            if len(result.jobs) >= max_jobs:
                break

            self.logger.info(f"Searching LinkedIn {self.country.value} for: {search_term}")

            try:
                # Search for remote jobs
                remote_jobs = self._search_jobs(search_term, max_jobs - len(result.jobs), remote=True)
                for job in remote_jobs:
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        if self._should_include_job(job):
                            result.jobs.append(job)

                # Also search for on-site jobs (will filter by visa)
                if len(result.jobs) < max_jobs:
                    onsite_jobs = self._search_jobs(search_term, max_jobs - len(result.jobs), remote=False)
                    for job in onsite_jobs:
                        if job.job_id not in seen_ids:
                            seen_ids.add(job.job_id)
                            if self._should_include_job(job):
                                result.jobs.append(job)

                result.total_found += len(remote_jobs) + len(onsite_jobs)

            except Exception as e:
                self.logger.error(f"Error searching LinkedIn: {e}")
                result.errors.append(f"Search error: {str(e)}")

            self._delay(3, 6)  # LinkedIn rate limits heavily

        self.logger.info(f"Found {len(result.jobs)} jobs from LinkedIn {self.country.value}")
        return result

    def _search_jobs(self, search_term: str, max_jobs: int, remote: bool = True) -> List[Job]:
        """Search LinkedIn with pagination."""
        jobs = []
        start = 0
        jobs_per_page = 25

        while len(jobs) < max_jobs:
            params = {
                "keywords": search_term,
                "location": self._get_location_name(),
                "geoId": self.geo_id,
                "start": start,
            }

            if remote:
                params["f_WT"] = "2"  # Remote filter

            # Add visa sponsorship keywords to search
            if VISA.needs_sponsorship.get(self.country, False):
                # LinkedIn doesn't have a direct visa filter, but we can search
                # We'll rely on post-filtering based on job description
                pass

            response = self._get(self.BASE_API, params=params)

            if not response:
                break

            # LinkedIn returns HTML fragments
            page_jobs = self._parse_job_cards(response.text, remote)

            if not page_jobs:
                self.logger.debug(f"No more jobs at start={start}")
                break

            jobs.extend(page_jobs)
            start += jobs_per_page
            self._delay(2, 4)

            # Safety limit
            if start > 200:
                break

        return jobs[:max_jobs]

    def _get_location_name(self) -> str:
        """Get location name for country."""
        names = {
            Country.US: "United States",
            Country.UK: "United Kingdom",
            Country.CANADA: "Canada",
            Country.NIGERIA: "Nigeria",
        }
        return names.get(self.country, "United States")

    def _parse_job_cards(self, html: str, is_remote_search: bool) -> List[Job]:
        """Parse job cards from LinkedIn HTML response."""
        jobs = []
        soup = self._parse_html(html)

        # LinkedIn job cards
        job_cards = soup.select("li, div.base-card")

        for card in job_cards:
            job = self._parse_card(card, is_remote_search)
            if job:
                jobs.append(job)

        return jobs

    def _parse_card(self, card, is_remote_search: bool) -> Optional[Job]:
        """Parse a single job card."""
        try:
            # Title
            title_elem = card.select_one("h3.base-search-card__title, h3.job-card-list__title")
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            # Company
            company_elem = card.select_one("h4.base-search-card__subtitle a, a.job-card-container__company-name")
            company = company_elem.get_text(strip=True) if company_elem else ""

            # Location
            location_elem = card.select_one("span.job-search-card__location, span.job-card-container__metadata-item")
            location = location_elem.get_text(strip=True) if location_elem else ""

            # Job URL and ID
            link_elem = card.select_one("a.base-card__full-link, a.job-card-list__title")
            job_url = ""
            job_id = ""
            if link_elem:
                job_url = link_elem.get("href", "")
                # Extract job ID from URL
                match = re.search(r'/jobs/view/(\d+)', job_url)
                if match:
                    job_id = match.group(1)
                elif re.search(r'-(\d+)\?', job_url):
                    job_id = re.search(r'-(\d+)\?', job_url).group(1)

            # Date posted
            date_elem = card.select_one("time.job-search-card__listdate, time")
            date_posted = ""
            if date_elem:
                date_posted = date_elem.get("datetime", "") or date_elem.get_text(strip=True)

            # Salary (if shown)
            salary_elem = card.select_one("span.job-search-card__salary-info")
            salary = salary_elem.get_text(strip=True) if salary_elem else "Not Listed"

            if not title or not company:
                return None

            # Determine visa sponsorship (we'll need to check full description later)
            # For now, check company against known sponsors
            visa_sponsored = company.lower() in [s.lower() for s in VISA.known_sponsors]

            # Work type
            if is_remote_search or "remote" in location.lower():
                work_type = WorkType.REMOTE_VISA_SPONSORED if visa_sponsored else WorkType.REMOTE_NO_VISA
            else:
                work_type = WorkType.ONSITE_VISA_SPONSORED if visa_sponsored else WorkType.ONSITE_NO_VISA

            return Job(
                company=company,
                role=title,
                location=location,
                work_type=work_type,
                visa_sponsored=visa_sponsored,
                pay_range=salary,
                source=self.name,
                job_url=job_url,
                country=self.country,
                date_posted=date_posted,
                status=JobStatus.FOUND,
            )

        except Exception as e:
            self.logger.debug(f"Error parsing LinkedIn card: {e}")
            return None

    def parse_job(self, data: Any) -> Optional[Job]:
        """Parse job from data (implements abstract method)."""
        if isinstance(data, dict):
            return self._parse_job_dict(data)
        return None

    def _parse_job_dict(self, data: Dict) -> Optional[Job]:
        """Parse job from dictionary data."""
        try:
            title = data.get("title", "")
            company = data.get("companyName", "")
            location = data.get("location", "")
            job_url = data.get("url", "")

            if not title or not company:
                return None

            visa_sponsored = detect_visa_sponsorship(
                data.get("description", ""),
                company,
                VISA.known_sponsors
            )

            is_remote = "remote" in location.lower()
            if is_remote:
                work_type = WorkType.REMOTE_VISA_SPONSORED if visa_sponsored else WorkType.REMOTE_NO_VISA
            else:
                work_type = WorkType.ONSITE_VISA_SPONSORED if visa_sponsored else WorkType.ONSITE_NO_VISA

            return Job(
                company=company,
                role=title,
                location=location,
                work_type=work_type,
                visa_sponsored=visa_sponsored,
                pay_range=data.get("salary", "Not Listed"),
                source=self.name,
                job_url=job_url,
                country=self.country,
                description=data.get("description", ""),
                status=JobStatus.FOUND,
            )

        except Exception as e:
            self.logger.error(f"Error parsing job dict: {e}")
            return None

    def get_job_details(self, job_id: str) -> Optional[Dict]:
        """
        Fetch full job description from LinkedIn.

        Args:
            job_id: LinkedIn job ID

        Returns:
            Dictionary with full job details
        """
        url = f"{self.JOB_VIEW_URL}/{job_id}"
        response = self._get(url)

        if not response:
            return None

        soup = self._parse_html(response.text)
        details = {}

        # Full description
        desc_elem = soup.select_one("div.description__text, div.show-more-less-html__markup")
        if desc_elem:
            details["description"] = desc_elem.get_text(strip=True)

            # Check for visa sponsorship in full description
            details["visa_mentioned"] = detect_visa_sponsorship(
                details["description"], "", VISA.known_sponsors
            )

        # Criteria (experience level, etc.)
        criteria = soup.select("li.description__job-criteria-item")
        for item in criteria:
            header = item.select_one("h3")
            value = item.select_one("span")
            if header and value:
                key = header.get_text(strip=True).lower().replace(" ", "_")
                details[key] = value.get_text(strip=True)

        return details

    def enrich_job_with_details(self, job: Job) -> Job:
        """
        Enrich a job with full details including visa sponsorship check.

        Args:
            job: Job object with job_url

        Returns:
            Updated Job object
        """
        # Extract job ID from URL
        match = re.search(r'/view/(\d+)', job.job_url)
        if not match:
            return job

        job_id = match.group(1)
        details = self.get_job_details(job_id)

        if not details:
            return job

        # Update job with details
        if details.get("description"):
            job.description = details["description"]

        # Update visa sponsorship based on full description
        if details.get("visa_mentioned"):
            job.visa_sponsored = True
            if "remote" in job.location.lower():
                job.work_type = WorkType.REMOTE_VISA_SPONSORED
            else:
                job.work_type = WorkType.ONSITE_VISA_SPONSORED

        # Extract salary from description if not listed
        if job.pay_range == "Not Listed":
            job.pay_range = extract_salary(job.description)

        return job
