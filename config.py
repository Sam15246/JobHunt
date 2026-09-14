import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# --- Scorer Backend ---
# "groq" (free), "gemini" (free w/ billing), or "claude" (paid). Auto-detects.
SCORER_BACKEND = os.getenv("SCORER_BACKEND", "auto")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/job_automation")

# --- Naukri Credentials ---
NAUKRI_EMAIL = os.getenv("NAUKRI_EMAIL", "")
NAUKRI_PASSWORD = os.getenv("NAUKRI_PASSWORD", "")

# --- Workday (per-employer) ---
# One entry per company you want the Workday scraper/applier to watch.
# tenant/dc/site/locale come straight out of the company's careers URL:
#   https://{tenant}.{dc}.myworkdayjobs.com/{locale}/{site}?locations=...
# location_facets is the "locations=" value from that URL -- it's an
# opaque Workday ID, not a place name, so double-check it's still the
# right filter before relying on it (these can be per-tenant and easy to
# get wrong).
WORKDAY_EMPLOYERS = {
    "mastercard": {
        "tenant": "mastercard",
        "dc": "wd1",
        "site": "CorporateCareers",
        "locale": "en-US",
        "company_name": "Mastercard",
        # From: https://mastercard.wd1.myworkdayjobs.com/en-US/CorporateCareers?locations=8eab563831bf10acbc722e4859721571
        "location_facets": ["8eab563831bf10acbc722e4859721571"],
        "title_patterns": [
            "software engineer i", "software engineer ii", "software engineer iii",
            "senior software engineer",
        ],
        "search_text": "software engineer",
    },
}

# Credentials per Workday employer -- add to .env as, e.g.,
# WORKDAY_MASTERCARD_EMAIL / WORKDAY_MASTERCARD_PASSWORD. Never hardcode
# these here.
WORKDAY_CREDENTIALS = {
    key: {
        "email": os.getenv(f"WORKDAY_{key.upper()}_EMAIL", ""),
        "password": os.getenv(f"WORKDAY_{key.upper()}_PASSWORD", ""),
    }
    for key in WORKDAY_EMPLOYERS
}

# Per-employer auto-submit toggle.
#   False (default) -- the bot logs in, uses "Use My Last Application",
#     answers any screening question it recognizes from SCREENING_ANSWERS,
#     and STOPS one screen before Submit. Job status becomes
#     "awaiting_review"; you finish it yourself (log into the employer's
#     Workday candidate portal, find the saved in-progress application,
#     click Submit).
#   True -- the bot clicks Submit too, same as the Naukri applier.
# Defaults to False everywhere on purpose -- see the JobHunt system review
# doc for why a fully-automated submit to a company you actually want to
# work for deserves a more deliberate decision than a Naukri listing does.
WORKDAY_AUTO_SUBMIT = {key: False for key in WORKDAY_EMPLOYERS}

# Recurring screening-question answers, matched by case-insensitive
# substring against the question's label text on the page. Add to this as
# you hit new repeated questions. Anything NOT matched here gets a
# screenshot and is left for you -- the applier never guesses an answer.
# Example:
# SCREENING_ANSWERS = {
#     "are you legally authorized to work": "Yes",
#     "will you now or in the future require sponsorship": "No",
# }
SCREENING_ANSWERS = {
    # Zaki/Ali: fill this in with the actual recurring questions + answers.
}

# --- Candidate Profile ---
CANDIDATE = {
    "name": "Syed Ali Mujtaba",
    "email": NAUKRI_EMAIL,
    "phone": os.getenv("CANDIDATE_PHONE", ""),
    "experience_years": 2,
    "notice_period": "40 days",
    "current_location": "India",
    "target_geos": [
        "india", "singapore", "uk", "saudi_arabia",
        "new_zealand", "australia", "netherlands", "remote",
    ],
    "requires_sponsorship_for": [
        "singapore", "uk", "saudi_arabia",
        "new_zealand", "australia", "netherlands",
    ],
}

# --- Keyword Matching ---
KEYWORDS = {
    "must_have": [
        "backend", "python", "java", "spring", "fastapi",
        "microservices", "rest api", "api",
    ],
    "nice_to_have": [
        "langchain", "kubernetes", "distributed systems",
        "payments", "fintech", "kafka", "docker", "aws",
    ],
    "soft_exclude": [
        "staff engineer", "principal", "director",
        "10+ years", "15+ years", "senior staff",
    ],
}

QA_TITLE_PATTERNS = ["qa", "sdet", "test automation", "quality assurance", "test engineer"]

# --- Scoring Thresholds ---
KEYWORD_SCORE_THRESHOLD = 40   # out of 100
CLAUDE_SCORE_THRESHOLD = 70    # out of 100

# --- Rate Limits ---
DAILY_LIMITS = {
    "naukri": 25,
    "greenhouse": 30,
    "lever": 30,
    "workday": 15,
}

# --- Paths ---
RESUME_DIR = os.path.join(os.path.dirname(__file__), "resumes", "templates")
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
BROWSER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_data")
