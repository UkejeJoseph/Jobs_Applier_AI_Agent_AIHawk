"""
AutoApply Scheduler
===================
APScheduler-based scheduler to run the pipeline automatically.
"""

import logging
import signal
import sys
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from autoapply.pipeline import AutoApplyPipeline, PipelineResult
from autoapply.config import APP_SETTINGS, LOGS_DIR, Country

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "scheduler.log"),
    ]
)
logger = logging.getLogger("autoapply.scheduler")


class AutoApplyScheduler:
    """
    Scheduler for automated job application runs.

    Features:
    - Runs pipeline every N hours (configurable)
    - Graceful shutdown on SIGINT/SIGTERM
    - Logging of all runs
    """

    def __init__(self, interval_hours: int = None):
        """
        Initialize the scheduler.

        Args:
            interval_hours: Hours between runs (defaults to config)
        """
        self.interval_hours = interval_hours or APP_SETTINGS.run_interval_hours
        self.scheduler = BlockingScheduler()
        self.pipeline = AutoApplyPipeline()
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup graceful shutdown handlers."""
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        """Graceful shutdown handler."""
        logger.info("Shutdown signal received. Stopping scheduler...")
        self.scheduler.shutdown(wait=False)
        sys.exit(0)

    def _run_job(self):
        """Execute the pipeline job."""
        logger.info("=" * 50)
        logger.info(f"Starting scheduled pipeline run at {datetime.now()}")
        logger.info("=" * 50)

        try:
            result = self.pipeline.run()

            logger.info(f"""
Run completed:
- Jobs found: {result.jobs_found}
- New jobs: {result.jobs_new}
- Applied: {result.jobs_applied}
- Skipped: {result.jobs_skipped}
- Duration: {result.duration_seconds:.1f}s
- Errors: {len(result.errors)}
            """)

            if result.errors:
                logger.warning(f"Errors encountered: {result.errors}")

        except Exception as e:
            logger.exception(f"Pipeline run failed: {e}")

    def start(self):
        """Start the scheduler."""
        logger.info(f"Starting AutoApply Scheduler (interval: {self.interval_hours} hours)")

        # Add the job
        self.scheduler.add_job(
            self._run_job,
            trigger=IntervalTrigger(hours=self.interval_hours),
            id="autoapply_pipeline",
            name="AutoApply Pipeline",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping runs
        )

        # Run immediately on start
        logger.info("Running initial pipeline...")
        self._run_job()

        # Start the scheduler
        logger.info("Scheduler started. Press Ctrl+C to stop.")
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped.")

    def run_once(self) -> PipelineResult:
        """Run the pipeline once without scheduling."""
        return self.pipeline.run()


def main():
    """Main entry point for the scheduler."""
    import argparse

    parser = argparse.ArgumentParser(description="AutoApply Job Application Scheduler")
    parser.add_argument(
        "--interval",
        type=int,
        default=APP_SETTINGS.run_interval_hours,
        help=f"Hours between runs (default: {APP_SETTINGS.run_interval_hours})"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (no scheduling)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape only, don't apply"
    )
    parser.add_argument(
        "--country",
        type=str,
        choices=["us", "uk", "canada", "nigeria", "all"],
        default="all",
        help="Country to scrape (default: all)"
    )

    args = parser.parse_args()

    scheduler = AutoApplyScheduler(interval_hours=args.interval)

    if args.dry_run:
        logger.info("Dry run mode - scraping only")
        countries = None
        if args.country != "all":
            country_map = {
                "us": Country.US,
                "uk": Country.UK,
                "canada": Country.CANADA,
                "nigeria": Country.NIGERIA,
            }
            countries = [country_map[args.country]]

        jobs = scheduler.pipeline.run_scrape_only(countries=countries)
        logger.info(f"Found {len(jobs)} jobs:")
        for job in jobs[:20]:  # Show first 20
            logger.info(f"  - {job.company}: {job.role} ({job.location})")

    elif args.once:
        logger.info("Running once...")
        result = scheduler.run_once()
        print(f"Result: {result.to_dict()}")

    else:
        scheduler.start()


if __name__ == "__main__":
    main()
