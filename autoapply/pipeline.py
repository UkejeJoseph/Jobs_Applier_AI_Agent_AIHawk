"""
AutoApply Pipeline
==================
Main orchestrator for the job application pipeline.
Coordinates scraping, filtering, resume generation, and application tracking.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from autoapply.config import (
    USER, RESUME, VISA, JOB_PREFS, APP_SETTINGS, SCRAPERS, LLM,
    Country, ResumeType, LOGS_DIR, GENERATED_RESUMES_DIR,
    get_generated_resume_path
)
from autoapply.core.job_schema import Job, JobStatus, WorkType, JobPriority
from autoapply.core.dedup import JobDatabase, get_database
from autoapply.scrapers import (
    JobBankCanadaScraper,
    UKSponsorList,
    IndeedScraper,
    LinkedInScraper,
    GlassdoorScraper,
    NigeriaRecruitersScraper,
    # ATS Scrapers
    GreenhouseScraper,
    LeverScraper,
    AshbyScraper,
    # Remote Job Boards
    WeWorkRemotelyScraper,
    RemoteOKScraper,
    WellfoundScraper,
    BuiltInScraper,
)

# Auto-apply imports (optional - only if selenium is installed)
try:
    from autoapply.core.auto_apply import AutoApplier, CoverLetterGenerator, ApplicationResult
    AUTO_APPLY_AVAILABLE = True
except ImportError:
    AUTO_APPLY_AVAILABLE = False

# Setup logging
logging.basicConfig(
    level=getattr(logging, APP_SETTINGS.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "autoapply.log") if APP_SETTINGS.log_to_file else logging.NullHandler(),
    ]
)
logger = logging.getLogger("autoapply.pipeline")


@dataclass
class PipelineResult:
    """Result from a pipeline run."""
    jobs_found: int = 0
    jobs_new: int = 0
    jobs_applied: int = 0
    jobs_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "jobs_found": self.jobs_found,
            "jobs_new": self.jobs_new,
            "jobs_applied": self.jobs_applied,
            "jobs_skipped": self.jobs_skipped,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class AutoApplyPipeline:
    """
    Main pipeline orchestrating the entire job application process.

    Pipeline stages:
    1. Scrape jobs from all sources
    2. Filter and deduplicate
    3. Generate tailored resumes and cover letters
    4. Track in database
    5. Export to CSV for UI
    """

    def __init__(self, db: Optional[JobDatabase] = None, auto_apply_enabled: bool = False):
        """Initialize the pipeline."""
        self.db = db or get_database()
        self.uk_sponsors = UKSponsorList()
        self.auto_apply_enabled = auto_apply_enabled and AUTO_APPLY_AVAILABLE
        self.applier: Optional[AutoApplier] = None
        self.cover_letter_gen: Optional[CoverLetterGenerator] = None

        if self.auto_apply_enabled:
            self.applier = AutoApplier(headless=APP_SETTINGS.browser_headless)
            self.cover_letter_gen = CoverLetterGenerator()

        # Initialize scrapers (15+ sources across job boards and ATS systems)
        self.scrapers = {
            Country.CANADA: [
                JobBankCanadaScraper(),  # Official Canadian job bank (LMIA jobs)
                LinkedInScraper(Country.CANADA),
            ],
            Country.US: [
                # Traditional Job Boards
                LinkedInScraper(Country.US),
                IndeedScraper(Country.US),  # Note: requires browser for bot detection
                GlassdoorScraper(Country.US),
                # ATS-based (Greenhouse, Lever, Ashby - scrapes 100+ companies)
                GreenhouseScraper(Country.US),  # Airbnb, Coinbase, Stripe, OpenAI, etc.
                LeverScraper(Country.US),       # Netflix, Twilio, Netlify, etc.
                AshbyScraper(Country.US),       # Notion, Linear, Vercel, etc.
                # Remote Job Boards
                RemoteOKScraper(Country.US),           # Remote tech jobs with salary
                WeWorkRemotelyScraper(Country.US),     # WeWorkRemotely
                BuiltInScraper(Country.US),            # BuiltIn tech jobs
                WellfoundScraper(Country.US),          # Startup jobs (AngelList)
            ],
            Country.UK: [
                LinkedInScraper(Country.UK),
                IndeedScraper(Country.UK),
                GlassdoorScraper(Country.UK),
                GreenhouseScraper(Country.UK),  # UK companies on Greenhouse
                LeverScraper(Country.UK),
            ],
            Country.NIGERIA: [
                NigeriaRecruitersScraper(),  # 40+ Nigerian recruiting companies
                GreenhouseScraper(Country.NIGERIA),  # African unicorns (Paystack, Flutterwave, Andela)
                LeverScraper(Country.NIGERIA),
            ],
        }

        logger.info("AutoApply Pipeline initialized")

    def run(self, countries: List[Country] = None, max_jobs_per_source: int = 50) -> PipelineResult:
        """
        Run the full pipeline.

        Args:
            countries: Countries to scrape (defaults to all)
            max_jobs_per_source: Max jobs per scraper

        Returns:
            PipelineResult with statistics
        """
        result = PipelineResult()

        if countries is None:
            countries = [Country.US, Country.UK, Country.CANADA, Country.NIGERIA]

        logger.info(f"Starting pipeline run for countries: {[c.value for c in countries]}")

        # Check daily application limit
        applied_today = self.db.get_applications_today()
        if applied_today >= APP_SETTINGS.max_applications_per_day:
            logger.warning(f"Daily application limit reached ({applied_today}/{APP_SETTINGS.max_applications_per_day})")
            result.errors.append("Daily application limit reached")
            result.end_time = datetime.now()
            return result

        remaining_applications = APP_SETTINGS.max_applications_per_day - applied_today

        # Load UK sponsor list for cross-referencing
        if Country.UK in countries:
            logger.info("Loading UK sponsor list...")
            self.uk_sponsors.download_sponsor_list()
            self.uk_sponsors.load_sponsors()

        # Stage 1: Scrape jobs from all sources
        logger.info("Stage 1: Scraping jobs...")
        all_jobs = []

        for country in countries:
            if country not in self.scrapers:
                continue

            for scraper in self.scrapers[country]:
                try:
                    scraper_result = scraper.scrape(
                        search_terms=JOB_PREFS.target_titles,
                        max_jobs=max_jobs_per_source
                    )

                    result.jobs_found += scraper_result.total_found

                    # Enrich UK jobs with sponsor verification
                    if country == Country.UK:
                        for job in scraper_result.jobs:
                            if self.uk_sponsors.is_sponsor(job.company):
                                job.visa_sponsored = True
                                if job.work_type == WorkType.ONSITE_NO_VISA:
                                    job.work_type = WorkType.ONSITE_VISA_SPONSORED
                                elif job.work_type == WorkType.REMOTE_NO_VISA:
                                    job.work_type = WorkType.REMOTE_VISA_SPONSORED

                    # Set priority for known sponsor companies
                    from autoapply.config import is_visa_sponsor
                    for job in scraper_result.jobs:
                        if is_visa_sponsor(job.company) and job.priority == JobPriority.TIER_5_UNKNOWN:
                            job.priority = JobPriority.TIER_4_KNOWN_SPONSOR
                        # Recalculate priority based on current data
                        job.priority = job._calculate_priority()
                        # If still unknown but known sponsor, upgrade
                        if job.priority == JobPriority.TIER_5_UNKNOWN and is_visa_sponsor(job.company):
                            job.priority = JobPriority.TIER_4_KNOWN_SPONSOR

                    all_jobs.extend(scraper_result.jobs)
                    result.errors.extend(scraper_result.errors)

                except Exception as e:
                    logger.error(f"Error running scraper {scraper.name}: {e}")
                    result.errors.append(f"Scraper error ({scraper.name}): {str(e)}")

        logger.info(f"Stage 1 complete: Found {len(all_jobs)} jobs")

        # Stage 2: Filter and deduplicate
        logger.info("Stage 2: Filtering and deduplicating...")
        new_jobs = []

        for job in all_jobs:
            # Check if already in database
            if self.db.job_exists(job.job_id):
                continue

            # Apply filters
            if not self._should_apply(job):
                self.db.add_job(job)
                self.db.mark_skipped(job.job_id, "Did not pass filters")
                result.jobs_skipped += 1
                continue

            # Add to database
            if self.db.add_job(job):
                new_jobs.append(job)
                result.jobs_new += 1

        logger.info(f"Stage 2 complete: {len(new_jobs)} new jobs after filtering")

        # Stage 3: Apply to jobs (sorted by priority - best first!)
        logger.info("Stage 3: Applying to jobs...")

        # Sort by priority (highest value first = best opportunities)
        new_jobs.sort(key=lambda j: -j.priority.value)
        jobs_to_apply = new_jobs[:remaining_applications]

        logger.info(f"Jobs to apply (sorted by priority): {len(jobs_to_apply)}")

        for job in jobs_to_apply:
            try:
                # Select appropriate resume
                resume_type = RESUME.select_resume_type(job.role, job.description)
                resume_path = get_generated_resume_path(job.company, job.role, resume_type)

                # Generate cover letter if enabled
                cover_letter = ""
                if APP_SETTINGS.auto_generate_cover_letter and self.cover_letter_gen:
                    cover_letter = self.cover_letter_gen.generate(job, {
                        "full_name": USER.name,
                        "years_experience": USER.years_experience,
                        "current_company": USER.current_company,
                    })

                # Actually apply if auto-apply is enabled
                if self.auto_apply_enabled and self.applier:
                    logger.info(f"Auto-applying to: {job.company} - {job.role}")
                    app_result = self.applier.apply(job, cover_letter)

                    if app_result.success:
                        self.db.mark_applied(
                            job.job_id,
                            resume_used=resume_type.value,
                            cover_letter=bool(cover_letter),
                            resume_path=str(resume_path),
                        )
                        result.jobs_applied += 1
                        logger.info(f"Successfully applied: {job.company} - {job.role}")
                    else:
                        logger.warning(f"Application may have failed: {app_result.error_message}")
                        result.errors.append(f"Application error ({job.company}): {app_result.error_message}")

                    # Delay between applications to avoid detection
                    import time
                    time.sleep(APP_SETTINGS.delay_between_applications_sec)
                else:
                    # Just mark as found (scrape-only mode)
                    self.db.mark_applied(
                        job.job_id,
                        resume_used=resume_type.value,
                        cover_letter=bool(cover_letter),
                        resume_path=str(resume_path),
                    )
                    result.jobs_applied += 1

                logger.info(f"Processed: {job.company} - {job.role}")

            except Exception as e:
                logger.error(f"Error processing job {job.job_id}: {e}")
                result.errors.append(f"Processing error: {str(e)}")

        # Stage 4: Export to CSV
        logger.info("Stage 4: Exporting to CSV...")
        export_results = self.db.export_all_countries(LOGS_DIR)
        for country, count in export_results.items():
            logger.info(f"Exported {count} jobs to {country}_jobs.csv")

        result.end_time = datetime.now()

        # Log summary
        logger.info(f"""
Pipeline run complete:
- Jobs found: {result.jobs_found}
- New jobs: {result.jobs_new}
- Jobs applied: {result.jobs_applied}
- Jobs skipped: {result.jobs_skipped}
- Duration: {result.duration_seconds:.1f}s
- Errors: {len(result.errors)}
        """)

        return result

    def _should_apply(self, job: Job) -> bool:
        """
        Determine if we should apply to a job based on filters.

        Logic:
        - Only exclude jobs with EXPLICIT "no sponsorship" language
        - Include junior/entry/graduate jobs (they CAN sponsor, just less likely)
        - Include on-site and hybrid IF they mention visa sponsorship
        - Always include remote jobs (can work from Nigeria)
        """
        text = f"{job.role} {job.description}".lower()

        # Only exclude jobs that EXPLICITLY say no sponsorship
        for keyword in JOB_PREFS.exclude_keywords:
            if keyword in text:
                logger.debug(f"Excluding {job.company} - {job.role}: explicit no-sponsorship '{keyword}'")
                return False

        # For US/UK/Canada - check visa sponsorship for on-site/hybrid
        if VISA.needs_sponsorship.get(job.country, False):
            # Remote jobs: always OK (can work from Nigeria)
            if job.work_type in [WorkType.REMOTE_VISA_SPONSORED, WorkType.REMOTE_NO_VISA]:
                return True

            # On-site/Hybrid WITH visa sponsorship: OK
            if job.work_type in [WorkType.ONSITE_VISA_SPONSORED, WorkType.HYBRID_VISA_SPONSORED]:
                return True

            # On-site/Hybrid WITHOUT explicit sponsorship: still include if job mentions sponsorship keywords
            if job.visa_sponsored:
                return True

            # Check if description mentions sponsorship (might not be tagged correctly)
            from autoapply.config import matches_visa_keywords, is_visa_sponsor
            if matches_visa_keywords(job.description):
                logger.debug(f"Including {job.company} - {job.role}: found visa keywords in description")
                return True

            # KNOWN SPONSORS (Amazon, Microsoft, Google, etc.) - include regardless!
            # These companies sponsor visas but don't always mention it in postings
            if is_visa_sponsor(job.company):
                logger.debug(f"Including {job.company} - {job.role}: known visa sponsor company")
                return True

            # Unknown company + on-site + no sponsorship mentioned - still include but log it
            # Many companies sponsor but don't advertise it
            logger.debug(f"Including {job.company} - {job.role}: on-site/hybrid, sponsorship unknown - worth trying")
            return True  # Include everything, let the application process filter

        return True

    def run_scrape_only(self, countries: List[Country] = None, max_jobs: int = 50) -> List[Job]:
        """
        Run only the scraping stage without applying.
        Useful for testing and previewing jobs.
        """
        if countries is None:
            countries = [Country.US, Country.UK, Country.CANADA, Country.NIGERIA]

        all_jobs = []

        for country in countries:
            if country not in self.scrapers:
                continue

            for scraper in self.scrapers[country]:
                try:
                    result = scraper.scrape(
                        search_terms=JOB_PREFS.target_titles,
                        max_jobs=max_jobs
                    )
                    all_jobs.extend(result.jobs)
                except Exception as e:
                    logger.error(f"Error in scraper {scraper.name}: {e}")

        return all_jobs

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return self.db.get_stats()

    def export_csvs(self) -> Dict[str, int]:
        """Export all country CSVs."""
        return self.db.export_all_countries(LOGS_DIR)

    def close(self):
        """Clean up resources."""
        if self.applier:
            self.applier.close()

    def run_with_auto_apply(
        self,
        countries: List[Country] = None,
        max_jobs_per_source: int = 30,
    ) -> PipelineResult:
        """
        Run pipeline with actual auto-apply enabled.

        This will:
        1. Scrape jobs from all sources
        2. Filter and deduplicate
        3. Actually submit applications via browser automation
        """
        # Enable auto-apply for this run
        if AUTO_APPLY_AVAILABLE and not self.applier:
            self.applier = AutoApplier(headless=APP_SETTINGS.browser_headless)
            self.cover_letter_gen = CoverLetterGenerator()
            self.auto_apply_enabled = True

        try:
            return self.run(countries, max_jobs_per_source)
        finally:
            self.close()


def run_pipeline():
    """Convenience function to run the pipeline."""
    pipeline = AutoApplyPipeline()
    return pipeline.run()


if __name__ == "__main__":
    result = run_pipeline()
    print(result.to_dict())
