"""
Browser Automation Module
=========================
Handles anti-bot detection using undetected-chromedriver.
Used when regular requests get blocked by captcha/bot protection.

Features:
- Undetected Chrome driver (bypasses Cloudflare, PerimeterX, etc.)
- Stealth mode with realistic fingerprints
- Cookie persistence across sessions
- Automatic captcha detection and waiting
- Proxy support (optional)
"""

import os
import time
import random
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from selenium.common.exceptions import (
        TimeoutException,
        NoSuchElementException,
        WebDriverException,
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    uc = None

from autoapply.config import APP_SETTINGS, LOGS_DIR

logger = logging.getLogger("autoapply.browser")


class BrowserConfig:
    """Configuration for the browser instance."""

    def __init__(
        self,
        headless: bool = True,
        proxy: Optional[str] = None,
        user_data_dir: Optional[Path] = None,
        download_dir: Optional[Path] = None,
        window_size: tuple = (1920, 1080),
        page_load_timeout: int = 30,
        implicit_wait: int = 10,
    ):
        self.headless = headless
        self.proxy = proxy
        self.user_data_dir = user_data_dir or LOGS_DIR / "chrome_profile"
        self.download_dir = download_dir or LOGS_DIR / "downloads"
        self.window_size = window_size
        self.page_load_timeout = page_load_timeout
        self.implicit_wait = implicit_wait


class StealthBrowser:
    """
    Undetected Chrome browser with anti-bot features.

    Usage:
        browser = StealthBrowser()
        browser.start()
        html = browser.get_page("https://example.com")
        browser.stop()

    Or as context manager:
        with StealthBrowser() as browser:
            html = browser.get_page("https://example.com")
    """

    # Common captcha indicators
    CAPTCHA_INDICATORS = [
        "captcha",
        "recaptcha",
        "hcaptcha",
        "challenge",
        "verify you are human",
        "are you a robot",
        "security check",
        "please verify",
        "access denied",
        "blocked",
        "unusual traffic",
    ]

    # Bot detection page indicators
    BOT_DETECTION_INDICATORS = [
        "cloudflare",
        "please wait",
        "checking your browser",
        "ddos protection",
        "just a moment",
        "ray id",
        "attention required",
    ]

    def __init__(self, config: Optional[BrowserConfig] = None):
        if not SELENIUM_AVAILABLE:
            raise ImportError(
                "Selenium/undetected-chromedriver not installed. "
                "Run: pip install undetected-chromedriver selenium"
            )

        self.config = config or BrowserConfig()
        self.driver: Optional[uc.Chrome] = None
        self._started = False

    def start(self) -> "StealthBrowser":
        """Start the browser."""
        if self._started:
            return self

        logger.info("Starting stealth browser...")

        # Ensure directories exist
        self.config.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.config.download_dir.mkdir(parents=True, exist_ok=True)

        # Chrome options
        options = uc.ChromeOptions()

        # Window size
        options.add_argument(f"--window-size={self.config.window_size[0]},{self.config.window_size[1]}")

        # Headless mode (use new headless mode for better stealth)
        if self.config.headless:
            options.add_argument("--headless=new")

        # Disable automation flags
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Performance optimizations
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")

        # Realistic browser settings
        options.add_argument("--lang=en-US,en")
        options.add_argument("--disable-notifications")

        # Download settings
        prefs = {
            "download.default_directory": str(self.config.download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_setting_values.notifications": 2,
        }
        options.add_experimental_option("prefs", prefs)

        # Proxy support
        if self.config.proxy:
            options.add_argument(f"--proxy-server={self.config.proxy}")

        try:
            # Create undetected Chrome driver
            self.driver = uc.Chrome(
                options=options,
                user_data_dir=str(self.config.user_data_dir),
                driver_executable_path=None,  # Auto-download
                version_main=None,  # Auto-detect Chrome version
            )

            # Set timeouts
            self.driver.set_page_load_timeout(self.config.page_load_timeout)
            self.driver.implicitly_wait(self.config.implicit_wait)

            self._started = True
            logger.info("Stealth browser started successfully")

        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            raise

        return self

    def stop(self):
        """Stop the browser."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.debug(f"Error closing browser: {e}")
            finally:
                self.driver = None
                self._started = False
                logger.info("Browser stopped")

    def __enter__(self) -> "StealthBrowser":
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def get_page(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
        wait_timeout: int = 15,
        handle_captcha: bool = True,
    ) -> str:
        """
        Navigate to URL and return page HTML.

        Args:
            url: URL to navigate to
            wait_for_selector: CSS selector to wait for before returning
            wait_timeout: Timeout for waiting
            handle_captcha: If True, wait for captcha pages to resolve

        Returns:
            Page HTML content
        """
        if not self._started:
            self.start()

        logger.debug(f"Navigating to: {url}")

        try:
            self.driver.get(url)

            # Random delay to appear human
            time.sleep(random.uniform(1, 3))

            # Handle bot detection / captcha pages
            if handle_captcha:
                self._handle_bot_detection()

            # Wait for specific element if requested
            if wait_for_selector:
                try:
                    WebDriverWait(self.driver, wait_timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
                    )
                except TimeoutException:
                    logger.warning(f"Timeout waiting for selector: {wait_for_selector}")

            return self.driver.page_source

        except TimeoutException:
            logger.error(f"Page load timeout for: {url}")
            return ""
        except WebDriverException as e:
            logger.error(f"WebDriver error: {e}")
            return ""

    def _handle_bot_detection(self, max_wait: int = 30):
        """
        Wait for bot detection / captcha pages to resolve.

        Some sites (Cloudflare) have a brief challenge that auto-resolves.
        For real captchas, uses captcha solving service if configured.
        """
        start_time = time.time()

        while time.time() - start_time < max_wait:
            page_source = self.driver.page_source
            page_source_lower = page_source.lower()
            title_lower = self.driver.title.lower()

            # Check if we're on a bot detection page
            is_bot_page = any(
                indicator in page_source_lower or indicator in title_lower
                for indicator in self.BOT_DETECTION_INDICATORS
            )

            if not is_bot_page:
                return  # We're past the bot detection

            # Check for captcha that requires solving
            has_captcha = any(
                indicator in page_source_lower
                for indicator in self.CAPTCHA_INDICATORS
            )

            if has_captcha:
                logger.warning("Captcha detected - attempting to solve...")

                # Try to auto-solve using captcha service
                solved = self._solve_captcha(page_source)
                if solved:
                    logger.info("Captcha solved successfully!")
                    time.sleep(2)  # Wait for page to update
                    continue

            time.sleep(2)

        logger.warning("Bot detection page didn't resolve within timeout")

    def _solve_captcha(self, page_source: str) -> bool:
        """
        Attempt to solve captcha using configured service.

        Returns True if captcha was solved successfully.
        """
        try:
            from autoapply.core.captcha_solver import CaptchaDetector, create_solver

            # Detect captcha type
            captcha_info = CaptchaDetector.detect_captcha(page_source, self.driver.current_url)

            if not captcha_info.get("type"):
                logger.debug("No solvable captcha detected")
                return False

            captcha_type = captcha_info["type"]
            site_key = captcha_info.get("site_key")

            if not site_key:
                logger.warning(f"Captcha detected ({captcha_type}) but couldn't find site key")
                return False

            # Get solver (will use env vars for API key)
            solver = create_solver()
            if not solver:
                logger.warning("No captcha solver configured. Set CAPTCHA_2CAPTCHA_API_KEY env var.")
                return False

            # Solve based on type
            result = None
            page_url = self.driver.current_url

            if captcha_type == "recaptcha_v2":
                result = solver.solve_recaptcha_v2(
                    site_key=site_key,
                    page_url=page_url,
                    invisible=captcha_info.get("invisible", False),
                )
            elif captcha_type == "recaptcha_v3":
                result = solver.solve_recaptcha_v3(
                    site_key=site_key,
                    page_url=page_url,
                )
            elif captcha_type == "hcaptcha":
                result = solver.solve_hcaptcha(
                    site_key=site_key,
                    page_url=page_url,
                )
            elif captcha_type == "turnstile":
                result = solver.solve_turnstile(
                    site_key=site_key,
                    page_url=page_url,
                )

            if result and result.success:
                # Inject the token into the page
                return self._inject_captcha_token(captcha_type, result.token)

        except ImportError:
            logger.debug("Captcha solver module not available")
        except Exception as e:
            logger.error(f"Error solving captcha: {e}")

        return False

    def _inject_captcha_token(self, captcha_type: str, token: str) -> bool:
        """
        Inject solved captcha token into the page and submit.
        """
        try:
            if captcha_type in ["recaptcha_v2", "recaptcha_v3"]:
                # Inject into g-recaptcha-response textarea
                script = f"""
                    document.getElementById('g-recaptcha-response').innerHTML = '{token}';
                    if (typeof ___grecaptcha_cfg !== 'undefined') {{
                        Object.keys(___grecaptcha_cfg.clients).forEach(function(key) {{
                            var client = ___grecaptcha_cfg.clients[key];
                            if (client && client.callback) {{
                                client.callback('{token}');
                            }}
                        }});
                    }}
                """
                self.driver.execute_script(script)

            elif captcha_type == "hcaptcha":
                # Inject into h-captcha-response
                script = f"""
                    document.querySelector('[name="h-captcha-response"]').value = '{token}';
                    document.querySelector('[name="g-recaptcha-response"]').value = '{token}';
                    if (typeof hcaptcha !== 'undefined') {{
                        hcaptcha.execute();
                    }}
                """
                self.driver.execute_script(script)

            elif captcha_type == "turnstile":
                # Inject Turnstile token
                script = f"""
                    var input = document.querySelector('[name="cf-turnstile-response"]');
                    if (input) input.value = '{token}';
                    if (typeof turnstile !== 'undefined') {{
                        turnstile.execute();
                    }}
                """
                self.driver.execute_script(script)

            # Try to click submit button if present
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                ".submit-button",
                "#submit",
            ]
            for selector in submit_selectors:
                try:
                    submit_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if submit_btn.is_displayed():
                        submit_btn.click()
                        break
                except NoSuchElementException:
                    continue

            return True

        except Exception as e:
            logger.error(f"Error injecting captcha token: {e}")
            return False

    def click_element(self, selector: str, wait_timeout: int = 10) -> bool:
        """Click an element by CSS selector."""
        try:
            element = WebDriverWait(self.driver, wait_timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            # Human-like click with random offset
            self._human_click(element)
            return True
        except (TimeoutException, NoSuchElementException) as e:
            logger.debug(f"Could not click element {selector}: {e}")
            return False

    def type_text(self, selector: str, text: str, clear_first: bool = True) -> bool:
        """Type text into an input field with human-like delays."""
        try:
            element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )

            if clear_first:
                element.clear()
                time.sleep(random.uniform(0.1, 0.3))

            # Type with human-like delays
            for char in text:
                element.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))

            return True
        except (TimeoutException, NoSuchElementException) as e:
            logger.debug(f"Could not type in element {selector}: {e}")
            return False

    def _human_click(self, element):
        """Click with human-like behavior."""
        from selenium.webdriver.common.action_chains import ActionChains

        actions = ActionChains(self.driver)

        # Move to element with slight offset
        actions.move_to_element_with_offset(
            element,
            random.randint(-5, 5),
            random.randint(-5, 5)
        )

        # Small pause before clicking
        time.sleep(random.uniform(0.1, 0.3))

        actions.click()
        actions.perform()

    def scroll_page(self, pixels: int = 500, smooth: bool = True):
        """Scroll the page down."""
        if smooth:
            # Smooth scroll in increments
            for _ in range(pixels // 100):
                self.driver.execute_script(f"window.scrollBy(0, 100);")
                time.sleep(random.uniform(0.05, 0.15))
        else:
            self.driver.execute_script(f"window.scrollBy(0, {pixels});")

    def get_element_text(self, selector: str) -> str:
        """Get text content of an element."""
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            return element.text
        except NoSuchElementException:
            return ""

    def get_elements(self, selector: str) -> List[Any]:
        """Get all elements matching selector."""
        try:
            return self.driver.find_elements(By.CSS_SELECTOR, selector)
        except NoSuchElementException:
            return []

    def wait_for_url_change(self, current_url: str, timeout: int = 15) -> bool:
        """Wait for URL to change from current."""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.current_url != current_url
            )
            return True
        except TimeoutException:
            return False

    def save_screenshot(self, filename: str = "screenshot.png") -> Path:
        """Save a screenshot for debugging."""
        path = LOGS_DIR / filename
        self.driver.save_screenshot(str(path))
        logger.info(f"Screenshot saved: {path}")
        return path

    def get_cookies(self) -> List[Dict]:
        """Get all cookies."""
        return self.driver.get_cookies()

    def set_cookies(self, cookies: List[Dict]):
        """Set cookies."""
        for cookie in cookies:
            try:
                self.driver.add_cookie(cookie)
            except Exception as e:
                logger.debug(f"Could not set cookie: {e}")

    @property
    def current_url(self) -> str:
        """Get current URL."""
        return self.driver.current_url if self.driver else ""

    @property
    def page_source(self) -> str:
        """Get current page source."""
        return self.driver.page_source if self.driver else ""


class BrowserPool:
    """
    Pool of browser instances for parallel scraping.

    Usage:
        pool = BrowserPool(size=3)
        with pool.get_browser() as browser:
            html = browser.get_page(url)
    """

    def __init__(self, size: int = 2, config: Optional[BrowserConfig] = None):
        self.size = size
        self.config = config
        self._browsers: List[StealthBrowser] = []
        self._available: List[StealthBrowser] = []
        self._lock = None  # Would use threading.Lock() for thread safety

    def _create_browser(self) -> StealthBrowser:
        """Create a new browser instance."""
        browser = StealthBrowser(self.config)
        browser.start()
        self._browsers.append(browser)
        return browser

    @contextmanager
    def get_browser(self):
        """Get a browser from the pool."""
        # Simple implementation - in production would use proper locking
        if self._available:
            browser = self._available.pop()
        elif len(self._browsers) < self.size:
            browser = self._create_browser()
        else:
            # Wait for one to become available (simplified)
            browser = self._create_browser()

        try:
            yield browser
        finally:
            self._available.append(browser)

    def shutdown(self):
        """Shutdown all browsers in the pool."""
        for browser in self._browsers:
            browser.stop()
        self._browsers.clear()
        self._available.clear()


# Singleton browser instance for simple use cases
_default_browser: Optional[StealthBrowser] = None


def get_browser(headless: bool = True) -> StealthBrowser:
    """Get or create the default browser instance."""
    global _default_browser
    if _default_browser is None:
        config = BrowserConfig(headless=headless)
        _default_browser = StealthBrowser(config)
    return _default_browser


def close_browser():
    """Close the default browser instance."""
    global _default_browser
    if _default_browser:
        _default_browser.stop()
        _default_browser = None
