"""
AutoApply Scrapers
==================
Job scrapers for multiple sources across US, UK, Canada, and Nigeria.

Includes:
- Job Boards: Indeed, LinkedIn, Glassdoor, WeWorkRemotely, RemoteOK, BuiltIn
- ATS Systems: Greenhouse, Lever, Ashby
- Country-specific: JobBank Canada, UK Sponsor List, Nigeria Recruiters
- Startup focused: Wellfound (AngelList)
"""

from .base import BaseScraper, ScraperResult
from .jobbank_canada import JobBankCanadaScraper
from .uk_sponsors import UKSponsorList
from .indeed import IndeedScraper
from .linkedin import LinkedInScraper
from .glassdoor import GlassdoorScraper
from .nigeria import NigeriaRecruitersScraper

# ATS-based scrapers
from .greenhouse import GreenhouseScraper, LeverScraper, AshbyScraper

# Remote job boards
from .remote_boards import (
    WeWorkRemotelyScraper,
    RemoteOKScraper,
    WellfoundScraper,
    BuiltInScraper,
    HackerNewsScraper,
)

__all__ = [
    # Base
    "BaseScraper",
    "ScraperResult",
    # Traditional Job Boards
    "IndeedScraper",
    "LinkedInScraper",
    "GlassdoorScraper",
    # ATS Scrapers (Greenhouse, Lever, Ashby)
    "GreenhouseScraper",
    "LeverScraper",
    "AshbyScraper",
    # Remote Job Boards
    "WeWorkRemotelyScraper",
    "RemoteOKScraper",
    "WellfoundScraper",
    "BuiltInScraper",
    "HackerNewsScraper",
    # Country-Specific
    "JobBankCanadaScraper",
    "UKSponsorList",
    "NigeriaRecruitersScraper",
]
