"""
Job Deduplication & Database
============================
SQLite-based job tracking with deduplication to prevent duplicate applications.
Exports to CSV files for UI display (US, UK, Canada, Nigeria).
"""

import sqlite3
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from .job_schema import Job, JobStatus, WorkType, Country


class JobDatabase:
    """
    SQLite database for job tracking and deduplication.

    Features:
    - Deduplication by job_id (hash of company + role + location + url)
    - Separate tracking for US, UK, Canada, Nigeria jobs
    - CSV export for UI display (12 columns)
    - Filter and search capabilities
    """

    def __init__(self, db_path: Path):
        """Initialize database connection."""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_database(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Main jobs table with all 12 columns + internal fields
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    company TEXT NOT NULL,
                    role TEXT NOT NULL,
                    location TEXT,
                    work_type TEXT,
                    visa_sponsored INTEGER DEFAULT 0,
                    pay_range TEXT DEFAULT 'Not Listed',
                    source TEXT,
                    date_applied TEXT,
                    status TEXT DEFAULT 'Found',
                    job_url TEXT,
                    resume_used TEXT,
                    cover_letter_generated INTEGER DEFAULT 0,
                    country TEXT,
                    description TEXT,
                    date_found TEXT,
                    date_posted TEXT,
                    generated_resume_path TEXT,
                    generated_cover_letter_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Index for faster lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_country ON jobs(country)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_company ON jobs(company)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_visa ON jobs(visa_sponsored)")

            # Application log table (for tracking application history)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS application_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                )
            """)

            # Daily stats table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    jobs_found INTEGER DEFAULT 0,
                    jobs_applied INTEGER DEFAULT 0,
                    jobs_skipped INTEGER DEFAULT 0
                )
            """)

            # Emails table for tracking job-related emails
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id TEXT UNIQUE,
                    sender TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT,
                    preview TEXT,
                    category TEXT DEFAULT 'other',
                    company TEXT,
                    job_id TEXT,
                    read INTEGER DEFAULT 0,
                    date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_category ON emails(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_company ON emails(company)")

    # =========================================================================
    # CORE CRUD OPERATIONS
    # =========================================================================

    def job_exists(self, job_id: str) -> bool:
        """Check if a job already exists in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,))
            return cursor.fetchone() is not None

    def add_job(self, job: Job) -> bool:
        """
        Add a new job to the database.
        Returns True if added, False if already exists.
        """
        if self.job_exists(job.job_id):
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            data = job.to_dict()

            cursor.execute("""
                INSERT INTO jobs (
                    job_id, company, role, location, work_type, visa_sponsored,
                    pay_range, source, date_applied, status, job_url, resume_used,
                    cover_letter_generated, country, description, date_found,
                    date_posted, generated_resume_path, generated_cover_letter_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["job_id"], data["company"], data["role"], data["location"],
                data["work_type"], 1 if data["visa_sponsored"] else 0,
                data["pay_range"], data["source"], data["date_applied"],
                data["status"], data["job_url"], data["resume_used"],
                1 if data["cover_letter_generated"] else 0, data["country"],
                data["description"], data["date_found"], data["date_posted"],
                data["generated_resume_path"], data["generated_cover_letter_path"]
            ))

            # Log the action
            self._log_action(cursor, job.job_id, "ADDED", f"Job found from {job.source}")

            # Update daily stats
            self._update_daily_stats(cursor, "jobs_found")

        return True

    def update_job(self, job: Job) -> bool:
        """Update an existing job."""
        if not self.job_exists(job.job_id):
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            data = job.to_dict()

            cursor.execute("""
                UPDATE jobs SET
                    company = ?, role = ?, location = ?, work_type = ?,
                    visa_sponsored = ?, pay_range = ?, source = ?,
                    date_applied = ?, status = ?, job_url = ?, resume_used = ?,
                    cover_letter_generated = ?, country = ?, description = ?,
                    date_posted = ?, generated_resume_path = ?,
                    generated_cover_letter_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
            """, (
                data["company"], data["role"], data["location"], data["work_type"],
                1 if data["visa_sponsored"] else 0, data["pay_range"], data["source"],
                data["date_applied"], data["status"], data["job_url"], data["resume_used"],
                1 if data["cover_letter_generated"] else 0, data["country"],
                data["description"], data["date_posted"], data["generated_resume_path"],
                data["generated_cover_letter_path"], data["job_id"]
            ))

        return True

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()

            if row:
                return self._row_to_job(row)
        return None

    def mark_applied(self, job_id: str, resume_used: str, cover_letter: bool,
                     resume_path: str = "", cover_letter_path: str = "") -> bool:
        """Mark a job as applied."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE jobs SET
                    status = ?,
                    date_applied = ?,
                    resume_used = ?,
                    cover_letter_generated = ?,
                    generated_resume_path = ?,
                    generated_cover_letter_path = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
            """, (
                JobStatus.APPLIED.value,
                datetime.now().isoformat(),
                resume_used,
                1 if cover_letter else 0,
                resume_path,
                cover_letter_path,
                job_id
            ))

            if cursor.rowcount > 0:
                self._log_action(cursor, job_id, "APPLIED",
                               f"Resume: {resume_used}, Cover Letter: {cover_letter}")
                self._update_daily_stats(cursor, "jobs_applied")
                return True

        return False

    def mark_skipped(self, job_id: str, reason: str = "") -> bool:
        """Mark a job as skipped."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE jobs SET
                    status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
            """, (JobStatus.SKIPPED.value, job_id))

            if cursor.rowcount > 0:
                self._log_action(cursor, job_id, "SKIPPED", reason)
                self._update_daily_stats(cursor, "jobs_skipped")
                return True

        return False

    def update_status(self, job_id: str, status: JobStatus) -> bool:
        """Update job status."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
            """, (status.value, job_id))

            if cursor.rowcount > 0:
                self._log_action(cursor, job_id, "STATUS_CHANGE", f"New status: {status.value}")
                return True

        return False

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    def get_jobs_by_country(self, country: Country,
                            status: Optional[JobStatus] = None,
                            limit: int = 100) -> List[Job]:
        """Get jobs for a specific country."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if status:
                cursor.execute("""
                    SELECT * FROM jobs WHERE country = ? AND status = ?
                    ORDER BY date_found DESC LIMIT ?
                """, (country.value, status.value, limit))
            else:
                cursor.execute("""
                    SELECT * FROM jobs WHERE country = ?
                    ORDER BY date_found DESC LIMIT ?
                """, (country.value, limit))

            return [self._row_to_job(row) for row in cursor.fetchall()]

    def get_pending_jobs(self, limit: int = 30) -> List[Job]:
        """Get jobs that haven't been applied to yet."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM jobs WHERE status = ?
                ORDER BY date_found DESC LIMIT ?
            """, (JobStatus.FOUND.value, limit))

            return [self._row_to_job(row) for row in cursor.fetchall()]

    def get_applied_jobs(self, days: int = 30) -> List[Job]:
        """Get jobs applied to in the last N days."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM jobs WHERE status = ?
                AND date_applied >= datetime('now', ?)
                ORDER BY date_applied DESC
            """, (JobStatus.APPLIED.value, f"-{days} days"))

            return [self._row_to_job(row) for row in cursor.fetchall()]

    def get_applications_today(self) -> int:
        """Get count of applications made today."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM jobs
                WHERE status = ? AND date(date_applied) = date('now')
            """, (JobStatus.APPLIED.value,))
            result = cursor.fetchone()
            return result[0] if result else 0

    def search_jobs(self, query: str, limit: int = 50) -> List[Job]:
        """Search jobs by company, role, or location."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            search_term = f"%{query}%"
            cursor.execute("""
                SELECT * FROM jobs
                WHERE company LIKE ? OR role LIKE ? OR location LIKE ?
                ORDER BY date_found DESC LIMIT ?
            """, (search_term, search_term, search_term, limit))

            return [self._row_to_job(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Total jobs by country
            cursor.execute("""
                SELECT country, COUNT(*) as count FROM jobs GROUP BY country
            """)
            stats["by_country"] = {row["country"]: row["count"] for row in cursor.fetchall()}

            # Total jobs by status
            cursor.execute("""
                SELECT status, COUNT(*) as count FROM jobs GROUP BY status
            """)
            stats["by_status"] = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Total visa sponsored
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE visa_sponsored = 1")
            stats["visa_sponsored"] = cursor.fetchone()[0]

            # Applications today
            stats["applied_today"] = self.get_applications_today()

            # Total jobs
            cursor.execute("SELECT COUNT(*) FROM jobs")
            stats["total_jobs"] = cursor.fetchone()[0]

            return stats

    # =========================================================================
    # CSV EXPORT
    # =========================================================================

    def export_to_csv(self, country: Country, output_path: Path) -> int:
        """
        Export jobs for a country to CSV (12 columns).
        Returns number of rows exported.
        """
        jobs = self.get_jobs_by_country(country, limit=10000)

        if not jobs:
            return 0

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Company", "Role", "Location", "Work Type", "Visa Sponsored",
                "Pay Range", "Source", "Date Applied", "Status", "Job URL",
                "Resume Used", "Cover Letter", "Priority"
            ])
            writer.writeheader()

            for job in jobs:
                writer.writerow(job.to_csv_row())

        return len(jobs)

    def export_all_countries(self, logs_dir: Path) -> Dict[str, int]:
        """Export all countries to their respective CSV files."""
        results = {}

        for country in [Country.US, Country.UK, Country.CANADA, Country.NIGERIA]:
            output_path = logs_dir / f"{country.value}_jobs.csv"
            count = self.export_to_csv(country, output_path)
            results[country.value] = count

        return results

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        """Convert database row to Job object."""
        return Job.from_dict({
            "job_id": row["job_id"],
            "company": row["company"],
            "role": row["role"],
            "location": row["location"],
            "work_type": row["work_type"],
            "visa_sponsored": bool(row["visa_sponsored"]),
            "pay_range": row["pay_range"],
            "source": row["source"],
            "date_applied": row["date_applied"],
            "status": row["status"],
            "job_url": row["job_url"],
            "resume_used": row["resume_used"],
            "cover_letter_generated": bool(row["cover_letter_generated"]),
            "country": row["country"],
            "description": row["description"],
            "date_found": row["date_found"],
            "date_posted": row["date_posted"],
            "generated_resume_path": row["generated_resume_path"],
            "generated_cover_letter_path": row["generated_cover_letter_path"],
        })

    def _log_action(self, cursor: sqlite3.Cursor, job_id: str,
                    action: str, details: str = ""):
        """Log an action to the application log."""
        cursor.execute("""
            INSERT INTO application_log (job_id, action, details)
            VALUES (?, ?, ?)
        """, (job_id, action, details))

    def _update_daily_stats(self, cursor: sqlite3.Cursor, field: str):
        """Update daily statistics."""
        today = datetime.now().strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT INTO daily_stats (date, {field})
            VALUES (?, 1)
            ON CONFLICT(date) DO UPDATE SET {field} = {field} + 1
        """.format(field=field), (today,))

    # =========================================================================
    # EMAIL TRACKING
    # =========================================================================

    def add_email(self, email_data: Dict[str, Any]) -> bool:
        """Add an email to the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO emails (
                        email_id, sender, subject, body, preview, category,
                        company, job_id, read, date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    email_data.get("email_id"),
                    email_data.get("sender"),
                    email_data.get("subject"),
                    email_data.get("body"),
                    email_data.get("preview"),
                    email_data.get("category", "other"),
                    email_data.get("company"),
                    email_data.get("job_id"),
                    1 if email_data.get("read") else 0,
                    email_data.get("date"),
                ))
                return True
            except sqlite3.IntegrityError:
                return False

    def get_emails(self, category: str = "all", limit: int = 100) -> List[Dict[str, Any]]:
        """Get emails, optionally filtered by category."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if category == "all":
                cursor.execute("""
                    SELECT * FROM emails ORDER BY date DESC LIMIT ?
                """, (limit,))
            elif category == "unread":
                cursor.execute("""
                    SELECT * FROM emails WHERE read = 0 ORDER BY date DESC LIMIT ?
                """, (limit,))
            else:
                cursor.execute("""
                    SELECT * FROM emails WHERE category = ? ORDER BY date DESC LIMIT ?
                """, (category, limit))

            return [dict(row) for row in cursor.fetchall()]

    def mark_email_read(self, email_id: int):
        """Mark an email as read."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE emails SET read = 1 WHERE id = ?", (email_id,))

    def get_email_stats(self) -> Dict[str, int]:
        """Get email statistics by category."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            stats = {"total": 0, "unread": 0}

            cursor.execute("SELECT COUNT(*) FROM emails")
            stats["total"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM emails WHERE read = 0")
            stats["unread"] = cursor.fetchone()[0]

            cursor.execute("SELECT category, COUNT(*) as count FROM emails GROUP BY category")
            for row in cursor.fetchall():
                stats[row["category"]] = row["count"]

            return stats

    def categorize_email(self, subject: str, body: str, sender: str) -> str:
        """Auto-categorize an email based on content."""
        text = f"{subject} {body}".lower()
        sender_lower = sender.lower()

        # Rejection keywords
        if any(kw in text for kw in ["unfortunately", "regret to inform", "not moving forward",
                                       "decided not to", "will not be proceeding", "other candidates"]):
            return "rejection"

        # Interview keywords
        if any(kw in text for kw in ["interview", "schedule a call", "meet with", "discuss your application",
                                       "next steps", "phone screen", "video call"]):
            return "interview"

        # Assessment keywords
        if any(kw in text for kw in ["assessment", "coding challenge", "take home", "technical test",
                                       "hackerrank", "codility", "leetcode"]):
            return "assessment"

        # Offer keywords
        if any(kw in text for kw in ["offer letter", "pleased to offer", "job offer", "compensation package",
                                       "start date", "excited to have you join"]):
            return "offer"

        # Thank you (application received)
        if any(kw in text for kw in ["thank you for applying", "application received", "we received your",
                                       "thank you for your interest"]):
            return "thank_you"

        # Recruiter outreach
        if any(kw in sender_lower for kw in ["recruiter", "talent", "hiring"]) or \
           any(kw in text for kw in ["reaching out", "found your profile", "great opportunity",
                                       "position that matches"]):
            return "recruiter"

        # Job alerts
        if any(kw in text for kw in ["new jobs", "job alert", "jobs matching", "new opportunities"]):
            return "job_alert"

        # On-site
        if any(kw in text for kw in ["on-site", "onsite interview", "visit our office", "in-person"]):
            return "onsite"

        return "other"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_database(db_path: Optional[Path] = None) -> JobDatabase:
    """Get or create the job database."""
    if db_path is None:
        from autoapply.config import APP_SETTINGS
        db_path = APP_SETTINGS.db_path

    return JobDatabase(db_path)
