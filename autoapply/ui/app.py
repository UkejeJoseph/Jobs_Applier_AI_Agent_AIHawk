"""
AutoApply Web Dashboard
=======================
Flask-based web UI for viewing and managing job applications.
Similar to Sprout.com interface with separate tables per country.
"""

import os
import threading
from datetime import datetime
from pathlib import Path

# Load .env file if exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed

from flask import Flask, render_template, jsonify, request, redirect, url_for

from autoapply.core.dedup import JobDatabase, get_database
from autoapply.core.job_schema import Job, JobStatus, Country, WorkType, JobPriority
from autoapply.config import APP_SETTINGS, LOGS_DIR, USER

# Scraping state
scraping_state = {
    "is_running": False,
    "status": "idle",
    "progress": 0,
    "jobs_found": 0,
    "errors": [],
    "complete": False,
}


def create_app(db: JobDatabase = None) -> Flask:
    """Create and configure the Flask application."""

    app = Flask(__name__,
                template_folder=str(Path(__file__).parent / "templates"),
                static_folder=str(Path(__file__).parent / "static"))

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "autoapply-secret-key")

    # Store database instance
    app.db = db or get_database()

    # ==========================================================================
    # ROUTES
    # ==========================================================================

    @app.route("/")
    def index():
        """Dashboard home page."""
        stats = app.db.get_stats()
        return render_template("index.html",
                               user=USER,
                               stats=stats,
                               now=datetime.now())

    @app.route("/jobs")
    def jobs_all():
        """All jobs view."""
        return redirect(url_for("jobs_by_country", country="all"))

    @app.route("/jobs/<country>")
    def jobs_by_country(country: str):
        """Jobs filtered by country."""
        # Get filter parameters
        status_filter = request.args.get("status", "all")
        visa_filter = request.args.get("visa", "all")
        work_type_filter = request.args.get("work_type", "all")
        search = request.args.get("search", "")

        # Get jobs from database
        if country == "all":
            jobs = []
            for c in [Country.US, Country.UK, Country.CANADA, Country.NIGERIA]:
                jobs.extend(app.db.get_jobs_by_country(c, limit=500))
        else:
            country_enum = {
                "us": Country.US,
                "uk": Country.UK,
                "canada": Country.CANADA,
                "nigeria": Country.NIGERIA,
            }.get(country.lower())

            if country_enum:
                jobs = app.db.get_jobs_by_country(country_enum, limit=500)
            else:
                jobs = []

        # Apply filters
        if status_filter != "all":
            jobs = [j for j in jobs if j.status.value.lower() == status_filter.lower()]

        if visa_filter == "yes":
            jobs = [j for j in jobs if j.visa_sponsored]
        elif visa_filter == "no":
            jobs = [j for j in jobs if not j.visa_sponsored]

        if work_type_filter != "all":
            jobs = [j for j in jobs if work_type_filter.lower() in j.work_type.value.lower()]

        if search:
            search_lower = search.lower()
            jobs = [j for j in jobs if
                    search_lower in j.company.lower() or
                    search_lower in j.role.lower() or
                    search_lower in j.location.lower()]

        return render_template("jobs.html",
                               jobs=jobs,
                               country=country,
                               status_filter=status_filter,
                               visa_filter=visa_filter,
                               work_type_filter=work_type_filter,
                               search=search,
                               user=USER)

    @app.route("/jobs/us")
    def jobs_us():
        """US jobs table."""
        return redirect(url_for("jobs_by_country", country="us"))

    @app.route("/jobs/uk")
    def jobs_uk():
        """UK jobs table."""
        return redirect(url_for("jobs_by_country", country="uk"))

    @app.route("/jobs/canada")
    def jobs_canada():
        """Canada jobs table."""
        return redirect(url_for("jobs_by_country", country="canada"))

    @app.route("/jobs/nigeria")
    def jobs_nigeria():
        """Nigeria jobs table."""
        return redirect(url_for("jobs_by_country", country="nigeria"))

    @app.route("/jobs/ranked")
    def jobs_ranked():
        """Jobs ranked by priority - best opportunities first."""
        from autoapply.core.job_schema import JobPriority
        from autoapply.config import is_visa_sponsor

        # Get filter parameters
        priority_filter = request.args.get("priority", "all")
        visa_filter = request.args.get("visa", "all")
        work_type_filter = request.args.get("work_type", "all")
        country_filter = request.args.get("country", "all")
        search = request.args.get("search", "")

        # Get all jobs
        jobs = []
        for c in [Country.US, Country.UK, Country.CANADA, Country.NIGERIA]:
            jobs.extend(app.db.get_jobs_by_country(c, limit=500))

        # Update priorities for known sponsors (Tier 4)
        for job in jobs:
            if is_visa_sponsor(job.company) and job.priority == JobPriority.TIER_5_UNKNOWN:
                job.priority = JobPriority.TIER_4_KNOWN_SPONSOR

        # Apply filters
        if priority_filter != "all":
            jobs = [j for j in jobs if str(j.priority.value) == priority_filter]

        if visa_filter == "yes":
            jobs = [j for j in jobs if j.visa_sponsored]
        elif visa_filter == "no":
            jobs = [j for j in jobs if not j.visa_sponsored]

        if work_type_filter == "remote":
            jobs = [j for j in jobs if "remote" in j.work_type.value.lower()]
        elif work_type_filter == "onsite":
            jobs = [j for j in jobs if "on-site" in j.work_type.value.lower()]
        elif work_type_filter == "hybrid":
            jobs = [j for j in jobs if "hybrid" in j.work_type.value.lower()]

        if country_filter != "all":
            country_map = {"us": Country.US, "uk": Country.UK, "canada": Country.CANADA, "nigeria": Country.NIGERIA}
            if country_filter in country_map:
                jobs = [j for j in jobs if j.country == country_map[country_filter]]

        if search:
            search_lower = search.lower()
            jobs = [j for j in jobs if
                    search_lower in j.company.lower() or
                    search_lower in j.role.lower() or
                    search_lower in j.location.lower()]

        # Sort by priority (highest first), then by date found (newest first)
        jobs.sort(key=lambda j: (-j.priority.value, j.date_found), reverse=False)

        return render_template("ranked.html",
                               jobs=jobs,
                               priority_filter=priority_filter,
                               visa_filter=visa_filter,
                               work_type_filter=work_type_filter,
                               country_filter=country_filter,
                               search=search,
                               user=USER)

    @app.route("/api/jobs")
    def api_jobs():
        """API endpoint for jobs data (for AJAX tables)."""
        country = request.args.get("country", "all")
        limit = int(request.args.get("limit", 100))

        if country == "all":
            jobs = []
            for c in [Country.US, Country.UK, Country.CANADA, Country.NIGERIA]:
                jobs.extend(app.db.get_jobs_by_country(c, limit=limit))
        else:
            country_enum = {
                "us": Country.US,
                "uk": Country.UK,
                "canada": Country.CANADA,
                "nigeria": Country.NIGERIA,
            }.get(country.lower())

            jobs = app.db.get_jobs_by_country(country_enum, limit=limit) if country_enum else []

        return jsonify({
            "jobs": [j.to_csv_row() for j in jobs],
            "total": len(jobs)
        })

    @app.route("/api/stats")
    def api_stats():
        """API endpoint for statistics."""
        return jsonify(app.db.get_stats())

    @app.route("/api/job/<job_id>/status", methods=["POST"])
    def update_job_status(job_id: str):
        """Update job status."""
        data = request.get_json()
        new_status = data.get("status")

        try:
            status_enum = JobStatus(new_status)
            app.db.update_status(job_id, status_enum)
            return jsonify({"success": True})
        except (ValueError, Exception) as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/stats")
    def stats():
        """Statistics page."""
        stats = app.db.get_stats()
        return render_template("stats.html", stats=stats, user=USER)

    @app.route("/export")
    def export():
        """Export jobs to CSV."""
        results = app.db.export_all_countries(LOGS_DIR)
        return render_template("export.html", results=results, logs_dir=LOGS_DIR, user=USER)

    @app.route("/settings")
    def settings():
        """Settings page."""
        return render_template("settings.html", user=USER, settings=APP_SETTINGS)

    @app.route("/emails")
    def emails():
        """Emails tracking page."""
        category = request.args.get("category", "all")
        email_id = request.args.get("id")

        # Get emails from database (mock data for now)
        # TODO: Implement actual email fetching via IMAP/Gmail API
        emails_data = app.db.get_emails(category) if hasattr(app.db, 'get_emails') else []

        # Mock email stats
        email_stats = {
            "total": len(emails_data),
            "unread": sum(1 for e in emails_data if not e.get('read', True)),
            "assessment": sum(1 for e in emails_data if e.get('category') == 'assessment'),
            "interview": sum(1 for e in emails_data if e.get('category') == 'interview'),
            "thank_you": sum(1 for e in emails_data if e.get('category') == 'thank_you'),
            "onsite": sum(1 for e in emails_data if e.get('category') == 'onsite'),
            "rejection": sum(1 for e in emails_data if e.get('category') == 'rejection'),
            "job_alert": sum(1 for e in emails_data if e.get('category') == 'job_alert'),
            "recruiter": sum(1 for e in emails_data if e.get('category') == 'recruiter'),
            "offer": sum(1 for e in emails_data if e.get('category') == 'offer'),
            "other": sum(1 for e in emails_data if e.get('category') == 'other'),
        }

        # Get selected email if id provided
        selected_email = None
        if email_id:
            selected_email = next((e for e in emails_data if str(e.get('id')) == email_id), None)

        return render_template("emails.html",
                               emails=emails_data,
                               category=category,
                               selected_email=selected_email,
                               stats=email_stats,
                               user=USER)

    @app.route("/job/<job_id>")
    def job_detail(job_id: str):
        """Job detail page."""
        # Find job across all countries
        job = None
        for country in [Country.US, Country.UK, Country.CANADA, Country.NIGERIA]:
            jobs = app.db.get_jobs_by_country(country, limit=500)
            for j in jobs:
                if j.job_id == job_id:
                    job = j
                    break
            if job:
                break

        if not job:
            return redirect(url_for("jobs_all"))

        # Update priority for known sponsors
        from autoapply.config import is_visa_sponsor
        if is_visa_sponsor(job.company) and job.priority == JobPriority.TIER_5_UNKNOWN:
            job.priority = JobPriority.TIER_4_KNOWN_SPONSOR

        return render_template("job_detail.html", job=job, user=USER)

    # ==========================================================================
    # SCRAPING API
    # ==========================================================================

    @app.route("/api/scrape", methods=["POST"])
    def start_scrape():
        """Start the job scraping process."""
        global scraping_state

        if scraping_state["is_running"]:
            return jsonify({"success": False, "error": "Scraping already in progress"})

        # Reset state
        scraping_state = {
            "is_running": True,
            "status": "Starting...",
            "progress": 0,
            "jobs_found": 0,
            "errors": [],
            "complete": False,
        }

        # Run scraping in background thread
        def run_scraper():
            global scraping_state
            try:
                from autoapply.pipeline import AutoApplyPipeline

                scraping_state["status"] = "Initializing pipeline..."
                scraping_state["progress"] = 10

                pipeline = AutoApplyPipeline(db=app.db)

                scraping_state["status"] = "Scraping job boards..."
                scraping_state["progress"] = 30

                # Run the pipeline (scrape only for now)
                result = pipeline.run(max_jobs_per_source=30)

                scraping_state["jobs_found"] = result.jobs_new
                scraping_state["errors"] = result.errors[:5]  # Limit errors
                scraping_state["progress"] = 100
                scraping_state["status"] = f"Found {result.jobs_new} new jobs"

            except Exception as e:
                scraping_state["errors"].append(str(e))
                scraping_state["status"] = f"Error: {str(e)}"

            finally:
                scraping_state["is_running"] = False
                scraping_state["complete"] = True

        thread = threading.Thread(target=run_scraper)
        thread.daemon = True
        thread.start()

        return jsonify({"success": True, "message": "Scraping started"})

    @app.route("/api/scrape/status")
    def scrape_status():
        """Get current scraping status."""
        return jsonify(scraping_state)

    @app.route("/api/scrape/stop", methods=["POST"])
    def stop_scrape():
        """Stop the scraping process."""
        global scraping_state
        scraping_state["is_running"] = False
        scraping_state["status"] = "Stopped by user"
        scraping_state["complete"] = True
        return jsonify({"success": True})

    @app.route("/api/chat", methods=["POST"])
    def chat():
        """AI Chat endpoint - processes user messages and returns AI responses."""
        data = request.get_json()
        user_message = data.get("message", "").strip().lower()

        if not user_message:
            return jsonify({"error": "No message provided"})

        # Get current stats for context
        stats = app.db.get_stats()

        # Process different types of requests
        response = ""

        # Stats requests
        if any(kw in user_message for kw in ["stats", "statistics", "numbers", "how many"]):
            response = f"""Here are your current job stats:

Total Jobs: {stats.get('total_jobs', 0)}
Visa Sponsored: {stats.get('visa_sponsored', 0)}
Applied Today: {stats.get('applied_today', 0)}

By Country:
- USA: {stats.get('by_country', {}).get('US', 0)}
- UK: {stats.get('by_country', {}).get('UK', 0)}
- Canada: {stats.get('by_country', {}).get('Canada', 0)}
- Nigeria: {stats.get('by_country', {}).get('Nigeria', 0)}

By Status:
- Found: {stats.get('by_status', {}).get('Found', 0)}
- Applied: {stats.get('by_status', {}).get('Applied', 0)}
- Interview: {stats.get('by_status', {}).get('Interview', 0)}"""

        # Top/Priority jobs
        elif any(kw in user_message for kw in ["top", "best", "priority", "high priority", "ranked"]):
            # Get top priority jobs
            top_jobs = []
            for c in [Country.US, Country.UK, Country.CANADA, Country.NIGERIA]:
                top_jobs.extend(app.db.get_jobs_by_country(c, limit=100))
            top_jobs.sort(key=lambda j: -j.priority.value)
            top_5 = top_jobs[:5]

            if top_5:
                job_list = "\n".join([
                    f"- {j.company}: {j.role} (Tier {j.priority.value})"
                    for j in top_5
                ])
                response = f"Here are your top 5 priority jobs:\n\n{job_list}\n\nView all at /jobs/ranked"
            else:
                response = "No jobs found yet. Try scraping first!"

        # Scraping
        elif any(kw in user_message for kw in ["scrape", "find jobs", "search", "refresh"]):
            response = "Starting job scraper... I'll find new opportunities across all job boards. Check the sidebar for progress!"
            # Trigger scraping (the frontend will call /api/scrape)

        # Suggestions/Ideas
        elif any(kw in user_message for kw in ["suggest", "improve", "idea", "help", "tips"]):
            response = """Here are some suggestions to improve your job search:

1. **Profile Optimization**: Make sure your resume highlights visa sponsorship keywords
2. **Priority Focus**: Apply to Tier 1 (Sponsor+Remote) jobs first
3. **Email Tracking**: Connect your Gmail to track responses automatically
4. **Daily Routine**: Aim for 10-15 applications per day to high-priority jobs
5. **Follow Up**: Jobs with no response after 2 weeks may need a follow-up

Would you like me to help with any of these?"""

        # Email related
        elif any(kw in user_message for kw in ["email", "inbox", "response", "reply"]):
            email_stats = app.db.get_email_stats() if hasattr(app.db, 'get_email_stats') else {}
            response = f"""Email Tracking Status:

To sync your emails, make sure GMAIL_EMAIL and GMAIL_APP_PASSWORD are set.
Then run: python -m autoapply.cli email sync

Visit /emails to view tracked emails and responses."""

        # Help
        elif any(kw in user_message for kw in ["help", "what can you do", "commands"]):
            response = """I can help you with:

- **"Show stats"** - View job search statistics
- **"Find high priority jobs"** - See your best opportunities
- **"Start scraping"** - Find new jobs across all boards
- **"Suggest improvements"** - Get tips for your job search
- **"Check emails"** - View email tracking status

Just type naturally and I'll do my best to help!"""

        # Default response
        else:
            response = f"""I understand you're asking about: "{data.get('message', '')}"

I can help with:
- Job statistics ("show stats")
- Top priority jobs ("find top jobs")
- Scraping new jobs ("start scraping")
- Improvement suggestions ("suggest ideas")

How can I assist your job search today?"""

        return jsonify({"response": response})

    @app.route("/api/email/sync", methods=["POST"])
    def sync_emails():
        """Sync emails from Gmail."""
        try:
            from autoapply.core.email_tracker import GmailIMAPClient, EmailTracker

            gmail_email = os.environ.get("GMAIL_EMAIL")
            gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

            if not gmail_email or not gmail_password:
                return jsonify({
                    "success": False,
                    "error": "Gmail credentials not configured. Set GMAIL_EMAIL and GMAIL_APP_PASSWORD."
                })

            client = GmailIMAPClient(gmail_email, gmail_password)
            tracker = EmailTracker(app.db, client)

            with client:
                stats = tracker.sync_emails(days_back=30)

            return jsonify({
                "success": True,
                "stats": stats,
                "message": f"Synced emails successfully"
            })

        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    @app.route("/api/email/test", methods=["POST"])
    def test_email_connection():
        """Test Gmail connection."""
        try:
            from autoapply.core.email_tracker import setup_gmail

            gmail_email = os.environ.get("GMAIL_EMAIL")
            gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

            if not gmail_email or not gmail_password:
                return jsonify({
                    "success": False,
                    "error": "Gmail credentials not configured"
                })

            if setup_gmail(gmail_email, gmail_password):
                return jsonify({
                    "success": True,
                    "message": f"Connected to {gmail_email} successfully"
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "Connection failed. Check your credentials."
                })

        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    @app.route("/api/apply/<job_id>", methods=["POST"])
    def apply_to_job(job_id: str):
        """Apply to a specific job."""
        try:
            from autoapply.core.auto_apply import AutoApplier, CoverLetterGenerator

            # Get job from database
            job = None
            for country in [Country.US, Country.UK, Country.CANADA, Country.NIGERIA]:
                jobs = app.db.get_jobs_by_country(country, limit=500)
                for j in jobs:
                    if j.job_id == job_id:
                        job = j
                        break
                if job:
                    break

            if not job:
                return jsonify({"success": False, "error": "Job not found"})

            # Apply in background thread
            def do_apply():
                applier = AutoApplier(headless=True)
                cover_gen = CoverLetterGenerator()
                try:
                    cover_letter = cover_gen.generate(job, {
                        "full_name": USER.name,
                        "years_experience": USER.years_experience,
                        "current_company": USER.current_company,
                    })
                    result = applier.apply(job, cover_letter)
                    if result.success:
                        app.db.mark_applied(job.job_id, resume_used="default", cover_letter=True)
                    return result
                finally:
                    applier.close()

            thread = threading.Thread(target=do_apply)
            thread.daemon = True
            thread.start()

            return jsonify({"success": True, "message": "Application started"})

        except ImportError:
            return jsonify({
                "success": False,
                "error": "Auto-apply not available. Install: pip install selenium undetected-chromedriver"
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    return app


def run_server(host: str = "127.0.0.1", port: int = 5000, debug: bool = True):
    """Run the Flask development server."""
    app = create_app()
    print(f"\n{'='*50}")
    print("AutoApply Dashboard")
    print(f"{'='*50}")
    print(f"Running at: http://{host}:{port}")
    print(f"Press Ctrl+C to stop\n")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server()
