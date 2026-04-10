"""
AutoApply Configuration
=======================
User profile, job preferences, and application settings for the AI Job Applicator.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

# =============================================================================
# BASE PATHS
# =============================================================================
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
RESUMES_DIR = BASE_DIR / "resumes"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
GENERATED_RESUMES_DIR = BASE_DIR / "resumes" / "generated"

# Create generated resumes directory if it doesn't exist
GENERATED_RESUMES_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# USER PROFILE
# =============================================================================
@dataclass
class UserProfile:
    """User's personal information for job applications."""
    name: str = "Joseph Ukeje"
    email: str = "ukejejoseph1@gmail.com"
    phone: str = "+2347087232777"
    location: str = "Nigeria"
    current_company: str = "Interswitch"
    current_location: str = "Germany"
    years_experience: int = 5

    # URLs
    linkedin: str = "https://www.linkedin.com/in/joseph-ukeje-8a0300220/"
    github: str = "https://github.com/UkejeJoseph"
    portfolio: str = "https://rusty-portfolio.vercel.app/"
    youtube: str = "https://www.youtube.com/channel/UChINM83eLpsJ43fbI_HQVHA"
    secondary_portfolio: str = "https://jesse-current-portfolio-7bje0kao0-josephs-projects-55e1b6a2.vercel.app/"

    # Project links (for showcasing in applications)
    projects: Dict[str, str] = field(default_factory=lambda: {
        "StableX Crypto Wallet": "https://stable-xv1.vercel.app/",
        "Nova Bills": "https://nova-bills.vercel.app/",
        "Rivet AI": "https://rivetai.com/",
        "File Share App": "https://file-sharing-app-xi.vercel.app/",
    })

    # Certification links
    certifications: Dict[str, str] = field(default_factory=lambda: {
        "Oracle Cloud DevOps": "https://catalog-education.oracle.com/ords/certview/sharebadge?id=2AE32043664103BD1F363F0CFB45953132E6DD1E0DC56DACCEF889C6FC349FE0",
        "Oracle Cloud Developer": "https://catalog-education.oracle.com/ords/certview/sharebadge?id=6249543B0DB4347806CEC83C635E2E1A7E83F74B9DE58F219CE7E340B93BA84F",
        "UiPath RPA": "https://cloud.uipath.com/intrepidtechnologiesltd/academy_/achievements",
    })

    # Open to
    open_to_remote: bool = True
    open_to_relocate: bool = True


# =============================================================================
# RESUME CONFIGURATION
# =============================================================================
class ResumeType(Enum):
    """Types of base resumes available."""
    JAVA_SENIOR = "java_senior"
    NODEJS_FULLSTACK = "nodejs_fullstack"


@dataclass
class ResumeConfig:
    """Resume file paths and selection logic."""
    base_resumes: Dict[ResumeType, Path] = field(default_factory=lambda: {
        ResumeType.JAVA_SENIOR: RESUMES_DIR / "base_java_senior.pdf",
        ResumeType.NODEJS_FULLSTACK: RESUMES_DIR / "base_nodejs_fullstack.pdf",
    })

    # Keywords to determine which resume to use
    java_keywords: List[str] = field(default_factory=lambda: [
        "java", "spring", "spring boot", "hibernate", "jpa", "maven",
        "kotlin", "scala", "j2ee", "jee", "weblogic", "tomcat",
        "microservices java", "backend java", "senior java"
    ])

    nodejs_keywords: List[str] = field(default_factory=lambda: [
        "node", "nodejs", "node.js", "typescript", "javascript", "express",
        "nestjs", "react", "vue", "angular", "fullstack", "full-stack",
        "full stack", "frontend", "front-end", "go ", "golang", "gin",
        "graphql", "rest api", "backend engineer", "software engineer"
    ])

    def select_resume_type(self, job_title: str, job_description: str) -> ResumeType:
        """Select the best resume type based on job title and description."""
        text = f"{job_title} {job_description}".lower()

        java_score = sum(1 for kw in self.java_keywords if kw in text)
        nodejs_score = sum(1 for kw in self.nodejs_keywords if kw in text)

        # Default to NodeJS/FullStack as it's more versatile
        if java_score > nodejs_score:
            return ResumeType.JAVA_SENIOR
        return ResumeType.NODEJS_FULLSTACK


# =============================================================================
# VISA & WORK AUTHORIZATION
# =============================================================================
# Import Country from job_schema to avoid duplicate enum
from autoapply.core.job_schema import Country


@dataclass
class VisaConfig:
    """Visa sponsorship requirements per country."""
    needs_sponsorship: Dict[Country, bool] = field(default_factory=lambda: {
        Country.US: True,       # Needs H1B
        Country.UK: True,       # Needs Skilled Worker visa
        Country.CANADA: True,   # Needs LMIA / work permit
        Country.NIGERIA: False, # Citizen - no visa needed
    })

    # Keywords indicating visa sponsorship in job descriptions
    visa_keywords: List[str] = field(default_factory=lambda: [
        "visa sponsorship", "h1b", "h-1b", "sponsor visa", "sponsorship available",
        "will sponsor", "sponsorship provided", "work visa", "immigration sponsorship",
        "skilled worker visa", "tier 2", "lmia", "work permit sponsor",
        "open to all nationalities", "international candidates welcome",
        "relocation assistance", "relocation package", "global talent"
    ])

    # Known H1B / visa sponsor companies - include jobs from these regardless of sponsorship mention
    # Source: H1B visa data, UK sponsor license list, LMIA data
    known_sponsors: List[str] = field(default_factory=lambda: [
        # FAANG / Big Tech
        "amazon", "google", "microsoft", "meta", "apple", "netflix", "alphabet",
        "aws", "azure", "facebook", "instagram", "whatsapp", "youtube",
        # Enterprise Tech
        "salesforce", "oracle", "ibm", "cisco", "intel", "nvidia", "amd",
        "adobe", "vmware", "paypal", "stripe", "square", "shopify", "sap",
        "servicenow", "workday", "splunk", "palo alto", "crowdstrike",
        # Startups / Unicorns
        "uber", "lyft", "airbnb", "doordash", "instacart", "robinhood",
        "coinbase", "plaid", "twilio", "datadog", "snowflake", "databricks",
        "mongodb", "elastic", "cloudflare", "fastly", "hashicorp", "gitlab",
        "figma", "notion", "airtable", "webflow", "vercel", "supabase",
        "openai", "anthropic", "stability ai", "hugging face", "cohere",
        # Finance
        "jpmorgan", "goldman sachs", "morgan stanley", "bank of america",
        "capital one", "american express", "visa", "mastercard", "citi",
        "barclays", "hsbc", "ubs", "credit suisse", "deutsche bank",
        "blackrock", "fidelity", "vanguard", "citadel", "two sigma",
        # Consulting / Big 4
        "mckinsey", "bain", "bcg", "deloitte", "pwc", "ey", "kpmg", "accenture",
        # Healthcare / Pharma
        "johnson & johnson", "pfizer", "moderna", "unitedhealth", "anthem",
        # Retail / E-commerce
        "walmart", "target", "costco", "ebay", "etsy", "wayfair",
        # Media / Entertainment
        "disney", "warner", "spotify", "tiktok", "bytedance", "snap",
        # African Tech
        "interswitch", "flutterwave", "paystack", "andela", "chipper cash",
        "kuda", "carbon", "moniepoint", "teamapt", "cowrywise",
        # UK Sponsors
        "revolut", "monzo", "starling", "deliveroo", "checkout.com",
        # Canada
        "shopify", "wealthsimple", "hootsuite", "clio", "benevity",
    ])


# =============================================================================
# JOB SEARCH PREFERENCES
# =============================================================================
class WorkType(Enum):
    """Work arrangement types."""
    REMOTE_VISA_SPONSORED = "Remote (Visa Sponsored)"
    REMOTE_NO_VISA = "Remote (No Visa)"
    ONSITE_VISA_SPONSORED = "On-site (Visa Sponsored)"
    ONSITE_NO_VISA = "On-site (No Visa)"
    HYBRID_VISA_SPONSORED = "Hybrid (Visa Sponsored)"
    HYBRID_NO_VISA = "Hybrid (No Visa)"


@dataclass
class JobPreferences:
    """Job search criteria and filters."""

    # Job titles to search for
    target_titles: List[str] = field(default_factory=lambda: [
        "Software Engineer",
        "Senior Software Engineer",
        "Backend Engineer",
        "Senior Backend Engineer",
        "Full Stack Engineer",
        "Senior Full Stack Engineer",
        "Java Developer",
        "Senior Java Developer",
        "Node.js Developer",
        "TypeScript Developer",
    ])

    # Experience level mapping
    experience_levels: List[str] = field(default_factory=lambda: [
        "mid", "mid-level", "senior", "staff", "lead"
    ])

    # Minimum salary (0 = no minimum)
    min_salary_usd: int = 0

    # Remote preferences
    accept_remote: bool = True
    accept_onsite_if_visa_sponsored: bool = True
    accept_hybrid_if_visa_sponsored: bool = True

    # Skills to match (for relevance scoring)
    primary_skills: List[str] = field(default_factory=lambda: [
        "java", "spring boot", "node.js", "typescript", "python",
        "postgresql", "mongodb", "redis", "docker", "kubernetes",
        "aws", "gcp", "microservices", "rest api", "graphql"
    ])

    # Keywords to exclude (spam filter) - only explicit "no visa" jobs
    exclude_keywords: List[str] = field(default_factory=lambda: [
        "clearance required", "us citizen only", "no sponsorship",
        "cannot sponsor", "unable to sponsor", "not able to sponsor",
        "must be authorized to work", "must be eligible to work without sponsorship",
        "will not sponsor", "does not sponsor", "unable to provide sponsorship",
    ])

    # Lower priority keywords (still include but rank lower)
    # Junior/entry/graduate jobs CAN sponsor, just less likely
    lower_priority_keywords: List[str] = field(default_factory=lambda: [
        "intern", "internship", "junior", "entry level", "graduate",
        "new grad", "early career"
    ])


# =============================================================================
# APPLICATION SETTINGS
# =============================================================================
@dataclass
class ApplicationSettings:
    """Application behavior settings."""

    # Rate limiting
    max_applications_per_day: int = 30
    delay_between_applications_sec: int = 120  # 2 minutes
    delay_between_scrapes_sec: int = 3  # Be nice to servers

    # Scheduler
    run_interval_hours: int = 4  # Run every 4 hours

    # Cover letter
    auto_generate_cover_letter: bool = True
    tailor_resume_per_job: bool = True

    # Save generated resumes
    save_generated_resumes: bool = True
    generated_resume_naming: str = "{company}_{role}_{date}_{resume_type}.pdf"

    # Logging
    log_to_file: bool = True
    log_level: str = "INFO"

    # Database
    db_path: Path = DATA_DIR / "jobs.db"

    # CSV export paths (for UI later)
    csv_paths: Dict[Country, Path] = field(default_factory=lambda: {
        Country.US: LOGS_DIR / "US_jobs.csv",
        Country.UK: LOGS_DIR / "UK_jobs.csv",
        Country.CANADA: LOGS_DIR / "Canada_jobs.csv",
        Country.NIGERIA: LOGS_DIR / "Nigeria_jobs.csv",
    })

    # Browser automation settings
    use_stealth_browser: bool = True  # Fall back to browser when blocked
    browser_headless: bool = True  # Run browser in headless mode

    # Captcha solving service (set via environment variable for security)
    # Supported: "2captcha", "anti-captcha", "capmonster"
    # Set CAPTCHA_2CAPTCHA_API_KEY, CAPTCHA_ANTICAPTCHA_API_KEY, or CAPTCHA_CAPMONSTER_API_KEY
    captcha_service: str = "2captcha"  # Default service to use

    # Proxy rotation settings
    use_proxy: bool = False  # Enable proxy rotation (set to True to use)
    proxy_rotation_strategy: str = "round_robin"  # "round_robin", "random", "weighted"

    # Static proxy list (format: "http://user:pass@host:port" or "http://host:port")
    # Can also be loaded from PROXY_LIST environment variable (comma-separated)
    proxy_list: List[str] = field(default_factory=list)

    # Proxy provider (requires credentials in environment variables)
    # Supported: "bright_data", "oxylabs", "smartproxy", "webshare"
    # Set env vars like BRIGHT_DATA_USERNAME, BRIGHT_DATA_PASSWORD, etc.
    proxy_provider: str = ""  # Leave empty to use static list or free proxies

    # Use free proxy lists (less reliable but free)
    use_free_proxies: bool = False


# =============================================================================
# SCRAPER SOURCES
# =============================================================================
@dataclass
class ScraperSources:
    """URLs and configurations for each job source."""

    # Canada - Official Job Bank (LMIA approved)
    canada_jobbank: Dict = field(default_factory=lambda: {
        "enabled": True,
        "base_url": "https://www.jobbank.gc.ca/jobsearch/jobsearch",
        "lmia_filter": "fsrc=32",  # LMIA-approved employers
        "search_params": {
            "searchstring": "software engineer",
            "sort": "D",  # Sort by date
        }
    })

    # UK - Gov.uk Sponsor List
    uk_sponsor_list: Dict = field(default_factory=lambda: {
        "enabled": True,
        "csv_url": "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers",
        "local_cache": DATA_DIR / "uk_sponsors.csv",
    })

    # USA - H1B Data sources
    usa_h1b: Dict = field(default_factory=lambda: {
        "enabled": True,
        "h1bvisajobs_url": "https://www.h1bvisajobs.com/h1b-jobs.php",
        "dol_lca_data": DATA_DIR / "h1b_sponsors.csv",  # Downloaded from DOL
    })

    # Indeed (US, UK, Canada)
    indeed: Dict = field(default_factory=lambda: {
        "enabled": True,
        "urls": {
            Country.US: "https://www.indeed.com/jobs",
            Country.UK: "https://uk.indeed.com/jobs",
            Country.CANADA: "https://ca.indeed.com/jobs",
        },
        "visa_filter": "sc=0kf:attr(FCGTU);",  # Visa sponsorship filter (US)
    })

    # LinkedIn
    linkedin: Dict = field(default_factory=lambda: {
        "enabled": True,
        "guest_api": "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
        "geo_ids": {
            Country.US: "103644278",
            Country.UK: "101165590",
            Country.CANADA: "101174742",
        }
    })

    # Glassdoor
    glassdoor: Dict = field(default_factory=lambda: {
        "enabled": True,
        "base_url": "https://www.glassdoor.com/Job/jobs.htm",
    })

    # Nigeria - Recruiting companies
    nigeria_recruiters: Dict = field(default_factory=lambda: {
        "enabled": True,
        "sources": {
            "RocketDevs": "https://www.rocketdevs.com/careers",
            "Crossing Hurdles": "https://app.careerpuck.com/job-board/crossing-hurdles",
            "Jobberman": "https://www.jobberman.com/jobs",
            "MyJobberman": "https://www.myjobberman.com",
        }
    })


# =============================================================================
# LLM CONFIGURATION (for cover letters and resume tailoring)
# =============================================================================
@dataclass
class LLMConfig:
    """LLM settings for AI-powered content generation."""

    # Use existing AIHawk LLM setup
    use_anthropic: bool = True
    model: str = "claude-opus-4-5"

    # API configuration (uses environment variables)
    # ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN should be set

    # Generation settings
    temperature: float = 0.7
    max_tokens: int = 2000

    # Prompts
    cover_letter_prompt: str = """
    Generate a professional cover letter for the following job:

    Company: {company}
    Role: {role}
    Job Description: {job_description}

    Candidate Profile:
    - Name: {name}
    - Experience: {years_experience} years
    - Current Role: Senior Software Engineer at Interswitch
    - Key Skills: Java, Spring Boot, Node.js, TypeScript, PostgreSQL, Docker, Kubernetes

    The cover letter should:
    1. Be concise (3-4 paragraphs)
    2. Highlight relevant experience matching the job requirements
    3. Show enthusiasm for the role and company
    4. Mention visa sponsorship requirement professionally if applicable
    """

    resume_tailor_prompt: str = """
    Suggest modifications to tailor this resume for the following job:

    Job Title: {role}
    Company: {company}
    Job Description: {job_description}

    Current Resume Summary: {resume_summary}

    Provide specific suggestions for:
    1. Summary section adjustments
    2. Which experiences to emphasize
    3. Skills to highlight
    4. Keywords to include
    """


# =============================================================================
# INSTANTIATE DEFAULT CONFIGS
# =============================================================================
USER = UserProfile()
RESUME = ResumeConfig()
VISA = VisaConfig()
JOB_PREFS = JobPreferences()
APP_SETTINGS = ApplicationSettings()
SCRAPERS = ScraperSources()
LLM = LLMConfig()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def get_resume_path(resume_type: ResumeType) -> Path:
    """Get the file path for a resume type."""
    return RESUME.base_resumes.get(resume_type)


def is_visa_sponsor(company_name: str) -> bool:
    """Check if a company is a known visa sponsor."""
    return company_name.lower() in [c.lower() for c in VISA.known_sponsors]


def matches_visa_keywords(text: str) -> bool:
    """Check if text contains visa sponsorship keywords."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in VISA.visa_keywords)


def should_exclude_job(title: str, description: str) -> bool:
    """Check if a job should be excluded based on keywords."""
    text = f"{title} {description}".lower()
    return any(kw in text for kw in JOB_PREFS.exclude_keywords)


def get_generated_resume_path(company: str, role: str, resume_type: ResumeType) -> Path:
    """Generate path for a tailored resume."""
    from datetime import datetime
    date_str = datetime.now().strftime("%Y%m%d")

    # Clean company and role names for filename
    company_clean = "".join(c if c.isalnum() else "_" for c in company)[:30]
    role_clean = "".join(c if c.isalnum() else "_" for c in role)[:30]

    filename = f"{company_clean}_{role_clean}_{date_str}_{resume_type.value}.pdf"
    return GENERATED_RESUMES_DIR / filename
