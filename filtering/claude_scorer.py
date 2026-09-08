import json
import logging
from sqlalchemy.orm import Session
from config import (
    ANTHROPIC_API_KEY, GEMINI_API_KEY, GROQ_API_KEY, SCORER_BACKEND,
    CANDIDATE, CLAUDE_SCORE_THRESHOLD,
)
from db.models import Job

logger = logging.getLogger(__name__)

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


def _get_backend() -> str:
    """Determine which scoring backend to use."""
    if SCORER_BACKEND != "auto":
        return SCORER_BACKEND
    if GROQ_API_KEY:
        return "groq"
    if GEMINI_API_KEY:
        return "gemini"
    if ANTHROPIC_API_KEY:
        return "claude"
    raise RuntimeError(
        "No scorer API key found. Set GROQ_API_KEY (free), GEMINI_API_KEY, or ANTHROPIC_API_KEY in .env"
    )


def _build_prompt(title: str, jd_text: str) -> str:
    return SCORING_PROMPT.format(
        title=title,
        jd_text=jd_text[:3000],
        experience_years=CANDIDATE["experience_years"],
        location=CANDIDATE["current_location"],
        notice_period=CANDIDATE["notice_period"],
    )


def _score_with_claude(title: str, jd_text: str) -> dict:
    """Score using Anthropic Claude API."""
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = _build_prompt(title, jd_text)

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


def _score_with_gemini(title: str, jd_text: str) -> dict:
    """Score using Google Gemini API."""
    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = _build_prompt(title, jd_text)

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "max_output_tokens": 200,
        },
    )

    response_text = response.text.strip()
    result = json.loads(response_text)
    return {
        "score": int(result.get("score", 0)),
        "reason": result.get("reason", ""),
    }


def _score_with_groq(title: str, jd_text: str) -> dict:
    """Score using Groq API (free tier, very fast)."""
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)
    prompt = _build_prompt(title, jd_text)

    response = client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=200,
    )

    response_text = response.choices[0].message.content.strip()
    result = json.loads(response_text)
    return {
        "score": int(result.get("score", 0)),
        "reason": result.get("reason", ""),
    }


def score_job(title: str, jd_text: str) -> dict:
    """Score a job using the configured backend. Returns {score: int, reason: str}."""
    backend = _get_backend()

    try:
        if backend == "groq":
            return _score_with_groq(title, jd_text)
        elif backend == "gemini":
            return _score_with_gemini(title, jd_text)
        else:
            return _score_with_claude(title, jd_text)

    except json.JSONDecodeError:
        logger.warning(f"Failed to parse {backend} response for '{title}'")
        return {"score": 0, "reason": f"Error: could not parse {backend} response"}

    except Exception as e:
        logger.error(f"{backend} API error for '{title}': {e}")
        return {"score": 0, "reason": f"Error: {str(e)}"}


# Keep backward-compatible alias
score_job_with_claude = score_job


def run_claude_scorer(session: Session) -> dict:
    """Score all keyword_passed jobs. Updates status to scored or scored_low.

    Returns dict with counts: {"scored": N, "scored_low": M, "errors": E}
    """
    backend = _get_backend()
    jobs = session.query(Job).filter(Job.status == "keyword_passed").all()
    logger.info(f"Scoring {len(jobs)} keyword-passed jobs with {backend}...")

    counts = {"scored": 0, "scored_low": 0, "errors": 0}

    for job in jobs:
        result = score_job(job.title, job.jd_text or "")

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
        f"Scoring complete: {counts['scored']} scored, "
        f"{counts['scored_low']} low, {counts['errors']} errors"
    )
    return counts
