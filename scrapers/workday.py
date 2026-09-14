"""Scraper for any myworkdayjobs.com tenant (Mastercard first), using
Workday's own public job-search API -- the same endpoint the career-site
page itself calls in your browser.

Heads-up (see the JobHunt system review doc for the full discussion):
Workday's site terms (workday.com/en-us/legal/site-terms.html) explicitly
prohibit automated data extraction and apps that interact with their sites
without written consent. This is the same category of risk as
scrapers/naukri.py's Apify-based scraping -- just against a different
platform's terms, and concentrated on one employer you actually want to
work for, which raises the stakes if it ever goes wrong.
"""
import re
import time
import logging
import requests
from scrapers.base import BaseScraper
from config import WORKDAY_EMPLOYERS

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20   # seconds, per HTTP call
PAGE_SIZE = 20
MAX_PAGES = 25         # hard stop: at most 500 postings pulled per employer per run

_TAG_RE = re.compile(r"<[^>]+>")

# Best-effort location -> geo_region mapping, built from the candidate's own
# target-geo list (config.CANDIDATE). Returns "other" rather than a guessed
# specific country when nothing matches, and None only when there's no
# location text at all -- a null geo_region is treated differently
# downstream than a wrong one.
GEO_HINTS = {
    "india": ["india", "bengaluru", "bangalore", "gurgaon", "gurugram", "pune",
              "hyderabad", "mumbai", "chennai", "noida", "delhi"],
    "singapore": ["singapore"],
    "uk": ["united kingdom", "uk", "london"],
    "saudi_arabia": ["saudi arabia", "riyadh", "jeddah"],
    "new_zealand": ["new zealand", "auckland", "wellington"],
    "australia": ["australia", "sydney", "melbourne"],
    "netherlands": ["netherlands", "amsterdam"],
    "remote": ["remote"],
}


class WorkdayScraper(BaseScraper):

    def fetch_employer(self, employer_key: str, max_results: int = 200) -> list[dict]:
        """Fetch + filter postings for one configured Workday employer
        (see config.WORKDAY_EMPLOYERS), including full job descriptions for
        the postings that match our title filter."""
        cfg = WORKDAY_EMPLOYERS[employer_key]
        tenant, dc = cfg["tenant"], cfg["dc"]
        site, locale = cfg["site"], cfg.get("locale", "en-US")
        title_patterns = [p.lower() for p in cfg.get("title_patterns", [])]

        search_url = f"https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
        job_base_url = f"https://{tenant}.{dc}.myworkdayjobs.com/{locale}/{site}"

        raw_postings = self._fetch_all_postings(search_url, cfg, max_results)
        jobs = self.parse_results(raw_postings, employer_key, job_base_url, title_patterns)

        # Full JD text matters a lot here: the pipeline's keyword_filter
        # scores title + jd_text against KEYWORDS, and a bare title like
        # "Software Engineer II" won't match anything in must_have on its
        # own. Only fetching detail for already-title-matched postings
        # keeps this to a handful of extra requests, not hundreds.
        for job in jobs:
            job["jd_text"] = self._fetch_description(search_url, job.pop("_external_path"))

        logger.info(f"{employer_key}: {len(jobs)} matching jobs after title filter")
        return jobs

    def _fetch_all_postings(self, search_url: str, cfg: dict, max_results: int) -> list[dict]:
        all_postings = []
        offset = 0
        for _ in range(MAX_PAGES):
            payload = {
                "appliedFacets": {"locations": cfg["location_facets"]} if cfg.get("location_facets") else {},
                "limit": PAGE_SIZE,
                "offset": offset,
                "searchText": cfg.get("search_text", ""),
            }
            try:
                resp = requests.post(search_url, json=payload, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"Workday search API error at offset {offset}: {e}")
                break

            data = resp.json()
            postings = data.get("jobPostings", [])
            total = data.get("total", 0)
            all_postings.extend(postings)
            offset += PAGE_SIZE

            if not postings or offset >= total or len(all_postings) >= max_results:
                break
            time.sleep(1)  # be polite between pages

        return all_postings[:max_results]

    def _fetch_description(self, search_url: str, external_path: str) -> str:
        detail_url = search_url.rsplit("/jobs", 1)[0] + external_path
        try:
            resp = requests.get(detail_url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            info = resp.json().get("jobPostingInfo", {})
            return self._strip_html(info.get("jobDescription", ""))
        except requests.RequestException as e:
            logger.warning(f"Could not fetch job description for {external_path}: {e}")
            return ""

    def parse_results(self, raw_items, employer_key, job_base_url, title_patterns):
        cfg = WORKDAY_EMPLOYERS[employer_key]
        company_name = cfg.get("company_name", employer_key)
        jobs = []
        for item in raw_items:
            title = (item.get("title") or "").strip()
            path = item.get("externalPath")
            if not title or not path:
                continue
            if title_patterns and not any(p in title.lower() for p in title_patterns):
                continue  # not one of the roles we care about -- skip before it touches the DB

            location_text = item.get("locationsText", "") or ""
            jobs.append({
                "title": title,
                "company": company_name,
                "url": self.normalize_url(job_base_url + path),
                "source": "career_page",
                "location": location_text,
                "geo_region": self._infer_geo_region(location_text),
                "ats_type": "workday",
                "discovered_sources": ["workday"],
                "_external_path": path,  # consumed by fetch_employer, never stored
            })
        return jobs

    @staticmethod
    def _strip_html(html: str) -> str:
        if not html:
            return ""
        text = _TAG_RE.sub(" ", html)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _infer_geo_region(location_text: str):
        if not location_text:
            return None
        text = location_text.lower()
        for geo, hints in GEO_HINTS.items():
            if any(h in text for h in hints):
                return geo
        return "other"
