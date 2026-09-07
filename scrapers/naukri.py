import time
import logging
import requests
from scrapers.base import BaseScraper
from config import APIFY_TOKEN

logger = logging.getLogger(__name__)

NAUKRI_ACTOR_ID = "epicscrapers~naukri-scraper"
APIFY_BASE = "https://api.apify.com/v2"


class NaukriScraper(BaseScraper):
    def fetch(self, keyword: str, location: str = "", max_results: int = 500) -> list[dict]:
        logger.info(f"Starting Naukri scrape: keyword='{keyword}', location='{location}'")

        run_url = f"{APIFY_BASE}/acts/{NAUKRI_ACTOR_ID}/runs"
        run_response = requests.post(
            run_url,
            json={"keyword": keyword, "location": location, "maxItems": max_results},
            headers={"Authorization": f"Bearer {APIFY_TOKEN}"},
            params={"waitForFinish": 300},
        )
        run_response.raise_for_status()
        run_data = run_response.json()["data"]
        run_id = run_data["id"]
        dataset_id = run_data["defaultDatasetId"]

        status = run_data.get("status", "")
        while status not in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            logger.info(f"Waiting for Apify run {run_id}... status={status}")
            time.sleep(10)
            status_resp = requests.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                headers={"Authorization": f"Bearer {APIFY_TOKEN}"},
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
        )
        dataset_resp.raise_for_status()
        raw_items = dataset_resp.json()

        logger.info(f"Fetched {len(raw_items)} raw items from Apify")
        return self.parse_results(raw_items)

    def parse_results(self, raw_items: list[dict]) -> list[dict]:
        jobs = []
        for item in raw_items:
            url = item.get("url")
            if not url:
                continue
            jobs.append({
                "title": item.get("title", "").strip(),
                "company": item.get("companyName", "").strip(),
                "url": self.normalize_url(url),
                "source": "naukri",
                "jd_text": item.get("jobDescription", ""),
                "location": item.get("location", ""),
                "ats_type": "naukri",
                "discovered_sources": ["naukri"],
            })
        logger.info(f"Parsed {len(jobs)} valid jobs from {len(raw_items)} items")
        return jobs


from db.connection import get_session
from db.models import Job
from sqlalchemy.dialects.postgresql import insert as pg_insert


def save_jobs_to_db(jobs: list[dict]) -> int:
    session = get_session()
    inserted = 0
    try:
        for job_data in jobs:
            stmt = pg_insert(Job).values(
                title=job_data["title"],
                company=job_data["company"],
                url=job_data["url"],
                source=job_data["source"],
                jd_text=job_data.get("jd_text"),
                location=job_data.get("location"),
                ats_type=job_data.get("ats_type", "unknown"),
                status="scraped",
                discovered_sources=job_data.get("discovered_sources", []),
            ).on_conflict_do_nothing(index_elements=["url"])
            result = session.execute(stmt)
            if result.rowcount > 0:
                inserted += 1
        session.commit()
        logger.info(f"Inserted {inserted} new jobs ({len(jobs) - inserted} duplicates skipped)")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return inserted
