"""
Greenhouse Job Board Scraper
============================
Scrapes jobs from Greenhouse-powered career pages.
Greenhouse is used by many tech companies (Airbnb, Pinterest, Coinbase, etc.)

API: boards.greenhouse.io/{company}/jobs
"""

import re
import json
from typing import List, Optional, Any, Dict
from urllib.parse import urljoin

from .base import BaseScraper, ScraperResult
from autoapply.core.job_schema import (
    Job, Country, WorkType, JobStatus,
    detect_visa_sponsorship, extract_salary
)
from autoapply.config import VISA


class GreenhouseScraper(BaseScraper):
    """
    Scraper for Greenhouse job boards.

    Greenhouse has a public JSON API for job listings.
    URL format: https://boards-api.greenhouse.io/v1/boards/{company}/jobs
    """

    # Companies known to sponsor visas and use Greenhouse
    SPONSOR_COMPANIES = [
        # Big Tech & Unicorns
        "airbnb", "pinterest", "coinbase", "stripe", "twitch",
        "figma", "notion", "airtable", "webflow", "vercel",
        "datadog", "mongodb", "elastic", "cloudflare", "hashicorp",
        "gitlab", "reddit", "discord", "roblox", "unity",
        "doordash", "instacart", "robinhood", "plaid", "brex",
        # AI/ML Companies
        "openai", "anthropic", "cohere", "huggingface", "scale",
        "deepmind", "stability", "midjourney", "runway",
        # Fintech
        "chime", "sofi", "affirm", "klarna", "checkout",
        "wise", "revolut", "monzo", "nubank",
        # Enterprise
        "snowflake", "databricks", "confluent", "cockroachlabs",
        "fivetran", "dbt", "airbyte", "prefect",
        # Security
        "crowdstrike", "snyk", "lacework", "orca",
        # E-commerce
        "shopify", "etsy", "wayfair", "farfetch",
        # African Tech (using Greenhouse)
        "andela", "paystack", "flutterwave", "chipper",
    ]

    # Additional companies to always check (even if not known sponsors)
    ALWAYS_CHECK = [
        "openai", "anthropic", "stripe", "coinbase", "airbnb",
        "figma", "notion", "vercel", "datadog", "cloudflare",
    ]

    BASE_API = "https://boards-api.greenhouse.io/v1/boards"
    BASE_URL = "https://boards.greenhouse.io"

    def __init__(self, country: Country = Country.US, companies: List[str] = None):
        super().__init__("Greenhouse", country)
        self.companies = companies or self.SPONSOR_COMPANIES

    def scrape(self, search_terms: List[str] = None, max_jobs: int = 200) -> ScraperResult:
        """
        Scrape jobs from multiple Greenhouse boards.
        """
        from autoapply.config import JOB_PREFS

        if search_terms is None:
            search_terms = JOB_PREFS.target_titles

        result = ScraperResult(source=self.name)
        seen_ids = set()

        for company in self.companies:
            if len(result.jobs) >= max_jobs:
                break

            self.logger.info(f"Checking Greenhouse: {company}")

            try:
                jobs = self._scrape_company(company, search_terms)

                for job in jobs:
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        if self._should_include_job(job):
                            result.jobs.append(job)

                result.total_found += len(jobs)

            except Exception as e:
                self.logger.debug(f"Error scraping {company}: {e}")
                result.errors.append(f"{company}: {str(e)}")

            self._delay(1, 2)  # Greenhouse is lenient

        self.logger.info(f"Found {len(result.jobs)} jobs from Greenhouse")
        return result

    def _scrape_company(self, company: str, search_terms: List[str]) -> List[Job]:
        """Scrape jobs from a single company's Greenhouse board."""
        jobs = []

        # Greenhouse JSON API
        api_url = f"{self.BASE_API}/{company}/jobs"

        response = self._get(api_url)
        if not response:
            return jobs

        try:
            data = response.json()
            job_listings = data.get("jobs", [])

            for job_data in job_listings:
                job = self._parse_job_data(job_data, company)
                if job and self._matches_search_terms(job, search_terms):
                    jobs.append(job)

        except json.JSONDecodeError:
            self.logger.debug(f"Invalid JSON from {company}")

        return jobs

    def _parse_job_data(self, data: Dict, company: str) -> Optional[Job]:
        """Parse Greenhouse job JSON into Job object."""
        try:
            title = data.get("title", "")
            location = data.get("location", {}).get("name", "")
            job_id = str(data.get("id", ""))

            # Get job URL
            absolute_url = data.get("absolute_url", "")
            if not absolute_url:
                absolute_url = f"{self.BASE_URL}/{company}/jobs/{job_id}"

            # Detect country from location
            country = self._detect_country_from_location(location)

            # Check for remote
            is_remote = any(kw in location.lower() for kw in ["remote", "anywhere", "distributed"])

            # Get departments/categories
            departments = [d.get("name", "") for d in data.get("departments", [])]

            # Check visa sponsorship
            full_text = f"{title} {location} {' '.join(departments)}"
            is_sponsor_company = company.lower() in [c.lower() for c in self.SPONSOR_COMPANIES]
            visa_sponsored = is_sponsor_company or detect_visa_sponsorship(full_text, company, VISA.known_sponsors)

            # Determine work type
            if is_remote and visa_sponsored:
                work_type = WorkType.REMOTE_VISA_SPONSORED
            elif is_remote:
                work_type = WorkType.REMOTE_NO_VISA
            elif visa_sponsored:
                work_type = WorkType.ONSITE_VISA_SPONSORED
            else:
                work_type = WorkType.ONSITE_NO_VISA

            return Job(
                company=company.title(),
                role=title,
                location=location,
                work_type=work_type,
                visa_sponsored=visa_sponsored,
                pay_range="Not Listed",
                source="Greenhouse",
                job_url=absolute_url,
                country=country,
                description=f"Departments: {', '.join(departments)}" if departments else "",
                status=JobStatus.FOUND,
            )

        except Exception as e:
            self.logger.debug(f"Error parsing job: {e}")
            return None

    def _matches_search_terms(self, job: Job, search_terms: List[str]) -> bool:
        """Check if job matches any search term."""
        job_text = f"{job.role} {job.description}".lower()

        # Also match common tech roles
        tech_keywords = ["engineer", "developer", "software", "backend", "frontend",
                        "fullstack", "devops", "sre", "data", "ml", "ai"]

        for term in search_terms:
            if term.lower() in job_text:
                return True

        for keyword in tech_keywords:
            if keyword in job_text:
                return True

        return False

    def _detect_country_from_location(self, location: str) -> Country:
        """Detect country from location string."""
        loc_lower = location.lower()

        if any(kw in loc_lower for kw in ["united states", "usa", "us,", "new york", "san francisco",
                                          "seattle", "austin", "boston", "chicago", "denver", "los angeles"]):
            return Country.US
        elif any(kw in loc_lower for kw in ["united kingdom", "uk", "london", "manchester", "edinburgh"]):
            return Country.UK
        elif any(kw in loc_lower for kw in ["canada", "toronto", "vancouver", "montreal"]):
            return Country.CANADA
        elif any(kw in loc_lower for kw in ["nigeria", "lagos", "abuja"]):
            return Country.NIGERIA
        else:
            return Country.US  # Default to US for remote/unspecified

    def parse_job(self, data: Any) -> Optional[Job]:
        """Parse raw job data (required by base class)."""
        if isinstance(data, dict):
            return self._parse_job_data(data, "unknown")
        return None


class LeverScraper(BaseScraper):
    """
    Scraper for Lever job boards.

    Lever has a public API similar to Greenhouse.
    URL format: https://api.lever.co/v0/postings/{company}
    """

    # Companies using Lever that are known to sponsor (verified working slugs)
    SPONSOR_COMPANIES = [
        # Verified working on Lever API
        "plaid", "duolingo", "benchling", "nextdoor", "notion",
        "alltrails", "replit", "checkout", "truebill", "watershed",
        "verkada", "airtable", "square", "affirm", "grammarly",
        # Tech companies
        "dropbox", "ramp", "webflow", "sourcegraph", "cockroachlabs",
        # African companies on Lever
        "cowrywise", "carbon", "kuda",
    ]

    BASE_API = "https://api.lever.co/v0/postings"

    def __init__(self, country: Country = Country.US, companies: List[str] = None):
        super().__init__("Lever", country)
        self.companies = companies or self.SPONSOR_COMPANIES

    def scrape(self, search_terms: List[str] = None, max_jobs: int = 200) -> ScraperResult:
        """Scrape jobs from Lever boards."""
        from autoapply.config import JOB_PREFS

        if search_terms is None:
            search_terms = JOB_PREFS.target_titles

        result = ScraperResult(source=self.name)
        seen_ids = set()

        for company in self.companies:
            if len(result.jobs) >= max_jobs:
                break

            self.logger.info(f"Checking Lever: {company}")

            try:
                jobs = self._scrape_company(company, search_terms)

                for job in jobs:
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        if self._should_include_job(job):
                            result.jobs.append(job)

                result.total_found += len(jobs)

            except Exception as e:
                self.logger.debug(f"Error scraping {company}: {e}")

            self._delay(1, 2)

        self.logger.info(f"Found {len(result.jobs)} jobs from Lever")
        return result

    def _scrape_company(self, company: str, search_terms: List[str]) -> List[Job]:
        """Scrape jobs from a single company's Lever board."""
        import requests
        jobs = []

        api_url = f"{self.BASE_API}/{company}"

        # Use direct requests (cloudscraper redirects to HTML for Lever)
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            }
            response = requests.get(api_url, headers=headers, timeout=30)
            response.raise_for_status()
            job_listings = response.json()
        except Exception as e:
            self.logger.debug(f"Lever API failed for {company}: {e}")
            return jobs

        if not isinstance(job_listings, list):
            return jobs

        for job_data in job_listings:
            job = self._parse_job_data(job_data, company)
            if job and self._matches_search_terms(job, search_terms):
                jobs.append(job)

        return jobs

    def _parse_job_data(self, data: Dict, company: str) -> Optional[Job]:
        """Parse Lever job JSON into Job object."""
        try:
            title = data.get("text", "")

            # Location from categories
            categories = data.get("categories", {})
            location = categories.get("location", "Remote")

            job_id = data.get("id", "")
            job_url = data.get("hostedUrl", "") or data.get("applyUrl", "")

            # Detect country
            country = self._detect_country_from_location(location)

            # Check remote
            is_remote = any(kw in location.lower() for kw in ["remote", "anywhere"])

            # Visa check
            is_sponsor = company.lower() in [c.lower() for c in self.SPONSOR_COMPANIES]
            visa_sponsored = is_sponsor

            if is_remote and visa_sponsored:
                work_type = WorkType.REMOTE_VISA_SPONSORED
            elif is_remote:
                work_type = WorkType.REMOTE_NO_VISA
            elif visa_sponsored:
                work_type = WorkType.ONSITE_VISA_SPONSORED
            else:
                work_type = WorkType.ONSITE_NO_VISA

            return Job(
                company=company.title(),
                role=title,
                location=location,
                work_type=work_type,
                visa_sponsored=visa_sponsored,
                pay_range="Not Listed",
                source="Lever",
                job_url=job_url,
                country=country,
                description=data.get("descriptionPlain", "")[:500],
                status=JobStatus.FOUND,
            )

        except Exception as e:
            self.logger.debug(f"Error parsing job: {e}")
            return None

    def _matches_search_terms(self, job: Job, search_terms: List[str]) -> bool:
        """Check if job matches search terms."""
        job_text = f"{job.role} {job.description}".lower()
        tech_keywords = ["engineer", "developer", "software", "backend", "frontend", "fullstack"]

        for term in search_terms:
            if term.lower() in job_text:
                return True
        for kw in tech_keywords:
            if kw in job_text:
                return True
        return False

    def _detect_country_from_location(self, location: str) -> Country:
        """Detect country from location."""
        loc = location.lower()
        if any(x in loc for x in ["us", "united states", "america"]):
            return Country.US
        elif any(x in loc for x in ["uk", "united kingdom", "london"]):
            return Country.UK
        elif "canada" in loc:
            return Country.CANADA
        elif "nigeria" in loc:
            return Country.NIGERIA
        return Country.US

    def parse_job(self, data: Any) -> Optional[Job]:
        if isinstance(data, dict):
            return self._parse_job_data(data, "unknown")
        return None


class AshbyScraper(BaseScraper):
    """
    Scraper for Ashby job boards.

    Ashby is a newer ATS used by many startups.
    URL format: https://jobs.ashbyhq.com/{company}
    API: https://jobs.ashbyhq.com/api/non-user-graphql
    """

    SPONSOR_COMPANIES = [
        "notion", "linear", "vercel", "planetscale", "railway",
        "resend", "cal", "dub", "typefully", "raycast",
        "posthog", "supabase", "neon", "turso",
    ]

    def __init__(self, country: Country = Country.US, companies: List[str] = None):
        super().__init__("Ashby", country)
        self.companies = companies or self.SPONSOR_COMPANIES

    def scrape(self, search_terms: List[str] = None, max_jobs: int = 100) -> ScraperResult:
        """Scrape Ashby job boards."""
        from autoapply.config import JOB_PREFS

        if search_terms is None:
            search_terms = JOB_PREFS.target_titles

        result = ScraperResult(source=self.name)
        seen_ids = set()

        for company in self.companies:
            if len(result.jobs) >= max_jobs:
                break

            self.logger.info(f"Checking Ashby: {company}")

            try:
                jobs = self._scrape_company(company, search_terms)

                for job in jobs:
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        result.jobs.append(job)

                result.total_found += len(jobs)

            except Exception as e:
                self.logger.debug(f"Error scraping {company}: {e}")

            self._delay(1, 2)

        self.logger.info(f"Found {len(result.jobs)} jobs from Ashby")
        return result

    def _scrape_company(self, company: str, search_terms: List[str]) -> List[Job]:
        """Scrape from Ashby REST API."""
        import requests
        jobs = []

        # Ashby REST API (works better than GraphQL)
        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company}"

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            }
            response = requests.get(api_url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            self.logger.debug(f"Ashby API failed for {company}: {e}")
            return jobs

        job_listings = data.get("jobs", [])

        for job_data in job_listings:
            try:
                title = job_data.get("title", "")
                location = job_data.get("location", "Remote")
                job_id = job_data.get("id", "")

                if not title:
                    continue

                job_url = f"https://jobs.ashbyhq.com/{company}/{job_id}"

                # Check if matches search terms
                title_lower = title.lower()
                if not any(term.lower() in title_lower for term in search_terms):
                    tech_kw = ["engineer", "developer", "software", "backend", "frontend", "data", "devops"]
                    if not any(kw in title_lower for kw in tech_kw):
                        continue

                is_remote = "remote" in location.lower() if location else False
                is_sponsor = company.lower() in [c.lower() for c in self.SPONSOR_COMPANIES]

                work_type = WorkType.REMOTE_VISA_SPONSORED if is_remote and is_sponsor else \
                           WorkType.REMOTE_NO_VISA if is_remote else \
                           WorkType.ONSITE_VISA_SPONSORED if is_sponsor else \
                           WorkType.ONSITE_NO_VISA

                jobs.append(Job(
                    company=company.title(),
                    role=title,
                    location=location or "Remote",
                    work_type=work_type,
                    visa_sponsored=is_sponsor,
                    pay_range="Not Listed",
                    source="Ashby",
                    job_url=job_url,
                    country=Country.US,
                    status=JobStatus.FOUND,
                ))

            except Exception:
                continue

        return jobs

    def parse_job(self, data: Any) -> Optional[Job]:
        return None
