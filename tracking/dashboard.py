import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from db.models import Job, Application

logger = logging.getLogger(__name__)


def get_pipeline_stats(session: Session) -> dict:
    def count_status(status: str) -> int:
        return session.query(func.count(Job.id)).filter(Job.status == status).scalar()

    total = session.query(func.count(Job.id)).scalar()
    apps_total = session.query(func.count(Application.id)).scalar()
    apps_submitted = session.query(func.count(Application.id)).filter(Application.status == "submitted").scalar()
    apps_failed = session.query(func.count(Application.id)).filter(Application.status == "failed").scalar()
    apps_interview = session.query(func.count(Application.id)).filter(Application.status == "interview").scalar()

    return {
        "total_scraped": total,
        "scraped": count_status("scraped"),
        "keyword_passed": count_status("keyword_passed"),
        "keyword_failed": count_status("keyword_failed"),
        "scored": count_status("scored"),
        "scored_low": count_status("scored_low"),
        "ready_to_apply": count_status("ready_to_apply"),
        "ready_for_manual_apply": count_status("ready_for_manual_apply"),
        "awaiting_review": count_status("awaiting_review"),
        "submitted": count_status("submitted"),
        "failed": count_status("failed"),
        "skipped": count_status("skipped"),
        "applications_total": apps_total,
        "applications_submitted": apps_submitted,
        "applications_failed": apps_failed,
        "applications_interview": apps_interview,
    }


def print_dashboard(session: Session):
    stats = get_pipeline_stats(session)

    print("\n" + "=" * 55)
    print("  JOB AUTOMATION PIPELINE - DASHBOARD")
    print("=" * 55)
    print(f"  Total jobs discovered:      {stats['total_scraped']:>6}")
    print("-" * 55)
    print("  PIPELINE STATUS:")
    print(f"    Awaiting keyword filter:  {stats['scraped']:>6}")
    print(f"    Keyword passed:           {stats['keyword_passed']:>6}")
    print(f"    Keyword failed:           {stats['keyword_failed']:>6}")
    print(f"    Claude scored (>=70):      {stats['scored']:>6}")
    print(f"    Claude scored (<70):      {stats['scored_low']:>6}")
    print(f"    Ready to apply (bot):     {stats['ready_to_apply']:>6}")
    print(f"    Ready to apply (manual):  {stats['ready_for_manual_apply']:>6}")
    print(f"    Awaiting your review:     {stats['awaiting_review']:>6}")
    print(f"    Submitted:                {stats['submitted']:>6}")
    print(f"    Failed:                   {stats['failed']:>6}")
    print(f"    Skipped:                  {stats['skipped']:>6}")
    print("-" * 55)
    print("  APPLICATIONS:")
    print(f"    Total submitted:          {stats['applications_submitted']:>6}")
    print(f"    Failed:                   {stats['applications_failed']:>6}")
    print(f"    Interviews:               {stats['applications_interview']:>6}")

    if stats["applications_submitted"] > 0:
        callback_rate = (stats["applications_interview"] / stats["applications_submitted"]) * 100
        print(f"    Callback rate:            {callback_rate:>5.1f}%")

    print("=" * 55 + "\n")
