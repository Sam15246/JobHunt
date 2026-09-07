from db.models import Job, Application


def test_insert_and_read_job(db_session):
    job = Job(
        title="Backend Engineer",
        company="TestCorp",
        url="https://naukri.com/job/12345",
        source="naukri",
        jd_text="We need a backend engineer...",
        status="scraped",
        ats_type="naukri",
    )
    db_session.add(job)
    db_session.flush()

    result = db_session.query(Job).filter_by(url="https://naukri.com/job/12345").first()
    assert result is not None
    assert result.title == "Backend Engineer"
    assert result.status == "scraped"
    assert result.ats_type == "naukri"


def test_insert_application(db_session):
    job = Job(
        title="QA Engineer",
        company="TestCorp",
        url="https://naukri.com/job/99999",
        source="naukri",
        status="submitted",
        ats_type="naukri",
    )
    db_session.add(job)
    db_session.flush()

    app = Application(
        job_id=job.id,
        status="submitted",
        resume_path="resumes/templates/backend.pdf",
    )
    db_session.add(app)
    db_session.flush()

    result = db_session.query(Application).filter_by(job_id=job.id).first()
    assert result is not None
    assert result.status == "submitted"
    assert result.resume_path == "resumes/templates/backend.pdf"


def test_url_uniqueness(db_session):
    job1 = Job(title="A", company="X", url="https://example.com/1", source="naukri", ats_type="naukri")
    db_session.add(job1)
    db_session.flush()

    job2 = Job(title="B", company="Y", url="https://example.com/1", source="naukri", ats_type="naukri")
    db_session.add(job2)

    from sqlalchemy.exc import IntegrityError
    import pytest
    with pytest.raises(IntegrityError):
        db_session.flush()
