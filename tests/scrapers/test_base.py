from scrapers.base import BaseScraper


class TestNormalizeUrl:
    def test_strips_utm_params(self):
        url = "https://naukri.com/job/123?utm_source=google&utm_medium=cpc"
        assert BaseScraper.normalize_url(url) == "https://naukri.com/job/123"

    def test_strips_ref_and_source_params(self):
        url = "https://naukri.com/job/123?ref=homepage&source=search"
        assert BaseScraper.normalize_url(url) == "https://naukri.com/job/123"

    def test_preserves_meaningful_params(self):
        url = "https://naukri.com/job/123?jobId=456"
        assert BaseScraper.normalize_url(url) == "https://naukri.com/job/123?jobId=456"

    def test_removes_trailing_slash(self):
        url = "https://naukri.com/job/123/"
        assert BaseScraper.normalize_url(url) == "https://naukri.com/job/123"

    def test_lowercases_scheme_and_host(self):
        url = "HTTPS://Naukri.COM/Job/123"
        assert BaseScraper.normalize_url(url) == "https://naukri.com/Job/123"

    def test_drops_fragment(self):
        url = "https://naukri.com/job/123#apply-section"
        assert BaseScraper.normalize_url(url) == "https://naukri.com/job/123"

    def test_handles_multiple_tracking_and_real_params(self):
        url = "https://naukri.com/job/123?jobId=456&utm_campaign=fall&ref=email"
        assert BaseScraper.normalize_url(url) == "https://naukri.com/job/123?jobId=456"

    def test_already_clean_url_unchanged(self):
        url = "https://naukri.com/job/123"
        assert BaseScraper.normalize_url(url) == "https://naukri.com/job/123"

    def test_empty_path(self):
        url = "https://naukri.com"
        assert BaseScraper.normalize_url(url) == "https://naukri.com"
