import re
import logging
from sqlalchemy.orm import Session
from config import QA_TITLE_PATTERNS
from db.models import Job

logger = logging.getLogger(__name__)

TIER1_ATS_TYPES = frozenset({"naukri", "greenhouse", "lever", "workday"})

_qa_pattern = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in QA_TITLE_PATTERNS) + r")\b",
    re.IGNORECASE,
)


def pick_resume_variant(title: str) -> str:
    """Return 'qa' if title matches QA patterns, else 'backend'."""
    if _qa_pattern.search(title):
        return "qa"
    return "backend"


def run_resume_router(session: Session) -> dict:
    """Assign resume variant to all scored jobs and advance their status.

    - Tier 1 ATS (naukri, greenhouse, lever) → ready_to_apply
    - Unknown/other ATS → ready_for_manual_apply

    Returns counts: {"ready_to_apply": N, "ready_for_manual_apply": M}
    """
    jobs = session.query(Job).filter(Job.status == "scored").all()
    logger.info(f"Routing resumes for {len(jobs)} scored jobs...")

    counts = {"ready_to_apply": 0, "ready_for_manual_apply": 0, "tailored": 0}

    for job in jobs:
        job.resume_variant = pick_resume_variant(job.title)

        # Tailor resume for this job (best-effort — falls back to generic)
        if job.jd_text:
            try:
                from resumes.tailor import tailor_resume
                from resumes.pdf_gen import generate_tailored_pdf
                tailored_text = tailor_resume(job.title, job.company, job.jd_text)
                generate_tailored_pdf(tailored_text, str(job.id))
                counts["tailored"] += 1
                logger.info(f"Tailored resume for: {job.title} @ {job.company}")
            except Exception as e:
                logger.warning(f"Resume tailoring failed for {job.title} @ {job.company}: {e}")

        if job.ats_type in TIER1_ATS_TYPES:
            job.status = "ready_to_apply"
            counts["ready_to_apply"] += 1
        else:
            job.status = "ready_for_manual_apply"
            counts["ready_for_manual_apply"] += 1

    session.commit()
    logger.info(
        f"Resume routing complete: {counts['ready_to_apply']} ready to apply, "
        f"{counts['ready_for_manual_apply']} for manual apply, "
        f"{counts['tailored']} resumes tailored"
    )
    return counts
