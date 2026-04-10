"""
Indeed Scraper
==============
Scraper for Indeed job listings (US, UK, Canada).
Extracts job data from hidden JSON in page source.
"""

import re
import json
from typing import List, Optional, Any, Dict
from urllib.parse import urlencode

from .base import BaseScraper, ScraperResult
from autoapply.core.job_schema import (
    Job, Country, WorkType, JobStatus,
    detect_country, detect_work_type, detect_visa_sponsorship, extract_salary
)
from autoapply.config import VISA


class IndeedScraper(BaseScraper):
    """
    Indeed job scraper.

    Supports:
    - US: indeed.com
    - UK: uk.indeed.com
    - Canada: ca.indeed.com

    Uses the hidden JSON data embedded in page source for cleaner extraction.
    """

    URLS = {
        Country.US: "https://www.indeed.com/jobs",
        Country.UK: "https://uk.indeed.com/jobs",
        Country.CANADA: "https://ca.indeed.com/jobs",
    }

    JOB_VIEW_URLS = {
        Country.US: "https://www.indeed.com/viewjob",
        Country.UK: "https://uk.indeed.com/viewjob",
        Country.CANADA: "https://ca.indeed.com/viewjob",
    }

    # Visa sponsorship filter (US only)
    VISA_FILTER = "sc=0kf:attr(FCGTU);"

    def __init__(self, country: Country = Country.US):
        super().__init__(f"Indeed {country.value}", country)

        if country not in self.URLS:
            raise ValueError(f"Indeed not supported for country: {country}")

        self.base_url = self.URLS[country]
        self.job_view_url = self.JOB_VIEW_URLS[country]

    def scrape(self, search_terms: List[str] = None, max_jobs: int = 100) -> ScraperResult:
        """
        Scrape jobs from Indeed.

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

            self.logger.info(f"Searching Indeed {self.country.value} for: {search_term}")

            try:
                jobs = self._search_jobs(search_term, max_jobs - len(result.jobs))

                for job in jobs:
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        if self._should_include_job(job):
                            result.jobs.append(job)

                result.total_found += len(jobs)

            except Exception as e:
                self.logger.error(f"Error searching for '{search_term}': {e}")
                result.errors.append(f"Search error: {str(e)}")

            self._delay(3, 6)  # Indeed is aggressive with bot detection

        self.logger.info(f"Found {len(result.jobs)} jobs from Indeed {self.country.value}")
        return result

    def _search_jobs(self, search_term: str, max_jobs: int) -> List[Job]:
        """Search for jobs with pagination."""
        jobs = []
        start = 0
        jobs_per_page = 15

        while len(jobs) < max_jobs:
            params = {
                "q": search_term,
                "l": "",  # Location (empty for all)
                "start": start,
                "sort": "date",  # Sort by date
            }

            # Add visa sponsorship filter for US
            if self.country == Country.US:
                params["sc"] = "0kf:attr(FCGTU);"

            response = self._get(self.base_url, params=params)
            if not response:
                break

            # Try to extract jobs from JSON in page
            page_jobs = self._extract_jobs_from_page(response.text)

            if not page_jobs:
                self.logger.debug(f"No more jobs found at start={start}")
                break

            for job_data in page_jobs:
                if len(jobs) >= max_jobs:
                    break

                job = self.parse_job(job_data)
                if job:
                    jobs.append(job)

            start += jobs_per_page
            self._delay(2, 4)

            # Safety limit
            if start > 200:
                break

        return jobs

    def _extract_jobs_from_page(self, html: str) -> List[Dict]:
        """
        Extract job data from hidden JSON in page source.

        Indeed embeds job data in a JavaScript object in the page.
        """
        jobs = []

        # Method 1: Look for window.mosaic.providerData
        pattern = r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*({.+?});'
        match = re.search(pattern, html, re.DOTALL)

        if match:
            try:
                data = json.loads(match.group(1))
                results = data.get("metaData", {}).get("mosaicProviderJobCardsModel", {}).get("results", [])
                jobs.extend(results)
            except json.JSONDecodeError:
                pass

        # Method 2: Look for data in script tags
        if not jobs:
            pattern = r'window\._initialData\s*=\s*({.+?});'
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    if "jobResults" in data:
                        jobs.extend(data["jobResults"].get("results", []))
                except json.JSONDecodeError:
                    pass

        # Method 3: Parse HTML directly as fallback
        if not jobs:
            jobs = self._extract_jobs_from_html(html)

        return jobs

    def _extract_jobs_from_html(self, html: str) -> List[Dict]:
        """Fallback: Extract jobs from HTML structure."""
        jobs = []
        soup = self._parse_html(html)

        job_cards = soup.select("div.job_seen_beacon, div.jobsearch-ResultsList > div")

        for card in job_cards:
            job_data = {}

            # Title
            title_elem = card.select_one("h2.jobTitle a span, a[data-jk] span")
            if title_elem:
                job_data["title"] = title_elem.get_text(strip=True)

            # Company
            company_elem = card.select_one("span.companyName, span[data-testid='company-name']")
            if company_elem:
                job_data["company"] = company_elem.get_text(strip=True)

            # Location
            location_elem = card.select_one("div.companyLocation, div[data-testid='text-location']")
            if location_elem:
                job_data["location"] = location_elem.get_text(strip=True)

            # Job key (ID)
            link_elem = card.select_one("a[data-jk], h2.jobTitle a")
            if link_elem:
                job_data["jobkey"] = link_elem.get("data-jk") or ""
                href = link_elem.get("href", "")
                jk_match = re.search(r'jk=([a-f0-9]+)', href)
                if jk_match:
                    job_data["jobkey"] = jk_match.group(1)

            # Salary
            salary_elem = card.select_one("div.salary-snippet, span.salary")
            if salary_elem:
                job_data["salary"] = salary_elem.get_text(strip=True)

            # Snippet/description
            snippet_elem = card.select_one("div.job-snippet, td.snip")
            if snippet_elem:
                job_data["snippet"] = snippet_elem.get_text(strip=True)

            if job_data.get("title") and job_data.get("company"):
                jobs.append(job_data)

        return jobs

    def parse_job(self, data: Any) -> Optional[Job]:
        """
        Parse job data into Job object.

        Args:
            data: Job data dictionary (from JSON or HTML)

        Returns:
            Job object or None
        """
        if not isinstance(data, dict):
            return None

        try:
            # Extract fields from various possible structures
            title = data.get("title") or data.get("jobTitle") or data.get("displayTitle", "")
            company = data.get("company") or data.get("companyName") or ""

            # Handle nested company object
            if isinstance(company, dict):
                company = company.get("name", "")

            location = data.get("location") or data.get("formattedLocation") or ""
            if isinstance(location, dict):
                location = location.get("city", "") + ", " + location.get("country", "")

            # Job key for URL
            job_key = data.get("jobkey") or data.get("jk") or ""

            # Salary
            salary = data.get("salary") or ""
            if isinstance(salary, dict):
                salary = salary.get("text", "") or salary.get("formattedSalary", "")
            if not salary:
                salary = extract_salary(data.get("snippet", "") or data.get("description", ""))
            salary = salary or "Not Listed"

            # Description snippet
            snippet = data.get("snippet") or data.get("description") or ""

            # Determine visa sponsorship
            full_text = f"{title} {snippet} {data.get('attributes', '')}"
            visa_sponsored = detect_visa_sponsorship(full_text, company, VISA.known_sponsors)

            # For Indeed US with visa filter, assume sponsorship available
            if self.country == Country.US:
                visa_sponsored = True  # We're using the visa filter

            # Determine work type
            is_remote = "remote" in f"{title} {location}".lower()
            if is_remote:
                work_type = WorkType.REMOTE_VISA_SPONSORED if visa_sponsored else WorkType.REMOTE_NO_VISA
            else:
                work_type = WorkType.ONSITE_VISA_SPONSORED if visa_sponsored else WorkType.ONSITE_NO_VISA

            # Build job URL
            job_url = ""
            if job_key:
                job_url = f"{self.job_view_url}?jk={job_key}"

            if not title or not company:
                return None

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
                description=snippet,
                status=JobStatus.FOUND,
            )

        except Exception as e:
            self.logger.error(f"Error parsing job: {e}")
            return None

    def get_job_details(self, job_key: str) -> Optional[Dict]:
        """
        Fetch full job description.

        Args:
            job_key: Indeed job key

        Returns:
            Dictionary with job details
        """
        url = f"{self.job_view_url}?jk={job_key}"
        response = self._get(url)

        if not response:
            return None

        soup = self._parse_html(response.text)
        details = {}

        # Full description
        desc_elem = soup.select_one("div#jobDescriptionText, div.jobsearch-jobDescriptionText")
        if desc_elem:
            details["description"] = desc_elem.get_text(strip=True)

        # Benefits
        benefits = soup.select("div.jobsearch-JobMetadataHeader-item")
        details["benefits"] = [b.get_text(strip=True) for b in benefits]

        return details
