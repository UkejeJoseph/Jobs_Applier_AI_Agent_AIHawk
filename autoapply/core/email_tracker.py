"""
Email Tracker Module
====================
Connects to Gmail/Outlook to track job application emails.
Auto-categorizes emails (rejections, interviews, assessments, etc.)

Two methods supported:
1. Gmail API (OAuth2) - More secure, recommended
2. IMAP with App Password - Simpler setup
"""

import os
import re
import email
import imaplib
import base64
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Load .env file if exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, rely on system env vars

logger = logging.getLogger("autoapply.email_tracker")


class EmailCategory(Enum):
    """Categories for job-related emails."""
    ASSESSMENT = "assessment"
    INTERVIEW = "interview"
    THANK_YOU = "thank_you"
    ONSITE = "onsite"
    REJECTION = "rejection"
    JOB_ALERT = "job_alert"
    RECRUITER = "recruiter"
    OFFER = "offer"
    OTHER = "other"


@dataclass
class TrackedEmail:
    """Represents a tracked email."""
    id: str
    sender: str
    subject: str
    body: str
    preview: str
    category: EmailCategory
    company: str
    date: datetime
    read: bool = False
    job_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email_id": self.id,
            "sender": self.sender,
            "subject": self.subject,
            "body": self.body,
            "preview": self.preview,
            "category": self.category.value,
            "company": self.company,
            "date": self.date.strftime("%Y-%m-%d %H:%M"),
            "read": self.read,
            "job_id": self.job_id,
        }


class EmailCategorizer:
    """Auto-categorize emails based on content."""

    # Keywords for each category
    CATEGORY_KEYWORDS = {
        EmailCategory.REJECTION: [
            "unfortunately", "regret to inform", "not moving forward",
            "decided not to", "will not be proceeding", "other candidates",
            "not selected", "position has been filled", "pursuing other",
            "after careful consideration", "we have decided", "not a match",
            "will not be able to offer", "decided to move forward with",
        ],
        EmailCategory.INTERVIEW: [
            "interview", "schedule a call", "meet with", "discuss your application",
            "next steps", "phone screen", "video call", "zoom meeting",
            "teams meeting", "google meet", "calendly", "availability",
            "like to speak with you", "interested in learning more",
        ],
        EmailCategory.ASSESSMENT: [
            "assessment", "coding challenge", "take home", "technical test",
            "hackerrank", "codility", "leetcode", "codesignal", "coderbyte",
            "complete the following", "coding exercise", "technical assessment",
            "skills assessment", "online test",
        ],
        EmailCategory.OFFER: [
            "offer letter", "pleased to offer", "job offer", "compensation package",
            "start date", "excited to have you join", "welcome to the team",
            "formal offer", "employment offer", "we would like to extend",
        ],
        EmailCategory.THANK_YOU: [
            "thank you for applying", "application received", "we received your",
            "thank you for your interest", "application has been submitted",
            "successfully submitted", "we have received",
        ],
        EmailCategory.RECRUITER: [
            "reaching out", "found your profile", "great opportunity",
            "position that matches", "thought of you", "your background",
            "linkedin profile", "impressive experience", "exciting role",
            "client is looking", "behalf of my client",
        ],
        EmailCategory.JOB_ALERT: [
            "new jobs", "job alert", "jobs matching", "new opportunities",
            "jobs for you", "recommended jobs", "based on your profile",
        ],
        EmailCategory.ONSITE: [
            "on-site", "onsite interview", "visit our office", "in-person",
            "final round", "meet the team", "office visit",
        ],
    }

    # Common company domains to extract company names
    COMPANY_DOMAINS = {
        "amazon": "Amazon",
        "google": "Google",
        "microsoft": "Microsoft",
        "meta": "Meta",
        "apple": "Apple",
        "netflix": "Netflix",
        "salesforce": "Salesforce",
        "oracle": "Oracle",
        "linkedin": "LinkedIn",
        "greenhouse": None,  # ATS, need to extract from content
        "lever": None,
        "workday": None,
        "icims": None,
        "smartrecruiters": None,
    }

    @classmethod
    def categorize(cls, subject: str, body: str, sender: str) -> EmailCategory:
        """Categorize an email based on its content."""
        text = f"{subject} {body}".lower()

        # Check each category
        for category, keywords in cls.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return category

        return EmailCategory.OTHER

    @classmethod
    def extract_company(cls, sender: str, subject: str, body: str) -> str:
        """Extract company name from email."""
        # Try to get from sender domain
        email_match = re.search(r'@([a-zA-Z0-9.-]+)', sender)
        if email_match:
            domain = email_match.group(1).lower()
            domain_parts = domain.split('.')

            # Check known companies
            for key, company in cls.COMPANY_DOMAINS.items():
                if key in domain:
                    if company:
                        return company
                    break

            # Use domain name as company (remove common suffixes)
            if len(domain_parts) >= 2:
                company_name = domain_parts[-2]
                if company_name not in ['gmail', 'yahoo', 'outlook', 'hotmail']:
                    return company_name.title()

        # Try to extract from subject
        # Look for patterns like "from Company" or "at Company"
        patterns = [
            r'from\s+([A-Z][a-zA-Z0-9\s]+)',
            r'at\s+([A-Z][a-zA-Z0-9\s]+)',
            r'([A-Z][a-zA-Z0-9]+)\s+is\s+hiring',
        ]

        for pattern in patterns:
            match = re.search(pattern, subject)
            if match:
                return match.group(1).strip()

        return "Unknown"


class GmailIMAPClient:
    """
    Gmail client using IMAP with App Password.

    Setup:
    1. Enable 2-Step Verification on your Google Account
    2. Go to https://myaccount.google.com/apppasswords
    3. Generate an App Password for "Mail"
    4. Use that password here
    """

    IMAP_SERVER = "imap.gmail.com"
    IMAP_PORT = 993

    def __init__(self, email: str, app_password: str):
        """
        Initialize Gmail IMAP client.

        Args:
            email: Gmail address (e.g., ukejejoseph1@gmail.com)
            app_password: 16-character App Password from Google
        """
        self.email = email
        self.app_password = app_password.replace(" ", "")  # Remove spaces
        self.connection: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> bool:
        """Connect to Gmail IMAP server."""
        try:
            self.connection = imaplib.IMAP4_SSL(self.IMAP_SERVER, self.IMAP_PORT)
            self.connection.login(self.email, self.app_password)
            logger.info(f"Connected to Gmail: {self.email}")
            return True
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP login failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from Gmail."""
        if self.connection:
            try:
                self.connection.logout()
            except:
                pass
            self.connection = None

    def fetch_job_emails(
        self,
        days_back: int = 30,
        folder: str = "INBOX",
        limit: int = 100,
    ) -> List[TrackedEmail]:
        """
        Fetch job-related emails from Gmail.

        Args:
            days_back: How many days back to search
            folder: Email folder to search
            limit: Maximum emails to fetch

        Returns:
            List of TrackedEmail objects
        """
        if not self.connection:
            if not self.connect():
                return []

        emails = []

        try:
            # Select folder
            self.connection.select(folder)

            # Build search criteria for job-related emails
            since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")

            # Search for job-related keywords
            job_keywords = [
                "application", "interview", "assessment", "offer",
                "position", "job", "role", "opportunity", "hiring",
                "recruiter", "talent", "career", "greenhouse", "lever",
                "workday", "applied", "candidate"
            ]

            all_email_ids = set()

            # Search for each keyword
            for keyword in job_keywords[:5]:  # Limit to avoid too many searches
                try:
                    _, message_ids = self.connection.search(
                        None,
                        f'(SINCE {since_date} OR SUBJECT "{keyword}" BODY "{keyword}")'
                    )
                    if message_ids[0]:
                        all_email_ids.update(message_ids[0].split())
                except:
                    continue

            # Also search common job email senders
            job_senders = ["greenhouse", "lever", "workday", "linkedin", "indeed", "glassdoor"]
            for sender in job_senders:
                try:
                    _, message_ids = self.connection.search(
                        None,
                        f'(SINCE {since_date} FROM "{sender}")'
                    )
                    if message_ids[0]:
                        all_email_ids.update(message_ids[0].split())
                except:
                    continue

            # Fetch email details
            email_ids = list(all_email_ids)[:limit]

            for email_id in email_ids:
                try:
                    tracked = self._fetch_email(email_id)
                    if tracked:
                        emails.append(tracked)
                except Exception as e:
                    logger.debug(f"Error fetching email {email_id}: {e}")
                    continue

            # Sort by date (newest first)
            emails.sort(key=lambda e: e.date, reverse=True)

        except Exception as e:
            logger.error(f"Error fetching emails: {e}")

        return emails

    def _fetch_email(self, email_id: bytes) -> Optional[TrackedEmail]:
        """Fetch and parse a single email."""
        try:
            _, msg_data = self.connection.fetch(email_id, "(RFC822)")
            raw_email = msg_data[0][1]

            # Parse email
            msg = email.message_from_bytes(raw_email)

            # Extract headers
            subject = self._decode_header(msg.get("Subject", ""))
            sender = self._decode_header(msg.get("From", ""))
            date_str = msg.get("Date", "")

            # Parse date
            try:
                date = email.utils.parsedate_to_datetime(date_str)
            except:
                date = datetime.now()

            # Extract body
            body = self._extract_body(msg)
            preview = body[:200] if body else ""

            # Categorize
            category = EmailCategorizer.categorize(subject, body, sender)
            company = EmailCategorizer.extract_company(sender, subject, body)

            return TrackedEmail(
                id=email_id.decode() if isinstance(email_id, bytes) else str(email_id),
                sender=sender,
                subject=subject,
                body=body,
                preview=preview,
                category=category,
                company=company,
                date=date,
                read=False,
            )

        except Exception as e:
            logger.debug(f"Error parsing email: {e}")
            return None

    def _decode_header(self, header: str) -> str:
        """Decode email header."""
        if not header:
            return ""
        decoded_parts = email.header.decode_header(header)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(encoding or 'utf-8', errors='ignore'))
            else:
                result.append(part)
        return ' '.join(result)

    def _extract_body(self, msg) -> str:
        """Extract plain text body from email."""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode('utf-8', errors='ignore')
                            break
                    except:
                        continue
                elif content_type == "text/html" and not body:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            # Basic HTML stripping
                            html = payload.decode('utf-8', errors='ignore')
                            body = re.sub(r'<[^>]+>', ' ', html)
                            body = re.sub(r'\s+', ' ', body).strip()
                    except:
                        continue
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode('utf-8', errors='ignore')
            except:
                pass

        return body[:5000]  # Limit body size

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class EmailTracker:
    """
    Main email tracker that syncs emails to the database.
    """

    def __init__(self, db, email_client: Optional[GmailIMAPClient] = None):
        """
        Initialize email tracker.

        Args:
            db: JobDatabase instance
            email_client: Email client (Gmail IMAP, etc.)
        """
        self.db = db
        self.client = email_client

    def sync_emails(self, days_back: int = 30) -> Dict[str, int]:
        """
        Sync emails from Gmail to database.

        Returns:
            Stats dict with counts by category
        """
        if not self.client:
            logger.warning("No email client configured")
            return {}

        # Fetch emails
        emails = self.client.fetch_job_emails(days_back=days_back)

        stats = {cat.value: 0 for cat in EmailCategory}
        added = 0

        for tracked_email in emails:
            # Add to database
            if self.db.add_email(tracked_email.to_dict()):
                added += 1
                stats[tracked_email.category.value] += 1

        logger.info(f"Synced {added} new emails")
        return stats

    @classmethod
    def create_from_env(cls, db) -> "EmailTracker":
        """
        Create EmailTracker from environment variables.

        Set these env vars:
        - GMAIL_EMAIL: Your Gmail address
        - GMAIL_APP_PASSWORD: Your App Password
        """
        gmail_email = os.environ.get("GMAIL_EMAIL")
        gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

        client = None
        if gmail_email and gmail_password:
            client = GmailIMAPClient(gmail_email, gmail_password)

        return cls(db, client)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def setup_gmail(email: str, app_password: str) -> bool:
    """
    Test Gmail connection and save credentials.

    Args:
        email: Gmail address
        app_password: App Password from Google

    Returns:
        True if connection successful
    """
    client = GmailIMAPClient(email, app_password)
    if client.connect():
        client.disconnect()
        logger.info("Gmail connection successful!")
        return True
    return False


def get_email_setup_instructions() -> str:
    """Get instructions for setting up Gmail App Password."""
    return """
    ╔══════════════════════════════════════════════════════════════════╗
    ║               Gmail App Password Setup                            ║
    ╠══════════════════════════════════════════════════════════════════╣
    ║                                                                   ║
    ║  1. Go to your Google Account: https://myaccount.google.com      ║
    ║                                                                   ║
    ║  2. Enable 2-Step Verification (if not already):                 ║
    ║     Security → 2-Step Verification → Turn On                     ║
    ║                                                                   ║
    ║  3. Generate App Password:                                        ║
    ║     Go to: https://myaccount.google.com/apppasswords             ║
    ║     - Select app: "Mail"                                          ║
    ║     - Select device: "Windows Computer"                           ║
    ║     - Click "Generate"                                            ║
    ║     - Copy the 16-character password                              ║
    ║                                                                   ║
    ║  4. Set environment variables:                                    ║
    ║     set GMAIL_EMAIL=ukejejoseph1@gmail.com                       ║
    ║     set GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx                   ║
    ║                                                                   ║
    ║  5. Or use the CLI:                                               ║
    ║     python -m autoapply.cli email setup                          ║
    ║                                                                   ║
    ╚══════════════════════════════════════════════════════════════════╝
    """
