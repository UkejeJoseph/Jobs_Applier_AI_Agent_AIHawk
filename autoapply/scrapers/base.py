"""
Base Scraper
============
Abstract base class for all job scrapers with common functionality.
Includes fallback to stealth browser for bot-protected sites.
Supports proxy rotation for avoiding IP-based blocking.
"""

import time
import random
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Generator
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Cloudscraper for Cloudflare bypass (free!)
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False
    cloudscraper = None

from autoapply.core.job_schema import Job, Country, WorkType, detect_visa_sponsorship, extract_salary
from autoapply.config import VISA, JOB_PREFS, APP_SETTINGS

# Try to import browser automation (optional)
try:
    from autoapply.core.browser import StealthBrowser, BrowserConfig
    BROWSER_AVAILABLE = True
except ImportError:
    BROWSER_AVAILABLE = False
    StealthBrowser = None

# Try to import proxy manager (optional)
try:
    from autoapply.core.proxy_manager import ProxyManager, Proxy, get_proxy_manager
    PROXY_AVAILABLE = True
except ImportError:
    PROXY_AVAILABLE = False
    ProxyManager = None
    Proxy = None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@dataclass
class ScraperResult:
    """Result from a scraping operation."""
    jobs: List[Job] = field(default_factory=list)
    total_found: int = 0
    errors: List[str] = field(default_factory=list)
    source: str = ""
    scrape_time: datetime = field(default_factory=datetime.now)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def jobs_count(self) -> int:
        return len(self.jobs)


class BaseScraper(ABC):
    """
    Abstract base class for job scrapers.

    All scrapers should inherit from this class and implement:
    - scrape() method
    - parse_job() method
    """

    # Default headers to mimic a real browser
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    # Rotating user agents for anti-bot detection
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    def __init__(
        self,
        name: str,
        country: Country,
        use_browser: bool = False,
        use_proxy: bool = False,
        proxy_manager: Optional["ProxyManager"] = None,
    ):
        """
        Initialize the scraper.

        Args:
            name: Scraper name for logging
            country: Target country for jobs
            use_browser: If True, use stealth browser instead of requests
            use_proxy: If True, use proxy rotation
            proxy_manager: Optional custom proxy manager
        """
        self.name = name
        self.country = country
        self.logger = logging.getLogger(f"scraper.{name}")

        # Use cloudscraper if available (bypasses Cloudflare)
        if CLOUDSCRAPER_AVAILABLE:
            self.session = cloudscraper.create_scraper(
                browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
            )
            self.logger.debug("Using cloudscraper for Cloudflare bypass")
        else:
            self.session = requests.Session()

        self._update_headers()

        # Browser automation for bot-protected sites
        self._use_browser = use_browser
        self._browser: Optional[StealthBrowser] = None
        self._browser_failures = 0  # Track consecutive failures to trigger browser fallback

        # Proxy rotation
        self._use_proxy = use_proxy and PROXY_AVAILABLE
        self._proxy_manager = proxy_manager
        self._current_proxy: Optional[Proxy] = None

        if self._use_proxy and not self._proxy_manager:
            self._proxy_manager = get_proxy_manager() if PROXY_AVAILABLE else None

    def _update_headers(self):
        """Update session headers with random user agent."""
        headers = self.DEFAULT_HEADERS.copy()
        headers["User-Agent"] = random.choice(self.USER_AGENTS)
        self.session.headers.update(headers)

    def _delay(self, min_sec: float = None, max_sec: float = None):
        """Add random delay between requests."""
        if min_sec is None:
            min_sec = APP_SETTINGS.delay_between_scrapes_sec
        if max_sec is None:
            max_sec = min_sec * 2

        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def _get(self, url: str, params: Dict = None, **kwargs) -> Optional[requests.Response]:
        """
        Make a GET request with error handling, retries, and proxy rotation.
        Falls back to stealth browser if blocked, or uses saved cookies.

        Args:
            url: URL to fetch
            params: Query parameters
            **kwargs: Additional arguments for requests.get

        Returns:
            Response object or None on failure
        """
        # If browser mode is enabled, use browser directly
        if self._use_browser:
            return self._get_with_browser(url, params)

        # Try to load saved cookies for this domain (from manual captcha solving)
        try:
            from urllib.parse import urlparse
            from autoapply.core.manual_captcha import ManualCaptchaSolver

            domain = urlparse(url).netloc.replace("www.", "")
            solver = ManualCaptchaSolver()

            if solver.has_valid_cookies(domain):
                self.logger.debug(f"Using saved cookies for {domain}")
                cookies = solver.load_cookies(domain)
                for cookie in cookies:
                    self.session.cookies.set(
                        cookie.get("name"),
                        cookie.get("value"),
                        domain=cookie.get("domain", domain),
                    )
        except Exception:
            pass  # Manual captcha module not available or no cookies

        max_retries = 3

        for attempt in range(max_retries):
            try:
                self._update_headers()  # Rotate user agent

                # Get proxy if enabled
                proxies = None
                if self._use_proxy and self._proxy_manager:
                    self._current_proxy = self._proxy_manager.get_proxy()
                    if self._current_proxy:
                        proxies = self._current_proxy.to_dict()
                        self.logger.debug(f"Using proxy: {self._current_proxy.url[:30]}...")

                start_time = time.time()
                response = self.session.get(url, params=params, timeout=30, proxies=proxies, **kwargs)
                response_time = time.time() - start_time

                response.raise_for_status()

                # Mark proxy success
                if self._current_proxy and self._proxy_manager:
                    self._proxy_manager.mark_success(self._current_proxy, response_time)

                self._browser_failures = 0  # Reset failure count on success
                return response

            except requests.exceptions.HTTPError as e:
                # Mark proxy failure
                if self._current_proxy and self._proxy_manager:
                    self._proxy_manager.mark_failed(self._current_proxy, f"HTTP {response.status_code}")

                if response.status_code == 429:  # Rate limited
                    wait_time = int(response.headers.get("Retry-After", 60))
                    self.logger.warning(f"Rate limited. Waiting {wait_time}s...")

                    # Try with different proxy
                    if self._use_proxy and self._proxy_manager and self._proxy_manager.has_proxies:
                        self.logger.info("Rotating proxy and retrying...")
                        continue

                    time.sleep(wait_time)

                elif response.status_code == 403:
                    self.logger.warning(f"Access forbidden for {url}.")

                    # Try different proxy first
                    if self._use_proxy and self._proxy_manager and self._proxy_manager.has_proxies:
                        self.logger.info("Trying different proxy...")
                        continue

                    # Fall back to browser
                    self.logger.info("Trying stealth browser...")
                    self._browser_failures += 1
                    browser_response = self._get_with_browser(url, params)
                    if browser_response:
                        return browser_response
                    return None
                else:
                    self.logger.error(f"HTTP error {response.status_code}: {e}")

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request failed (attempt {attempt + 1}): {e}")

                # Mark proxy failure
                if self._current_proxy and self._proxy_manager:
                    self._proxy_manager.mark_failed(self._current_proxy, str(e))

                self._browser_failures += 1

            # Exponential backoff
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

        # After all retries failed, try browser as last resort
        if self._browser_failures >= 2 and BROWSER_AVAILABLE:
            self.logger.info(f"Multiple failures detected, trying stealth browser for {url}")
            return self._get_with_browser(url, params)

        return None

    def _get_with_browser(self, url: str, params: Dict = None) -> Optional[requests.Response]:
        """
        Fetch URL using stealth browser (for bot-protected sites).

        Returns a mock Response object with the page content.
        """
        if not BROWSER_AVAILABLE:
            self.logger.warning("Browser automation not available. Install undetected-chromedriver.")
            return None

        try:
            # Build URL with params
            if params:
                from urllib.parse import urlencode
                url = f"{url}?{urlencode(params)}"

            # Initialize browser if needed
            if self._browser is None:
                self.logger.info("Starting stealth browser...")
                config = BrowserConfig(headless=True)
                self._browser = StealthBrowser(config)
                self._browser.start()

            # Fetch page
            html = self._browser.get_page(url)

            if html:
                # Create mock response object
                mock_response = MockResponse(html, url)
                return mock_response

        except Exception as e:
            self.logger.error(f"Browser fetch failed: {e}")

        return None

    def _close_browser(self):
        """Close the browser if it's open."""
        if self._browser:
            self._browser.stop()
            self._browser = None

    def __del__(self):
        """Cleanup browser on object destruction."""
        self._close_browser()

    def _matches_search(self, job: Job, search_terms: List[str]) -> bool:
        """
        Check if job matches any search term.

        Args:
            job: Job object to check
            search_terms: List of search terms to match against

        Returns:
            True if job matches any search term
        """
        job_text = f"{job.role} {job.description}".lower()
        return any(term.lower() in job_text for term in search_terms)

    def _parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML content."""
        return BeautifulSoup(html, "html.parser")

    def _should_include_job(self, job: Job) -> bool:
        """
        Check if a job should be included based on filters.

        Checks:
        - Visa sponsorship requirements
        - Work type preferences
        - Exclude keywords
        """
        # Check exclude keywords
        text = f"{job.role} {job.description}".lower()
        for keyword in JOB_PREFS.exclude_keywords:
            if keyword in text:
                self.logger.debug(f"Excluding job due to keyword: {keyword}")
                return False

        # For countries needing visa sponsorship
        if VISA.needs_sponsorship.get(self.country, False):
            # If on-site and no visa sponsorship, skip
            if job.work_type == WorkType.ONSITE_NO_VISA:
                self.logger.debug(f"Excluding on-site job without visa sponsorship")
                return False

        return True

    def _detect_visa_sponsorship(self, text: str, company: str) -> bool:
        """Check if job offers visa sponsorship."""
        return detect_visa_sponsorship(text, company, VISA.known_sponsors)

    def _extract_salary(self, text: str) -> str:
        """Extract salary from job text."""
        return extract_salary(text)

    @abstractmethod
    def scrape(self, search_terms: List[str] = None, max_jobs: int = 100) -> ScraperResult:
        """
        Scrape jobs from the source.

        Args:
            search_terms: List of job titles/keywords to search
            max_jobs: Maximum number of jobs to return

        Returns:
            ScraperResult with found jobs
        """
        pass

    @abstractmethod
    def parse_job(self, data: Any) -> Optional[Job]:
        """
        Parse job data into a Job object.

        Args:
            data: Raw job data (HTML element, JSON, etc.)

        Returns:
            Job object or None if parsing fails
        """
        pass

    def scrape_with_pagination(self, base_url: str, search_terms: List[str],
                               max_pages: int = 10, jobs_per_page: int = 25) -> Generator[Job, None, None]:
        """
        Generator that scrapes with pagination.

        Override in subclass to implement source-specific pagination.
        """
        raise NotImplementedError("Subclass must implement pagination logic")


class MockResponse:
    """Mock requests.Response for browser-fetched content."""

    def __init__(self, text: str, url: str):
        self.text = text
        self.content = text.encode('utf-8')
        self.url = url
        self.status_code = 200
        self.headers = {}

    def raise_for_status(self):
        pass

    def json(self):
        import json
        return json.loads(self.text)


class SponsorListScraper(BaseScraper):
    """
    Base class for scrapers that download official sponsor lists.
    Used for UK gov.uk and US H1B data.
    """

    def __init__(self, name: str, country: Country, cache_dir: Path):
        super().__init__(name, country)
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._sponsors: set = set()

    @abstractmethod
    def download_sponsor_list(self) -> bool:
        """Download and cache the sponsor list."""
        pass

    @abstractmethod
    def load_sponsors(self) -> set:
        """Load sponsors from cache."""
        pass

    def is_sponsor(self, company_name: str) -> bool:
        """Check if a company is a known sponsor."""
        if not self._sponsors:
            self._sponsors = self.load_sponsors()

        # Normalize company name for comparison
        company_lower = company_name.lower().strip()

        # Check exact match
        if company_lower in self._sponsors:
            return True

        # Check partial match (company name might be abbreviated)
        for sponsor in self._sponsors:
            if sponsor in company_lower or company_lower in sponsor:
                return True

        return False

    def scrape(self, search_terms: List[str] = None, max_jobs: int = 100) -> ScraperResult:
        """
        Sponsor list scrapers don't scrape jobs directly.
        They provide sponsor lookup functionality.
        """
        result = ScraperResult(source=self.name)

        if self.download_sponsor_list():
            self._sponsors = self.load_sponsors()
            result.total_found = len(self._sponsors)
            self.logger.info(f"Loaded {len(self._sponsors)} sponsors from {self.name}")
        else:
            result.errors.append("Failed to download sponsor list")

        return result

    def parse_job(self, data: Any) -> Optional[Job]:
        """Not used for sponsor list scrapers."""
        return None
