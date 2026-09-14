"""Shared DB write helpers for scrapers.

Pulled out of scrapers/naukri.py so every scraper (Naukri, Workday, and
whatever comes next) saves jobs the same way — including the same-role
cooldown check, which plain URL-uniqueness can't provide on platforms like
Workday that reissue a "same" opening under a new requisition ID/URL when
they repost it.
"""
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from db.connection import get_session
from db.models import Job

logger = logging.getLogger(__name__)


def is_recent_duplicate_role(session, company: str, title: str, location: str | None,
                              cooldown_days: int) -> bool:
    """True if a job with the same company + title + location was already
    scraped within the cooldown window.

    Matching is case-insensitive and exact on title text — deliberately not
    fuzzy, since a wrong match would silently hide a real new opening.
    Pass cooldown_days=0 (the default everywhere except Workday) to disable
    this check entirely and rely on URL-uniqueness alone.
    """
    if not cooldown_days or cooldown_days <= 0:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(days=cooldown_days)
    query = session.query(func.count(Job.id)).filter(
        func.lower(Job.company) == company.lower(),
        func.lower(Job.title) == title.lower(),
        Job.created_at >= cutoff,
    )
    if location:
        query = query.filter(func.lower(Job.location) == location.lower())

    return query.scalar() > 0


def save_jobs_to_db(jobs: list[dict], cooldown_days: int = 0, session=None) -> int:
    """Insert scraped jobs, skipping URL duplicates (DB constraint) and,
    when cooldown_days > 0, skipping same company+title+location postings
    seen within the cooldown window even if the URL differs.

    Pass an existing session (e.g. a test's db_session fixture) to run
    inside someone else's transaction; otherwise a new one is opened and
    closed here, same as before this was split out of scrapers/naukri.py.

    Returns the number of jobs actually inserted.
    """
    owns_session = session is None
    if owns_session:
        session = get_session()

    inserted = 0
    skipped_role_duplicate = 0
    try:
        for job_data in jobs:
            if is_recent_duplicate_role(
                session, job_data["company"], job_data["title"],
                job_data.get("location"), cooldown_days,
            ):
                skipped_role_duplicate += 1
                continue

            stmt = pg_insert(Job).values(
                title=job_data["title"],
                company=job_data["company"],
                url=job_data["url"],
                source=job_data["source"],
                jd_text=job_data.get("jd_text"),
                location=job_data.get("location"),
                geo_region=job_data.get("geo_region"),
                ats_type=job_data.get("ats_type", "unknown"),
                status="scraped",
                discovered_sources=job_data.get("discovered_sources", []),
            ).on_conflict_do_nothing(index_elements=["url"])
            result = session.execute(stmt)
            if result.rowcount > 0:
                inserted += 1

        session.commit()
        url_duplicates = len(jobs) - inserted - skipped_role_duplicate
        logger.info(
            f"Inserted {inserted} new jobs ({url_duplicates} URL duplicates, "
            f"{skipped_role_duplicate} same-role reposts skipped)"
        )
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()

    return inserted
