import logging
from sqlalchemy.orm import Session
from config import KEYWORDS, KEYWORD_SCORE_THRESHOLD
from db.models import Job

logger = logging.getLogger(__name__)


def compute_keyword_score(jd_text: str) -> int:
    """Score a job description by keyword overlap. Returns 0-100.

    Scoring:
    - Each must_have keyword found: +15 points
    - Each nice_to_have keyword found: +5 points
    - Each soft_exclude keyword found: -10 points
    - Clamped to [0, 100]
    """
    if not jd_text:
        return 0

    text_lower = jd_text.lower()

    score = 0
    for kw in KEYWORDS["must_have"]:
        if kw.lower() in text_lower:
            score += 15

    for kw in KEYWORDS["nice_to_have"]:
        if kw.lower() in text_lower:
            score += 5

    for kw in KEYWORDS["soft_exclude"]:
        if kw.lower() in text_lower:
            score -= 10

    return max(0, min(100, score))


def run_keyword_filter(session: Session) -> dict:
    """Process all jobs with status='scraped', update to keyword_passed or keyword_failed.

    Returns dict with counts: {"passed": N, "failed": M}
    """
    jobs = session.query(Job).filter(Job.status == "scraped").all()
    logger.info(f"Keyword filtering {len(jobs)} scraped jobs...")

    counts = {"passed": 0, "failed": 0}

    for job in jobs:
        combined_text = f"{job.title} {job.jd_text or ''}"
        score = compute_keyword_score(combined_text)

        job.keyword_score = score
        if score >= KEYWORD_SCORE_THRESHOLD:
            job.status = "keyword_passed"
            counts["passed"] += 1
        else:
            job.status = "keyword_failed"
            counts["failed"] += 1

    session.commit()
    logger.info(f"Keyword filter complete: {counts['passed']} passed, {counts['failed']} failed")
    return counts
