"""
Nigeria Recruiters Scraper
==========================
Scraper for Nigerian recruiting companies and foreign companies hiring in Nigeria:
- RocketDevs
- Crossing Hurdles
- Andela
- Decagon
- AltSchool Africa
- Gebeya
- Talent QL
- Tech Talent Africa
- Jobberman
- MyJobMag
- LinkedIn "Remote Nigeria" jobs from foreign companies
"""

import re
from typing import List, Optional, Any, Dict
from urllib.parse import urljoin, quote

from .base import BaseScraper, ScraperResult
from autoapply.core.job_schema import (
    Job, Country, WorkType, JobStatus,
    extract_salary
)


class NigeriaRecruitersScraper(BaseScraper):
    """
    Scraper for Nigeria-based recruiting companies and remote Nigeria jobs.

    Sources:
    - RocketDevs: Tech talent from Africa for global companies
    - Crossing Hurdles: Recruitment firm for Nigerian tech talent
    - Andela: Africa's largest tech talent company
    - Decagon: Nigerian software engineering talent
    - AltSchool Africa: Tech education and placement
    - Gebeya: Pan-African tech talent marketplace
    - TalentQL (now AltSchool): Nigerian dev talent pipeline
    - Jobberman: Nigeria's largest job board
    - MyJobMag: African job board
    - LinkedIn: Foreign companies posting "Remote Nigeria"
    """

    SOURCES = {
        "RocketDevs": {
            "url": "https://www.rocketdevs.com/careers",
            "type": "careers_page",
        },
        "Crossing Hurdles": {
            "url": "https://app.careerpuck.com/job-board/crossing-hurdles",
            "type": "job_board",
        },
        "Andela": {
            "url": "https://andela.com/careers",
            "jobs_url": "https://boards.greenhouse.io/andela",
            "type": "greenhouse",
        },
        "Decagon": {
            "url": "https://decagon.institute/careers",
            "type": "careers_page",
        },
        "AltSchool Africa": {
            "url": "https://www.altschoolafrica.com/careers",
            "type": "careers_page",
        },
        "Gebeya": {
            "url": "https://gebeya.com/jobs",
            "type": "job_board",
        },
        "Paystack": {
            "url": "https://paystack.com/careers",
            "jobs_url": "https://boards.greenhouse.io/paystack",
            "type": "greenhouse",
        },
        "Flutterwave": {
            "url": "https://flutterwave.com/careers",
            "jobs_url": "https://boards.greenhouse.io/flutterwave",
            "type": "greenhouse",
        },
        "Kuda Bank": {
            "url": "https://kuda.com/careers",
            "type": "careers_page",
        },
        "Moniepoint": {
            "url": "https://moniepoint.com/careers",
            "type": "careers_page",
        },
        "Piggyvest": {
            "url": "https://www.piggyvest.com/careers",
            "type": "careers_page",
        },
        "Jobberman": {
            "url": "https://www.jobberman.com/jobs",
            "type": "job_board",
            "search_url": "https://www.jobberman.com/jobs?q={query}",
        },
        "MyJobMag": {
            "url": "https://www.myjobmag.com/jobs-in-nigeria",
            "type": "job_board",
            "search_url": "https://www.myjobmag.com/search/jobs?q={query}",
        },
        "HotNigerianJobs": {
            "url": "https://www.hotnigerianjobs.com",
            "type": "hotnigerianjobs",
            "search_url": "https://www.hotnigerianjobs.com/search?q={query}",
            "description": "Popular Nigerian job board",
        },
        # Foreign companies actively hiring from Nigeria
        "Turing": {
            "url": "https://www.turing.com/jobs",
            "type": "turing",
            "description": "US company hiring remote devs globally",
        },
        "Crossover": {
            "url": "https://www.crossover.com/jobs",
            "type": "crossover",
            "description": "Remote-first company hiring globally",
        },
        "Tunga": {
            "url": "https://tunga.io/careers",
            "type": "careers_page",
            "description": "Dutch company hiring African developers",
        },
        "Tether": {
            "url": "https://tether.to/careers",
            "jobs_url": "https://jobs.lever.co/tether",
            "type": "lever",
            "description": "Crypto company with remote positions",
        },
        "Toptal": {
            "url": "https://www.toptal.com/careers",
            "type": "careers_page",
            "description": "Top 3% freelance talent network",
        },
        "Deel": {
            "url": "https://www.deel.com/careers",
            "jobs_url": "https://jobs.ashbyhq.com/Deel",
            "type": "ashby",
            "description": "Global HR platform, remote-first",
        },
        "Remote.com Jobs": {
            "url": "https://remote.com/jobs/all",
            "type": "remotecom",
            "description": "Remote.com job board - all remote jobs",
        },
        "GitLab": {
            "url": "https://about.gitlab.com/jobs/all-jobs/",
            "type": "careers_page",
            "description": "Fully remote company",
        },
        "Automattic": {
            "url": "https://automattic.com/work-with-us/",
            "type": "careers_page",
            "description": "WordPress.com - fully distributed",
        },
        "Zapier": {
            "url": "https://zapier.com/jobs",
            "type": "careers_page",
            "description": "Remote-first automation company",
        },
        "Canonical": {
            "url": "https://canonical.com/careers",
            "jobs_url": "https://boards.greenhouse.io/canonical",
            "type": "greenhouse",
            "description": "Ubuntu - remote positions available",
        },
        "Sourcegraph": {
            "url": "https://about.sourcegraph.com/jobs",
            "type": "careers_page",
            "description": "Remote-first code intelligence",
        },
        "LinkedIn Nigeria Remote": {
            "type": "linkedin",
            "geo_id": "105365761",  # Nigeria
        },
        "Twitter/X Jobs": {
            "type": "twitter",
            "description": "Job posts on Twitter/X",
        },
        # Additional job boards
        "RemoteAfrica": {
            "url": "https://remoteafrica.io/jobs",
            "type": "remoteafrica",
            "description": "Remote jobs for African talent",
        },
        "Wellfound": {
            "url": "https://wellfound.com/jobs",
            "type": "wellfound",
            "description": "Startup jobs (formerly AngelList)",
        },
        "Greenhouse Jobs": {
            "url": "https://boards.greenhouse.io",
            "type": "greenhouse_search",
            "description": "Greenhouse job board aggregator",
        },
        "Ashby Jobs": {
            "url": "https://jobs.ashbyhq.com",
            "type": "ashby_search",
            "description": "Ashby job board aggregator",
        },
        # More remote-first companies
        "Buffer": {
            "url": "https://buffer.com/journey",
            "type": "careers_page",
            "description": "Fully remote social media company",
        },
        "Doist": {
            "url": "https://doist.com/careers",
            "type": "careers_page",
            "description": "Remote-first (Todoist, Twist)",
        },
        "Hotjar": {
            "url": "https://www.hotjar.com/careers",
            "type": "careers_page",
            "description": "Remote-first analytics company",
        },
        "InVision": {
            "url": "https://www.invisionapp.com/company/careers",
            "type": "careers_page",
            "description": "Fully remote design platform",
        },
        "Toggl": {
            "url": "https://toggl.com/jobs",
            "type": "careers_page",
            "description": "Remote-first time tracking",
        },
        "Help Scout": {
            "url": "https://www.helpscout.com/company/careers",
            "type": "careers_page",
            "description": "Remote-first customer service",
        },
        "Close": {
            "url": "https://jobs.lever.co/close.io",
            "type": "lever",
            "description": "Remote-first CRM company",
        },
        "Customer.io": {
            "url": "https://jobs.lever.co/customer.io",
            "type": "lever",
            "description": "Remote-first messaging platform",
        },
    }

    def __init__(self):
        super().__init__("Nigeria Recruiters", Country.NIGERIA)

    def scrape(self, search_terms: List[str] = None, max_jobs: int = 100) -> ScraperResult:
        """
        Scrape jobs from all Nigeria sources.

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

        # Scrape each source
        for source_name, source_config in self.SOURCES.items():
            if len(result.jobs) >= max_jobs:
                break

            self.logger.info(f"Scraping {source_name}...")

            try:
                source_type = source_config.get("type", "")

                if source_name == "RocketDevs":
                    jobs = self._scrape_rocketdevs(search_terms, max_jobs - len(result.jobs))
                elif source_name == "Crossing Hurdles":
                    jobs = self._scrape_crossing_hurdles(search_terms, max_jobs - len(result.jobs))
                elif source_name == "Jobberman":
                    jobs = self._scrape_jobberman(search_terms, max_jobs - len(result.jobs))
                elif source_name == "MyJobMag":
                    jobs = self._scrape_myjobmag(search_terms, max_jobs - len(result.jobs))
                elif source_name == "HotNigerianJobs":
                    jobs = self._scrape_hotnigerianjobs(search_terms, max_jobs - len(result.jobs))
                elif source_name == "LinkedIn Nigeria Remote":
                    jobs = self._scrape_linkedin_nigeria(search_terms, max_jobs - len(result.jobs))
                elif source_name == "Twitter/X Jobs":
                    jobs = self._scrape_twitter_jobs(search_terms, max_jobs - len(result.jobs))
                elif source_name == "RemoteAfrica":
                    jobs = self._scrape_remoteafrica(search_terms, max_jobs - len(result.jobs))
                elif source_name == "Wellfound":
                    jobs = self._scrape_wellfound(search_terms, max_jobs - len(result.jobs))
                elif source_name == "Greenhouse Jobs":
                    jobs = self._scrape_greenhouse_search(search_terms, max_jobs - len(result.jobs))
                elif source_name == "Ashby Jobs":
                    jobs = self._scrape_ashby_search(search_terms, max_jobs - len(result.jobs))
                elif source_name == "Remote.com Jobs":
                    jobs = self._scrape_remotecom_jobs(search_terms, max_jobs - len(result.jobs))
                elif source_type == "turing":
                    jobs = self._scrape_turing(search_terms, max_jobs - len(result.jobs))
                elif source_type == "crossover":
                    jobs = self._scrape_crossover(search_terms, max_jobs - len(result.jobs))
                elif source_type == "lever":
                    jobs = self._scrape_lever(source_name, source_config, search_terms, max_jobs - len(result.jobs))
                elif source_type == "ashby":
                    jobs = self._scrape_ashby(source_name, source_config, search_terms, max_jobs - len(result.jobs))
                elif source_type == "greenhouse":
                    jobs = self._scrape_greenhouse(source_name, source_config, search_terms, max_jobs - len(result.jobs))
                elif source_type == "careers_page":
                    jobs = self._scrape_generic_careers(source_name, source_config, search_terms, max_jobs - len(result.jobs))
                else:
                    jobs = []

                for job in jobs:
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        result.jobs.append(job)

                result.total_found += len(jobs)

            except Exception as e:
                self.logger.error(f"Error scraping {source_name}: {e}")
                result.errors.append(f"{source_name} error: {str(e)}")

            self._delay(2, 4)

        self.logger.info(f"Found {len(result.jobs)} jobs from Nigeria recruiters")
        return result

    def _scrape_rocketdevs(self, search_terms: List[str], max_jobs: int) -> List[Job]:
        """Scrape RocketDevs careers page."""
        jobs = []
        url = self.SOURCES["RocketDevs"]["url"]

        response = self._get(url)
        if not response:
            return jobs

        soup = self._parse_html(response.text)

        # RocketDevs typically lists jobs in a structured format
        # Adjust selectors based on actual page structure
        job_cards = soup.select("div.job-card, div.position, article.job, div[class*='job']")

        for card in job_cards:
            if len(jobs) >= max_jobs:
                break

            job = self._parse_rocketdevs_card(card, url)
            if job and self._matches_search(job, search_terms):
                jobs.append(job)

        # If no structured jobs found, look for general listings
        if not jobs:
            # Try alternative selectors
            links = soup.select("a[href*='job'], a[href*='career'], a[href*='position']")
            for link in links[:max_jobs]:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if title and any(term.lower() in title.lower() for term in search_terms):
                    job = Job(
                        company="RocketDevs",
                        role=title,
                        location="Remote Nigeria",
                        work_type=WorkType.REMOTE_NO_VISA,
                        visa_sponsored=False,
                        pay_range="Not Listed",
                        source="RocketDevs",
                        job_url=urljoin(url, href),
                        country=Country.NIGERIA,
                        status=JobStatus.FOUND,
                    )
                    jobs.append(job)

        return jobs

    def _parse_rocketdevs_card(self, card, base_url: str) -> Optional[Job]:
        """Parse a RocketDevs job card."""
        try:
            # Title
            title_elem = card.select_one("h2, h3, h4, .title, .job-title")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Link
            link_elem = card.select_one("a")
            job_url = urljoin(base_url, link_elem.get("href", "")) if link_elem else ""

            # Location (usually remote for RocketDevs)
            location_elem = card.select_one(".location, .job-location")
            location = location_elem.get_text(strip=True) if location_elem else "Remote Nigeria"

            if not title:
                return None

            return Job(
                company="RocketDevs",
                role=title,
                location=location,
                work_type=WorkType.REMOTE_NO_VISA,
                visa_sponsored=False,
                pay_range="Not Listed",
                source="RocketDevs",
                job_url=job_url,
                country=Country.NIGERIA,
                status=JobStatus.FOUND,
            )

        except Exception as e:
            self.logger.debug(f"Error parsing RocketDevs card: {e}")
            return None

    def _scrape_crossing_hurdles(self, search_terms: List[str], max_jobs: int) -> List[Job]:
        """Scrape Crossing Hurdles job board (CareerPuck platform)."""
        jobs = []
        url = self.SOURCES["Crossing Hurdles"]["url"]

        response = self._get(url)
        if not response:
            return jobs

        soup = self._parse_html(response.text)

        # CareerPuck job board structure
        job_cards = soup.select("div.job-card, div.job-listing, article, li.job")

        for card in job_cards:
            if len(jobs) >= max_jobs:
                break

            job = self._parse_crossing_hurdles_card(card, url)
            if job and self._matches_search(job, search_terms):
                jobs.append(job)

        return jobs

    def _parse_crossing_hurdles_card(self, card, base_url: str) -> Optional[Job]:
        """Parse a Crossing Hurdles job card."""
        try:
            # Title
            title_elem = card.select_one("h2, h3, .job-title, .title a")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Company (might be the client company)
            company_elem = card.select_one(".company, .client, .employer")
            company = company_elem.get_text(strip=True) if company_elem else "Crossing Hurdles Client"

            # Link
            link_elem = card.select_one("a[href*='job'], a.job-link")
            if not link_elem:
                link_elem = card.select_one("a")
            job_url = urljoin(base_url, link_elem.get("href", "")) if link_elem else ""

            # Location
            location_elem = card.select_one(".location, .job-location")
            location = location_elem.get_text(strip=True) if location_elem else "Remote Nigeria"

            # Salary
            salary_elem = card.select_one(".salary, .compensation")
            salary = salary_elem.get_text(strip=True) if salary_elem else "Not Listed"

            if not title:
                return None

            return Job(
                company=company,
                role=title,
                location=location,
                work_type=WorkType.REMOTE_NO_VISA,
                visa_sponsored=False,
                pay_range=salary,
                source="Crossing Hurdles",
                job_url=job_url,
                country=Country.NIGERIA,
                status=JobStatus.FOUND,
            )

        except Exception as e:
            self.logger.debug(f"Error parsing Crossing Hurdles card: {e}")
            return None

    def _scrape_jobberman(self, search_terms: List[str], max_jobs: int) -> List[Job]:
        """Scrape Jobberman job board."""
        jobs = []

        for search_term in search_terms:
            if len(jobs) >= max_jobs:
                break

            url = f"https://www.jobberman.com/jobs?q={search_term.replace(' ', '+')}"

            response = self._get(url)
            if not response:
                continue

            soup = self._parse_html(response.text)

            # Jobberman job cards
            job_cards = soup.select("article.job-card, div.job-listing, div.listing-card")

            for card in job_cards:
                if len(jobs) >= max_jobs:
                    break

                job = self._parse_jobberman_card(card, url)
                if job:
                    jobs.append(job)

            self._delay(1, 2)

        return jobs

    def _parse_jobberman_card(self, card, base_url: str) -> Optional[Job]:
        """Parse a Jobberman job card."""
        try:
            # Title
            title_elem = card.select_one("h2 a, h3 a, .job-title a, p.text-lg a")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Company
            company_elem = card.select_one(".company-name, .employer, p.text-sm")
            company = company_elem.get_text(strip=True) if company_elem else ""

            # Link
            link_elem = card.select_one("a[href*='/jobs/']")
            if not link_elem:
                link_elem = title_elem
            job_url = ""
            if link_elem:
                href = link_elem.get("href", "")
                job_url = href if href.startswith("http") else urljoin("https://www.jobberman.com", href)

            # Location
            location_elem = card.select_one(".location, span.text-gray-500")
            location = location_elem.get_text(strip=True) if location_elem else "Nigeria"

            # Type (remote/onsite)
            type_elem = card.select_one(".job-type, .work-type")
            job_type = type_elem.get_text(strip=True).lower() if type_elem else ""

            is_remote = "remote" in location.lower() or "remote" in job_type

            if not title:
                return None

            return Job(
                company=company or "Unknown Company",
                role=title,
                location=location,
                work_type=WorkType.REMOTE_NO_VISA if is_remote else WorkType.ONSITE_NO_VISA,
                visa_sponsored=False,
                pay_range="Not Listed",
                source="Jobberman",
                job_url=job_url,
                country=Country.NIGERIA,
                status=JobStatus.FOUND,
            )

        except Exception as e:
            self.logger.debug(f"Error parsing Jobberman card: {e}")
            return None

    def _matches_search(self, job: Job, search_terms: List[str]) -> bool:
        """Check if job matches any search term."""
        job_text = f"{job.role} {job.description}".lower()
        return any(term.lower() in job_text for term in search_terms)

    def _scrape_linkedin_nigeria(self, search_terms: List[str], max_jobs: int) -> List[Job]:
        """
        Scrape LinkedIn for foreign companies posting jobs in Nigeria, EMEA, or Africa.
        These are typically remote positions from international companies.
        """
        jobs = []

        # Search multiple locations: Nigeria, EMEA, Africa
        location_searches = [
            {"location": "Nigeria", "geo_id": "105365761"},
            {"location": "EMEA", "geo_id": None},  # No specific geo_id, use keyword
            {"location": "Africa", "geo_id": "103537801"},
            {"location": "Remote", "geo_id": None},  # Global remote
        ]

        for search_term in search_terms:
            if len(jobs) >= max_jobs:
                break

            for loc_config in location_searches:
                if len(jobs) >= max_jobs:
                    break

                # LinkedIn guest API
                url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

                # Build keywords to include location context
                keywords = search_term
                if loc_config["location"] == "EMEA":
                    keywords = f"{search_term} EMEA"
                elif loc_config["location"] == "Remote":
                    keywords = f"{search_term} remote Nigeria OR remote Africa OR remote EMEA"

                params = {
                    "keywords": keywords,
                    "f_WT": "2",  # Remote filter
                    "start": 0,
                }

                if loc_config["geo_id"]:
                    params["geoId"] = loc_config["geo_id"]
                    params["location"] = loc_config["location"]

                response = self._get(url, params=params)
                if not response:
                    continue

                soup = self._parse_html(response.text)
                job_cards = soup.select("li, div.base-card")

                for card in job_cards:
                    if len(jobs) >= max_jobs:
                        break

                    job = self._parse_linkedin_card(card)
                    if job and self._matches_search(job, search_terms):
                        # Check if location is relevant (Nigeria, EMEA, Africa, Remote)
                        loc_lower = job.location.lower()
                        if any(kw in loc_lower for kw in ["nigeria", "emea", "africa", "remote", "anywhere"]):
                            job.source = f"LinkedIn ({loc_config['location']})"
                            jobs.append(job)

                self._delay(2, 3)

        return jobs

    def _parse_linkedin_card(self, card) -> Optional[Job]:
        """Parse a LinkedIn job card."""
        try:
            title_elem = card.select_one("h3.base-search-card__title, h3.job-card-list__title")
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            company_elem = card.select_one("h4.base-search-card__subtitle a, a.job-card-container__company-name")
            company = company_elem.get_text(strip=True) if company_elem else ""

            location_elem = card.select_one("span.job-search-card__location")
            location = location_elem.get_text(strip=True) if location_elem else "Nigeria Remote"

            link_elem = card.select_one("a.base-card__full-link, a.job-card-list__title")
            job_url = link_elem.get("href", "") if link_elem else ""

            if not title or not company:
                return None

            return Job(
                company=company,
                role=title,
                location=location,
                work_type=WorkType.REMOTE_NO_VISA,
                visa_sponsored=False,
                pay_range="Not Listed",
                source="LinkedIn Nigeria",
                job_url=job_url,
                country=Country.NIGERIA,
                status=JobStatus.FOUND,
            )
        except Exception as e:
            self.logger.debug(f"Error parsing LinkedIn card: {e}")
            return None

    def _scrape_myjobmag(self, search_terms: List[str], max_jobs: int) -> List[Job]:
        """Scrape MyJobMag job board."""
        jobs = []

        for search_term in search_terms:
            if len(jobs) >= max_jobs:
                break

            url = f"https://www.myjobmag.com/search/jobs?q={quote(search_term)}"
            response = self._get(url)
            if not response:
                continue

            soup = self._parse_html(response.text)
            job_cards = soup.select("div.job-list-item, article.job-card, li.job-item")

            for card in job_cards:
                if len(jobs) >= max_jobs:
                    break

                title_elem = card.select_one("h2 a, h3 a, .job-title a")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                href = title_elem.get("href", "")
                job_url = href if href.startswith("http") else urljoin("https://www.myjobmag.com", href)

                company_elem = card.select_one(".company-name, .employer")
                company = company_elem.get_text(strip=True) if company_elem else "Unknown"

                location_elem = card.select_one(".job-location, .location")
                location = location_elem.get_text(strip=True) if location_elem else "Nigeria"

                if title and self._matches_search(Job(company=company, role=title, location=location), search_terms):
                    jobs.append(Job(
                        company=company,
                        role=title,
                        location=location,
                        work_type=WorkType.REMOTE_NO_VISA if "remote" in location.lower() else WorkType.ONSITE_NO_VISA,
                        visa_sponsored=False,
                        pay_range="Not Listed",
                        source="MyJobMag",
                        job_url=job_url,
                        country=Country.NIGERIA,
                        status=JobStatus.FOUND,
                    ))

            self._delay(1, 2)

        return jobs

    def _scrape_hotnigerianjobs(self, search_terms: List[str], max_jobs: int) -> List[Job]:
        """
        Scrape HotNigerianJobs for software/tech jobs.

        Searches for: software engineer, backend engineer, fullstack developer
        """
        jobs = []
        base_url = "https://www.hotnigerianjobs.com"

        # Search terms specific to tech roles
        tech_searches = []
        for term in search_terms:
            tech_searches.append(term)
            # Add variations for common tech roles
            term_lower = term.lower()
            if "software" in term_lower:
                tech_searches.extend(["backend engineer", "fullstack developer", "full stack developer"])
            elif "backend" in term_lower:
                tech_searches.extend(["software engineer", "python developer", "java developer", "node developer"])
            elif "fullstack" in term_lower or "full stack" in term_lower:
                tech_searches.extend(["software engineer", "web developer"])

        # Deduplicate
        tech_searches = list(dict.fromkeys(tech_searches))[:6]

        for search_term in tech_searches:
            if len(jobs) >= max_jobs:
                break

            # HotNigerianJobs search URL
            search_url = f"{base_url}/search?q={quote(search_term)}"

            response = self._get(search_url)
            if not response:
                # Try alternate URL format
                search_url = f"{base_url}/jobs?q={quote(search_term)}"
                response = self._get(search_url)
                if not response:
                    continue

            soup = self._parse_html(response.text)

            # HotNigerianJobs job card selectors
            job_cards = soup.select(
                "div.job-listing, "
                "div.job-item, "
                "article.job, "
                "div[class*='job-card'], "
                "li.job-result, "
                "div.listing-item, "
                "tr.job-row"
            )

            for card in job_cards:
                if len(jobs) >= max_jobs:
                    break

                # Extract title
                title_elem = card.select_one(
                    "h2 a, h3 a, h4 a, "
                    ".job-title a, "
                    "a.job-link, "
                    ".title a, "
                    "td.job-title a"
                )
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                href = title_elem.get("href", "")

                # Skip non-tech jobs
                title_lower = title.lower()
                tech_keywords = [
                    "software", "developer", "engineer", "backend", "frontend",
                    "fullstack", "full stack", "python", "java", "node", "react",
                    "devops", "data", "cloud", "mobile", "ios", "android", "web"
                ]
                if not any(kw in title_lower for kw in tech_keywords):
                    continue

                # Build job URL
                job_url = href if href.startswith("http") else urljoin(base_url, href) if href else search_url

                # Extract company
                company_elem = card.select_one(
                    ".company-name, "
                    ".employer, "
                    ".company, "
                    "span.company, "
                    "td.company"
                )
                company = company_elem.get_text(strip=True) if company_elem else "HotNigerianJobs Listing"

                # Extract location
                location_elem = card.select_one(
                    ".job-location, "
                    ".location, "
                    "span.location, "
                    "td.location"
                )
                location = location_elem.get_text(strip=True) if location_elem else "Nigeria"

                # Determine work type
                is_remote = "remote" in f"{title} {location}".lower()
                work_type = WorkType.REMOTE_NO_VISA if is_remote else WorkType.ONSITE_NO_VISA

                # Extract salary if available
                salary_elem = card.select_one(
                    ".salary, "
                    ".job-salary, "
                    "span.salary"
                )
                salary = salary_elem.get_text(strip=True) if salary_elem else "Not Listed"

                jobs.append(Job(
                    company=company,
                    role=title,
                    location=location,
                    work_type=work_type,
                    visa_sponsored=False,
                    pay_range=salary,
                    source="HotNigerianJobs",
                    job_url=job_url,
                    country=Country.NIGERIA,
                    status=JobStatus.FOUND,
                ))

            self._delay(1, 2)

        # Also try direct category pages for IT/Tech jobs
        if len(jobs) < max_jobs:
            category_urls = [
                f"{base_url}/it-jobs",
                f"{base_url}/technology-jobs",
                f"{base_url}/computer-jobs",
                f"{base_url}/software-jobs",
            ]

            for cat_url in category_urls:
                if len(jobs) >= max_jobs:
                    break

                response = self._get(cat_url)
                if not response:
                    continue

                soup = self._parse_html(response.text)
                job_cards = soup.select(
                    "div.job-listing, div.job-item, article.job, "
                    "div[class*='job-card'], li.job-result"
                )

                for card in job_cards[:max_jobs - len(jobs)]:
                    title_elem = card.select_one("h2 a, h3 a, h4 a, .job-title a, a.job-link")
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    href = title_elem.get("href", "")

                    if not self._matches_search(Job(company="", role=title, location=""), search_terms):
                        continue

                    job_url = href if href.startswith("http") else urljoin(base_url, href) if href else cat_url

                    company_elem = card.select_one(".company-name, .employer, .company")
                    company = company_elem.get_text(strip=True) if company_elem else "HotNigerianJobs Listing"

                    location_elem = card.select_one(".job-location, .location")
                    location = location_elem.get_text(strip=True) if location_elem else "Nigeria"

                    is_remote = "remote" in f"{title} {location}".lower()

                    jobs.append(Job(
                        company=company,
                        role=title,
                        location=location,
                        work_type=WorkType.REMOTE_NO_VISA if is_remote else WorkType.ONSITE_NO_VISA,
                        visa_sponsored=False,
                        pay_range="Not Listed",
                        source="HotNigerianJobs",
                        job_url=job_url,
                        country=Country.NIGERIA,
                        status=JobStatus.FOUND,
                    ))

                self._delay(1, 2)

        return jobs

    def _scrape_greenhouse(self, source_name: str, config: dict, search_terms: List[str], max_jobs: int) -> List[Job]:
        """Scrape Greenhouse job boards (used by Andela, Paystack, Flutterwave, etc.)."""
        jobs = []
        jobs_url = config.get("jobs_url", config.get("url"))

        response = self._get(jobs_url)
        if not response:
            return jobs

        soup = self._parse_html(response.text)

        # Greenhouse job listings
        job_cards = soup.select("div.opening, section.level-0 > div, tr.job-post")

        for card in job_cards:
            if len(jobs) >= max_jobs:
                break

            title_elem = card.select_one("a, h4, td.cell-title a")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            href = title_elem.get("href", "")
            job_url = href if href.startswith("http") else urljoin(jobs_url, href)

            location_elem = card.select_one("span.location, td.cell-location")
            location = location_elem.get_text(strip=True) if location_elem else "Nigeria"

            if title and self._matches_search(Job(company=source_name, role=title, location=location), search_terms):
                jobs.append(Job(
                    company=source_name,
                    role=title,
                    location=location,
                    work_type=WorkType.REMOTE_NO_VISA if "remote" in location.lower() else WorkType.ONSITE_NO_VISA,
                    visa_sponsored=False,
                    pay_range="Not Listed",
                    source=source_name,
                    job_url=job_url,
                    country=Country.NIGERIA,
                    status=JobStatus.FOUND,
                ))

        return jobs

    def _scrape_generic_careers(self, source_name: str, config: dict, search_terms: List[str], max_jobs: int) -> List[Job]:
        """Scrape generic careers pages."""
        jobs = []
        url = config.get("url")

        response = self._get(url)
        if not response:
            return jobs

        soup = self._parse_html(response.text)

        # Try common job listing patterns
        job_cards = soup.select(
            "div.job-card, div.job-listing, article.job, "
            "div.career-item, li.job-item, div.position, "
            "div[class*='job'], div[class*='career'], div[class*='opening']"
        )

        for card in job_cards:
            if len(jobs) >= max_jobs:
                break

            # Try various title selectors
            title_elem = card.select_one(
                "h2 a, h3 a, h4 a, a.job-title, "
                ".title a, .job-name a, [class*='title'] a"
            )
            if not title_elem:
                title_elem = card.select_one("h2, h3, h4, .title, .job-name")

            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            href = title_elem.get("href", "") if title_elem.name == "a" else ""
            if not href:
                link = card.select_one("a")
                href = link.get("href", "") if link else ""

            job_url = href if href.startswith("http") else urljoin(url, href) if href else url

            # Location
            location_elem = card.select_one(".location, .job-location, [class*='location']")
            location = location_elem.get_text(strip=True) if location_elem else "Nigeria"

            if title and self._matches_search(Job(company=source_name, role=title, location=location), search_terms):
                jobs.append(Job(
                    company=source_name,
                    role=title,
                    location=location,
                    work_type=WorkType.REMOTE_NO_VISA if "remote" in location.lower() else WorkType.ONSITE_NO_VISA,
                    visa_sponsored=False,
                    pay_range="Not Listed",
                    source=source_name,
                    job_url=job_url,
                    country=Country.NIGERIA,
                    status=JobStatus.FOUND,
                ))

        return jobs

    def _scrape_remoteafrica(self, search_terms: List[str], max_jobs: int) -> List[Job]:
        """Scrape RemoteAfrica.io job board."""
        jobs = []
        url = "https://remoteafrica.io/jobs"

        response = self._get(url)
        if not response:
            return jobs

        soup = self._parse_html(response.text)

        # RemoteAfrica job cards
        job_cards = soup.select("div.job-card, article.job, a[href*='/jobs/'], div[class*='job-listing']")

        for card in job_cards:
            if len(jobs) >= max_jobs:
                break

            title_elem = card.select_one("h2, h3, h4, .job-title, [class*='title']")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)

            if not self._matches_search(Job(company="", role=title, location=""), search_terms):
                continue

            company_elem = card.select_one(".company, .company-name, [class*='company']")
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            location_elem = card.select_one(".location, [class*='location']")
            location = location_elem.get_text(strip=True) if location_elem else "Remote Africa"

            href = card.get("href", "") if card.name == "a" else ""
            if not href:
                link = card.select_one("a")
                href = link.get("href", "") if link else ""
            job_url = href if href.startswith("http") else urljoin(url, href) if href else url

            salary_elem = card.select_one(".salary, [class*='salary']")
            salary = salary_elem.get_text(strip=True) if salary_elem else "Not Listed"

            jobs.append(Job(
                company=company,
                role=title,
                location=location,
                work_type=WorkType.REMOTE_NO_VISA,
                visa_sponsored=False,
                pay_range=salary,
                source="RemoteAfrica",
                job_url=job_url,
                country=Country.NIGERIA,
                status=JobStatus.FOUND,
            ))

        return jobs

    def _scrape_remotecom_jobs(self, search_terms: List[str], max_jobs: int) -> List[Job]:
        """
        Scrape Remote.com job board at https://remote.com/jobs/all

        Remote.com is a platform for remote work - lists jobs from companies
        using their HR/payroll services as well as general remote job listings.
        """
        jobs = []

        # Main job listing page
        base_url = "https://remote.com/jobs/all"

        # Search for each term
        for search_term in search_terms[:3]:
            if len(jobs) >= max_jobs:
                break

            # Remote.com search URL (query parameter may vary)
            search_url = f"{base_url}?query={quote(search_term)}"

            response = self._get(search_url)
            if not response:
                # Try alternate URL format
                search_url = f"https://remote.com/jobs?search={quote(search_term)}"
                response = self._get(search_url)
                if not response:
                    continue

            soup = self._parse_html(response.text)

            # Remote.com job cards - try multiple selectors
            job_cards = soup.select(
                "div[class*='job-card'], "
                "div[class*='JobCard'], "
                "article[class*='job'], "
                "a[href*='/jobs/'], "
                "div[class*='listing'], "
                "li[class*='job']"
            )

            for card in job_cards:
                if len(jobs) >= max_jobs:
                    break

                # Extract title
                title_elem = card.select_one(
                    "h2, h3, h4, "
                    "[class*='title'], "
                    "[class*='Title'], "
                    "a[class*='job']"
                )
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)

                if not self._matches_search(Job(company="", role=title, location=""), search_terms):
                    continue

                # Extract company
                company_elem = card.select_one(
                    "[class*='company'], "
                    "[class*='Company'], "
                    "[class*='employer']"
                )
                company = company_elem.get_text(strip=True) if company_elem else "Remote.com Company"

                # Extract location
                location_elem = card.select_one(
                    "[class*='location'], "
                    "[class*='Location']"
                )
                location = location_elem.get_text(strip=True) if location_elem else "Remote"

                # Get job URL
                href = card.get("href", "") if card.name == "a" else ""
                if not href:
                    link = card.select_one("a")
                    href = link.get("href", "") if link else ""
                job_url = href if href.startswith("http") else urljoin(base_url, href) if href else search_url

                # Extract salary if available
                salary_elem = card.select_one(
                    "[class*='salary'], "
                    "[class*='Salary'], "
                    "[class*='compensation']"
                )
                salary = salary_elem.get_text(strip=True) if salary_elem else "Not Listed"

                jobs.append(Job(
                    company=company,
                    role=title,
                    location=location,
                    work_type=WorkType.REMOTE_NO_VISA,
                    visa_sponsored=False,
                    pay_range=salary,
                    source="Remote.com",
                    job_url=job_url,
                    country=Country.NIGERIA,
                    status=JobStatus.FOUND,
                ))

            self._delay(2, 3)

        # Also try the main listing page without search for broader results
        if len(jobs) < max_jobs:
            response = self._get(base_url)
            if response:
                soup = self._parse_html(response.text)
                job_cards = soup.select(
                    "div[class*='job-card'], "
                    "div[class*='JobCard'], "
                    "article[class*='job'], "
                    "a[href*='/jobs/']"
                )

                for card in job_cards[:max_jobs - len(jobs)]:
                    title_elem = card.select_one("h2, h3, h4, [class*='title'], [class*='Title']")
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)

                    if not self._matches_search(Job(company="", role=title, location=""), search_terms):
                        continue

                    company_elem = card.select_one("[class*='company'], [class*='Company']")
                    company = company_elem.get_text(strip=True) if company_elem else "Remote.com Company"

                    href = card.get("href", "") if card.name == "a" else ""
                    if not href:
                        link = card.select_one("a")
                        href = link.get("href", "") if link else ""
                    job_url = href if href.startswith("http") else urljoin(base_url, href) if href else base_url

                    jobs.append(Job(
                        company=company,
                        role=title,
                        location="Remote",
                        work_type=WorkType.REMOTE_NO_VISA,
                        visa_sponsored=False,
                        pay_range="Not Listed",
                        source="Remote.com",
                        job_url=job_url,
                        country=Country.NIGERIA,
                        status=JobStatus.FOUND,
                    ))

        return jobs

    def _scrape_wellfound(self, search_terms: List[str], max_jobs: int) -> List[Job]:
        """Scrape Wellfound (formerly AngelList) for startup jobs."""
        jobs = []

        for search_term in search_terms:
            if len(jobs) >= max_jobs:
                break

            # Wellfound search with remote + Africa/Nigeria filter
            url = f"https://wellfound.com/jobs?q={quote(search_term)}&remote=true"

            response = self._get(url)
            if not response:
                continue

            soup = self._parse_html(response.text)

            # Wellfound job cards
            job_cards = soup.select(
                "div[data-test='JobSearchResults'] > div, "
                "div.styles_component__job, "
                "a[href*='/jobs/']"
            )

            for card in job_cards:
                if len(jobs) >= max_jobs:
                    break

                title_elem = card.select_one("h2, h3, [class*='title'], a[class*='title']")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)

                company_elem = card.select_one("[class*='company'], [class*='startup']")
                company = company_elem.get_text(strip=True) if company_elem else "Startup"

                location_elem = card.select_one("[class*='location']")
                location = location_elem.get_text(strip=True) if location_elem else "Remote"

                href = card.get("href", "") if card.name == "a" else ""
                if not href:
                    link = card.select_one("a[href*='/jobs/']")
                    href = link.get("href", "") if link else ""
                job_url = href if href.startswith("http") else urljoin("https://wellfound.com", href) if href else ""

                salary_elem = card.select_one("[class*='salary'], [class*='compensation']")
                salary = salary_elem.get_text(strip=True) if salary_elem else "Not Listed"

                jobs.append(Job(
                    company=company,
                    role=title,
                    location=location,
                    work_type=WorkType.REMOTE_NO_VISA,
                    visa_sponsored=False,
                    pay_range=salary,
                    source="Wellfound",
                    job_url=job_url,
                    country=Country.NIGERIA,
                    status=JobStatus.FOUND,
                ))

            self._delay(2, 3)

        return jobs

    def _scrape_greenhouse_search(self, search_terms: List[str], max_jobs: int) -> List[Job]:
        """
        Search Greenhouse job board aggregator for remote/Africa/EMEA positions.
        Uses https://job-boards.greenhouse.io/ main search + known company boards.
        """
        jobs = []

        # STEP 1: Search the main Greenhouse aggregator at job-boards.greenhouse.io
        # This searches across ALL Greenhouse-hosted job boards
        aggregator_base = "https://job-boards.greenhouse.io"

        # Location-based searches for Africa/EMEA/Nigeria/Remote
        location_searches = [
            "remote africa",
            "remote emea",
            "remote nigeria",
            "emea",
            "africa",
            "worldwide remote",
            "work from anywhere",
        ]

        for search_term in search_terms[:3]:  # Limit to top 3 job titles
            if len(jobs) >= max_jobs:
                break

            for location_query in location_searches[:4]:  # Limit location searches
                if len(jobs) >= max_jobs:
                    break

                # Greenhouse search URL format
                search_url = f"{aggregator_base}?q={quote(search_term)}&location={quote(location_query)}"

                response = self._get(search_url)
                if not response:
                    continue

                soup = self._parse_html(response.text)

                # Parse job listings from aggregator
                job_cards = soup.select(
                    "div.opening, "
                    "div[class*='job'], "
                    "a[href*='/jobs/'], "
                    "tr[class*='job'], "
                    "li[class*='job']"
                )

                for card in job_cards:
                    if len(jobs) >= max_jobs:
                        break

                    # Extract title
                    if card.name == "a":
                        title = card.get_text(strip=True)
                        href = card.get("href", "")
                    else:
                        title_elem = card.select_one("a, h2, h3, .title, [class*='title']")
                        if not title_elem:
                            continue
                        title = title_elem.get_text(strip=True)
                        href = title_elem.get("href", "") if title_elem.name == "a" else ""
                        if not href:
                            link = card.select_one("a")
                            href = link.get("href", "") if link else ""

                    if not title:
                        continue

                    # Extract company from URL or card
                    company_elem = card.select_one("[class*='company'], [class*='employer'], span.company")
                    company = company_elem.get_text(strip=True) if company_elem else ""

                    # Try to extract company from URL (boards.greenhouse.io/companyname)
                    if not company and href:
                        import re
                        match = re.search(r'boards\.greenhouse\.io/([^/]+)', href)
                        if match:
                            company = match.group(1).replace('-', ' ').title()

                    company = company or "Greenhouse Company"

                    # Extract location
                    location_elem = card.select_one("span.location, [class*='location']")
                    location = location_elem.get_text(strip=True) if location_elem else f"Remote {location_query.title()}"

                    if not self._matches_search(Job(company=company, role=title, location=location), search_terms):
                        continue

                    job_url = href if href.startswith("http") else urljoin(aggregator_base, href) if href else search_url

                    jobs.append(Job(
                        company=company,
                        role=title,
                        location=location,
                        work_type=WorkType.REMOTE_NO_VISA,
                        visa_sponsored=False,
                        pay_range="Not Listed",
                        source="Greenhouse Aggregator",
                        job_url=job_url,
                        country=Country.NIGERIA,
                        status=JobStatus.FOUND,
                    ))

                self._delay(1, 2)

        # STEP 2: Also check specific known remote-friendly companies using Greenhouse
        greenhouse_companies = [
            ("hashicorp", "HashiCorp"),
            ("cloudflare", "Cloudflare"),
            ("figma", "Figma"),
            ("coinbase", "Coinbase"),
            ("discord", "Discord"),
            ("stripe", "Stripe"),
            ("twitch", "Twitch"),
            ("cockroachlabs", "Cockroach Labs"),
            ("netlify", "Netlify"),
            ("vercel", "Vercel"),
            ("airtable", "Airtable"),
            ("notion", "Notion"),
            ("linear", "Linear"),
            ("planetscale", "PlanetScale"),
            ("render", "Render"),
            ("zapier", "Zapier"),
            ("webflow", "Webflow"),
            ("supabase", "Supabase"),
        ]

        for board_id, company_name in greenhouse_companies:
            if len(jobs) >= max_jobs:
                break

            url = f"https://boards.greenhouse.io/{board_id}"
            response = self._get(url)

            if not response:
                continue

            soup = self._parse_html(response.text)

            # Greenhouse job listings
            job_cards = soup.select("div.opening, section.level-0 > div")

            for card in job_cards:
                if len(jobs) >= max_jobs:
                    break

                title_elem = card.select_one("a")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                href = title_elem.get("href", "")

                location_elem = card.select_one("span.location")
                location = location_elem.get_text(strip=True) if location_elem else ""

                # Filter for remote/EMEA/Africa positions
                loc_lower = location.lower()
                if not any(kw in loc_lower for kw in ["remote", "emea", "africa", "nigeria", "anywhere", "worldwide"]):
                    continue

                if not self._matches_search(Job(company=company_name, role=title, location=location), search_terms):
                    continue

                job_url = href if href.startswith("http") else urljoin(url, href)

                jobs.append(Job(
                    company=company_name,
                    role=title,
                    location=location,
                    work_type=WorkType.REMOTE_NO_VISA,
                    visa_sponsored=False,
                    pay_range="Not Listed",
                    source=f"Greenhouse ({company_name})",
                    job_url=job_url,
                    country=Country.NIGERIA,
                    status=JobStatus.FOUND,
                ))

            self._delay(1, 2)

        return jobs

    def _scrape_ashby_search(self, search_terms: List[str], max_jobs: int) -> List[Job]:
        """
        Search Ashby job board aggregator for remote/Africa/EMEA positions.
        Uses https://jobs.ashbyhq.com/ main search + known company boards.
        """
        jobs = []

        # STEP 1: Search the main Ashby aggregator at jobs.ashbyhq.com
        aggregator_base = "https://jobs.ashbyhq.com"

        # Location-based searches for Africa/EMEA/Nigeria/Remote
        location_searches = [
            "remote africa",
            "remote emea",
            "remote nigeria",
            "emea",
            "africa",
            "worldwide",
            "work from anywhere",
        ]

        for search_term in search_terms[:3]:  # Limit to top 3 job titles
            if len(jobs) >= max_jobs:
                break

            for location_query in location_searches[:4]:  # Limit location searches
                if len(jobs) >= max_jobs:
                    break

                # Ashby search URL format (may vary, trying common patterns)
                search_url = f"{aggregator_base}?q={quote(search_term + ' ' + location_query)}"

                response = self._get(search_url)
                if not response:
                    continue

                soup = self._parse_html(response.text)

                # Parse job listings from aggregator - Ashby uses React/dynamic loading
                # Try multiple selector patterns
                job_cards = soup.select(
                    "a[href*='/jobs/'], "
                    "div[class*='JobListing'], "
                    "div[class*='job-card'], "
                    "tr[class*='job'], "
                    "li[class*='job'], "
                    "div[data-testid*='job']"
                )

                for card in job_cards:
                    if len(jobs) >= max_jobs:
                        break

                    # Extract title
                    if card.name == "a":
                        title = card.get_text(strip=True)
                        href = card.get("href", "")
                    else:
                        title_elem = card.select_one("a, h2, h3, .title, [class*='title'], [class*='Title']")
                        if not title_elem:
                            continue
                        title = title_elem.get_text(strip=True)
                        href = title_elem.get("href", "") if title_elem.name == "a" else ""
                        if not href:
                            link = card.select_one("a")
                            href = link.get("href", "") if link else ""

                    if not title:
                        continue

                    # Extract company from URL or card
                    company_elem = card.select_one("[class*='company'], [class*='Company'], span.company")
                    company = company_elem.get_text(strip=True) if company_elem else ""

                    # Try to extract company from URL (jobs.ashbyhq.com/CompanyName)
                    if not company and href:
                        import re
                        match = re.search(r'jobs\.ashbyhq\.com/([^/]+)', href)
                        if match:
                            company = match.group(1).replace('-', ' ').title()

                    company = company or "Ashby Company"

                    # Extract location
                    location_elem = card.select_one("[class*='location'], [class*='Location']")
                    location = location_elem.get_text(strip=True) if location_elem else f"Remote {location_query.title()}"

                    if not self._matches_search(Job(company=company, role=title, location=location), search_terms):
                        continue

                    job_url = href if href.startswith("http") else urljoin(aggregator_base, href) if href else search_url

                    jobs.append(Job(
                        company=company,
                        role=title,
                        location=location,
                        work_type=WorkType.REMOTE_NO_VISA,
                        visa_sponsored=False,
                        pay_range="Not Listed",
                        source="Ashby Aggregator",
                        job_url=job_url,
                        country=Country.NIGERIA,
                        status=JobStatus.FOUND,
                    ))

                self._delay(1, 2)

        # STEP 2: Also check specific known remote-friendly companies using Ashby
        ashby_companies = [
            ("Deel", "https://jobs.ashbyhq.com/Deel"),
            ("Ramp", "https://jobs.ashbyhq.com/ramp"),
            ("Mercury", "https://jobs.ashbyhq.com/Mercury"),
            ("Retool", "https://jobs.ashbyhq.com/Retool"),
            ("OpenSea", "https://jobs.ashbyhq.com/OpenSea"),
            ("Pipe", "https://jobs.ashbyhq.com/pipe"),
            ("Dbt Labs", "https://jobs.ashbyhq.com/dbtlabs"),
            ("PostHog", "https://jobs.ashbyhq.com/PostHog"),
            ("Airbyte", "https://jobs.ashbyhq.com/Airbyte"),
            ("Monte Carlo", "https://jobs.ashbyhq.com/montecarlodata"),
            ("Linear", "https://jobs.ashbyhq.com/Linear"),
            ("Railway", "https://jobs.ashbyhq.com/Railway"),
            ("Cal.com", "https://jobs.ashbyhq.com/Cal.com"),
            ("Resend", "https://jobs.ashbyhq.com/Resend"),
        ]

        for company_name, board_url in ashby_companies:
            if len(jobs) >= max_jobs:
                break

            response = self._get(board_url)

            if not response:
                continue

            soup = self._parse_html(response.text)

            # Ashby job listings
            job_cards = soup.select("a[href*='/jobs/'], div[class*='job'], tr[class*='job']")

            for card in job_cards:
                if len(jobs) >= max_jobs:
                    break

                if card.name == "a":
                    title = card.get_text(strip=True)
                    href = card.get("href", "")
                else:
                    title_elem = card.select_one("a, td:first-child")
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    href = title_elem.get("href", "") if title_elem.name == "a" else ""

                if not title:
                    continue

                # Get location
                location_elem = card.select_one("[class*='location'], td:nth-child(2)")
                location = location_elem.get_text(strip=True) if location_elem else ""

                # Filter for remote/EMEA/Africa
                loc_lower = location.lower()
                if not any(kw in loc_lower for kw in ["remote", "emea", "africa", "nigeria", "anywhere", "worldwide", ""]):
                    # Empty location often means remote
                    if location:
                        continue

                if not self._matches_search(Job(company=company_name, role=title, location=location), search_terms):
                    continue

                job_url = href if href.startswith("http") else urljoin(board_url, href) if href else board_url

                jobs.append(Job(
                    company=company_name,
                    role=title,
                    location=location or "Remote",
                    work_type=WorkType.REMOTE_NO_VISA,
                    visa_sponsored=False,
                    pay_range="Not Listed",
                    source=f"Ashby ({company_name})",
                    job_url=job_url,
                    country=Country.NIGERIA,
                    status=JobStatus.FOUND,
                ))

            self._delay(1, 2)

        return jobs

    def _scrape_twitter_jobs(self, search_terms: List[str], max_jobs: int) -> List[Job]:
        """
        Scrape Twitter/X for job posts.

        Searches for job postings using patterns commonly seen on Twitter:
        - "remote (Africa)" - common format for Africa-eligible remote jobs
        - "work from anywhere" - fully remote positions
        - "Nigeria" - jobs specifically mentioning Nigeria
        - "please apply" - common in job posting tweets
        - "software engineer", "backend engineer", "fullstack engineer" variations

        Note: Twitter requires authentication for full API access.
        This uses Nitter (public Twitter frontend) for unauthenticated access.
        """
        jobs = []

        # Enhanced Twitter search queries based on common job posting patterns
        # Users on Twitter often write: "remote (Africa)", "work from anywhere", "please apply"
        search_queries = [
            # "remote (Africa)" pattern - very common for Africa-eligible jobs
            '"{term}" "remote" "(Africa)" hiring',
            '"{term}" remote "(Africa)" OR "remote Africa"',

            # Work from anywhere pattern
            '"{term}" "work from anywhere" hiring',
            '"{term}" "work from anywhere" Nigeria',

            # EMEA pattern
            '"{term}" "remote EMEA" hiring',
            '"{term}" remote EMEA OR "remote (EMEA)"',

            # Nigeria-specific
            '"{term}" hiring Nigeria remote',
            '"{term}" remote Nigeria "please apply"',

            # "Please apply" pattern - common in job tweets
            '"{term}" hiring "please apply" remote',
            '"{term}" "we are hiring" "please apply"',

            # General remote with apply call-to-action
            '"{term}" remote hiring ("apply" OR "dm" OR "interested")',
        ]

        # Role variations to search
        role_variations = []
        for term in search_terms[:3]:
            role_variations.append(term)
            # Add common variations
            term_lower = term.lower()
            if "software" in term_lower:
                role_variations.append("backend engineer")
                role_variations.append("fullstack engineer")
            elif "backend" in term_lower:
                role_variations.append("software engineer")
            elif "fullstack" in term_lower or "full stack" in term_lower:
                role_variations.append("software engineer")

        # Deduplicate
        role_variations = list(dict.fromkeys(role_variations))[:4]

        # Nitter instances (Twitter frontend for unauthenticated access)
        nitter_instances = [
            "https://nitter.net",
            "https://nitter.privacydev.net",
            "https://nitter.poast.org",
            "https://nitter.1d4.us",
        ]

        for search_term in role_variations:
            if len(jobs) >= max_jobs:
                break

            for query_template in search_queries[:4]:  # Limit to 4 query patterns per term
                if len(jobs) >= max_jobs:
                    break

                query = query_template.format(term=search_term)

                for nitter_url in nitter_instances:
                    try:
                        search_url = f"{nitter_url}/search?f=tweets&q={quote(query)}"
                        response = self._get(search_url)

                        if not response:
                            continue

                        soup = self._parse_html(response.text)

                        # Parse Nitter tweet cards
                        tweets = soup.select("div.timeline-item, div.tweet, article")

                        for tweet in tweets[:5]:  # Limit per query
                            if len(jobs) >= max_jobs:
                                break

                            tweet_text = tweet.get_text(strip=True)
                            tweet_text_lower = tweet_text.lower()

                            # Check if it's actually a job post with strong indicators
                            job_indicators = [
                                "hiring", "job", "position", "apply",
                                "looking for", "join us", "opening",
                                "we're hiring", "we are hiring",
                                "please apply", "send dm", "send cv",
                                "remote opportunity", "open role"
                            ]
                            if not any(ind in tweet_text_lower for ind in job_indicators):
                                continue

                            # Extra check: must mention relevant role
                            role_keywords = [
                                "engineer", "developer", "software", "backend",
                                "frontend", "fullstack", "full stack", "swe",
                                "dev", "programmer"
                            ]
                            if not any(kw in tweet_text_lower for kw in role_keywords):
                                continue

                            # Extract username
                            username_elem = tweet.select_one("a.username, a.fullname, a[href*='/@']")
                            username = username_elem.get_text(strip=True) if username_elem else "Unknown"
                            username = username.replace("@", "")

                            # Extract tweet URL
                            link_elem = tweet.select_one("a.tweet-link, a[href*='/status/']")
                            tweet_url = ""
                            if link_elem:
                                href = link_elem.get("href", "")
                                if href.startswith("http"):
                                    tweet_url = href
                                else:
                                    # Convert Nitter URL to Twitter URL
                                    tweet_url = f"https://twitter.com{href.replace(nitter_url, '')}"

                            # Determine location from tweet content
                            location = "Remote"
                            if "africa" in tweet_text_lower:
                                location = "Remote (Africa)"
                            elif "emea" in tweet_text_lower:
                                location = "Remote (EMEA)"
                            elif "nigeria" in tweet_text_lower:
                                location = "Remote Nigeria"
                            elif "anywhere" in tweet_text_lower:
                                location = "Work from Anywhere"

                            # Create job entry
                            jobs.append(Job(
                                company=f"Twitter: @{username}",
                                role=f"{search_term} (Twitter Post)",
                                location=location,
                                work_type=WorkType.REMOTE_NO_VISA,
                                visa_sponsored=False,
                                pay_range="Not Listed",
                                source="Twitter/X",
                                job_url=tweet_url,
                                country=Country.NIGERIA,
                                description=tweet_text[:300],
                                status=JobStatus.FOUND,
                            ))

                        break  # Success with this Nitter instance, don't try others

                    except Exception as e:
                        self.logger.debug(f"Nitter error ({nitter_url}): {e}")
                        continue

                self._delay(2, 4)

        return jobs

    def _scrape_turing(self, search_terms: List[str], max_jobs: int) -> List[Job]:
        """Scrape Turing.com jobs."""
        jobs = []
        url = "https://www.turing.com/jobs"

        response = self._get(url)
        if not response:
            return jobs

        soup = self._parse_html(response.text)

        # Turing job cards
        job_cards = soup.select("div.job-card, a[href*='/jobs/'], div[class*='JobCard']")

        for card in job_cards:
            if len(jobs) >= max_jobs:
                break

            title_elem = card.select_one("h2, h3, .job-title, [class*='title']")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)

            if not self._matches_search(Job(company="Turing", role=title, location="Remote"), search_terms):
                continue

            href = card.get("href", "") if card.name == "a" else ""
            if not href:
                link = card.select_one("a")
                href = link.get("href", "") if link else ""

            job_url = href if href.startswith("http") else urljoin(url, href) if href else url

            jobs.append(Job(
                company="Turing",
                role=title,
                location="Remote (Global)",
                work_type=WorkType.REMOTE_NO_VISA,
                visa_sponsored=False,
                pay_range="Not Listed",
                source="Turing",
                job_url=job_url,
                country=Country.NIGERIA,
                status=JobStatus.FOUND,
            ))

        return jobs

    def _scrape_crossover(self, search_terms: List[str], max_jobs: int) -> List[Job]:
        """Scrape Crossover.com jobs."""
        jobs = []
        url = "https://www.crossover.com/jobs"

        response = self._get(url)
        if not response:
            return jobs

        soup = self._parse_html(response.text)

        # Crossover job cards
        job_cards = soup.select("div.job-card, a.job-link, div[class*='job']")

        for card in job_cards:
            if len(jobs) >= max_jobs:
                break

            title_elem = card.select_one("h2, h3, h4, .title, [class*='title']")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)

            if not self._matches_search(Job(company="Crossover", role=title, location="Remote"), search_terms):
                continue

            href = card.get("href", "") if card.name == "a" else ""
            if not href:
                link = card.select_one("a")
                href = link.get("href", "") if link else ""

            job_url = href if href.startswith("http") else urljoin(url, href) if href else url

            # Crossover shows salary ranges
            salary_elem = card.select_one(".salary, [class*='salary'], [class*='pay']")
            salary = salary_elem.get_text(strip=True) if salary_elem else "Not Listed"

            jobs.append(Job(
                company="Crossover",
                role=title,
                location="Remote (Global)",
                work_type=WorkType.REMOTE_NO_VISA,
                visa_sponsored=False,
                pay_range=salary,
                source="Crossover",
                job_url=job_url,
                country=Country.NIGERIA,
                status=JobStatus.FOUND,
            ))

        return jobs

    def _scrape_lever(self, source_name: str, config: dict, search_terms: List[str], max_jobs: int) -> List[Job]:
        """Scrape Lever job boards."""
        jobs = []
        jobs_url = config.get("jobs_url", config.get("url"))

        response = self._get(jobs_url)
        if not response:
            return jobs

        soup = self._parse_html(response.text)

        # Lever job listings
        job_cards = soup.select("div.posting, a.posting-title")

        for card in job_cards:
            if len(jobs) >= max_jobs:
                break

            if card.name == "a":
                title = card.get_text(strip=True)
                href = card.get("href", "")
            else:
                title_elem = card.select_one("a.posting-title, h5")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                href = title_elem.get("href", "") if title_elem.name == "a" else ""

            if not self._matches_search(Job(company=source_name, role=title, location="Remote"), search_terms):
                continue

            job_url = href if href.startswith("http") else urljoin(jobs_url, href) if href else jobs_url

            location_elem = card.select_one(".location, .posting-categories")
            location = location_elem.get_text(strip=True) if location_elem else "Remote"

            jobs.append(Job(
                company=source_name,
                role=title,
                location=location,
                work_type=WorkType.REMOTE_NO_VISA if "remote" in location.lower() else WorkType.ONSITE_NO_VISA,
                visa_sponsored=False,
                pay_range="Not Listed",
                source=source_name,
                job_url=job_url,
                country=Country.NIGERIA,
                status=JobStatus.FOUND,
            ))

        return jobs

    def _scrape_ashby(self, source_name: str, config: dict, search_terms: List[str], max_jobs: int) -> List[Job]:
        """Scrape Ashby job boards (used by Deel, etc.)."""
        jobs = []
        jobs_url = config.get("jobs_url", config.get("url"))

        response = self._get(jobs_url)
        if not response:
            return jobs

        soup = self._parse_html(response.text)

        # Ashby job listings
        job_cards = soup.select("a[href*='/jobs/'], div.job-posting, tr[class*='job']")

        for card in job_cards:
            if len(jobs) >= max_jobs:
                break

            if card.name == "a":
                title = card.get_text(strip=True)
                href = card.get("href", "")
            else:
                title_elem = card.select_one("a, h3, td:first-child")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                href = title_elem.get("href", "") if title_elem.name == "a" else ""

            if not title or not self._matches_search(Job(company=source_name, role=title, location="Remote"), search_terms):
                continue

            job_url = href if href.startswith("http") else urljoin(jobs_url, href) if href else jobs_url

            location_elem = card.select_one(".location, td:nth-child(2)")
            location = location_elem.get_text(strip=True) if location_elem else "Remote"

            jobs.append(Job(
                company=source_name,
                role=title,
                location=location,
                work_type=WorkType.REMOTE_NO_VISA if "remote" in location.lower() else WorkType.ONSITE_NO_VISA,
                visa_sponsored=False,
                pay_range="Not Listed",
                source=source_name,
                job_url=job_url,
                country=Country.NIGERIA,
                status=JobStatus.FOUND,
            ))

        return jobs

    def parse_job(self, data: Any) -> Optional[Job]:
        """Parse job from generic data (implements abstract method)."""
        if isinstance(data, dict):
            return Job(
                company=data.get("company", "Unknown"),
                role=data.get("title", ""),
                location=data.get("location", "Nigeria"),
                work_type=WorkType.REMOTE_NO_VISA,
                visa_sponsored=False,
                pay_range=data.get("salary", "Not Listed"),
                source=data.get("source", "Nigeria Recruiters"),
                job_url=data.get("url", ""),
                country=Country.NIGERIA,
                status=JobStatus.FOUND,
            )
        return None
