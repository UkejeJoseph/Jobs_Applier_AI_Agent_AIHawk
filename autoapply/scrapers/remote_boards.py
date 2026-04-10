"""
Remote Job Boards Scraper
=========================
Scrapers for remote-focused job boards:
- WeWorkRemotely
- RemoteOK
- Remote.co
- FlexJobs
- Working Nomads
- Remotive
- AngelList/Wellfound (startups)
- BuiltIn (tech jobs)
"""

import re
import json
from typing import List, Optional, Any, Dict
from urllib.parse import urljoin, quote

from .base import BaseScraper, ScraperResult
from autoapply.core.job_schema import (
    Job, Country, WorkType, JobStatus,
    detect_visa_sponsorship, extract_salary
)
from autoapply.config import VISA


class WeWorkRemotelyScraper(BaseScraper):
    """
    Scraper for WeWorkRemotely - one of the largest remote job boards.

    Uses RSS feeds (no captcha!) instead of HTML scraping.
    Categories: Programming, DevOps, Design, Product, etc.
    """

    BASE_URL = "https://weworkremotely.com"
    # RSS feeds - NO CAPTCHA NEEDED!
    RSS_FEEDS = [
        "/categories/remote-programming-jobs.rss",
        "/categories/remote-devops-sysadmin-jobs.rss",
        "/categories/remote-back-end-programming-jobs.rss",
        "/categories/remote-full-stack-programming-jobs.rss",
        "/categories/remote-front-end-programming-jobs.rss",
    ]

    def __init__(self, country: Country = Country.US):
        super().__init__("WeWorkRemotely", country)

    def scrape(self, search_terms: List[str] = None, max_jobs: int = 100) -> ScraperResult:
        """Scrape remote jobs from WeWorkRemotely RSS feeds (no captcha!)."""
        import requests
        import xml.etree.ElementTree as ET

        result = ScraperResult(source=self.name)
        seen_ids = set()

        for rss_url in self.RSS_FEEDS:
            if len(result.jobs) >= max_jobs:
                break

            url = f"{self.BASE_URL}{rss_url}"
            self.logger.info(f"Scraping WWR RSS: {rss_url}")

            try:
                # Use direct requests for RSS (no cloudflare on RSS)
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()

                jobs = self._parse_rss(response.text)

                for job in jobs:
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        result.jobs.append(job)

                result.total_found += len(jobs)

            except Exception as e:
                self.logger.debug(f"RSS fetch failed: {e}")
                continue

            self._delay(1, 2)

        self.logger.info(f"Found {len(result.jobs)} jobs from WeWorkRemotely")
        return result

    def _parse_rss(self, xml_content: str) -> List[Job]:
        """Parse WeWorkRemotely RSS feed."""
        import xml.etree.ElementTree as ET
        import html

        jobs = []

        try:
            root = ET.fromstring(xml_content)

            for item in root.findall('.//item'):
                try:
                    title_elem = item.find('title')
                    link_elem = item.find('link')
                    region_elem = item.find('region')
                    desc_elem = item.find('description')

                    if title_elem is None or link_elem is None:
                        continue

                    full_title = title_elem.text or ""
                    job_url = link_elem.text or ""
                    region = region_elem.text if region_elem is not None else "Remote Worldwide"
                    description = html.unescape(desc_elem.text or "") if desc_elem is not None else ""

                    # Parse title format: "Company: Job Title"
                    if ": " in full_title:
                        company, role = full_title.split(": ", 1)
                    else:
                        company = "Unknown"
                        role = full_title

                    # Extract salary from description if present
                    pay_range = "Not Listed"
                    if "$" in description:
                        import re
                        salary_match = re.search(r'\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*(?:per|/)\s*(?:year|yr|annually))?', description)
                        if salary_match:
                            pay_range = salary_match.group()

                    # WWR jobs are all remote
                    is_worldwide = any(x in region.lower() for x in ["worldwide", "anywhere", "global"])
                    visa_sponsored = is_worldwide

                    work_type = WorkType.REMOTE_VISA_SPONSORED if visa_sponsored else WorkType.REMOTE_NO_VISA

                    jobs.append(Job(
                        company=company.strip(),
                        role=role.strip(),
                        location=region,
                        work_type=work_type,
                        visa_sponsored=visa_sponsored,
                        pay_range=pay_range,
                        source="WeWorkRemotely",
                        job_url=job_url,
                        country=Country.US,
                        status=JobStatus.FOUND,
                    ))

                except Exception as e:
                    self.logger.debug(f"Error parsing RSS item: {e}")
                    continue

        except ET.ParseError as e:
            self.logger.error(f"RSS parse error: {e}")

        return jobs

    def _parse_listing_page(self, html: str) -> List[Job]:
        """Parse job listings from WWR page."""
        jobs = []
        soup = self._parse_html(html)

        # WWR 2024 structure: li.feature or li.new-listing-container
        job_items = soup.select("li.feature, li.new-listing-container, section.jobs li")

        for item in job_items:
            try:
                # Find the job link (new structure uses class listing-link--unlocked)
                title_link = item.select_one(
                    "a.listing-link--unlocked, a.listing-link, a[href*='/remote-jobs/'][href*='-']"
                )
                if not title_link:
                    continue

                href = title_link.get("href", "")
                # Skip non-job links
                if not href or "/remote-jobs/" not in href or href.endswith("/new"):
                    continue

                # New structure: h3.new-listing__header__title or span.new-listing__header__title__text
                title_elem = item.select_one(
                    "h3.new-listing__header__title span, "
                    "h3.new-listing__header__title__text, "
                    "span.new-listing__header__title__text, "
                    "span.title, h3"
                )

                # Company name in the listing
                company_elem = item.select_one(
                    ".new-listing__company-name, "
                    ".new-listing__header__company, "
                    "span.company, .company"
                )

                # Location
                location_elem = item.select_one(
                    ".new-listing__header__location, "
                    "span.region, .region, .location"
                )

                title = title_elem.get_text(strip=True) if title_elem else ""
                company = company_elem.get_text(strip=True) if company_elem else "Unknown"
                location = location_elem.get_text(strip=True) if location_elem else "Remote Worldwide"

                # Fallback: extract from link text
                if not title:
                    link_text = title_link.get_text(strip=True)
                    # Often format is "Title1dCompanyLocation"
                    title = link_text.split("1d")[0] if "1d" in link_text else link_text[:60]

                if not title or len(title) < 3:
                    continue

                job_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

                # WWR jobs are all remote
                is_worldwide = any(x in location.lower() for x in ["worldwide", "anywhere", "global", "remote"])

                # Assume visa sponsored if worldwide/remote
                visa_sponsored = is_worldwide or detect_visa_sponsorship(
                    f"{title} {location}", company, VISA.known_sponsors
                )

                work_type = WorkType.REMOTE_VISA_SPONSORED if visa_sponsored else WorkType.REMOTE_NO_VISA

                jobs.append(Job(
                    company=company if company != "Unknown" else title.split(" at ")[-1] if " at " in title else "Remote Company",
                    role=title,
                    location=location,
                    work_type=work_type,
                    visa_sponsored=visa_sponsored,
                    pay_range="Not Listed",
                    source="WeWorkRemotely",
                    job_url=job_url,
                    country=Country.US,
                    status=JobStatus.FOUND,
                ))

            except Exception as e:
                self.logger.debug(f"Error parsing WWR job: {e}")
                continue

        return jobs

    def parse_job(self, data: Any) -> Optional[Job]:
        return None


class RemoteOKScraper(BaseScraper):
    """
    Scraper for RemoteOK - remote tech jobs.

    Has a JSON API available.
    """

    API_URL = "https://remoteok.com/api"
    BASE_URL = "https://remoteok.com"

    def __init__(self, country: Country = Country.US):
        super().__init__("RemoteOK", country)

    def scrape(self, search_terms: List[str] = None, max_jobs: int = 100) -> ScraperResult:
        """Scrape from RemoteOK API."""
        import requests
        result = ScraperResult(source=self.name)

        self.logger.info("Fetching RemoteOK jobs...")

        # RemoteOK API works better with plain requests (cloudscraper causes encoding issues)
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            }
            response = requests.get(self.API_URL, headers=headers, timeout=30)
            response.raise_for_status()
        except Exception as e:
            self.logger.error(f"Failed to fetch RemoteOK: {e}")
            result.errors.append(str(e))
            return result

        try:
            # RemoteOK returns array, first item is metadata
            data = response.json()
            job_listings = data[1:] if isinstance(data, list) else []

            for job_data in job_listings[:max_jobs]:
                job = self._parse_job_data(job_data)
                if job:
                    result.jobs.append(job)

            result.total_found = len(job_listings)

        except (json.JSONDecodeError, IndexError) as e:
            self.logger.error(f"Error parsing RemoteOK API: {e}")
            result.errors.append(str(e))

        self.logger.info(f"Found {len(result.jobs)} jobs from RemoteOK")
        return result

    def _parse_job_data(self, data: Dict) -> Optional[Job]:
        """Parse RemoteOK job data."""
        try:
            title = data.get("position", "")
            company = data.get("company", "Unknown")
            location = data.get("location", "Remote Worldwide")

            if not title:
                return None

            # Filter for tech jobs - be very inclusive to not miss opportunities
            tags = [t.lower() for t in data.get("tags", [])]
            title_lower = title.lower()
            tech_keywords = [
                "engineer", "developer", "software", "backend", "frontend", "fullstack",
                "devops", "sre", "data", "ml", "ai", "python", "java", "node", "golang",
                "react", "typescript", "cloud", "infrastructure", "platform", "senior",
                "lead", "architect", "manager", "analyst", "scientist", "tech", "it",
                "system", "network", "security", "mobile", "web", "api", "database",
                "design", "product", "qa", "test", "automation"
            ]

            is_tech = any(kw in title_lower for kw in tech_keywords)
            has_tech_tags = any(kw in tag for tag in tags for kw in tech_keywords)

            # Be inclusive - if unsure, include it
            if not is_tech and not has_tech_tags and len(tags) > 0:
                # Skip only obvious non-tech roles
                non_tech = ["sales", "marketing", "hr", "recruiter", "legal", "finance", "accounting"]
                if any(nt in title_lower for nt in non_tech):
                    return None

            job_url = data.get("url", "") or f"{self.BASE_URL}/remote-jobs/{data.get('slug', '')}"
            salary_min = data.get("salary_min", 0)
            salary_max = data.get("salary_max", 0)

            pay_range = "Not Listed"
            if salary_min and salary_max:
                pay_range = f"${salary_min:,} - ${salary_max:,}"
            elif salary_min:
                pay_range = f"${salary_min:,}+"

            # Check visa sponsorship
            is_worldwide = "worldwide" in location.lower() or "anywhere" in location.lower()
            visa_sponsored = is_worldwide or company.lower() in [c.lower() for c in VISA.known_sponsors]

            work_type = WorkType.REMOTE_VISA_SPONSORED if visa_sponsored else WorkType.REMOTE_NO_VISA

            return Job(
                company=company,
                role=title,
                location=location,
                work_type=work_type,
                visa_sponsored=visa_sponsored,
                pay_range=pay_range,
                source="RemoteOK",
                job_url=job_url,
                country=Country.US,
                description=", ".join(tags),
                status=JobStatus.FOUND,
            )

        except Exception as e:
            self.logger.debug(f"Error parsing RemoteOK job: {e}")
            return None

    def parse_job(self, data: Any) -> Optional[Job]:
        if isinstance(data, dict):
            return self._parse_job_data(data)
        return None


class WellfoundScraper(BaseScraper):
    """
    Scraper for Wellfound (formerly AngelList Talent).

    Focuses on startup jobs, many of which sponsor visas.
    """

    BASE_URL = "https://wellfound.com"
    SEARCH_URL = "https://wellfound.com/role/l/software-engineer"

    def __init__(self, country: Country = Country.US):
        super().__init__("Wellfound", country)

    def scrape(self, search_terms: List[str] = None, max_jobs: int = 100) -> ScraperResult:
        """Scrape startup jobs from Wellfound."""
        result = ScraperResult(source=self.name)

        # Wellfound requires JavaScript, use browser if available
        search_urls = [
            "/role/l/software-engineer/remote",
            "/role/l/backend-engineer/remote",
            "/role/l/fullstack-engineer/remote",
        ]

        for search_path in search_urls:
            if len(result.jobs) >= max_jobs:
                break

            url = f"{self.BASE_URL}{search_path}"
            self.logger.info(f"Scraping Wellfound: {search_path}")

            response = self._get(url)
            if not response:
                continue

            jobs = self._parse_listing_page(response.text)

            for job in jobs:
                result.jobs.append(job)

            result.total_found += len(jobs)
            self._delay(3, 5)  # Be gentle

        self.logger.info(f"Found {len(result.jobs)} jobs from Wellfound")
        return result

    def _parse_listing_page(self, html: str) -> List[Job]:
        """Parse Wellfound job listings."""
        jobs = []
        soup = self._parse_html(html)

        # Wellfound uses React, data might be in script tags
        job_cards = soup.select("div[class*='job'], article, [data-test='job-card']")

        for card in job_cards:
            try:
                title_elem = card.select_one("h2, h3, [class*='title']")
                company_elem = card.select_one("[class*='company'], .startup-link")
                location_elem = card.select_one("[class*='location']")

                title = title_elem.get_text(strip=True) if title_elem else ""
                company = company_elem.get_text(strip=True) if company_elem else "Startup"
                location = location_elem.get_text(strip=True) if location_elem else "Remote"

                if not title or not any(kw in title.lower() for kw in ["engineer", "developer"]):
                    continue

                link = card.select_one("a[href*='/jobs/']")
                job_url = link.get("href", "") if link else ""
                if job_url and not job_url.startswith("http"):
                    job_url = f"{self.BASE_URL}{job_url}"

                # Startups often sponsor
                visa_sponsored = True  # Assume yes for startups
                work_type = WorkType.REMOTE_VISA_SPONSORED

                jobs.append(Job(
                    company=company,
                    role=title,
                    location=location,
                    work_type=work_type,
                    visa_sponsored=visa_sponsored,
                    pay_range="Not Listed",
                    source="Wellfound",
                    job_url=job_url,
                    country=Country.US,
                    status=JobStatus.FOUND,
                ))

            except Exception:
                continue

        return jobs

    def parse_job(self, data: Any) -> Optional[Job]:
        return None


class BuiltInScraper(BaseScraper):
    """
    Scraper for BuiltIn - tech jobs in major US cities.

    Has sections for different cities: Austin, Boston, Chicago, Colorado, etc.
    """

    BASE_URL = "https://builtin.com"
    CITY_URLS = {
        "remote": "/jobs/remote",
        "nyc": "/jobs/new-york",
        "sf": "/jobs/san-francisco",
        "la": "/jobs/los-angeles",
        "seattle": "/jobs/seattle",
        "austin": "/jobs/austin",
        "boston": "/jobs/boston",
        "chicago": "/jobs/chicago",
    }

    def __init__(self, country: Country = Country.US, cities: List[str] = None):
        super().__init__("BuiltIn", country)
        self.cities = cities or ["remote", "sf", "nyc", "seattle"]

    def scrape(self, search_terms: List[str] = None, max_jobs: int = 100) -> ScraperResult:
        """Scrape tech jobs from BuiltIn."""
        result = ScraperResult(source=self.name)

        for city in self.cities:
            if len(result.jobs) >= max_jobs:
                break

            if city not in self.CITY_URLS:
                continue

            url = f"{self.BASE_URL}{self.CITY_URLS[city]}/dev-engineering"
            self.logger.info(f"Scraping BuiltIn: {city}")

            response = self._get(url)
            if not response:
                continue

            jobs = self._parse_listing_page(response.text, city)

            for job in jobs:
                result.jobs.append(job)

            result.total_found += len(jobs)
            self._delay(2, 4)

        self.logger.info(f"Found {len(result.jobs)} jobs from BuiltIn")
        return result

    def _parse_listing_page(self, html: str, city: str) -> List[Job]:
        """Parse BuiltIn job listings."""
        jobs = []
        soup = self._parse_html(html)

        job_cards = soup.select("div[class*='job-card'], article[class*='job']")

        for card in job_cards:
            try:
                title_elem = card.select_one("h2, h3, [class*='title']")
                company_elem = card.select_one("[class*='company']")
                location_elem = card.select_one("[class*='location']")

                title = title_elem.get_text(strip=True) if title_elem else ""
                company = company_elem.get_text(strip=True) if company_elem else "Unknown"
                location = location_elem.get_text(strip=True) if location_elem else city.title()

                if not title:
                    continue

                link = card.select_one("a[href*='/job/']")
                job_url = link.get("href", "") if link else ""
                if job_url and not job_url.startswith("http"):
                    job_url = f"{self.BASE_URL}{job_url}"

                is_remote = city == "remote" or "remote" in location.lower()
                visa_sponsored = detect_visa_sponsorship(f"{title} {location}", company, VISA.known_sponsors)

                if is_remote:
                    work_type = WorkType.REMOTE_VISA_SPONSORED if visa_sponsored else WorkType.REMOTE_NO_VISA
                else:
                    work_type = WorkType.ONSITE_VISA_SPONSORED if visa_sponsored else WorkType.ONSITE_NO_VISA

                jobs.append(Job(
                    company=company,
                    role=title,
                    location=location,
                    work_type=work_type,
                    visa_sponsored=visa_sponsored,
                    pay_range="Not Listed",
                    source="BuiltIn",
                    job_url=job_url,
                    country=Country.US,
                    status=JobStatus.FOUND,
                ))

            except Exception:
                continue

        return jobs

    def parse_job(self, data: Any) -> Optional[Job]:
        return None


class HackerNewsScraper(BaseScraper):
    """
    Scraper for HackerNews Jobs (Y Combinator startups).

    Uses the free Firebase API - NO CAPTCHA!
    Great source for startup jobs that often sponsor visas.
    """

    API_URL = "https://hacker-news.firebaseio.com/v0"

    def __init__(self, country: Country = Country.US):
        super().__init__("HackerNews", country)

    def scrape(self, search_terms: List[str] = None, max_jobs: int = 100) -> ScraperResult:
        """Scrape jobs from HackerNews (Y Combinator startups)."""
        import requests
        result = ScraperResult(source=self.name)

        self.logger.info("Fetching HackerNews jobs...")

        try:
            # Get job story IDs
            response = requests.get(f"{self.API_URL}/jobstories.json", timeout=30)
            response.raise_for_status()
            job_ids = response.json()

            # Fetch each job (limit to avoid too many requests)
            for job_id in job_ids[:max_jobs]:
                try:
                    job_response = requests.get(f"{self.API_URL}/item/{job_id}.json", timeout=10)
                    job_data = job_response.json()

                    if not job_data:
                        continue

                    job = self._parse_job_data(job_data)
                    if job:
                        result.jobs.append(job)

                except Exception as e:
                    self.logger.debug(f"Error fetching job {job_id}: {e}")
                    continue

            result.total_found = len(job_ids)

        except Exception as e:
            self.logger.error(f"Error fetching HackerNews jobs: {e}")
            result.errors.append(str(e))

        self.logger.info(f"Found {len(result.jobs)} jobs from HackerNews")
        return result

    def _parse_job_data(self, data: Dict) -> Optional[Job]:
        """Parse HackerNews job data."""
        try:
            title = data.get("title", "")
            text = data.get("text", "")
            url = data.get("url", "")

            if not title:
                return None

            # HN job titles often format: "Company (Location) is hiring Role"
            company = "YC Startup"
            role = title
            location = "Remote"

            # Try to extract company from title
            if " is hiring" in title.lower():
                parts = title.lower().split(" is hiring")
                company_part = parts[0].strip()
                role_part = parts[1].strip() if len(parts) > 1 else title

                # Check for location in parentheses
                if "(" in company_part and ")" in company_part:
                    loc_start = company_part.find("(")
                    loc_end = company_part.find(")")
                    location = company_part[loc_start+1:loc_end].title()
                    company = company_part[:loc_start].strip().title()
                else:
                    company = company_part.title()

                role = role_part.title() if role_part else "Software Engineer"
            elif "(YC" in title:
                # Format: "Company (YC W24) - Role"
                parts = title.split(" - ", 1)
                if len(parts) == 2:
                    company = parts[0].split("(")[0].strip()
                    role = parts[1].strip()

            # Job URL
            job_url = url if url else f"https://news.ycombinator.com/item?id={data.get('id', '')}"

            # YC companies often sponsor visas
            is_remote = any(x in location.lower() for x in ["remote", "anywhere", "worldwide"])
            visa_sponsored = True  # YC companies typically sponsor

            work_type = WorkType.REMOTE_VISA_SPONSORED if is_remote else WorkType.ONSITE_VISA_SPONSORED

            return Job(
                company=company,
                role=role,
                location=location,
                work_type=work_type,
                visa_sponsored=visa_sponsored,
                pay_range="Not Listed",
                source="HackerNews",
                job_url=job_url,
                country=Country.US,
                description=text[:500] if text else "",
                status=JobStatus.FOUND,
            )

        except Exception as e:
            self.logger.debug(f"Error parsing HN job: {e}")
            return None

    def parse_job(self, data: Any) -> Optional[Job]:
        if isinstance(data, dict):
            return self._parse_job_data(data)
        return None
