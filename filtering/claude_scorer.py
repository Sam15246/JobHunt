import json
import logging
from sqlalchemy.orm import Session
import anthropic
from config import ANTHROPIC_API_KEY, CANDIDATE, CLAUDE_SCORE_THRESHOLD
from db.models import Job

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SCORING_PROMPT = """Analyze this job description and score how well the candidate fits.

Job Title: {title}
Job Description:
{jd_text}

Candidate Profile:
- {experience_years}+ years backend experience (Java/Spring Boot, Python/FastAPI)
- Microservices, async processing, distributed systems
- Banking/payment systems (HSBC, Visa Click-to-Pay)
- LangChain/AI agent experience
- Current location: {location}
- Notice period: {notice_period}

Score the fit from 0-100 where:
- 90-100: Perfect match on skills, experience, and seniority
- 70-89: Strong match, meets most requirements
- 50-69: Partial match, missing some key requirements
- 0-49: Poor match

Return ONLY a JSON object (no markdown, no explanation outside the JSON):
{{"score": <number>, "reason": "<1-2 sentence explanation>"}}"""


def score_job_with_claude(title: str, jd_text: str) -> dict:
    """Send a job to Claude for fit scoring. Returns {score: int, reason: str}."""
    try:
        prompt = SCORING_PROMPT.format(
            title=title,
            jd_text=jd_text[:3000],
            experience_years=CANDIDATE["experience_years"],
            location=CANDIDATE["current_location"],
            notice_period=CANDIDATE["notice_period"],
        )

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text.strip()
        result = json.loads(response_text)
        return {
            "score": int(result.get("score", 0)),
            "reason": result.get("reason", ""),
        }

    except json.JSONDecodeError:
        logger.warning(f"Failed to parse Claude response for '{title}'")
        return {"score": 0, "reason": "Error: could not parse Claude response"}

    except Exception as e:
        logger.error(f"Claude API error for '{title}': {e}")
        return {"score": 0, "reason": f"Error: {str(e)}"}


def run_claude_scorer(session: Session) -> dict:
    """Score all keyword_passed jobs with Claude. Updates status to scored or scored_low.

    Returns dict with counts: {"scored": N, "scored_low": M, "errors": E}
    """
    jobs = session.query(Job).filter(Job.status == "keyword_passed").all()
    logger.info(f"Claude scoring {len(jobs)} keyword-passed jobs...")

    counts = {"scored": 0, "scored_low": 0, "errors": 0}

    for job in jobs:
        result = score_job_with_claude(job.title, job.jd_text or "")

        job.claude_score = result["score"]
        job.claude_reason = result["reason"]

        if result["score"] >= CLAUDE_SCORE_THRESHOLD:
            job.status = "scored"
            counts["scored"] += 1
        else:
            job.status = "scored_low"
            counts["scored_low"] += 1

        if result["score"] == 0 and "Error" in result["reason"]:
            counts["errors"] += 1

    session.commit()
    logger.info(
        f"Claude scoring complete: {counts['scored']} scored, "
        f"{counts['scored_low']} low, {counts['errors']} errors"
    )
    return counts
