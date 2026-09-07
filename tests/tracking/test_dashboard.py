from tracking.dashboard import get_pipeline_stats
from db.models import Job, Application


def test_pipeline_stats_empty_db(db_session):
    stats = get_pipeline_stats(db_session)
    assert stats["total_scraped"] == 0
    assert stats["keyword_passed"] == 0
    assert stats["scored"] == 0
    assert stats["submitted"] == 0


def test_pipeline_stats_with_data(db_session):
    jobs = [
        Job(title="A", company="X", url="https://a.com/1", source="naukri", status="scraped", ats_type="naukri"),
        Job(title="B", company="Y", url="https://a.com/2", source="naukri", status="scraped", ats_type="naukri"),
        Job(title="C", company="Z", url="https://a.com/3", source="naukri", status="keyword_passed", keyword_score=60, ats_type="naukri"),
        Job(title="D", company="W", url="https://a.com/4", source="naukri", status="keyword_failed", keyword_score=20, ats_type="naukri"),
        Job(title="E", company="V", url="https://a.com/5", source="naukri", status="scored", claude_score=85, ats_type="naukri"),
        Job(title="F", company="U", url="https://a.com/6", source="naukri", status="ready_to_apply", claude_score=75, ats_type="naukri"),
        Job(title="G", company="T", url="https://a.com/7", source="naukri", status="submitted", claude_score=90, ats_type="naukri"),
    ]
    for j in jobs:
        db_session.add(j)
    db_session.flush()

    app = Application(job_id=jobs[-1].id, status="submitted", resume_path="resumes/templates/backend.pdf")
    db_session.add(app)
    db_session.flush()

    stats = get_pipeline_stats(db_session)
    assert stats["total_scraped"] == 7
    assert stats["keyword_passed"] == 1
    assert stats["keyword_failed"] == 1
    assert stats["scored"] == 1
    assert stats["ready_to_apply"] == 1
    assert stats["submitted"] == 1
    assert stats["applications_total"] == 1
