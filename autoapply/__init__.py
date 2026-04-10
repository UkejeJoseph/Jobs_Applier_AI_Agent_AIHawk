"""
AutoApply - AI-Powered Job Application Bot
==========================================

Automated job scraping, filtering, and application for:
- USA (H1B visa sponsorship)
- UK (Skilled Worker visa)
- Canada (LMIA-approved employers)
- Nigeria (Remote jobs from recruiting firms)

Features:
- Multi-source job scraping (Indeed, LinkedIn, Glassdoor, Job Bank, etc.)
- Intelligent visa sponsorship detection
- Resume tailoring per job using AI
- Cover letter generation using Claude
- Deduplication to prevent double applications
- CSV export for UI tracking (12 columns per job)
"""

__version__ = "1.0.0"
__author__ = "Joseph Ukeje"

from .config import (
    USER,
    RESUME,
    VISA,
    JOB_PREFS,
    APP_SETTINGS,
    SCRAPERS,
    LLM,
    Country,
    ResumeType,
    WorkType,
)

from .core import Job, JobStatus, JobDatabase

__all__ = [
    "USER",
    "RESUME",
    "VISA",
    "JOB_PREFS",
    "APP_SETTINGS",
    "SCRAPERS",
    "LLM",
    "Country",
    "ResumeType",
    "WorkType",
    "Job",
    "JobStatus",
    "JobDatabase",
]
