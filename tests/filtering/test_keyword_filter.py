from filtering.keyword_filter import compute_keyword_score, run_keyword_filter
from db.models import Job


class TestComputeKeywordScore:
    def test_high_score_for_strong_match(self):
        jd = "We need a backend Python developer with FastAPI and microservices experience"
        score = compute_keyword_score(jd)
        assert score >= 60

    def test_low_score_for_no_match(self):
        jd = "Looking for a graphic designer with Photoshop and Illustrator skills"
        score = compute_keyword_score(jd)
        assert score < 20

    def test_nice_to_have_adds_bonus(self):
        jd_base = "Backend Python developer needed"
        jd_bonus = "Backend Python developer needed with Kubernetes and Docker experience"
        score_base = compute_keyword_score(jd_base)
        score_bonus = compute_keyword_score(jd_bonus)
        assert score_bonus > score_base

    def test_soft_exclude_penalizes(self):
        jd_normal = "Backend Python developer, 3 years experience"
        jd_senior = "Staff Engineer, Backend Python developer, 10+ years experience"
        score_normal = compute_keyword_score(jd_normal)
        score_senior = compute_keyword_score(jd_senior)
        assert score_senior < score_normal

    def test_score_clamped_0_to_100(self):
        jd_empty = ""
        jd_full = " ".join(["python backend java spring fastapi microservices api rest"] * 10)
        assert compute_keyword_score(jd_empty) >= 0
        assert compute_keyword_score(jd_full) <= 100

    def test_case_insensitive(self):
        jd_lower = "backend python developer with fastapi"
        jd_upper = "BACKEND PYTHON Developer with FASTAPI"
        assert compute_keyword_score(jd_lower) == compute_keyword_score(jd_upper)


class TestRunKeywordFilter:
    def test_updates_job_status_to_passed(self, db_session):
        job = Job(
            title="Python Backend Developer",
            company="TestCo",
            url="https://naukri.com/kf/1",
            source="naukri",
            jd_text="Backend Python FastAPI microservices developer needed",
            status="scraped",
            ats_type="naukri",
        )
        db_session.add(job)
        db_session.flush()

        run_keyword_filter(db_session)

        db_session.refresh(job)
        assert job.status == "keyword_passed"
        assert job.keyword_score >= 40

    def test_updates_job_status_to_failed(self, db_session):
        job = Job(
            title="Graphic Designer",
            company="DesignCo",
            url="https://naukri.com/kf/2",
            source="naukri",
            jd_text="Looking for graphic designer with Photoshop skills",
            status="scraped",
            ats_type="naukri",
        )
        db_session.add(job)
        db_session.flush()

        run_keyword_filter(db_session)

        db_session.refresh(job)
        assert job.status == "keyword_failed"
        assert job.keyword_score < 40
