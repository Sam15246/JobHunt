"""Resume tailoring module — rewrites the base resume to match a specific JD.

Uses Groq (free) by default. Reads the base resume from
resumes/base_resume.txt, sends it + the JD to the LLM, gets back a
tailored version with reordered bullets and JD-specific keywords woven in.
Does NOT fabricate experience or skills — only reorders, emphasizes, and
adjusts phrasing.

Output: plain text (fed to the PDF generator in resumes/pdf_gen.py).
"""
import os
import json
import logging
from config import GROQ_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

BASE_RESUME_PATH = os.path.join(os.path.dirname(__file__), "base_resume.txt")

TAILOR_PROMPT = """You are an expert resume writer. Your task is to tailor the candidate's resume for a specific job posting.

RULES (strictly follow):
1. ONLY reorder, emphasize, and rephrase existing content. NEVER invent experience, skills, or achievements the candidate doesn't have.
2. Move the most relevant bullets to the top of each section.
3. Mirror exact keywords and phrases from the job description where the candidate genuinely has that experience.
4. Adjust the headline/tagline to align with the target role.
5. If the JD emphasizes a skill the candidate has but is buried, bring it forward.
6. Keep the same overall structure: headline, skills, experience, projects, education, certifications.
7. Keep it to ONE page — do not add new bullets. You may slightly shorten less relevant bullets to make room for expanding relevant ones.
8. Return ONLY the tailored resume text, nothing else. No commentary, no markdown fences, no "Here is your tailored resume" preamble.

TARGET JOB:
Title: {job_title}
Company: {company}

Job Description:
{jd_text}

CANDIDATE'S BASE RESUME:
{resume_text}

Return the tailored resume now:"""


def _load_base_resume() -> str:
    with open(BASE_RESUME_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _tailor_with_groq(prompt: str) -> str:
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def _tailor_with_gemini(prompt: str) -> str:
    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config={"max_output_tokens": 4000},
    )
    return response.text.strip()


def _tailor_with_claude(prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def tailor_resume(job_title: str, company: str, jd_text: str) -> str:
    """Tailor the base resume for a specific job. Returns the tailored resume
    as plain text. Raises on failure (caller decides what to do)."""
    resume_text = _load_base_resume()
    prompt = TAILOR_PROMPT.format(
        job_title=job_title,
        company=company,
        jd_text=jd_text[:4000],
        resume_text=resume_text,
    )

    # Use whichever backend is available (same priority as scorer)
    if GROQ_API_KEY:
        logger.info(f"Tailoring resume for '{job_title}' @ {company} via Groq")
        text = _tailor_with_groq(prompt)
    elif GEMINI_API_KEY:
        logger.info(f"Tailoring resume for '{job_title}' @ {company} via Gemini")
        text = _tailor_with_gemini(prompt)
    elif ANTHROPIC_API_KEY:
        logger.info(f"Tailoring resume for '{job_title}' @ {company} via Claude")
        text = _tailor_with_claude(prompt)
    else:
        raise RuntimeError("No API key found for resume tailoring. Set GROQ_API_KEY in .env")

    # Strip any markdown fences the LLM might have added
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    return text
