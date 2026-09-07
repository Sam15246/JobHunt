from resumes.router import pick_resume_variant, run_resume_router
from db.models import Job


class TestPickResumeVariant:
    def test_qa_title_returns_qa(self):
        assert pick_resume_variant("QA Engineer") == "qa"
        assert pick_resume_variant("Senior SDET") == "qa"
        assert pick_resume_variant("Test Automation Engineer") == "qa"
        assert pick_resume_variant("Quality Assurance Lead") == "qa"
        assert pick_resume_variant("Test Engineer - Backend") == "qa"

    def test_non_qa_title_returns_backend(self):
        assert pick_resume_variant("Backend Developer") == "backend"
        assert pick_resume_variant("Full Stack Engineer") == "backend"
        assert pick_resume_variant("Python Developer") == "backend"
        assert pick_resume_variant("Gen AI Engineer") == "backend"
        assert pick_resume_variant("Forward Deployed Engineer") == "backend"

    def test_case_insensitive(self):
        assert pick_resume_variant("qa engineer") == "qa"
        assert pick_resume_variant("QA ENGINEER") == "qa"
        assert pick_resume_variant("Qa Engineer") == "qa"

    def test_partial_match_not_triggered(self):
        assert pick_resume_variant("Aquatic Systems Engineer") == "backend"


class TestRunResumeRouter:
    def test_assigns_backend_variant_for_non_qa_title(self, db_session):
        job = Job(
            title="Backend Developer",
            company="Corp",
            url="https://naukri.com/rr/1",
            source="naukri",
            status="scored",
            claude_score=85,
            ats_type="naukri",
        )
        db_session.add(job)
        db_session.flush()

        run_resume_router(db_session)

        db_session.refresh(job)
        assert job.resume_variant == "backend"

    def test_assigns_qa_variant_for_qa_title(self, db_session):
        job = Job(
            title="SDET Engineer",
            company="Corp",
            url="https://naukri.com/rr/2",
            source="naukri",
            status="scored",
            claude_score=75,
            ats_type="naukri",
        )
        db_session.add(job)
        db_session.flush()

        run_resume_router(db_session)

        db_session.refresh(job)
        assert job.resume_variant == "qa"

    def test_naukri_job_goes_to_ready_to_apply(self, db_session):
        job = Job(
            title="Backend Dev",
            company="Corp",
            url="https://naukri.com/rr/3",
            source="naukri",
            status="scored",
            claude_score=80,
            ats_type="naukri",
        )
        db_session.add(job)
        db_session.flush()

        run_resume_router(db_session)

        db_session.refresh(job)
        assert job.status == "ready_to_apply"

    def test_unknown_ats_goes_to_manual_apply(self, db_session):
        job = Job(
            title="Backend Dev",
            company="GoogleCorp",
            url="https://careers.google.com/job/1",
            source="career_page",
            status="scored",
            claude_score=90,
            ats_type="unknown",
        )
        db_session.add(job)
        db_session.flush()

        run_resume_router(db_session)

        db_session.refresh(job)
        assert job.status == "ready_for_manual_apply"
