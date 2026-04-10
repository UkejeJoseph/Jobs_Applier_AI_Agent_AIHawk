"""
Auto-Apply Module
=================
Selenium-based form filling for automated job applications.

Supports:
- Greenhouse ATS
- Lever ATS
- Workday
- Ashby
- BambooHR
- SmartRecruiters
- Generic job application forms
"""

import os
import re
import time
import random
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException,
        NoSuchElementException,
        ElementNotInteractableException,
        StaleElementReferenceException,
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

from autoapply.core.browser import StealthBrowser, BrowserConfig
from autoapply.core.job_schema import Job, JobStatus
from autoapply.config import USER, APP_SETTINGS, RESUMES_DIR, GENERATED_RESUMES_DIR

logger = logging.getLogger("autoapply.auto_apply")


class ATSType(Enum):
    """Application Tracking System types."""
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    ASHBY = "ashby"
    BAMBOOHR = "bamboohr"
    SMARTRECRUITERS = "smartrecruiters"
    ICIMS = "icims"
    GENERIC = "generic"
    UNKNOWN = "unknown"


@dataclass
class ApplicationResult:
    """Result of an application attempt."""
    success: bool
    job_id: str
    ats_type: ATSType
    error_message: str = ""
    screenshot_path: Optional[Path] = None
    confirmation_number: str = ""


@dataclass
class FormField:
    """Represents a form field to fill."""
    name: str
    selector: str
    value: str
    field_type: str = "text"  # text, select, checkbox, radio, file, textarea


class ATSDetector:
    """Detects which ATS a job application page uses."""

    ATS_PATTERNS = {
        ATSType.GREENHOUSE: [
            "greenhouse.io",
            "boards.greenhouse.io",
            "job-boards.greenhouse.io",
            "grnh.se",
            "data-greenhouse",
        ],
        ATSType.LEVER: [
            "lever.co",
            "jobs.lever.co",
            "data-lever",
        ],
        ATSType.WORKDAY: [
            "workday.com",
            "myworkdayjobs.com",
            "wd1.myworkdayjobs",
            "wd3.myworkdayjobs",
            "wd5.myworkdayjobs",
        ],
        ATSType.ASHBY: [
            "ashbyhq.com",
            "jobs.ashbyhq.com",
        ],
        ATSType.BAMBOOHR: [
            "bamboohr.com",
            "app.bamboohr.com",
        ],
        ATSType.SMARTRECRUITERS: [
            "smartrecruiters.com",
            "jobs.smartrecruiters.com",
        ],
        ATSType.ICIMS: [
            "icims.com",
            "careers-",
            "jobs-",
        ],
    }

    @classmethod
    def detect(cls, url: str, page_source: str = "") -> ATSType:
        """Detect ATS type from URL and page source."""
        url_lower = url.lower()
        source_lower = page_source.lower()

        for ats_type, patterns in cls.ATS_PATTERNS.items():
            for pattern in patterns:
                if pattern in url_lower or pattern in source_lower:
                    return ats_type

        return ATSType.UNKNOWN


class AutoApplier:
    """
    Main class for automated job applications.

    Usage:
        applier = AutoApplier()
        result = applier.apply(job)
    """

    def __init__(
        self,
        resume_path: Optional[Path] = None,
        cover_letter_generator=None,
        headless: bool = True,
    ):
        """
        Initialize the auto-applier.

        Args:
            resume_path: Path to default resume file
            cover_letter_generator: Function to generate cover letters
            headless: Run browser in headless mode
        """
        if not SELENIUM_AVAILABLE:
            raise ImportError(
                "Selenium not installed. Run: pip install selenium undetected-chromedriver"
            )

        self.resume_path = resume_path or self._find_default_resume()
        self.cover_letter_generator = cover_letter_generator
        self.headless = headless
        self.browser: Optional[StealthBrowser] = None

        # User data for form filling
        self.user_data = {
            "first_name": USER.name.split()[0],
            "last_name": " ".join(USER.name.split()[1:]) if len(USER.name.split()) > 1 else "",
            "full_name": USER.name,
            "email": USER.email,
            "phone": USER.phone,
            "location": USER.location,
            "linkedin": USER.linkedin,
            "github": USER.github,
            "portfolio": USER.portfolio,
            "years_experience": str(USER.years_experience),
            "current_company": USER.current_company,
        }

    def _find_default_resume(self) -> Optional[Path]:
        """Find a default resume file."""
        for ext in [".pdf", ".docx", ".doc"]:
            for resume_dir in [RESUMES_DIR, GENERATED_RESUMES_DIR]:
                if resume_dir.exists():
                    resumes = list(resume_dir.glob(f"*{ext}"))
                    if resumes:
                        return resumes[0]
        return None

    def _start_browser(self):
        """Start browser if not already started."""
        if self.browser is None:
            config = BrowserConfig(headless=self.headless)
            self.browser = StealthBrowser(config)
            self.browser.start()

    def _stop_browser(self):
        """Stop browser."""
        if self.browser:
            self.browser.stop()
            self.browser = None

    def apply(self, job: Job, cover_letter: str = "") -> ApplicationResult:
        """
        Apply to a job.

        Args:
            job: Job object to apply to
            cover_letter: Optional cover letter text

        Returns:
            ApplicationResult with success/failure info
        """
        logger.info(f"Attempting to apply: {job.company} - {job.role}")

        try:
            self._start_browser()

            # Navigate to job URL
            self.browser.get_page(job.job_url, handle_captcha=True)
            time.sleep(random.uniform(2, 4))

            # Detect ATS type
            ats_type = ATSDetector.detect(
                job.job_url,
                self.browser.page_source
            )
            logger.info(f"Detected ATS: {ats_type.value}")

            # Find and click apply button
            if not self._click_apply_button():
                return ApplicationResult(
                    success=False,
                    job_id=job.job_id,
                    ats_type=ats_type,
                    error_message="Could not find apply button",
                )

            time.sleep(random.uniform(2, 3))

            # Route to appropriate ATS handler
            if ats_type == ATSType.GREENHOUSE:
                result = self._apply_greenhouse(job, cover_letter)
            elif ats_type == ATSType.LEVER:
                result = self._apply_lever(job, cover_letter)
            elif ats_type == ATSType.WORKDAY:
                result = self._apply_workday(job, cover_letter)
            elif ats_type == ATSType.ASHBY:
                result = self._apply_ashby(job, cover_letter)
            else:
                result = self._apply_generic(job, cover_letter)

            result.ats_type = ats_type
            return result

        except Exception as e:
            logger.error(f"Application failed: {e}")
            screenshot = None
            if self.browser:
                try:
                    screenshot = self.browser.save_screenshot(f"error_{job.job_id}.png")
                except:
                    pass

            return ApplicationResult(
                success=False,
                job_id=job.job_id,
                ats_type=ATSType.UNKNOWN,
                error_message=str(e),
                screenshot_path=screenshot,
            )

    def _click_apply_button(self) -> bool:
        """Find and click the apply button."""
        apply_selectors = [
            # Common apply button patterns
            "button[data-qa='apply-button']",
            "a[data-qa='apply-button']",
            "button.apply-button",
            "a.apply-button",
            "button[class*='apply']",
            "a[class*='apply']",
            "#apply-now",
            "#apply-button",
            ".apply-now",
            "button[aria-label*='Apply']",
            "a[aria-label*='Apply']",
            # Greenhouse specific
            "a[data-click-id='apply']",
            ".postings-btn",
            "a.postings-link",
            # Lever specific
            ".posting-btn-submit",
            "a.postings-link",
            # Text-based selectors (last resort)
            "//button[contains(text(), 'Apply')]",
            "//a[contains(text(), 'Apply')]",
            "//button[contains(text(), 'Submit Application')]",
        ]

        for selector in apply_selectors:
            try:
                if selector.startswith("//"):
                    # XPath selector
                    elements = self.browser.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.browser.driver.find_elements(By.CSS_SELECTOR, selector)

                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        self.browser._human_click(element)
                        logger.info(f"Clicked apply button: {selector}")
                        return True
            except (NoSuchElementException, ElementNotInteractableException):
                continue

        return False

    def _apply_greenhouse(self, job: Job, cover_letter: str) -> ApplicationResult:
        """Handle Greenhouse ATS applications."""
        logger.info("Processing Greenhouse application...")

        try:
            # Wait for form to load
            WebDriverWait(self.browser.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form, #application-form, .application"))
            )

            # Fill basic info
            self._fill_field("#first_name", self.user_data["first_name"])
            self._fill_field("#last_name", self.user_data["last_name"])
            self._fill_field("#email", self.user_data["email"])
            self._fill_field("#phone", self.user_data["phone"])

            # LinkedIn / GitHub
            self._fill_field("input[name*='linkedin']", self.user_data["linkedin"])
            self._fill_field("input[name*='github']", self.user_data["github"])
            self._fill_field("input[name*='portfolio']", self.user_data["portfolio"])

            # Upload resume
            if self.resume_path and self.resume_path.exists():
                self._upload_file("input[type='file'][name*='resume']", self.resume_path)
                self._upload_file("input[type='file'][id*='resume']", self.resume_path)
                self._upload_file("input[data-field='resume']", self.resume_path)

            # Cover letter
            if cover_letter:
                self._fill_field("textarea[name*='cover']", cover_letter)
                self._fill_field("#cover_letter", cover_letter)

            # Handle custom questions
            self._handle_greenhouse_questions()

            # Scroll to bottom and submit
            self.browser.scroll_page(1000)
            time.sleep(1)

            # Submit
            if self._click_submit_button():
                time.sleep(3)
                if self._check_success():
                    return ApplicationResult(
                        success=True,
                        job_id=job.job_id,
                        ats_type=ATSType.GREENHOUSE,
                    )

            return ApplicationResult(
                success=False,
                job_id=job.job_id,
                ats_type=ATSType.GREENHOUSE,
                error_message="Submission may have failed - please verify",
            )

        except Exception as e:
            return ApplicationResult(
                success=False,
                job_id=job.job_id,
                ats_type=ATSType.GREENHOUSE,
                error_message=str(e),
            )

    def _apply_lever(self, job: Job, cover_letter: str) -> ApplicationResult:
        """Handle Lever ATS applications."""
        logger.info("Processing Lever application...")

        try:
            # Wait for form
            WebDriverWait(self.browser.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form, .application-form"))
            )

            # Fill fields
            self._fill_field("input[name='name']", self.user_data["full_name"])
            self._fill_field("input[name='email']", self.user_data["email"])
            self._fill_field("input[name='phone']", self.user_data["phone"])
            self._fill_field("input[name='org']", self.user_data["current_company"])

            # URLs
            self._fill_field("input[name*='urls[LinkedIn]']", self.user_data["linkedin"])
            self._fill_field("input[name*='urls[GitHub]']", self.user_data["github"])
            self._fill_field("input[name*='urls[Portfolio]']", self.user_data["portfolio"])

            # Resume
            if self.resume_path and self.resume_path.exists():
                self._upload_file("input[type='file'][name='resume']", self.resume_path)
                self._upload_file("input.resume-upload", self.resume_path)

            # Cover letter
            if cover_letter:
                self._fill_field("textarea[name='comments']", cover_letter)

            # Handle custom questions
            self._handle_lever_questions()

            time.sleep(1)

            # Submit
            if self._click_submit_button():
                time.sleep(3)
                if self._check_success():
                    return ApplicationResult(
                        success=True,
                        job_id=job.job_id,
                        ats_type=ATSType.LEVER,
                    )

            return ApplicationResult(
                success=False,
                job_id=job.job_id,
                ats_type=ATSType.LEVER,
                error_message="Submission may have failed",
            )

        except Exception as e:
            return ApplicationResult(
                success=False,
                job_id=job.job_id,
                ats_type=ATSType.LEVER,
                error_message=str(e),
            )

    def _apply_workday(self, job: Job, cover_letter: str) -> ApplicationResult:
        """Handle Workday ATS applications."""
        logger.info("Processing Workday application...")

        try:
            # Workday often requires creating an account or signing in
            # For now, just fill what we can

            WebDriverWait(self.browser.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form, [data-automation-id='applicationForm']"))
            )

            # Try to use "Apply Manually" if available
            try:
                manual_btn = self.browser.driver.find_element(
                    By.XPATH, "//button[contains(text(), 'Apply Manually')]"
                )
                manual_btn.click()
                time.sleep(2)
            except NoSuchElementException:
                pass

            # Fill fields using Workday's data-automation-id attributes
            self._fill_field("[data-automation-id='legalNameSection_firstName']", self.user_data["first_name"])
            self._fill_field("[data-automation-id='legalNameSection_lastName']", self.user_data["last_name"])
            self._fill_field("[data-automation-id='email']", self.user_data["email"])
            self._fill_field("[data-automation-id='phone-number']", self.user_data["phone"])

            # Resume upload
            if self.resume_path:
                self._upload_file("[data-automation-id='file-upload-input-ref']", self.resume_path)

            return ApplicationResult(
                success=False,
                job_id=job.job_id,
                ats_type=ATSType.WORKDAY,
                error_message="Workday requires manual completion - form partially filled",
            )

        except Exception as e:
            return ApplicationResult(
                success=False,
                job_id=job.job_id,
                ats_type=ATSType.WORKDAY,
                error_message=str(e),
            )

    def _apply_ashby(self, job: Job, cover_letter: str) -> ApplicationResult:
        """Handle Ashby ATS applications."""
        logger.info("Processing Ashby application...")

        try:
            WebDriverWait(self.browser.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form"))
            )

            # Ashby uses standard form fields
            self._fill_field("input[name='name']", self.user_data["full_name"])
            self._fill_field("input[name='email']", self.user_data["email"])
            self._fill_field("input[name='phone']", self.user_data["phone"])
            self._fill_field("input[name*='linkedin']", self.user_data["linkedin"])
            self._fill_field("input[name*='github']", self.user_data["github"])

            # Resume
            if self.resume_path:
                self._upload_file("input[type='file']", self.resume_path)

            # Cover letter
            if cover_letter:
                self._fill_field("textarea[name*='cover']", cover_letter)
                self._fill_field("textarea", cover_letter)

            if self._click_submit_button():
                time.sleep(3)
                if self._check_success():
                    return ApplicationResult(
                        success=True,
                        job_id=job.job_id,
                        ats_type=ATSType.ASHBY,
                    )

            return ApplicationResult(
                success=False,
                job_id=job.job_id,
                ats_type=ATSType.ASHBY,
                error_message="Submission may have failed",
            )

        except Exception as e:
            return ApplicationResult(
                success=False,
                job_id=job.job_id,
                ats_type=ATSType.ASHBY,
                error_message=str(e),
            )

    def _apply_generic(self, job: Job, cover_letter: str) -> ApplicationResult:
        """Handle generic application forms."""
        logger.info("Processing generic application...")

        try:
            # Try common field patterns
            field_mappings = [
                # Name fields
                ("input[name*='first']", self.user_data["first_name"]),
                ("input[name*='First']", self.user_data["first_name"]),
                ("input[id*='first']", self.user_data["first_name"]),
                ("input[placeholder*='First']", self.user_data["first_name"]),
                ("input[name*='last']", self.user_data["last_name"]),
                ("input[name*='Last']", self.user_data["last_name"]),
                ("input[id*='last']", self.user_data["last_name"]),
                ("input[placeholder*='Last']", self.user_data["last_name"]),
                ("input[name*='name']", self.user_data["full_name"]),
                ("input[name='name']", self.user_data["full_name"]),

                # Email
                ("input[type='email']", self.user_data["email"]),
                ("input[name*='email']", self.user_data["email"]),
                ("input[name='email']", self.user_data["email"]),

                # Phone
                ("input[type='tel']", self.user_data["phone"]),
                ("input[name*='phone']", self.user_data["phone"]),
                ("input[name*='Phone']", self.user_data["phone"]),

                # LinkedIn
                ("input[name*='linkedin']", self.user_data["linkedin"]),
                ("input[name*='LinkedIn']", self.user_data["linkedin"]),
                ("input[placeholder*='LinkedIn']", self.user_data["linkedin"]),

                # GitHub
                ("input[name*='github']", self.user_data["github"]),
                ("input[name*='GitHub']", self.user_data["github"]),
                ("input[placeholder*='GitHub']", self.user_data["github"]),
            ]

            filled_count = 0
            for selector, value in field_mappings:
                if self._fill_field(selector, value):
                    filled_count += 1

            # Resume upload
            if self.resume_path:
                file_inputs = ["input[type='file']", "input[accept*='pdf']", "input[name*='resume']"]
                for selector in file_inputs:
                    if self._upload_file(selector, self.resume_path):
                        break

            # Cover letter
            if cover_letter:
                textarea_selectors = ["textarea[name*='cover']", "textarea[name*='message']", "textarea"]
                for selector in textarea_selectors:
                    if self._fill_field(selector, cover_letter):
                        break

            if filled_count < 3:
                return ApplicationResult(
                    success=False,
                    job_id=job.job_id,
                    ats_type=ATSType.GENERIC,
                    error_message=f"Only filled {filled_count} fields - form may need manual completion",
                )

            if self._click_submit_button():
                time.sleep(3)
                if self._check_success():
                    return ApplicationResult(
                        success=True,
                        job_id=job.job_id,
                        ats_type=ATSType.GENERIC,
                    )

            return ApplicationResult(
                success=False,
                job_id=job.job_id,
                ats_type=ATSType.GENERIC,
                error_message="Submission may have failed - please verify",
            )

        except Exception as e:
            return ApplicationResult(
                success=False,
                job_id=job.job_id,
                ats_type=ATSType.GENERIC,
                error_message=str(e),
            )

    def _fill_field(self, selector: str, value: str) -> bool:
        """Fill a form field."""
        try:
            elements = self.browser.driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                if element.is_displayed() and element.is_enabled():
                    element.clear()
                    time.sleep(random.uniform(0.1, 0.3))

                    # Type with human-like delays
                    for char in value:
                        element.send_keys(char)
                        time.sleep(random.uniform(0.02, 0.08))

                    logger.debug(f"Filled field: {selector}")
                    return True
        except (NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException):
            pass
        return False

    def _upload_file(self, selector: str, file_path: Path) -> bool:
        """Upload a file to a file input."""
        try:
            elements = self.browser.driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                try:
                    # File inputs don't need to be visible
                    element.send_keys(str(file_path.absolute()))
                    logger.debug(f"Uploaded file: {selector}")
                    time.sleep(1)
                    return True
                except:
                    continue
        except (NoSuchElementException, ElementNotInteractableException):
            pass
        return False

    def _click_submit_button(self) -> bool:
        """Find and click the submit button."""
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button[data-qa='submit-application']",
            "button[class*='submit']",
            ".submit-button",
            "#submit",
            "#submit-application",
            "//button[contains(text(), 'Submit')]",
            "//button[contains(text(), 'Apply')]",
            "//input[@value='Submit']",
            "//input[@value='Apply']",
        ]

        for selector in submit_selectors:
            try:
                if selector.startswith("//"):
                    elements = self.browser.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.browser.driver.find_elements(By.CSS_SELECTOR, selector)

                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        self.browser._human_click(element)
                        logger.info(f"Clicked submit: {selector}")
                        return True
            except (NoSuchElementException, ElementNotInteractableException):
                continue

        return False

    def _check_success(self) -> bool:
        """Check if application was submitted successfully."""
        success_indicators = [
            "thank you",
            "application received",
            "successfully submitted",
            "application submitted",
            "we've received your application",
            "confirmation",
            "applied",
        ]

        page_text = self.browser.page_source.lower()
        url = self.browser.current_url.lower()

        for indicator in success_indicators:
            if indicator in page_text or indicator in url:
                logger.info(f"Success indicator found: {indicator}")
                return True

        return False

    def _handle_greenhouse_questions(self):
        """Handle common Greenhouse custom questions."""
        # Visa sponsorship questions
        visa_selectors = [
            "input[name*='visa']",
            "input[name*='sponsorship']",
            "input[name*='authorized']",
            "select[name*='visa']",
            "select[name*='sponsorship']",
        ]

        for selector in visa_selectors:
            try:
                element = self.browser.driver.find_element(By.CSS_SELECTOR, selector)
                if element.tag_name == "select":
                    select = Select(element)
                    # Try to select "Yes" or "I will require sponsorship"
                    for option in select.options:
                        if "yes" in option.text.lower() or "require" in option.text.lower():
                            select.select_by_visible_text(option.text)
                            break
                else:
                    # Radio/checkbox - look for "Yes" label
                    pass
            except NoSuchElementException:
                continue

        # Years of experience
        exp_selectors = ["input[name*='experience']", "select[name*='experience']"]
        for selector in exp_selectors:
            try:
                element = self.browser.driver.find_element(By.CSS_SELECTOR, selector)
                if element.tag_name == "select":
                    select = Select(element)
                    # Select appropriate experience range
                    for option in select.options:
                        if "5" in option.text or "3-5" in option.text or "5-7" in option.text:
                            select.select_by_visible_text(option.text)
                            break
                else:
                    element.send_keys(self.user_data["years_experience"])
            except NoSuchElementException:
                continue

    def _handle_lever_questions(self):
        """Handle common Lever custom questions."""
        # Similar pattern to Greenhouse
        self._handle_greenhouse_questions()

    def close(self):
        """Clean up resources."""
        self._stop_browser()


class CoverLetterGenerator:
    """Generates cover letters using LLM."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def generate(self, job: Job, user_data: dict) -> str:
        """Generate a cover letter for a job."""
        if not self.llm_client:
            return self._generate_template(job, user_data)

        # Use LLM to generate
        prompt = f"""
        Generate a professional cover letter for:

        Company: {job.company}
        Role: {job.role}
        Location: {job.location}

        Candidate:
        - Name: {user_data.get('full_name', '')}
        - Experience: {user_data.get('years_experience', 5)} years
        - Current Company: {user_data.get('current_company', '')}

        Keep it concise (3 paragraphs), professional, and highlight relevant experience.
        """

        try:
            response = self.llm_client.generate(prompt)
            return response
        except:
            return self._generate_template(job, user_data)

    def _generate_template(self, job: Job, user_data: dict) -> str:
        """Generate a template cover letter."""
        return f"""Dear Hiring Manager,

I am writing to express my interest in the {job.role} position at {job.company}. With {user_data.get('years_experience', 5)} years of experience in software engineering, I believe I would be a valuable addition to your team.

In my current role at {user_data.get('current_company', 'my company')}, I have developed expertise in backend development, microservices architecture, and cloud technologies. I am particularly drawn to {job.company}'s mission and would welcome the opportunity to contribute to your team's success.

I am excited about this opportunity and would love to discuss how my skills and experience align with your needs. Thank you for considering my application.

Best regards,
{user_data.get('full_name', '')}
"""
