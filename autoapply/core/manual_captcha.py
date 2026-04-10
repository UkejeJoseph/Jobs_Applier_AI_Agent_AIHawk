"""
Manual Captcha Solver (FREE)
============================
Opens a browser window for YOU to solve the captcha manually.
Saves cookies so you don't have to solve again for hours/days.

How it works:
1. Opens browser to the blocked site
2. You solve the captcha manually
3. Saves cookies to file
4. Future requests use saved cookies (no captcha!)

Usage:
    solver = ManualCaptchaSolver()
    cookies = solver.solve_and_save("https://indeed.com")
    # Now use cookies in your scraper
"""

import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List

logger = logging.getLogger("autoapply.manual_captcha")

# Cookie storage directory
COOKIE_DIR = Path(__file__).parent.parent / "cookies"
COOKIE_DIR.mkdir(exist_ok=True)


class ManualCaptchaSolver:
    """
    Free captcha solver - you solve it manually, cookies are saved.

    Sites typically remember you for 24-72 hours after solving.
    """

    # How long cookies stay valid (conservative estimate)
    COOKIE_VALIDITY_HOURS = {
        "indeed.com": 24,
        "builtin.com": 48,
        "glassdoor.com": 24,
        "weworkremotely.com": 72,
        "default": 24,
    }

    def __init__(self):
        self.cookie_dir = COOKIE_DIR

    def get_cookie_file(self, domain: str) -> Path:
        """Get cookie file path for a domain."""
        safe_name = domain.replace(".", "_").replace("/", "_")
        return self.cookie_dir / f"{safe_name}_cookies.json"

    def has_valid_cookies(self, domain: str) -> bool:
        """Check if we have valid (non-expired) cookies for a domain."""
        cookie_file = self.get_cookie_file(domain)

        if not cookie_file.exists():
            return False

        try:
            with open(cookie_file, "r") as f:
                data = json.load(f)

            saved_time = datetime.fromisoformat(data.get("saved_at", "2000-01-01"))
            validity_hours = self.COOKIE_VALIDITY_HOURS.get(
                domain, self.COOKIE_VALIDITY_HOURS["default"]
            )

            if datetime.now() - saved_time < timedelta(hours=validity_hours):
                return True

        except Exception as e:
            logger.debug(f"Error reading cookies for {domain}: {e}")

        return False

    def load_cookies(self, domain: str) -> List[Dict]:
        """Load saved cookies for a domain."""
        cookie_file = self.get_cookie_file(domain)

        if not cookie_file.exists():
            return []

        try:
            with open(cookie_file, "r") as f:
                data = json.load(f)
            return data.get("cookies", [])
        except Exception:
            return []

    def save_cookies(self, domain: str, cookies: List[Dict]):
        """Save cookies for a domain."""
        cookie_file = self.get_cookie_file(domain)

        data = {
            "domain": domain,
            "saved_at": datetime.now().isoformat(),
            "cookies": cookies,
        }

        with open(cookie_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved {len(cookies)} cookies for {domain}")

    def solve_manually(self, url: str, wait_seconds: int = 120) -> Optional[List[Dict]]:
        """
        Open browser for manual captcha solving.

        Args:
            url: URL to open (with captcha)
            wait_seconds: How long to wait for you to solve

        Returns:
            List of cookies after solving, or None if failed
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError:
            logger.error("Selenium not installed. Run: pip install selenium")
            return None

        print(f"\n{'='*60}")
        print("MANUAL CAPTCHA SOLVING")
        print('='*60)
        print(f"Opening: {url}")
        print(f"Please solve the captcha in the browser window.")
        print(f"You have {wait_seconds} seconds.")
        print('='*60 + "\n")

        # Open regular Chrome (not headless - you need to see it!)
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        try:
            driver = webdriver.Chrome(options=options)
            driver.get(url)

            print("Waiting for you to solve the captcha...")
            print("Press Enter here when done (or wait for timeout)")

            # Wait for user to solve
            start_time = time.time()
            while time.time() - start_time < wait_seconds:
                # Check if page loaded past captcha
                try:
                    # Simple check - if we can find job content, captcha is solved
                    page_source = driver.page_source.lower()
                    if any(x in page_source for x in ["job", "career", "position", "apply"]):
                        if "captcha" not in page_source and "challenge" not in page_source:
                            print("Captcha appears to be solved!")
                            break
                except:
                    pass
                time.sleep(2)

            # Get cookies
            cookies = driver.get_cookies()
            driver.quit()

            if cookies:
                # Extract domain from URL
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.replace("www.", "")
                self.save_cookies(domain, cookies)
                return cookies

        except Exception as e:
            logger.error(f"Error in manual captcha solving: {e}")

        return None

    def get_session_with_cookies(self, domain: str):
        """
        Get a requests session with saved cookies.

        Usage:
            solver = ManualCaptchaSolver()
            session = solver.get_session_with_cookies("indeed.com")
            response = session.get("https://indeed.com/jobs")
        """
        import requests

        session = requests.Session()
        cookies = self.load_cookies(domain)

        for cookie in cookies:
            session.cookies.set(
                cookie.get("name"),
                cookie.get("value"),
                domain=cookie.get("domain", domain),
            )

        # Add realistic headers
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

        return session


def solve_for_site(url: str) -> bool:
    """
    Convenience function to solve captcha for a site.

    Returns True if cookies were saved successfully.
    """
    solver = ManualCaptchaSolver()

    from urllib.parse import urlparse
    domain = urlparse(url).netloc.replace("www.", "")

    # Check if we already have valid cookies
    if solver.has_valid_cookies(domain):
        print(f"Already have valid cookies for {domain}")
        return True

    # Solve manually
    cookies = solver.solve_manually(url)
    return cookies is not None


# Quick CLI
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python manual_captcha.py <url>")
        print("Example: python manual_captcha.py https://indeed.com/jobs")
        sys.exit(1)

    url = sys.argv[1]
    success = solve_for_site(url)

    if success:
        print("\nSuccess! Cookies saved. Your scraper can now use them.")
    else:
        print("\nFailed to save cookies.")
