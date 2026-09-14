from datetime import datetime, timedelta, timezone
from db.models import Job
from db.repository import is_recent_duplicate_role, save_jobs_to_db


class TestIsRecentDuplicateRole:
    def test_false_when_cooldown_disabled(self, db_session):
        db_session.add(Job(title="Software Engineer II", company="Mastercard",
                            url="https://a.com/1", source="career_page",
                            location="Pune, India", ats_type="workday"))
        db_session.flush()

        assert is_recent_duplicate_role(db_session, "Mastercard", "Software Engineer II",
                                         "Pune, India", cooldown_days=0) is False

    def test_true_for_recent_same_role_different_url(self, db_session):
        db_session.add(Job(title="Software Engineer II", company="Mastercard",
                            url="https://a.com/req-111", source="career_page",
                            location="Pune, India", ats_type="workday"))
        db_session.flush()

        # Same company+title+location, brand-new URL (as if Workday reposted
        # it under a new requisition ID) -- should still count as a dup.
        assert is_recent_duplicate_role(db_session, "Mastercard", "Software Engineer II",
                                         "Pune, India", cooldown_days=45) is True

    def test_case_insensitive_match(self, db_session):
        db_session.add(Job(title="Software Engineer II", company="Mastercard",
                            url="https://a.com/2", source="career_page",
                            location="Pune, India", ats_type="workday"))
        db_session.flush()

        assert is_recent_duplicate_role(db_session, "mastercard", "software engineer ii",
                                         "pune, india", cooldown_days=45) is True

    def test_false_outside_cooldown_window(self, db_session):
        old_job = Job(title="Software Engineer II", company="Mastercard",
                       url="https://a.com/3", source="career_page",
                       location="Pune, India", ats_type="workday")
        db_session.add(old_job)
        db_session.flush()
        old_job.created_at = datetime.now(timezone.utc) - timedelta(days=90)
        db_session.flush()

        assert is_recent_duplicate_role(db_session, "Mastercard", "Software Engineer II",
                                         "Pune, India", cooldown_days=45) is False

    def test_false_for_different_title(self, db_session):
        db_session.add(Job(title="Software Engineer II", company="Mastercard",
                            url="https://a.com/4", source="career_page",
                            location="Pune, India", ats_type="workday"))
        db_session.flush()

        assert is_recent_duplicate_role(db_session, "Mastercard", "Software Engineer III",
                                         "Pune, India", cooldown_days=45) is False


class TestSaveJobsToDb:
    def test_inserts_new_jobs(self, db_session):
        jobs = [{
            "title": "Backend Dev", "company": "Corp", "url": "https://x.com/1",
            "source": "naukri", "ats_type": "naukri",
        }]
        inserted = save_jobs_to_db(jobs, session=db_session)
        assert inserted == 1
        assert db_session.query(Job).filter_by(url="https://x.com/1").first() is not None

    def test_skips_url_duplicate(self, db_session):
        job = {"title": "Backend Dev", "company": "Corp", "url": "https://x.com/2",
               "source": "naukri", "ats_type": "naukri"}
        save_jobs_to_db([job], session=db_session)
        inserted_again = save_jobs_to_db([job], session=db_session)
        assert inserted_again == 0

    def test_skips_same_role_repost_when_cooldown_set(self, db_session):
        first = {"title": "Software Engineer II", "company": "Mastercard",
                  "url": "https://mc.com/req-1", "source": "career_page",
                  "location": "Pune, India", "ats_type": "workday"}
        save_jobs_to_db([first], session=db_session)

        # Same role, different URL (simulated repost under a new req ID)
        reposted = {**first, "url": "https://mc.com/req-2"}
        inserted = save_jobs_to_db([reposted], cooldown_days=45, session=db_session)
        assert inserted == 0
        assert db_session.query(Job).filter_by(url="https://mc.com/req-2").first() is None

    def test_does_not_skip_repost_when_cooldown_disabled(self, db_session):
        first = {"title": "Software Engineer II", "company": "Mastercard",
                  "url": "https://mc.com/req-3", "source": "career_page",
                  "location": "Pune, India", "ats_type": "workday"}
        save_jobs_to_db([first], session=db_session)  # cooldown_days=0 default

        reposted = {**first, "url": "https://mc.com/req-4"}
        inserted = save_jobs_to_db([reposted], session=db_session)
        assert inserted == 1
