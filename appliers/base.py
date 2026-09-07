import os
import logging
from datetime import datetime
from config import SCREENSHOT_DIR

logger = logging.getLogger(__name__)


class BaseApplier:
    """Base class for all Playwright-based appliers."""

    platform: str = "unknown"

    async def take_screenshot(self, page, job_id: str, label: str = "") -> str:
        """Save a screenshot and return the file path."""
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{label}" if label else ""
        filename = f"{job_id}_{timestamp}{suffix}.png"
        filepath = os.path.join(SCREENSHOT_DIR, filename)
        await page.screenshot(path=filepath, full_page=True)
        logger.info(f"Screenshot saved: {filepath}")
        return filepath

    async def apply(self, page, job: dict) -> dict:
        """Apply to a single job. Override in subclasses.

        Args:
            page: Playwright page object (already logged in)
            job: dict with keys: id, url, title, company, resume_path

        Returns:
            dict: {"status": "submitted"|"failed", "error_log": str|None, "screenshot_path": str}
        """
        raise NotImplementedError
