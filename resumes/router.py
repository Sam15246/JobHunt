import re
import logging
from sqlalchemy.orm import Session
from config import QA_TITLE_PATTERNS
from db.models import Job

logger = logging.getLogger(__name__)

TIER1_ATS_TYPES = frozenset({"naukri", "greenhouse", "lever"})

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

    counts = {"ready_to_apply": 0, "ready_for_manual_apply": 0}

    for job in jobs:
        job.resume_variant = pick_resume_variant(job.title)

        if job.ats_type in TIER1_ATS_TYPES:
            job.status = "ready_to_apply"
            counts["ready_to_apply"] += 1
        else:
            job.status = "ready_for_manual_apply"
            counts["ready_for_manual_apply"] += 1

    session.commit()
    logger.info(
        f"Resume routing complete: {counts['ready_to_apply']} ready to apply, "
        f"{counts['ready_for_manual_apply']} for manual apply"
    )
    return counts
