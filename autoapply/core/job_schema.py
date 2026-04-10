"""
Job Schema & Normalization
==========================
Standardized job data structure used across all scrapers and the application pipeline.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
import hashlib
import json


class JobStatus(Enum):
    """Status of a job application."""
    FOUND = "Found"
    APPLIED = "Applied"
    PENDING = "Pending"
    INTERVIEW = "Interview"
    REJECTED = "Rejected"
    OFFER = "Offer"
    SKIPPED = "Skipped"


class JobPriority(Enum):
    """
    Priority ranking for jobs - higher value = apply first.

    Tier 1: Sponsorship + Remote (BEST - can work anywhere + they sponsor)
    Tier 2: Sponsorship + On-site/Hybrid (they sponsor, you'd relocate)
    Tier 3: Remote EMEA/Africa/Nigeria (no visa needed, work from home)
    Tier 4: Known sponsor company (Amazon, Google, etc.) - they usually sponsor
    Tier 5: Unknown (worth trying)
    """
    TIER_1_SPONSOR_REMOTE = 5      # Sponsorship Available + Remote
    TIER_2_SPONSOR_ONSITE = 4      # Sponsorship Available + On-site/Hybrid
    TIER_3_REMOTE_EMEA = 3         # Remote EMEA/Africa/Nigeria (no visa needed)
    TIER_4_KNOWN_SPONSOR = 2       # Known sponsor company - usually sponsors
    TIER_5_UNKNOWN = 1             # Unknown - still worth trying


class WorkType(Enum):
    """Work arrangement type."""
    REMOTE_VISA_SPONSORED = "Remote (Visa Sponsored)"
    REMOTE_NO_VISA = "Remote (No Visa)"
    ONSITE_VISA_SPONSORED = "On-site (Visa Sponsored)"
    HYBRID_VISA_SPONSORED = "Hybrid (Visa Sponsored)"
    ONSITE_NO_VISA = "On-site (No Visa)"  # Usually skipped
    UNKNOWN = "Unknown"


class Country(Enum):
    """Target countries."""
    US = "US"
    UK = "UK"
    CANADA = "Canada"
    NIGERIA = "Nigeria"
    OTHER = "Other"


@dataclass
class Job:
    """
    Normalized job data structure.

    12 columns as specified:
    1. Company
    2. Role
    3. Location
    4. Work Type
    5. Visa Sponsored
    6. Pay Range
    7. Source
    8. Date Applied
    9. Status
    10. Job URL
    11. Resume Used
    12. Cover Letter
    """

    # Core fields (Columns 1-7)
    company: str
    role: str
    location: str
    work_type: WorkType = WorkType.UNKNOWN
    visa_sponsored: bool = False
    pay_range: str = "Not Listed"
    source: str = ""

    # Application tracking (Columns 8-12)
    date_applied: Optional[datetime] = None
    status: JobStatus = JobStatus.FOUND
    job_url: str = ""
    resume_used: str = ""  # "Java" or "NodeJS"
    cover_letter_generated: bool = False

    # Internal fields (not in CSV export)
    country: Country = Country.OTHER
    job_id: str = ""  # Unique hash
    description: str = ""
    date_found: datetime = field(default_factory=datetime.now)
    date_posted: Optional[str] = None

    # Generated resume path (saved per job)
    generated_resume_path: str = ""
    generated_cover_letter_path: str = ""

    # Priority ranking (calculated)
    priority: JobPriority = JobPriority.TIER_5_UNKNOWN

    def __post_init__(self):
        """Generate unique job ID and calculate priority after initialization."""
        if not self.job_id:
            self.job_id = self._generate_id()
        # Calculate priority
        self.priority = self._calculate_priority()

    def _calculate_priority(self) -> "JobPriority":
        """
        Calculate job priority based on sponsorship, work type, and company.

        Priority Order:
        1. Sponsorship + Remote (BEST)
        2. Sponsorship + On-site/Hybrid
        3. Remote EMEA/Africa/Nigeria (no visa needed)
        4. Known sponsor company (Amazon, Google, etc.)
        5. Unknown
        """
        is_remote = self.work_type in [WorkType.REMOTE_VISA_SPONSORED, WorkType.REMOTE_NO_VISA]
        is_onsite_hybrid = self.work_type in [
            WorkType.ONSITE_VISA_SPONSORED, WorkType.HYBRID_VISA_SPONSORED,
            WorkType.ONSITE_NO_VISA
        ]

        # Tier 1: Sponsorship + Remote
        if self.visa_sponsored and is_remote:
            return JobPriority.TIER_1_SPONSOR_REMOTE

        # Tier 2: Sponsorship + On-site/Hybrid
        if self.visa_sponsored and is_onsite_hybrid:
            return JobPriority.TIER_2_SPONSOR_ONSITE

        # Tier 3: Remote EMEA/Africa/Nigeria (work from Nigeria, no visa needed)
        if is_remote and self.country == Country.NIGERIA:
            return JobPriority.TIER_3_REMOTE_EMEA

        # Check for EMEA/Africa remote in location/description
        emea_keywords = ["emea", "africa", "nigeria", "remote africa", "remote emea"]
        location_lower = self.location.lower()
        if is_remote and any(kw in location_lower for kw in emea_keywords):
            return JobPriority.TIER_3_REMOTE_EMEA

        # Tier 4: Known sponsor company (we'll check this in pipeline with config)
        # For now, mark as unknown - pipeline will upgrade this
        return JobPriority.TIER_5_UNKNOWN

    def _generate_id(self) -> str:
        """Generate unique ID from company + role + location."""
        unique_string = f"{self.company}|{self.role}|{self.location}|{self.job_url}"
        return hashlib.md5(unique_string.encode()).hexdigest()[:16]

    def to_csv_row(self) -> Dict[str, Any]:
        """Convert to CSV row format (13 columns - includes priority)."""
        return {
            "Priority": self.priority.value if isinstance(self.priority, JobPriority) else self.priority,
            "Company": self.company,
            "Role": self.role,
            "Location": self.location,
            "Work Type": self.work_type.value if isinstance(self.work_type, WorkType) else self.work_type,
            "Visa Sponsored": "Y" if self.visa_sponsored else "N",
            "Pay Range": self.pay_range,
            "Source": self.source,
            "Date Applied": self.date_applied.strftime("%Y-%m-%d %H:%M") if self.date_applied else "",
            "Status": self.status.value if isinstance(self.status, JobStatus) else self.status,
            "Job URL": self.job_url,
            "Resume Used": self.resume_used,
            "Cover Letter": "Y" if self.cover_letter_generated else "N",
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to full dictionary for database storage."""
        return {
            "job_id": self.job_id,
            "company": self.company,
            "role": self.role,
            "location": self.location,
            "work_type": self.work_type.value if isinstance(self.work_type, WorkType) else self.work_type,
            "visa_sponsored": self.visa_sponsored,
            "pay_range": self.pay_range,
            "source": self.source,
            "date_applied": self.date_applied.isoformat() if self.date_applied else None,
            "status": self.status.value if isinstance(self.status, JobStatus) else self.status,
            "job_url": self.job_url,
            "resume_used": self.resume_used,
            "cover_letter_generated": self.cover_letter_generated,
            "country": self.country.value if isinstance(self.country, Country) else self.country,
            "description": self.description,
            "date_found": self.date_found.isoformat() if self.date_found else None,
            "date_posted": self.date_posted,
            "generated_resume_path": self.generated_resume_path,
            "generated_cover_letter_path": self.generated_cover_letter_path,
            "priority": self.priority.value if isinstance(self.priority, JobPriority) else self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create Job from dictionary."""
        # Handle enum conversions
        work_type = data.get("work_type", "Unknown")
        if isinstance(work_type, str):
            try:
                work_type = WorkType(work_type)
            except ValueError:
                work_type = WorkType.UNKNOWN

        status = data.get("status", "Found")
        if isinstance(status, str):
            try:
                status = JobStatus(status)
            except ValueError:
                status = JobStatus.FOUND

        country = data.get("country", "Other")
        if isinstance(country, str):
            try:
                country = Country(country)
            except ValueError:
                country = Country.OTHER

        # Handle datetime conversions
        date_applied = data.get("date_applied")
        if isinstance(date_applied, str) and date_applied:
            date_applied = datetime.fromisoformat(date_applied)

        date_found = data.get("date_found")
        if isinstance(date_found, str) and date_found:
            date_found = datetime.fromisoformat(date_found)
        else:
            date_found = datetime.now()

        priority = data.get("priority", 1)
        if isinstance(priority, int):
            try:
                priority = JobPriority(priority)
            except ValueError:
                priority = JobPriority.TIER_5_UNKNOWN
        elif isinstance(priority, str):
            priority = JobPriority.TIER_5_UNKNOWN

        return cls(
            job_id=data.get("job_id", ""),
            company=data.get("company", ""),
            role=data.get("role", ""),
            location=data.get("location", ""),
            work_type=work_type,
            visa_sponsored=data.get("visa_sponsored", False),
            pay_range=data.get("pay_range", "Not Listed"),
            source=data.get("source", ""),
            date_applied=date_applied,
            status=status,
            job_url=data.get("job_url", ""),
            resume_used=data.get("resume_used", ""),
            cover_letter_generated=data.get("cover_letter_generated", False),
            country=country,
            description=data.get("description", ""),
            date_found=date_found,
            date_posted=data.get("date_posted"),
            generated_resume_path=data.get("generated_resume_path", ""),
            generated_cover_letter_path=data.get("generated_cover_letter_path", ""),
        )


# =============================================================================
# NORMALIZATION FUNCTIONS
# =============================================================================

def normalize_company_name(name: str) -> str:
    """Normalize company name for comparison."""
    if not name:
        return ""
    # Remove common suffixes
    suffixes = [" inc", " inc.", " llc", " ltd", " limited", " corp", " corporation", " co.", " co"]
    name_lower = name.lower().strip()
    for suffix in suffixes:
        if name_lower.endswith(suffix):
            name_lower = name_lower[:-len(suffix)]
    return name_lower.strip()


def normalize_location(location: str) -> str:
    """Normalize location string."""
    if not location:
        return ""
    location = location.strip()
    # Common normalizations
    location = location.replace("United States", "USA")
    location = location.replace("United Kingdom", "UK")
    return location


def detect_country(location: str) -> Country:
    """Detect country from location string."""
    location_lower = location.lower()

    us_indicators = ["usa", "united states", "u.s.", "us-", "california", "new york",
                     "texas", "washington", "florida", "seattle", "san francisco",
                     "austin", "boston", "chicago", "denver", "atlanta"]

    uk_indicators = ["uk", "united kingdom", "england", "london", "manchester",
                     "birmingham", "edinburgh", "scotland", "wales", "bristol"]

    canada_indicators = ["canada", "toronto", "vancouver", "montreal", "ottawa",
                         "calgary", "ontario", "british columbia", "quebec"]

    nigeria_indicators = ["nigeria", "lagos", "abuja", "port harcourt", "ibadan"]

    for indicator in us_indicators:
        if indicator in location_lower:
            return Country.US

    for indicator in uk_indicators:
        if indicator in location_lower:
            return Country.UK

    for indicator in canada_indicators:
        if indicator in location_lower:
            return Country.CANADA

    for indicator in nigeria_indicators:
        if indicator in location_lower:
            return Country.NIGERIA

    # Check for "Remote" with country context
    if "remote" in location_lower:
        if any(ind in location_lower for ind in us_indicators):
            return Country.US
        if any(ind in location_lower for ind in uk_indicators):
            return Country.UK
        if any(ind in location_lower for ind in canada_indicators):
            return Country.CANADA
        if any(ind in location_lower for ind in nigeria_indicators):
            return Country.NIGERIA

    return Country.OTHER


def detect_work_type(location: str, description: str, visa_sponsored: bool) -> WorkType:
    """Detect work type from location and description."""
    text = f"{location} {description}".lower()

    is_remote = any(kw in text for kw in ["remote", "work from home", "wfh", "anywhere"])
    is_hybrid = any(kw in text for kw in ["hybrid", "flexible", "partial remote"])
    is_onsite = any(kw in text for kw in ["on-site", "onsite", "in-office", "in office"])

    # Default to remote if nothing specified and location is vague
    if not is_onsite and not is_hybrid:
        is_remote = True

    if is_remote:
        return WorkType.REMOTE_VISA_SPONSORED if visa_sponsored else WorkType.REMOTE_NO_VISA
    elif is_hybrid:
        return WorkType.HYBRID_VISA_SPONSORED if visa_sponsored else WorkType.ONSITE_NO_VISA
    else:
        return WorkType.ONSITE_VISA_SPONSORED if visa_sponsored else WorkType.ONSITE_NO_VISA


def extract_salary(text: str) -> str:
    """Extract salary range from job text."""
    import re

    # Common patterns
    patterns = [
        r'\$[\d,]+[kK]?\s*[-–]\s*\$[\d,]+[kK]?',  # $100k - $150k
        r'\$[\d,]+\s*[-–]\s*[\d,]+',               # $100,000 - $150,000
        r'[\d,]+[kK]\s*[-–]\s*[\d,]+[kK]',         # 100k - 150k
        r'£[\d,]+\s*[-–]\s*£[\d,]+',               # £50,000 - £70,000
        r'CA\$[\d,]+\s*[-–]\s*CA\$[\d,]+',         # CA$80,000 - CA$120,000
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)

    # Check for single salary mention
    single_patterns = [
        r'\$[\d,]+[kK]?\s*(?:per year|annually|/yr|/year)',
        r'[\d,]+[kK]\s*(?:per year|annually)',
    ]

    for pattern in single_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

    return "Not Listed"


def detect_visa_sponsorship(text: str, company: str, known_sponsors: list) -> bool:
    """Detect if job offers visa sponsorship."""
    text_lower = text.lower()
    company_lower = company.lower()

    # Check known sponsors
    for sponsor in known_sponsors:
        if sponsor.lower() in company_lower:
            return True

    # Positive indicators
    positive_keywords = [
        "visa sponsorship", "h1b", "h-1b", "sponsor visa",
        "sponsorship available", "will sponsor", "sponsorship provided",
        "work visa", "immigration sponsorship", "skilled worker visa",
        "tier 2", "lmia", "work permit sponsor", "relocation assistance",
        "open to all nationalities", "international candidates"
    ]

    # Negative indicators (no sponsorship)
    negative_keywords = [
        "no sponsorship", "cannot sponsor", "unable to sponsor",
        "not able to sponsor", "must be authorized to work",
        "us citizen only", "citizen or permanent resident",
        "without sponsorship"
    ]

    # Check for negative first
    for kw in negative_keywords:
        if kw in text_lower:
            return False

    # Check for positive
    for kw in positive_keywords:
        if kw in text_lower:
            return True

    return False
