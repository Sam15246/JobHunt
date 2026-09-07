import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- Scorer Backend ---
# "gemini" (free) or "claude" (paid). Auto-detects based on which key is set.
SCORER_BACKEND = os.getenv("SCORER_BACKEND", "auto")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/job_automation")

# --- Naukri Credentials ---
NAUKRI_EMAIL = os.getenv("NAUKRI_EMAIL", "")
NAUKRI_PASSWORD = os.getenv("NAUKRI_PASSWORD", "")

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
