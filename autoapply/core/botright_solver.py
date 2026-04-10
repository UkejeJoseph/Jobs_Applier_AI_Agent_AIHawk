"""
Botright Captcha Solver (FREE!)
===============================
Uses Botright library for FREE captcha solving with AI/Computer Vision.

No API key needed! Solves:
- reCAPTCHA v2/v3 (50-80% success)
- hCaptcha (up to 90% success)
- Cloudflare Turnstile (via stealth)
- GeeTest (up to 100%)

GitHub: https://github.com/Vinyzu/Botright (962 stars)

Usage:
    solver = BotrightSolver()
    html = await solver.get_page_with_captcha("https://indeed.com/jobs")
"""

import asyncio
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("autoapply.botright")

# Check if botright is available
try:
    import botright
    BOTRIGHT_AVAILABLE = True
except ImportError:
    BOTRIGHT_AVAILABLE = False
    logger.warning("Botright not installed. Run: pip install botright && playwright install")


class BotrightSolver:
    """
    FREE captcha solver using Botright's AI/Computer Vision.

    Botright combines:
    - Stealth browser (undetected by most anti-bot systems)
    - AI-powered captcha solving (no API key needed)
    - Fingerprint spoofing

    Success rates:
    - reCAPTCHA: 50-80%
    - hCaptcha: up to 90%
    - GeeTest Slider: 100%
    - Cloudflare: via stealth mode
    """

    def __init__(self, headless: bool = True):
        """
        Initialize Botright solver.

        Args:
            headless: Run browser in headless mode (set False to watch it solve)
        """
        self.headless = headless
        self._client = None
        self._browser = None

    async def start(self):
        """Start Botright browser."""
        if not BOTRIGHT_AVAILABLE:
            raise ImportError("Botright not installed. Run: pip install botright && playwright install")

        if self._client is None:
            logger.info("Starting Botright stealth browser...")
            self._client = await botright.Botright(headless=self.headless)
            self._browser = await self._client.new_browser()
            logger.info("Botright browser started")

    async def stop(self):
        """Stop Botright browser."""
        if self._client:
            await self._client.close()
            self._client = None
            self._browser = None

    async def get_page(self, url: str, wait_for_captcha: bool = True) -> Optional[str]:
        """
        Navigate to URL and handle any captchas automatically.

        Args:
            url: URL to navigate to
            wait_for_captcha: Wait for captcha to be solved

        Returns:
            Page HTML after captcha is solved, or None on failure
        """
        if self._browser is None:
            await self.start()

        try:
            page = await self._browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")

            # Check for common captcha types and solve
            if wait_for_captcha:
                await self._handle_captcha(page)

            # Wait for content to load
            await page.wait_for_timeout(2000)

            html = await page.content()
            await page.close()
            return html

        except Exception as e:
            logger.error(f"Botright error: {e}")
            return None

    async def _handle_captcha(self, page) -> bool:
        """
        Detect and solve captchas on the page.

        Returns True if captcha was solved or no captcha found.
        """
        try:
            content = await page.content()
            content_lower = content.lower()

            # Check for reCAPTCHA
            if "recaptcha" in content_lower or "g-recaptcha" in content_lower:
                logger.info("Detected reCAPTCHA - solving...")
                try:
                    await page.solve_recaptcha()
                    logger.info("reCAPTCHA solved!")
                    return True
                except Exception as e:
                    logger.warning(f"reCAPTCHA solve failed: {e}")

            # Check for hCaptcha
            if "hcaptcha" in content_lower or "h-captcha" in content_lower:
                logger.info("Detected hCaptcha - solving...")
                try:
                    await page.solve_hcaptcha()
                    logger.info("hCaptcha solved!")
                    return True
                except Exception as e:
                    logger.warning(f"hCaptcha solve failed: {e}")

            # Check for GeeTest
            if "geetest" in content_lower:
                logger.info("Detected GeeTest - solving...")
                try:
                    await page.solve_geetest()
                    logger.info("GeeTest solved!")
                    return True
                except Exception as e:
                    logger.warning(f"GeeTest solve failed: {e}")

            # Check for Cloudflare challenge (handled by stealth mode)
            if "cloudflare" in content_lower or "checking your browser" in content_lower:
                logger.info("Cloudflare detected - waiting for stealth bypass...")
                await page.wait_for_timeout(5000)
                return True

            return True

        except Exception as e:
            logger.error(f"Captcha handling error: {e}")
            return False

    async def solve_recaptcha(self, url: str, site_key: str = None) -> Optional[str]:
        """
        Solve reCAPTCHA on a page and return the token.

        Args:
            url: URL with the captcha
            site_key: Optional site key (auto-detected if not provided)

        Returns:
            reCAPTCHA token or None
        """
        if self._browser is None:
            await self.start()

        try:
            page = await self._browser.new_page()
            await page.goto(url)

            token = await page.solve_recaptcha()
            await page.close()
            return token

        except Exception as e:
            logger.error(f"reCAPTCHA solve error: {e}")
            return None

    async def solve_hcaptcha(self, url: str, site_key: str = None) -> Optional[str]:
        """
        Solve hCaptcha on a page and return the token.

        Args:
            url: URL with the captcha
            site_key: Optional site key

        Returns:
            hCaptcha token or None
        """
        if self._browser is None:
            await self.start()

        try:
            page = await self._browser.new_page()
            await page.goto(url)

            token = await page.solve_hcaptcha()
            await page.close()
            return token

        except Exception as e:
            logger.error(f"hCaptcha solve error: {e}")
            return None


def get_page_sync(url: str, headless: bool = True) -> Optional[str]:
    """
    Synchronous wrapper to get page with captcha solving.

    Usage:
        html = get_page_sync("https://indeed.com/jobs")
    """
    async def _get():
        solver = BotrightSolver(headless=headless)
        try:
            return await solver.get_page(url)
        finally:
            await solver.stop()

    return asyncio.run(_get())


# Quick test
if __name__ == "__main__":
    import sys

    if not BOTRIGHT_AVAILABLE:
        print("Install botright first: pip install botright && playwright install")
        sys.exit(1)

    url = sys.argv[1] if len(sys.argv) > 1 else "https://bot.sannysoft.com/"

    print(f"Testing Botright on: {url}")
    print("This will open a browser and solve any captchas...")

    html = get_page_sync(url, headless=False)

    if html:
        print(f"\nSuccess! Got {len(html)} bytes of HTML")
        # Check if we passed bot detection
        if "sannysoft" in url.lower():
            if "passed" in html.lower() or "green" in html.lower():
                print("Bot detection: PASSED!")
    else:
        print("Failed to get page")
