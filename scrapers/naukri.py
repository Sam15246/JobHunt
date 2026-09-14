import time
import logging
import requests
from scrapers.base import BaseScraper
from config import APIFY_TOKEN
from db.repository import save_jobs_to_db  # noqa: F401 -- re-exported, main.py imports it from here

logger = logging.getLogger(__name__)

NAUKRI_ACTOR_ID = "epicscrapers~naukri-scraper"
APIFY_BASE = "https://api.apify.com/v2"

REQUEST_TIMEOUT = 60  # seconds per HTTP request
MAX_POLL_ATTEMPTS = 60  # 60 * 10s = 10 minutes max wait


class NaukriScraper(BaseScraper):
    def fetch(self, keyword: str, location: str = "", max_results: int = 500) -> list[dict]:
        logger.info(f"Starting Naukri scrape: keyword='{keyword}', location='{location}'")

        run_url = f"{APIFY_BASE}/acts/{NAUKRI_ACTOR_ID}/runs"
        run_response = requests.post(
            run_url,
            json={"keyword": keyword, "location": location, "maxItems": max_results},
            headers={"Authorization": f"Bearer {APIFY_TOKEN}"},
            params={"waitForFinish": 300},
            timeout=REQUEST_TIMEOUT,
        )
        run_response.raise_for_status()
        run_data = run_response.json()["data"]
        run_id = run_data["id"]
        dataset_id = run_data["defaultDatasetId"]

        status = run_data.get("status", "")
        poll_count = 0
        while status not in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            poll_count += 1
            if poll_count > MAX_POLL_ATTEMPTS:
                logger.error(f"Apify run {run_id} timed out after {poll_count} polls")
                return []
            logger.info(f"Waiting for Apify run {run_id}... status={status} (poll {poll_count}/{MAX_POLL_ATTEMPTS})")
            time.sleep(10)
            status_resp = requests.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                headers={"Authorization": f"Bearer {APIFY_TOKEN}"},
                timeout=REQUEST_TIMEOUT,
            )
            status_resp.raise_for_status()
            status = status_resp.json()["data"]["status"]

        if status != "SUCCEEDED":
            logger.error(f"Apify run {run_id} ended with status: {status}")
            return []

        dataset_url = f"{APIFY_BASE}/datasets/{dataset_id}/items"
        dataset_resp = requests.get(
            dataset_url,
            headers={"Authorization": f"Bearer {APIFY_TOKEN}"},
            params={"format": "json", "limit": max_results},
            timeout=REQUEST_TIMEOUT,
        )
        dataset_resp.raise_for_status()
        raw_items = dataset_resp.json()

        logger.info(f"Fetched {len(raw_items)} raw items from Apify")
        return self.parse_results(raw_items)

    def parse_results(self, raw_items: list[dict]) -> list[dict]:
        jobs = []
        for item in raw_items:
            url = item.get("jobURL") or item.get("url")
            if not url:
                continue
            jobs.append({
                "title": item.get("title", "").strip(),
                "company": item.get("companyName", "").strip(),
                "url": self.normalize_url(url),
                "source": "naukri",
                "jd_text": item.get("jobDescription", ""),
                "location": item.get("locationLabel") or item.get("location", ""),
                "ats_type": "naukri",
                "discovered_sources": ["naukri"],
            })
        logger.info(f"Parsed {len(jobs)} valid jobs from {len(raw_items)} items")
        return jobs
