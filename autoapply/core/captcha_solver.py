"""
Captcha Solver Module
=====================
Integrates with captcha solving services to bypass reCAPTCHA, hCaptcha, etc.

Supported services:
- 2Captcha (recommended, ~$2.99 per 1000 solves)
- Anti-Captcha (~$2 per 1000 solves)
- CapMonster (self-hosted option)

Usage:
    solver = CaptchaSolver(service="2captcha", api_key="your_key")
    token = solver.solve_recaptcha(site_key, page_url)
"""

import time
import logging
import base64
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass

import requests

logger = logging.getLogger("autoapply.captcha")


class CaptchaService(Enum):
    """Supported captcha solving services."""
    TWO_CAPTCHA = "2captcha"
    ANTI_CAPTCHA = "anti-captcha"
    CAP_MONSTER = "capmonster"


@dataclass
class CaptchaResult:
    """Result from captcha solving."""
    success: bool
    token: str = ""
    error: str = ""
    cost: float = 0.0
    solve_time: float = 0.0


class CaptchaSolver:
    """
    Universal captcha solver supporting multiple services.

    Solves:
    - reCAPTCHA v2 (checkbox and invisible)
    - reCAPTCHA v3
    - hCaptcha
    - Image captchas
    - Text captchas
    - FunCaptcha
    - Turnstile (Cloudflare)
    """

    # API endpoints
    ENDPOINTS = {
        CaptchaService.TWO_CAPTCHA: {
            "submit": "https://2captcha.com/in.php",
            "result": "https://2captcha.com/res.php",
        },
        CaptchaService.ANTI_CAPTCHA: {
            "submit": "https://api.anti-captcha.com/createTask",
            "result": "https://api.anti-captcha.com/getTaskResult",
        },
        CaptchaService.CAP_MONSTER: {
            "submit": "https://api.capmonster.cloud/createTask",
            "result": "https://api.capmonster.cloud/getTaskResult",
        },
    }

    def __init__(
        self,
        service: str = "2captcha",
        api_key: str = "",
        timeout: int = 120,
        poll_interval: int = 5,
    ):
        """
        Initialize captcha solver.

        Args:
            service: Service to use ("2captcha", "anti-captcha", "capmonster")
            api_key: API key for the service
            timeout: Max time to wait for solution (seconds)
            poll_interval: Time between polling for result (seconds)
        """
        self.service = CaptchaService(service)
        self.api_key = api_key
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.session = requests.Session()

        if not api_key:
            logger.warning("No API key provided for captcha solver")

    def solve_recaptcha_v2(
        self,
        site_key: str,
        page_url: str,
        invisible: bool = False,
        data_s: str = "",
    ) -> CaptchaResult:
        """
        Solve reCAPTCHA v2.

        Args:
            site_key: The site key (data-sitekey attribute)
            page_url: URL of the page with captcha
            invisible: True if invisible reCAPTCHA
            data_s: data-s parameter if present

        Returns:
            CaptchaResult with token
        """
        start_time = time.time()

        if self.service == CaptchaService.TWO_CAPTCHA:
            return self._solve_2captcha_recaptcha_v2(
                site_key, page_url, invisible, data_s, start_time
            )
        elif self.service in [CaptchaService.ANTI_CAPTCHA, CaptchaService.CAP_MONSTER]:
            return self._solve_anticaptcha_recaptcha_v2(
                site_key, page_url, invisible, start_time
            )

        return CaptchaResult(success=False, error="Unsupported service")

    def solve_recaptcha_v3(
        self,
        site_key: str,
        page_url: str,
        action: str = "verify",
        min_score: float = 0.3,
    ) -> CaptchaResult:
        """
        Solve reCAPTCHA v3.

        Args:
            site_key: The site key
            page_url: URL of the page
            action: The action parameter
            min_score: Minimum score required (0.1-0.9)

        Returns:
            CaptchaResult with token
        """
        start_time = time.time()

        if self.service == CaptchaService.TWO_CAPTCHA:
            return self._solve_2captcha_recaptcha_v3(
                site_key, page_url, action, min_score, start_time
            )
        elif self.service in [CaptchaService.ANTI_CAPTCHA, CaptchaService.CAP_MONSTER]:
            return self._solve_anticaptcha_recaptcha_v3(
                site_key, page_url, action, min_score, start_time
            )

        return CaptchaResult(success=False, error="Unsupported service")

    def solve_hcaptcha(
        self,
        site_key: str,
        page_url: str,
    ) -> CaptchaResult:
        """
        Solve hCaptcha.

        Args:
            site_key: The site key (data-sitekey)
            page_url: URL of the page

        Returns:
            CaptchaResult with token
        """
        start_time = time.time()

        if self.service == CaptchaService.TWO_CAPTCHA:
            return self._solve_2captcha_hcaptcha(site_key, page_url, start_time)
        elif self.service in [CaptchaService.ANTI_CAPTCHA, CaptchaService.CAP_MONSTER]:
            return self._solve_anticaptcha_hcaptcha(site_key, page_url, start_time)

        return CaptchaResult(success=False, error="Unsupported service")

    def solve_turnstile(
        self,
        site_key: str,
        page_url: str,
    ) -> CaptchaResult:
        """
        Solve Cloudflare Turnstile.

        Args:
            site_key: The site key
            page_url: URL of the page

        Returns:
            CaptchaResult with token
        """
        start_time = time.time()

        if self.service == CaptchaService.TWO_CAPTCHA:
            # 2Captcha uses the same endpoint as hCaptcha for Turnstile
            params = {
                "key": self.api_key,
                "method": "turnstile",
                "sitekey": site_key,
                "pageurl": page_url,
                "json": 1,
            }
            return self._submit_and_wait_2captcha(params, start_time)

        elif self.service in [CaptchaService.ANTI_CAPTCHA, CaptchaService.CAP_MONSTER]:
            task = {
                "type": "TurnstileTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": site_key,
            }
            return self._submit_and_wait_anticaptcha(task, start_time)

        return CaptchaResult(success=False, error="Unsupported service")

    def solve_image_captcha(
        self,
        image_base64: str = "",
        image_path: str = "",
        image_url: str = "",
    ) -> CaptchaResult:
        """
        Solve image-based captcha.

        Args:
            image_base64: Base64 encoded image
            image_path: Path to image file
            image_url: URL of captcha image

        Returns:
            CaptchaResult with text solution
        """
        start_time = time.time()

        # Get base64 image
        if image_path:
            with open(image_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode()
        elif image_url:
            response = self.session.get(image_url)
            image_base64 = base64.b64encode(response.content).decode()

        if not image_base64:
            return CaptchaResult(success=False, error="No image provided")

        if self.service == CaptchaService.TWO_CAPTCHA:
            params = {
                "key": self.api_key,
                "method": "base64",
                "body": image_base64,
                "json": 1,
            }
            return self._submit_and_wait_2captcha(params, start_time)

        elif self.service in [CaptchaService.ANTI_CAPTCHA, CaptchaService.CAP_MONSTER]:
            task = {
                "type": "ImageToTextTask",
                "body": image_base64,
            }
            return self._submit_and_wait_anticaptcha(task, start_time)

        return CaptchaResult(success=False, error="Unsupported service")

    # ==================== 2Captcha Implementation ====================

    def _solve_2captcha_recaptcha_v2(
        self, site_key: str, page_url: str, invisible: bool, data_s: str, start_time: float
    ) -> CaptchaResult:
        """Solve reCAPTCHA v2 using 2Captcha."""
        params = {
            "key": self.api_key,
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": page_url,
            "json": 1,
        }
        if invisible:
            params["invisible"] = 1
        if data_s:
            params["data-s"] = data_s

        return self._submit_and_wait_2captcha(params, start_time)

    def _solve_2captcha_recaptcha_v3(
        self, site_key: str, page_url: str, action: str, min_score: float, start_time: float
    ) -> CaptchaResult:
        """Solve reCAPTCHA v3 using 2Captcha."""
        params = {
            "key": self.api_key,
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": page_url,
            "version": "v3",
            "action": action,
            "min_score": min_score,
            "json": 1,
        }
        return self._submit_and_wait_2captcha(params, start_time)

    def _solve_2captcha_hcaptcha(
        self, site_key: str, page_url: str, start_time: float
    ) -> CaptchaResult:
        """Solve hCaptcha using 2Captcha."""
        params = {
            "key": self.api_key,
            "method": "hcaptcha",
            "sitekey": site_key,
            "pageurl": page_url,
            "json": 1,
        }
        return self._submit_and_wait_2captcha(params, start_time)

    def _submit_and_wait_2captcha(
        self, params: Dict, start_time: float
    ) -> CaptchaResult:
        """Submit task to 2Captcha and wait for result."""
        endpoints = self.ENDPOINTS[CaptchaService.TWO_CAPTCHA]

        try:
            # Submit captcha
            response = self.session.post(endpoints["submit"], data=params)
            data = response.json()

            if data.get("status") != 1:
                return CaptchaResult(
                    success=False,
                    error=data.get("request", "Unknown error"),
                )

            task_id = data["request"]
            logger.info(f"2Captcha task submitted: {task_id}")

            # Poll for result
            result_params = {
                "key": self.api_key,
                "action": "get",
                "id": task_id,
                "json": 1,
            }

            while time.time() - start_time < self.timeout:
                time.sleep(self.poll_interval)

                response = self.session.get(endpoints["result"], params=result_params)
                data = response.json()

                if data.get("status") == 1:
                    solve_time = time.time() - start_time
                    logger.info(f"Captcha solved in {solve_time:.1f}s")
                    return CaptchaResult(
                        success=True,
                        token=data["request"],
                        solve_time=solve_time,
                    )
                elif data.get("request") != "CAPCHA_NOT_READY":
                    return CaptchaResult(
                        success=False,
                        error=data.get("request", "Unknown error"),
                    )

            return CaptchaResult(success=False, error="Timeout waiting for solution")

        except Exception as e:
            logger.error(f"2Captcha error: {e}")
            return CaptchaResult(success=False, error=str(e))

    # ==================== Anti-Captcha/CapMonster Implementation ====================

    def _solve_anticaptcha_recaptcha_v2(
        self, site_key: str, page_url: str, invisible: bool, start_time: float
    ) -> CaptchaResult:
        """Solve reCAPTCHA v2 using Anti-Captcha/CapMonster."""
        task_type = "RecaptchaV2TaskProxyless"
        if invisible:
            task_type = "RecaptchaV2EnterpriseTaskProxyless"

        task = {
            "type": task_type,
            "websiteURL": page_url,
            "websiteKey": site_key,
        }
        return self._submit_and_wait_anticaptcha(task, start_time)

    def _solve_anticaptcha_recaptcha_v3(
        self, site_key: str, page_url: str, action: str, min_score: float, start_time: float
    ) -> CaptchaResult:
        """Solve reCAPTCHA v3 using Anti-Captcha/CapMonster."""
        task = {
            "type": "RecaptchaV3TaskProxyless",
            "websiteURL": page_url,
            "websiteKey": site_key,
            "minScore": min_score,
            "pageAction": action,
        }
        return self._submit_and_wait_anticaptcha(task, start_time)

    def _solve_anticaptcha_hcaptcha(
        self, site_key: str, page_url: str, start_time: float
    ) -> CaptchaResult:
        """Solve hCaptcha using Anti-Captcha/CapMonster."""
        task = {
            "type": "HCaptchaTaskProxyless",
            "websiteURL": page_url,
            "websiteKey": site_key,
        }
        return self._submit_and_wait_anticaptcha(task, start_time)

    def _submit_and_wait_anticaptcha(
        self, task: Dict, start_time: float
    ) -> CaptchaResult:
        """Submit task to Anti-Captcha/CapMonster and wait for result."""
        endpoints = self.ENDPOINTS[self.service]

        try:
            # Submit task
            payload = {
                "clientKey": self.api_key,
                "task": task,
            }
            response = self.session.post(endpoints["submit"], json=payload)
            data = response.json()

            if data.get("errorId", 0) != 0:
                return CaptchaResult(
                    success=False,
                    error=data.get("errorDescription", "Unknown error"),
                )

            task_id = data["taskId"]
            logger.info(f"Anti-Captcha task submitted: {task_id}")

            # Poll for result
            result_payload = {
                "clientKey": self.api_key,
                "taskId": task_id,
            }

            while time.time() - start_time < self.timeout:
                time.sleep(self.poll_interval)

                response = self.session.post(endpoints["result"], json=result_payload)
                data = response.json()

                if data.get("errorId", 0) != 0:
                    return CaptchaResult(
                        success=False,
                        error=data.get("errorDescription", "Unknown error"),
                    )

                if data.get("status") == "ready":
                    solution = data.get("solution", {})
                    token = (
                        solution.get("gRecaptchaResponse") or
                        solution.get("token") or
                        solution.get("text", "")
                    )
                    solve_time = time.time() - start_time
                    logger.info(f"Captcha solved in {solve_time:.1f}s")
                    return CaptchaResult(
                        success=True,
                        token=token,
                        solve_time=solve_time,
                        cost=data.get("cost", 0),
                    )

            return CaptchaResult(success=False, error="Timeout waiting for solution")

        except Exception as e:
            logger.error(f"Anti-Captcha error: {e}")
            return CaptchaResult(success=False, error=str(e))

    def get_balance(self) -> float:
        """Get account balance."""
        try:
            if self.service == CaptchaService.TWO_CAPTCHA:
                response = self.session.get(
                    "https://2captcha.com/res.php",
                    params={"key": self.api_key, "action": "getbalance", "json": 1},
                )
                data = response.json()
                return float(data.get("request", 0))

            elif self.service in [CaptchaService.ANTI_CAPTCHA, CaptchaService.CAP_MONSTER]:
                endpoint = (
                    "https://api.anti-captcha.com/getBalance"
                    if self.service == CaptchaService.ANTI_CAPTCHA
                    else "https://api.capmonster.cloud/getBalance"
                )
                response = self.session.post(
                    endpoint,
                    json={"clientKey": self.api_key},
                )
                data = response.json()
                return float(data.get("balance", 0))

        except Exception as e:
            logger.error(f"Failed to get balance: {e}")

        return 0.0


class CaptchaDetector:
    """
    Detect captcha type from page HTML/URL.
    """

    @staticmethod
    def detect_captcha(html: str, url: str = "") -> Dict[str, Any]:
        """
        Detect what type of captcha is on a page.

        Returns:
            Dict with captcha info: {"type": "recaptcha_v2", "site_key": "..."}
        """
        result = {"type": None, "site_key": None}

        html_lower = html.lower()

        # reCAPTCHA v2/v3
        if "recaptcha" in html_lower or "grecaptcha" in html_lower:
            import re

            # Try to find site key
            patterns = [
                r'data-sitekey=["\']([^"\']+)["\']',
                r'grecaptcha\.render\([^,]+,\s*{\s*["\']?sitekey["\']?\s*:\s*["\']([^"\']+)["\']',
                r'sitekey:\s*["\']([^"\']+)["\']',
            ]

            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    result["site_key"] = match.group(1)
                    break

            # Detect version
            if "grecaptcha.execute" in html or "recaptcha/api.js?render=" in html:
                result["type"] = "recaptcha_v3"
            else:
                result["type"] = "recaptcha_v2"

            # Check if invisible
            if "invisible" in html_lower:
                result["invisible"] = True

        # hCaptcha
        elif "hcaptcha" in html_lower:
            import re
            result["type"] = "hcaptcha"

            match = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
            if match:
                result["site_key"] = match.group(1)

        # Cloudflare Turnstile
        elif "turnstile" in html_lower or "challenges.cloudflare.com" in html_lower:
            import re
            result["type"] = "turnstile"

            match = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
            if match:
                result["site_key"] = match.group(1)

        # Image captcha (generic)
        elif "captcha" in html_lower:
            result["type"] = "image"

        return result


# Convenience function
def create_solver(
    service: str = "2captcha",
    api_key: str = None,
) -> Optional[CaptchaSolver]:
    """
    Create a captcha solver with config from environment or settings.

    Args:
        service: Service name
        api_key: API key (or reads from env)

    Returns:
        CaptchaSolver instance or None
    """
    import os

    if api_key is None:
        # Try to get from environment
        env_vars = {
            "2captcha": "CAPTCHA_2CAPTCHA_API_KEY",
            "anti-captcha": "CAPTCHA_ANTICAPTCHA_API_KEY",
            "capmonster": "CAPTCHA_CAPMONSTER_API_KEY",
        }
        api_key = os.environ.get(env_vars.get(service, ""), "")

    if not api_key:
        logger.warning(f"No API key found for {service}")
        return None

    return CaptchaSolver(service=service, api_key=api_key)
