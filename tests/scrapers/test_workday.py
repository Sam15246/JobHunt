import pytest
from unittest.mock import patch, MagicMock
from scrapers.workday import WorkdayScraper


TEST_EMPLOYER_CFG = {
    "mastercard": {
        "tenant": "mastercard",
        "dc": "wd1",
        "site": "CorporateCareers",
        "locale": "en-US",
        "company_name": "Mastercard",
        "location_facets": ["abc123"],
        "title_patterns": ["software engineer i", "software engineer ii", "senior software engineer"],
        "search_text": "software engineer",
    },
}

JOB_BASE_URL = "https://mastercard.wd1.myworkdayjobs.com/en-US/CorporateCareers"

RAW_POSTINGS = [
    {"title": "Software Engineer II", "externalPath": "/job/Pune/Software-Engineer-II_R-123", "locationsText": "Pune, India"},
    {"title": "Senior Software Engineer", "externalPath": "/job/Gurgaon/Senior-SWE_R-456", "locationsText": "Gurgaon, India"},
    {"title": "Product Manager", "externalPath": "/job/Pune/PM_R-789", "locationsText": "Pune, India"},
    {"title": "Software Engineer II", "externalPath": "/job/London/SWE-II_R-999", "locationsText": "London, United Kingdom"},
    {"title": "No Path Job"},
    {"externalPath": "/job/x/y"},
]


class TestParseResults:
    @patch("scrapers.workday.WORKDAY_EMPLOYERS", TEST_EMPLOYER_CFG)
    def test_filters_by_title_pattern(self):
        scraper = WorkdayScraper()
        jobs = scraper.parse_results(
            RAW_POSTINGS, "mastercard", JOB_BASE_URL,
            [p.lower() for p in TEST_EMPLOYER_CFG["mastercard"]["title_patterns"]],
        )
        titles = [j["title"] for j in jobs]
        assert "Product Manager" not in titles
        assert titles.count("Software Engineer II") == 2
        assert "Senior Software Engineer" in titles

    @patch("scrapers.workday.WORKDAY_EMPLOYERS", TEST_EMPLOYER_CFG)
    def test_skips_entries_missing_title_or_path(self):
        scraper = WorkdayScraper()
        jobs = scraper.parse_results(RAW_POSTINGS, "mastercard", JOB_BASE_URL, [])
        assert all(j["title"] and j.get("_external_path") for j in jobs)
        assert len(jobs) == 4  # the two malformed entries are dropped

    @patch("scrapers.workday.WORKDAY_EMPLOYERS", TEST_EMPLOYER_CFG)
    def test_url_is_built_and_normalized(self):
        scraper = WorkdayScraper()
        jobs = scraper.parse_results(RAW_POSTINGS[:1], "mastercard", JOB_BASE_URL, [])
        assert jobs[0]["url"] == JOB_BASE_URL + "/job/Pune/Software-Engineer-II_R-123"

    @patch("scrapers.workday.WORKDAY_EMPLOYERS", TEST_EMPLOYER_CFG)
    def test_geo_region_inferred_from_location(self):
        scraper = WorkdayScraper()
        jobs = scraper.parse_results(RAW_POSTINGS, "mastercard", JOB_BASE_URL, [])
        by_title_loc = {(j["title"], j["location"]): j["geo_region"] for j in jobs}
        assert by_title_loc[("Software Engineer II", "Pune, India")] == "india"
        assert by_title_loc[("Software Engineer II", "London, United Kingdom")] == "uk"

    @patch("scrapers.workday.WORKDAY_EMPLOYERS", TEST_EMPLOYER_CFG)
    def test_ats_type_and_source_set(self):
        scraper = WorkdayScraper()
        jobs = scraper.parse_results(RAW_POSTINGS[:1], "mastercard", JOB_BASE_URL, [])
        assert jobs[0]["ats_type"] == "workday"
        assert jobs[0]["source"] == "career_page"
        assert jobs[0]["discovered_sources"] == ["workday"]


class TestGeoInference:
    def test_unknown_location_returns_other(self):
        assert WorkdayScraper._infer_geo_region("Berlin, Germany") == "other"

    def test_empty_location_returns_none(self):
        assert WorkdayScraper._infer_geo_region("") is None

    def test_remote_detected(self):
        assert WorkdayScraper._infer_geo_region("Remote - India") == "india"  # first matching hint wins


class TestStripHtml:
    def test_removes_tags(self):
        html = "<p>We need a <b>backend</b> engineer.</p>"
        assert WorkdayScraper._strip_html(html) == "We need a backend engineer."

    def test_empty_input(self):
        assert WorkdayScraper._strip_html("") == ""

    def test_collapses_whitespace(self):
        html = "<div>Line one</div>\n\n<div>   Line two</div>"
        assert WorkdayScraper._strip_html(html) == "Line one Line two"


class TestFetchAllPostings:
    @patch("scrapers.workday.WORKDAY_EMPLOYERS", TEST_EMPLOYER_CFG)
    @patch("scrapers.workday.requests")
    @patch("scrapers.workday.time.sleep", return_value=None)
    def test_stops_when_total_reached(self, mock_sleep, mock_requests):
        page1 = MagicMock()
        page1.json.return_value = {"total": 2, "jobPostings": [RAW_POSTINGS[0], RAW_POSTINGS[1]]}
        page1.raise_for_status = MagicMock()
        mock_requests.post.return_value = page1
        mock_requests.RequestException = Exception

        scraper = WorkdayScraper()
        postings = scraper._fetch_all_postings(
            "https://mastercard.wd1.myworkdayjobs.com/wday/cxs/mastercard/CorporateCareers/jobs",
            TEST_EMPLOYER_CFG["mastercard"], max_results=200,
        )
        assert len(postings) == 2
        mock_requests.post.assert_called_once()  # total reached after first page -> no second call

    @patch("scrapers.workday.WORKDAY_EMPLOYERS", TEST_EMPLOYER_CFG)
    @patch("scrapers.workday.requests")
    def test_stops_on_request_error_instead_of_raising(self, mock_requests):
        mock_requests.post.side_effect = Exception("boom")
        mock_requests.RequestException = Exception

        scraper = WorkdayScraper()
        postings = scraper._fetch_all_postings(
            "https://mastercard.wd1.myworkdayjobs.com/wday/cxs/mastercard/CorporateCareers/jobs",
            TEST_EMPLOYER_CFG["mastercard"], max_results=200,
        )
        assert postings == []
