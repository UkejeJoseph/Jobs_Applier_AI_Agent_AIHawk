"""
AutoApply Core Module
=====================
Core functionality for job deduplication, normalization, and application tracking.
"""

from .job_schema import Job, JobStatus, WorkType
from .dedup import JobDatabase

# Browser automation (optional - requires undetected-chromedriver)
try:
    from .browser import StealthBrowser, BrowserConfig, BrowserPool
    BROWSER_AVAILABLE = True
except ImportError:
    BROWSER_AVAILABLE = False
    StealthBrowser = None
    BrowserConfig = None
    BrowserPool = None

# Captcha solving (optional - requires API key)
try:
    from .captcha_solver import CaptchaSolver, CaptchaDetector, create_solver
    CAPTCHA_AVAILABLE = True
except ImportError:
    CAPTCHA_AVAILABLE = False
    CaptchaSolver = None
    CaptchaDetector = None
    create_solver = None

# Proxy rotation (optional)
try:
    from .proxy_manager import ProxyManager, ProxyRotator, get_proxy_manager, setup_proxies
    PROXY_AVAILABLE = True
except ImportError:
    PROXY_AVAILABLE = False
    ProxyManager = None
    ProxyRotator = None
    get_proxy_manager = None
    setup_proxies = None

__all__ = [
    "Job",
    "JobStatus",
    "WorkType",
    "JobDatabase",
    # Browser
    "StealthBrowser",
    "BrowserConfig",
    "BrowserPool",
    "BROWSER_AVAILABLE",
    # Captcha
    "CaptchaSolver",
    "CaptchaDetector",
    "create_solver",
    "CAPTCHA_AVAILABLE",
    # Proxy
    "ProxyManager",
    "ProxyRotator",
    "get_proxy_manager",
    "setup_proxies",
    "PROXY_AVAILABLE",
]
