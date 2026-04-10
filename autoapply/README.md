# AutoApply - AI-Powered Job Application System

Automated job scraping and application system for visa-sponsored positions across multiple platforms.

## Features

- **Multi-Platform Scraping**: 9+ job sites scraped automatically
- **LinkedIn Auto-Apply**: Automatic Easy Apply with AI resume tailoring
- **Glassdoor Integration**: Cookie-based authentication for job scraping
- **AI Resume Tailoring**: Customize resume to match each job description
- **Visa Sponsorship Filter**: Skip jobs that don't sponsor visas
- **Free Captcha Solving**: Audio-based reCAPTCHA solver (no API keys needed)

## Supported Job Sites

| Site | Method | Status |
|------|--------|--------|
| Indeed | JobSpy | Working |
| LinkedIn | JobSpy + Auto-Apply Bot | Working |
| Glassdoor | Cookie Auth | Working |
| RemoteOK | Direct API | Working |
| WeWorkRemotely | RSS Feeds | Working |
| HackerNews Jobs | Firebase API | Working |
| Greenhouse | JSON API | Working |
| Lever | JSON API | Working |
| Ashby | REST API | Working |

## Project Structure

```
autoapply/
├── linkedin_bot/           # LinkedIn Auto-Apply Bot (cloned from GodsScion)
│   ├── config/
│   │   ├── secrets.py      # LinkedIn credentials
│   │   ├── personals.py    # Your personal info (name, phone, etc.)
│   │   ├── questions.py    # Application question answers
│   │   ├── search.py       # Job search filters & preferences
│   │   └── settings.py     # Bot settings
│   ├── resumes/
│   │   ├── senior_java.pdf
│   │   └── fullstack_nodejs.pdf
│   └── runAiBot.py         # Main bot script
├── scrapers/               # Job scrapers for different sites
│   ├── indeed.py
│   ├── linkedin.py
│   ├── glassdoor.py
│   ├── greenhouse.py
│   ├── remote_boards.py
│   └── ...
├── core/
│   ├── free_captcha_solver.py   # FREE reCAPTCHA audio solver
│   ├── manual_captcha.py        # Manual captcha with cookie save
│   └── botright_solver.py       # Botright AI solver
└── cookies/
    └── glassdoor_cookies.json   # Saved login cookies
```

## Installation

### Prerequisites
- Python 3.10+
- Google Chrome

### Install Dependencies

```bash
# Core dependencies
pip install python-jobspy playwright undetected-chromedriver pyautogui

# Install Playwright browsers
python -m playwright install chromium

# Optional: For AI resume tailoring (FREE)
# Download Ollama from https://ollama.com/download
# Then run: ollama pull llama3.2
```

## Configuration

### 1. LinkedIn Credentials
Edit `autoapply/linkedin_bot/config/secrets.py`:
```python
username = "your_email@gmail.com"
password = "your_password"
```

### 2. Personal Info
Edit `autoapply/linkedin_bot/config/personals.py`:
```python
first_name = "Your"
last_name = "Name"
phone_number = "+1234567890"
```

### 3. Search Preferences
Edit `autoapply/linkedin_bot/config/search.py`:
```python
search_terms = [
    "Java Developer",
    "Software Engineer",
    "Backend Developer",
    # ... more titles
]
search_location = ""  # Empty for global search
experience_level = ["Associate", "Mid-Senior level"]
```

### 4. Application Answers
Edit `autoapply/linkedin_bot/config/questions.py`:
```python
require_visa = "Yes"
years_of_experience = "5"
us_citizenship = "Non-citizen seeking work authorization"
```

## Usage

### Run LinkedIn Auto-Apply Bot

```bash
cd autoapply/linkedin_bot
python runAiBot.py
```

The bot will:
1. Open Chrome browser
2. Log into LinkedIn
3. Search for jobs matching your criteria
4. Apply to Easy Apply jobs automatically
5. Answer application questions
6. Skip jobs with "No Sponsorship" keywords

### Scrape Jobs with JobSpy

```python
from jobspy import scrape_jobs

jobs = scrape_jobs(
    site_name=["indeed", "linkedin", "glassdoor"],
    search_term="Java Developer visa sponsorship",
    location="United States",
    results_wanted=50,
    country_indeed='USA'
)
jobs.to_csv("jobs.csv")
```

### Use Glassdoor with Saved Cookies

```python
import json
from playwright.async_api import async_playwright

# Load saved cookies
with open('autoapply/cookies/glassdoor_cookies.json') as f:
    cookies = json.load(f)

# Use with Playwright
async with async_playwright() as p:
    browser = await p.chromium.launch()
    context = await browser.new_context()
    await context.add_cookies(cookies)
    # Now browse Glassdoor as logged-in user
```

## AI Resume Tailoring

### Option 1: Ollama (FREE, Local)

1. Download Ollama: https://ollama.com/download
2. Install a model:
   ```bash
   ollama pull llama3.2
   ```
3. Update `autoapply/linkedin_bot/config/secrets.py`:
   ```python
   use_AI = True
   ai_provider = "openai"
   llm_api_url = "http://localhost:11434/v1/"
   llm_api_key = "not-needed"
   llm_model = "llama3.2"
   ```

### Option 2: OpenAI (Paid)

```python
use_AI = True
ai_provider = "openai"
llm_api_url = "https://api.openai.com/v1/"
llm_api_key = "sk-your-api-key"
llm_model = "gpt-4o-mini"
```

## Visa Sponsorship Filtering

The bot automatically skips jobs containing these keywords:
- "US Citizen"
- "No Sponsorship"
- "Cannot Sponsor"
- "Security Clearance Required"
- "must be authorized to work"

Configure in `search.py`:
```python
bad_words = ["US Citizen", "No Sponsorship", "Cannot Sponsor", ...]
```

## Target Companies

The bot specifically searches for jobs at these remote-friendly companies:
- Turing
- Crossover
- Trilogy
- Deel
- Toptal
- Arc
- Remote
- GitLab
- Automattic

## Free Captcha Solver

For sites with reCAPTCHA v2:

```python
from autoapply.core.free_captcha_solver import solve_captcha

html = solve_captcha("https://site-with-captcha.com")
# Returns page HTML after solving captcha
```

Success rate: 70-90% using Google Speech Recognition (FREE).

## Estimated Jobs Per Run

| Source | Jobs |
|--------|------|
| Indeed | ~100+ |
| LinkedIn | ~100+ |
| Glassdoor | ~50+ |
| RemoteOK | ~100 |
| WeWorkRemotely | ~50 |
| HackerNews | ~30 |
| Greenhouse | ~200 |
| Lever | ~150 |
| Ashby | ~100 |
| **TOTAL** | **~880+ jobs** |

## Credits

- LinkedIn Auto-Apply Bot: [GodsScion/Auto_job_applier_linkedIn](https://github.com/GodsScion/Auto_job_applier_linkedIn)
- JobSpy: [speedyapply/JobSpy](https://github.com/speedyapply/JobSpy)
- Free Captcha Solver: Based on [AminBhst/Buster](https://github.com/AminBhst/Buster)

## License

MIT License - See LICENSE file for details.

## Disclaimer

This tool is for educational purposes. Use responsibly and in compliance with each platform's Terms of Service. The authors are not responsible for any account bans or legal issues arising from misuse.
