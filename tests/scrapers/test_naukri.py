import pytest
from unittest.mock import patch, MagicMock
from scrapers.naukri import NaukriScraper
from db.models import Job


MOCK_APIFY_RESPONSE = [
    {
        "title": "Backend Developer",
        "companyName": "TechCorp",
        "url": "https://www.naukri.com/job-listings-backend-dev-123",
        "jobDescription": "We need a Python backend developer...",
        "location": "Bangalore",
        "experience": "2-5 years",
    },
    {
        "title": "Senior Java Engineer",
        "companyName": "FinCo",
        "url": "https://www.naukri.com/job-listings-java-456",
        "jobDescription": "Looking for experienced Java developer...",
        "location": "Mumbai",
        "experience": "3-7 years",
    },
]


class TestNaukriScraper:
    def test_parse_apify_results(self):
        scraper = NaukriScraper()
        jobs = scraper.parse_results(MOCK_APIFY_RESPONSE)
        assert len(jobs) == 2
        assert jobs[0]["title"] == "Backend Developer"
        assert jobs[0]["company"] == "TechCorp"
        assert jobs[0]["source"] == "naukri"
        assert jobs[0]["ats_type"] == "naukri"

    def test_parse_skips_entries_without_url(self):
        scraper = NaukriScraper()
        data = [{"title": "No URL Job", "companyName": "X"}]
        jobs = scraper.parse_results(data)
        assert len(jobs) == 0

    def test_urls_are_normalized(self):
        scraper = NaukriScraper()
        data = [{
            "title": "Test",
            "companyName": "X",
            "url": "https://www.naukri.com/job/123?utm_source=google",
            "jobDescription": "desc",
            "location": "Delhi",
        }]
        jobs = scraper.parse_results(data)
        assert "utm_source" not in jobs[0]["url"]

    @patch("scrapers.naukri.requests")
    def test_fetch_from_apify(self, mock_requests):
        mock_run_response = MagicMock()
        mock_run_response.json.return_value = {
            "data": {"id": "run123", "defaultDatasetId": "ds456"}
        }
        mock_run_response.raise_for_status = MagicMock()

        mock_dataset_response = MagicMock()
        mock_dataset_response.json.return_value = MOCK_APIFY_RESPONSE
        mock_dataset_response.raise_for_status = MagicMock()

        mock_status_response = MagicMock()
        mock_status_response.json.return_value = {"data": {"status": "SUCCEEDED"}}
        mock_status_response.raise_for_status = MagicMock()

        mock_requests.post.return_value = mock_run_response
        mock_requests.get.side_effect = [mock_status_response, mock_dataset_response]

        scraper = NaukriScraper()
        jobs = scraper.fetch(keyword="backend engineer", location="bangalore")
        assert len(jobs) == 2
        mock_requests.post.assert_called_once()


def test_save_jobs_mapping(db_session):
    """Test that job dicts map correctly to Job model via direct ORM insert."""
    job_data = {
        "title": "Backend Dev",
        "company": "Corp",
        "url": "https://naukri.com/job/111",
        "source": "naukri",
        "jd_text": "description",
        "location": "Bangalore",
        "ats_type": "naukri",
        "discovered_sources": ["naukri"],
    }
    job = Job(
        title=job_data["title"],
        company=job_data["company"],
        url=job_data["url"],
        source=job_data["source"],
        jd_text=job_data["jd_text"],
        location=job_data["location"],
        ats_type=job_data["ats_type"],
        status="scraped",
        discovered_sources=job_data["discovered_sources"],
    )
    db_session.add(job)
    db_session.flush()

    result = db_session.query(Job).filter_by(url="https://naukri.com/job/111").first()
    assert result is not None
    assert result.title == "Backend Dev"
    assert result.status == "scraped"
