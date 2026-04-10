"""
Glassdoor Scraper
=================
Scraper for Glassdoor job listings using Apollo GraphQL state extraction.
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


class GlassdoorScraper(BaseScraper):
    """
    Glassdoor job scraper.

    Glassdoor uses Apollo GraphQL - job data is embedded as JSON in the page.
    We extract the apolloState object which contains structured job data.

    Supports: US, UK, Canada
    """

    URLS = {
        Country.US: "https://www.glassdoor.com/Job/jobs.htm",
        Country.UK: "https://www.glassdoor.co.uk/Job/jobs.htm",
        Country.CANADA: "https://www.glassdoor.ca/Job/jobs.htm",
        Country.NIGERIA: "https://www.glassdoor.com/Job/jobs.htm",  # Search globally for Nigeria/EMEA/Africa
    }

    JOB_VIEW_URLS = {
        Country.US: "https://www.glassdoor.com/job-listing",
        Country.UK: "https://www.glassdoor.co.uk/job-listing",
        Country.CANADA: "https://www.glassdoor.ca/job-listing",
        Country.NIGERIA: "https://www.glassdoor.com/job-listing",
    }

    # Location keywords for EMEA/Africa searches
    EMEA_KEYWORDS = ["emea", "africa", "nigeria", "remote africa", "remote emea", "remote nigeria"]

    def __init__(self, country: Country = Country.US, search_emea: bool = False):
        super().__init__(f"Glassdoor {country.value}", country)

        if country not in self.URLS:
            raise ValueError(f"Glassdoor not supported for country: {country}")

        self.base_url = self.URLS[country]
        self.job_view_url = self.JOB_VIEW_URLS[country]
        self.search_emea = search_emea or country == Country.NIGERIA

    def scrape(self, search_terms: List[str] = None, max_jobs: int = 100) -> ScraperResult:
        """
        Scrape jobs from Glassdoor.

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

            self.logger.info(f"Searching Glassdoor {self.country.value} for: {search_term}")

            try:
                jobs = self._search_jobs(search_term, max_jobs - len(result.jobs))

                for job in jobs:
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        if self._should_include_job(job):
                            result.jobs.append(job)

                result.total_found += len(jobs)

            except Exception as e:
                self.logger.error(f"Error searching Glassdoor: {e}")
                result.errors.append(f"Search error: {str(e)}")

            self._delay(4, 8)  # Glassdoor has aggressive bot detection

        self.logger.info(f"Found {len(result.jobs)} jobs from Glassdoor {self.country.value}")
        return result

    def _search_jobs(self, search_term: str, max_jobs: int) -> List[Job]:
        """Search Glassdoor with pagination."""
        jobs = []
        page = 1

        while len(jobs) < max_jobs:
            # Glassdoor URL format
            keyword_slug = search_term.lower().replace(" ", "-")
            url = f"{self.base_url}?sc.keyword={quote(search_term)}"

            if page > 1:
                url += f"&p={page}"

            # Add visa sponsorship keyword
            if VISA.needs_sponsorship.get(self.country, False):
                url += "&sc.keyword=" + quote(f"{search_term} visa sponsorship")

            # For Nigeria/EMEA searches, add location keywords
            if self.search_emea:
                url += "&sc.keyword=" + quote(f"{search_term} remote EMEA OR Africa OR Nigeria")

            response = self._get(url)
            if not response:
                break

            # Extract jobs from Apollo state
            page_jobs = self._extract_jobs_from_apollo(response.text)

            if not page_jobs:
                # Fallback to HTML parsing
                page_jobs = self._extract_jobs_from_html(response.text)

            if not page_jobs:
                self.logger.debug(f"No more jobs found on page {page}")
                break

            for job_data in page_jobs:
                if len(jobs) >= max_jobs:
                    break
                job = self.parse_job(job_data)
                if job:
                    jobs.append(job)

            page += 1
            self._delay(3, 6)

            # Safety limit
            if page > 10:
                break

        return jobs

    def _extract_jobs_from_apollo(self, html: str) -> List[Dict]:
        """
        Extract job data from Apollo GraphQL state.

        Glassdoor embeds all data in window.appCache or apolloState.
        """
        jobs = []

        # Pattern 1: apolloState in script
        patterns = [
            r'apolloState":\s*({.+?})\s*[,}]',
            r'window\.__APOLLO_STATE__\s*=\s*({.+?});',
            r'"jobListings":\s*(\[.+?\])',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)

                    # Handle different data structures
                    if isinstance(data, list):
                        jobs.extend(data)
                    elif isinstance(data, dict):
                        # Look for job listings in the Apollo cache
                        for key, value in data.items():
                            if 'JobListing' in key or 'jobListing' in key:
                                if isinstance(value, dict):
                                    jobs.append(value)
                            elif isinstance(value, dict) and value.get('__typename') == 'JobListing':
                                jobs.append(value)

                except json.JSONDecodeError:
                    continue

            if jobs:
                break

        return jobs

    def _extract_jobs_from_html(self, html: str) -> List[Dict]:
        """Fallback: Extract jobs from HTML structure."""
        jobs = []
        soup = self._parse_html(html)

        # Glassdoor job cards
        job_cards = soup.select(
            "li.react-job-listing, "
            "div[data-test='jobListing'], "
            "article.job-listing, "
            "div.JobCard"
        )

        for card in job_cards:
            job_data = {}

            # Title
            title_elem = card.select_one(
                "a.jobLink, "
                "a[data-test='job-link'], "
                "div.job-title, "
                "span.job-title"
            )
            if title_elem:
                job_data["title"] = title_elem.get_text(strip=True)
                job_data["url"] = title_elem.get("href", "")

            # Company
            company_elem = card.select_one(
                "span.EmployerProfile, "
                "div.employer-name, "
                "a[data-test='employer-name']"
            )
            if company_elem:
                job_data["company"] = company_elem.get_text(strip=True)

            # Location
            location_elem = card.select_one(
                "span.loc, "
                "span.location, "
                "div[data-test='emp-location']"
            )
            if location_elem:
                job_data["location"] = location_elem.get_text(strip=True)

            # Salary
            salary_elem = card.select_one(
                "span.salary-estimate, "
                "span[data-test='detailSalary'], "
                "div.salary"
            )
            if salary_elem:
                job_data["salary"] = salary_elem.get_text(strip=True)

            # Job ID from URL or data attribute
            job_id = card.get("data-id") or card.get("data-job-id")
            if not job_id and job_data.get("url"):
                match = re.search(r'jobListingId=(\d+)', job_data.get("url", ""))
                if match:
                    job_id = match.group(1)
            job_data["job_id"] = job_id or ""

            if job_data.get("title") and job_data.get("company"):
                jobs.append(job_data)

        return jobs

    def parse_job(self, data: Any) -> Optional[Job]:
        """
        Parse job data into Job object.

        Args:
            data: Job data dictionary

        Returns:
            Job object or None
        """
        if not isinstance(data, dict):
            return None

        try:
            # Handle different field names from Apollo vs HTML
            title = (
                data.get("title") or
                data.get("jobTitle") or
                data.get("header", {}).get("jobTitle") or
                ""
            )

            company = (
                data.get("company") or
                data.get("employer", {}).get("name") or
                data.get("header", {}).get("employerName") or
                ""
            )

            location = (
                data.get("location") or
                data.get("header", {}).get("locationName") or
                data.get("map", {}).get("locationName") or
                ""
            )

            # Salary
            salary = data.get("salary", "Not Listed")
            if isinstance(salary, dict):
                salary_text = salary.get("salaryText") or salary.get("payPeriod", "")
                if salary.get("min") and salary.get("max"):
                    salary = f"${salary['min']:,} - ${salary['max']:,}"
                else:
                    salary = salary_text or "Not Listed"
            elif not salary:
                salary = "Not Listed"

            # Job URL
            job_url = data.get("url") or data.get("jobLink") or ""
            if job_url and not job_url.startswith("http"):
                job_url = f"{self.job_view_url}/{job_url}"

            # Job ID
            job_id = str(data.get("job_id") or data.get("jobListingId") or data.get("id") or "")

            # Description snippet
            description = (
                data.get("description") or
                data.get("jobDescription") or
                data.get("header", {}).get("jobDescription") or
                ""
            )

            if not title or not company:
                return None

            # Determine visa sponsorship
            full_text = f"{title} {description} {location}"
            visa_sponsored = detect_visa_sponsorship(full_text, company, VISA.known_sponsors)

            # Work type
            is_remote = "remote" in f"{title} {location}".lower()
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
                pay_range=salary,
                source=self.name,
                job_url=job_url,
                country=self.country,
                description=description[:500] if description else "",
                status=JobStatus.FOUND,
            )

        except Exception as e:
            self.logger.error(f"Error parsing Glassdoor job: {e}")
            return None

    def get_job_details(self, job_listing_id: str) -> Optional[Dict]:
        """
        Fetch full job details.

        Args:
            job_listing_id: Glassdoor job listing ID

        Returns:
            Dictionary with job details
        """
        url = f"{self.job_view_url}?jobListingId={job_listing_id}"
        response = self._get(url)

        if not response:
            return None

        details = {}

        # Try Apollo extraction first
        apollo_data = self._extract_jobs_from_apollo(response.text)
        if apollo_data:
            for item in apollo_data:
                if str(item.get("jobListingId")) == job_listing_id:
                    details = item
                    break

        # Fallback to HTML
        if not details.get("description"):
            soup = self._parse_html(response.text)
            desc_elem = soup.select_one(
                "div.JobDetails, "
                "div.desc, "
                "div[data-test='jobDescription']"
            )
            if desc_elem:
                details["description"] = desc_elem.get_text(strip=True)

        return details
