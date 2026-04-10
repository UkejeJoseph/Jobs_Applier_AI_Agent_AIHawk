"""
Canada Job Bank Scraper
=======================
Scraper for jobbank.gc.ca - Canada's official government job board.
Uses LMIA filter (fsrc=32) to find jobs from employers with approved work permits.
"""

import re
from typing import List, Optional, Any
from datetime import datetime

from bs4 import Tag

from .base import BaseScraper, ScraperResult
from autoapply.core.job_schema import Job, Country, WorkType, JobStatus


class JobBankCanadaScraper(BaseScraper):
    """
    Scraper for Canada Job Bank (jobbank.gc.ca).

    This is the official Canadian government job board.
    The LMIA filter (fsrc=32) returns jobs from employers who have
    obtained or applied for a Labour Market Impact Assessment,
    meaning they're approved to hire foreign workers.
    """

    BASE_URL = "https://www.jobbank.gc.ca/jobsearch/jobsearch"
    JOB_DETAIL_URL = "https://www.jobbank.gc.ca/jobsearch/jobposting"

    def __init__(self):
        super().__init__("JobBank Canada", Country.CANADA)

    def scrape(self, search_terms: List[str] = None, max_jobs: int = 100) -> ScraperResult:
        """
        Scrape jobs from Canada Job Bank.

        Args:
            search_terms: List of job titles to search (defaults to config)
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

            self.logger.info(f"Searching Job Bank for: {search_term}")

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
                result.errors.append(f"Search error for '{search_term}': {str(e)}")

            self._delay(2, 4)  # Be nice to government servers

        self.logger.info(f"Found {len(result.jobs)} jobs from Job Bank Canada")
        return result

    def _search_jobs(self, search_term: str, max_jobs: int) -> List[Job]:
        """Search for jobs with a specific term."""
        jobs = []
        page = 1
        jobs_per_page = 25

        while len(jobs) < max_jobs:
            params = {
                "searchstring": search_term,
                "fsrc": "32",  # LMIA-approved employers filter
                "sort": "D",  # Sort by date (newest first)
                "page": page,
            }

            response = self._get(self.BASE_URL, params=params)
            if not response:
                break

            soup = self._parse_html(response.text)
            job_cards = soup.select("article.resultJobItem")

            if not job_cards:
                self.logger.debug(f"No more jobs found on page {page}")
                break

            for card in job_cards:
                if len(jobs) >= max_jobs:
                    break

                job = self.parse_job(card)
                if job:
                    jobs.append(job)

            page += 1
            self._delay(1, 2)

            # Safety limit
            if page > 20:
                break

        return jobs

    def parse_job(self, data: Any) -> Optional[Job]:
        """
        Parse a job card from Job Bank search results.

        Args:
            data: BeautifulSoup Tag element for job card

        Returns:
            Job object or None
        """
        if not isinstance(data, Tag):
            return None

        try:
            # Extract job title
            title_elem = data.select_one("a.resultJobItem-title span.noctitle")
            if not title_elem:
                title_elem = data.select_one("a.resultJobItem-title")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Extract company
            company_elem = data.select_one("li.business span")
            company = company_elem.get_text(strip=True) if company_elem else ""

            # Extract location
            location_elem = data.select_one("li.location span")
            location = location_elem.get_text(strip=True) if location_elem else ""
            location = f"{location}, Canada" if location and "Canada" not in location else location

            # Extract job URL
            link_elem = data.select_one("a.resultJobItem-title")
            job_id = ""
            job_url = ""
            if link_elem and link_elem.get("href"):
                href = link_elem.get("href")
                # Extract job ID from URL
                match = re.search(r'/(\d+)', href)
                if match:
                    job_id = match.group(1)
                    job_url = f"{self.JOB_DETAIL_URL}/{job_id}"

            # Extract salary if available
            salary_elem = data.select_one("li.salary span")
            salary = salary_elem.get_text(strip=True) if salary_elem else "Not Listed"

            # Extract date posted
            date_elem = data.select_one("li.date span")
            date_posted = date_elem.get_text(strip=True) if date_elem else ""

            # LMIA filter means visa sponsorship is available
            visa_sponsored = True

            # Determine work type (need to check job details for remote)
            work_type = WorkType.ONSITE_VISA_SPONSORED
            if "remote" in f"{title} {location}".lower():
                work_type = WorkType.REMOTE_VISA_SPONSORED

            if not title or not company:
                return None

            return Job(
                company=company,
                role=title,
                location=location,
                work_type=work_type,
                visa_sponsored=visa_sponsored,
                pay_range=salary,
                source="Job Bank Canada",
                job_url=job_url,
                country=Country.CANADA,
                date_posted=date_posted,
                status=JobStatus.FOUND,
            )

        except Exception as e:
            self.logger.error(f"Error parsing job card: {e}")
            return None

    def get_job_details(self, job_id: str) -> Optional[dict]:
        """
        Fetch full job details for additional info like description.

        Args:
            job_id: Job Bank job ID

        Returns:
            Dictionary with job details or None
        """
        url = f"{self.JOB_DETAIL_URL}/{job_id}"
        response = self._get(url)

        if not response:
            return None

        soup = self._parse_html(response.text)

        details = {}

        # Extract full description
        desc_elem = soup.select_one("div.job-posting-detail-requirements")
        if desc_elem:
            details["description"] = desc_elem.get_text(strip=True)

        # Check for remote work
        work_setting = soup.select_one("span.work-setting")
        if work_setting:
            details["work_setting"] = work_setting.get_text(strip=True)

        return details
