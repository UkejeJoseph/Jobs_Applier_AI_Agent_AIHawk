#!/usr/bin/env python3
"""
AutoApply CLI
=============
Command-line interface for the AutoApply job application bot.

Usage:
    python -m autoapply.cli run              # Run pipeline once
    python -m autoapply.cli schedule         # Start scheduler (runs every 4 hours)
    python -m autoapply.cli scrape           # Scrape only (preview jobs)
    python -m autoapply.cli stats            # Show statistics
    python -m autoapply.cli export           # Export CSVs
"""

import argparse
import sys
from datetime import datetime

from autoapply.config import (
    USER, APP_SETTINGS, LOGS_DIR,
    Country
)


def cmd_run(args):
    """Run the pipeline once."""
    from autoapply.pipeline import AutoApplyPipeline

    print(f"Running AutoApply pipeline for {USER.name}...")
    print(f"Max applications today: {APP_SETTINGS.max_applications_per_day}")
    print(f"Auto-apply: {'ENABLED' if args.auto_apply else 'DISABLED (scrape only)'}")
    print("-" * 50)

    countries = None
    if args.country != "all":
        country_map = {
            "us": Country.US,
            "uk": Country.UK,
            "canada": Country.CANADA,
            "nigeria": Country.NIGERIA,
        }
        countries = [country_map[args.country]]
        print(f"Targeting: {args.country.upper()}")

    pipeline = AutoApplyPipeline(auto_apply_enabled=args.auto_apply)

    try:
        result = pipeline.run(countries=countries, max_jobs_per_source=args.max_jobs)
    finally:
        pipeline.close()

    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)
    print(f"Jobs found:   {result.jobs_found}")
    print(f"New jobs:     {result.jobs_new}")
    print(f"Applied:      {result.jobs_applied}")
    print(f"Skipped:      {result.jobs_skipped}")
    print(f"Duration:     {result.duration_seconds:.1f}s")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for err in result.errors[:5]:
            print(f"  - {err}")

    print(f"\nCSV exports saved to: {LOGS_DIR}")


def cmd_schedule(args):
    """Start the scheduler."""
    from autoapply.scheduler import AutoApplyScheduler

    print(f"Starting AutoApply Scheduler")
    print(f"Interval: {args.interval} hours")
    print(f"Max applications/day: {APP_SETTINGS.max_applications_per_day}")
    print("-" * 50)
    print("Press Ctrl+C to stop\n")

    scheduler = AutoApplyScheduler(interval_hours=args.interval)
    scheduler.start()


def cmd_scrape(args):
    """Scrape jobs without applying (preview mode)."""
    from autoapply.pipeline import AutoApplyPipeline

    print(f"Scraping jobs (preview mode)...")
    print("-" * 50)

    countries = None
    if args.country != "all":
        country_map = {
            "us": Country.US,
            "uk": Country.UK,
            "canada": Country.CANADA,
            "nigeria": Country.NIGERIA,
        }
        countries = [country_map[args.country]]

    pipeline = AutoApplyPipeline()
    jobs = pipeline.run_scrape_only(countries=countries, max_jobs=args.max_jobs)

    print(f"\nFound {len(jobs)} jobs:\n")

    # Group by country
    by_country = {}
    for job in jobs:
        country = job.country.value
        if country not in by_country:
            by_country[country] = []
        by_country[country].append(job)

    for country, country_jobs in by_country.items():
        print(f"\n--- {country} ({len(country_jobs)} jobs) ---")
        for job in country_jobs[:10]:
            visa = "V" if job.visa_sponsored else " "
            remote = "R" if "remote" in job.work_type.value.lower() else "O"
            print(f"  [{visa}][{remote}] {job.company}: {job.role}")
            print(f"        {job.location} | {job.pay_range}")

        if len(country_jobs) > 10:
            print(f"  ... and {len(country_jobs) - 10} more")


def cmd_stats(args):
    """Show statistics."""
    from autoapply.core.dedup import get_database

    db = get_database()
    stats = db.get_stats()

    print("\nAutoApply Statistics")
    print("=" * 50)
    print(f"Total jobs tracked: {stats.get('total_jobs', 0)}")
    print(f"Visa sponsored:     {stats.get('visa_sponsored', 0)}")
    print(f"Applied today:      {stats.get('applied_today', 0)}")

    print("\nBy Country:")
    for country, count in stats.get('by_country', {}).items():
        print(f"  {country}: {count}")

    print("\nBy Status:")
    for status, count in stats.get('by_status', {}).items():
        print(f"  {status}: {count}")


def cmd_export(args):
    """Export to CSV files."""
    from autoapply.pipeline import AutoApplyPipeline

    print("Exporting to CSV files...")

    pipeline = AutoApplyPipeline()
    results = pipeline.export_csvs()

    print("\nExported:")
    for country, count in results.items():
        print(f"  {country}_jobs.csv: {count} jobs")

    print(f"\nFiles saved to: {LOGS_DIR}")


def cmd_test(args):
    """Test scraper connections."""
    print("Testing scraper connections...\n")

    from autoapply.scrapers import (
        JobBankCanadaScraper,
        IndeedScraper,
        LinkedInScraper,
        GlassdoorScraper,
        NigeriaRecruitersScraper,
    )

    scrapers = [
        ("Job Bank Canada", JobBankCanadaScraper()),
        ("Indeed US", IndeedScraper(Country.US)),
        ("LinkedIn US", LinkedInScraper(Country.US)),
        ("Glassdoor US", GlassdoorScraper(Country.US)),
        ("Nigeria Recruiters", NigeriaRecruitersScraper()),
    ]

    for name, scraper in scrapers:
        print(f"Testing {name}...", end=" ")
        try:
            result = scraper.scrape(search_terms=["Software Engineer"], max_jobs=3)
            if result.jobs:
                print(f"OK ({len(result.jobs)} jobs)")
            else:
                print(f"No jobs found (may be OK)")
        except Exception as e:
            print(f"FAILED: {e}")


def cmd_apply(args):
    """Apply to pending jobs using browser automation."""
    from autoapply.core.dedup import get_database
    from autoapply.core.job_schema import JobStatus

    print(f"Auto-Apply Mode")
    print(f"Applying to up to {args.limit} pending jobs...")
    print("-" * 50)

    try:
        from autoapply.core.auto_apply import AutoApplier, CoverLetterGenerator
    except ImportError:
        print("Error: Auto-apply requires selenium and undetected-chromedriver")
        print("Install with: pip install selenium undetected-chromedriver")
        return

    db = get_database()

    # Get pending jobs (status = Found)
    country_map = {
        "us": Country.US,
        "uk": Country.UK,
        "canada": Country.CANADA,
        "nigeria": Country.NIGERIA,
    }

    if args.country == "all":
        countries = list(country_map.values())
    else:
        countries = [country_map[args.country]]

    pending_jobs = []
    for country in countries:
        jobs = db.get_jobs_by_country(country, limit=100)
        pending_jobs.extend([j for j in jobs if j.status == JobStatus.FOUND])

    if not pending_jobs:
        print("No pending jobs to apply to.")
        print("Run 'python -m autoapply.cli scrape' first to find jobs.")
        return

    print(f"Found {len(pending_jobs)} pending jobs")
    jobs_to_apply = pending_jobs[:args.limit]
    print(f"Will apply to {len(jobs_to_apply)} jobs")
    print()

    applier = AutoApplier(headless=args.headless)
    cover_gen = CoverLetterGenerator()

    applied = 0
    failed = 0

    try:
        for i, job in enumerate(jobs_to_apply, 1):
            print(f"[{i}/{len(jobs_to_apply)}] {job.company} - {job.role}")

            # Generate cover letter
            cover_letter = cover_gen.generate(job, {
                "full_name": USER.name,
                "years_experience": USER.years_experience,
                "current_company": USER.current_company,
            })

            # Apply
            result = applier.apply(job, cover_letter)

            if result.success:
                print(f"  SUCCESS - Applied via {result.ats_type.value}")
                db.mark_applied(job.job_id, resume_used="default", cover_letter=True)
                applied += 1
            else:
                print(f"  FAILED - {result.error_message}")
                failed += 1

            # Delay between applications
            import time
            if i < len(jobs_to_apply):
                delay = APP_SETTINGS.delay_between_applications_sec
                print(f"  Waiting {delay}s before next application...")
                time.sleep(delay)

    finally:
        applier.close()

    print()
    print("=" * 50)
    print(f"Applied:  {applied}")
    print(f"Failed:   {failed}")
    print("=" * 50)


def cmd_ui(args):
    """Start the web dashboard."""
    from autoapply.ui.app import run_server
    run_server(host=args.host, port=args.port, debug=args.debug)


def cmd_proxy(args):
    """Manage and test proxies."""
    from autoapply.core.proxy_manager import (
        ProxyManager, ProxyProvider, get_proxy_manager, setup_proxies
    )

    manager = get_proxy_manager()

    if args.action == "add":
        if args.proxy:
            manager.add_proxies(args.proxy.split(","))
            print(f"Added {len(args.proxy.split(','))} proxies")
        elif args.provider:
            try:
                provider = ProxyProvider(args.provider)
                manager.add_from_provider(provider, args.country, args.count)
                print(f"Added proxies from {args.provider}")
            except ValueError:
                print(f"Unknown provider: {args.provider}")
                print("Supported: bright_data, oxylabs, smartproxy, webshare")
        elif args.free:
            manager.load_free_proxies(args.count)
            print("Loaded free proxies (these may be unreliable)")
        else:
            print("Specify --proxy, --provider, or --free")

    elif args.action == "test":
        print("Testing proxy health...")
        if not manager.has_proxies:
            print("No proxies configured. Use 'proxy add' first.")
            return
        results = manager.health_check_all(timeout=10)
        print(f"\nResults:")
        print(f"  Healthy:   {results['healthy']}")
        print(f"  Unhealthy: {results['unhealthy']}")

    elif args.action == "stats":
        stats = manager.get_stats()
        print("\nProxy Pool Statistics")
        print("=" * 40)
        print(f"Total proxies:     {stats['total']}")
        print(f"Available:         {stats['available']}")
        print(f"Blacklisted:       {stats['blacklisted']}")
        print(f"Avg success rate:  {stats['avg_success_rate']}%")

        if stats['by_provider']:
            print("\nBy Provider:")
            for provider, count in stats['by_provider'].items():
                print(f"  {provider}: {count}")

        if stats['by_country']:
            print("\nBy Country:")
            for country, count in stats['by_country'].items():
                print(f"  {country}: {count}")

    elif args.action == "clear":
        manager.remove_blacklisted()
        print("Removed blacklisted proxies")

    else:
        print(f"Unknown action: {args.action}")


def cmd_email(args):
    """Manage email tracking."""
    from autoapply.core.email_tracker import (
        GmailIMAPClient, EmailTracker, setup_gmail, get_email_setup_instructions
    )
    from autoapply.core.dedup import get_database
    import os

    if args.action == "setup":
        print(get_email_setup_instructions())
        print("\nEnter your Gmail credentials:")
        email_addr = input("Gmail address: ").strip()
        app_password = input("App Password (16 chars): ").strip()

        if setup_gmail(email_addr, app_password):
            print("\nConnection successful!")
            print("\nTo save credentials, run:")
            print(f'  set GMAIL_EMAIL={email_addr}')
            print(f'  set GMAIL_APP_PASSWORD={app_password}')
        else:
            print("\nConnection failed. Check your credentials.")

    elif args.action == "sync":
        gmail_email = os.environ.get("GMAIL_EMAIL")
        gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

        if not gmail_email or not gmail_password:
            print("Gmail credentials not set. Run: python -m autoapply.cli email setup")
            return

        print(f"Syncing emails for {gmail_email}...")
        db = get_database()
        client = GmailIMAPClient(gmail_email, gmail_password)
        tracker = EmailTracker(db, client)

        with client:
            stats = tracker.sync_emails(days_back=30)

        print("\nSync complete!")
        for category, count in stats.items():
            if count > 0:
                print(f"  {category}: {count}")

    elif args.action == "test":
        gmail_email = os.environ.get("GMAIL_EMAIL")
        gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

        if not gmail_email or not gmail_password:
            print("Gmail credentials not set.")
            print("Run: python -m autoapply.cli email setup")
            return

        print(f"Testing connection to {gmail_email}...")
        if setup_gmail(gmail_email, gmail_password):
            print("Connection successful!")
        else:
            print("Connection failed.")


def cmd_captcha(args):
    """Test captcha solving service."""
    from autoapply.core.captcha_solver import create_solver

    solver = create_solver(args.service)
    if not solver:
        print(f"No API key configured for {args.service}")
        print(f"Set environment variable: CAPTCHA_{args.service.upper().replace('-', '_')}_API_KEY")
        return

    print(f"Testing {args.service} captcha solver...")

    # Check balance
    balance = solver.get_balance()
    print(f"Account balance: ${balance:.2f}")

    if balance < 0.01:
        print("Warning: Low balance. Add funds to your account.")


def main():
    parser = argparse.ArgumentParser(
        description="AutoApply - AI Job Application Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m autoapply.cli run                    # Run once
  python -m autoapply.cli run --country us       # Run for US only
  python -m autoapply.cli schedule               # Start scheduler
  python -m autoapply.cli scrape --country uk    # Preview UK jobs
  python -m autoapply.cli stats                  # Show statistics
  python -m autoapply.cli export                 # Export CSVs
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run pipeline once")
    run_parser.add_argument(
        "--country", "-c",
        choices=["us", "uk", "canada", "nigeria", "all"],
        default="all",
        help="Country to target"
    )
    run_parser.add_argument(
        "--max-jobs", "-m",
        type=int,
        default=50,
        help="Max jobs per scraper"
    )
    run_parser.add_argument(
        "--auto-apply", "-a",
        action="store_true",
        help="Enable auto-apply (actually submit applications via browser)"
    )
    run_parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)"
    )
    run_parser.set_defaults(func=cmd_run)

    # Apply command (apply to specific jobs)
    apply_parser = subparsers.add_parser("apply", help="Apply to pending jobs")
    apply_parser.add_argument(
        "--country", "-c",
        choices=["us", "uk", "canada", "nigeria", "all"],
        default="all",
        help="Country to target"
    )
    apply_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="Max applications (default: 10)"
    )
    apply_parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode"
    )
    apply_parser.set_defaults(func=cmd_apply)

    # Schedule command
    schedule_parser = subparsers.add_parser("schedule", help="Start scheduler")
    schedule_parser.add_argument(
        "--interval", "-i",
        type=int,
        default=APP_SETTINGS.run_interval_hours,
        help=f"Hours between runs (default: {APP_SETTINGS.run_interval_hours})"
    )
    schedule_parser.set_defaults(func=cmd_schedule)

    # Scrape command (preview)
    scrape_parser = subparsers.add_parser("scrape", help="Scrape only (preview)")
    scrape_parser.add_argument(
        "--country", "-c",
        choices=["us", "uk", "canada", "nigeria", "all"],
        default="all",
        help="Country to target"
    )
    scrape_parser.add_argument(
        "--max-jobs", "-m",
        type=int,
        default=20,
        help="Max jobs per scraper"
    )
    scrape_parser.set_defaults(func=cmd_scrape)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # Export command
    export_parser = subparsers.add_parser("export", help="Export CSVs")
    export_parser.set_defaults(func=cmd_export)

    # Test command
    test_parser = subparsers.add_parser("test", help="Test scraper connections")
    test_parser.set_defaults(func=cmd_test)

    # UI command
    ui_parser = subparsers.add_parser("ui", help="Start web dashboard")
    ui_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    ui_parser.add_argument(
        "--port", "-p",
        type=int,
        default=5000,
        help="Port to run on (default: 5000)"
    )
    ui_parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode"
    )
    ui_parser.set_defaults(func=cmd_ui)

    # Proxy command
    proxy_parser = subparsers.add_parser("proxy", help="Manage proxies")
    proxy_parser.add_argument(
        "action",
        choices=["add", "test", "stats", "clear"],
        help="Action: add, test, stats, or clear"
    )
    proxy_parser.add_argument(
        "--proxy", "-p",
        help="Comma-separated proxy URLs (http://user:pass@host:port)"
    )
    proxy_parser.add_argument(
        "--provider",
        choices=["bright_data", "oxylabs", "smartproxy", "webshare"],
        help="Proxy provider to use"
    )
    proxy_parser.add_argument(
        "--free",
        action="store_true",
        help="Load free proxies (less reliable)"
    )
    proxy_parser.add_argument(
        "--country",
        default="us",
        help="Country for geo-targeting (default: us)"
    )
    proxy_parser.add_argument(
        "--count", "-n",
        type=int,
        default=10,
        help="Number of proxies to add (default: 10)"
    )
    proxy_parser.set_defaults(func=cmd_proxy)

    # Email command
    email_parser = subparsers.add_parser("email", help="Manage email tracking")
    email_parser.add_argument(
        "action",
        choices=["setup", "sync", "test"],
        help="Action: setup, sync, or test"
    )
    email_parser.set_defaults(func=cmd_email)

    # Captcha command
    captcha_parser = subparsers.add_parser("captcha", help="Test captcha solver")
    captcha_parser.add_argument(
        "--service", "-s",
        choices=["2captcha", "anti-captcha", "capmonster"],
        default="2captcha",
        help="Captcha service to test (default: 2captcha)"
    )
    captcha_parser.set_defaults(func=cmd_captcha)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
