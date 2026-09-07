import os
import asyncio
import logging
import random
from datetime import datetime, timezone
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from appliers.base import BaseApplier
from appliers.anti_detection import (
    get_random_user_agent, get_random_viewport, random_delay,
    get_application_gap, human_type, human_click, MAX_SESSION_MINUTES,
)
from db.connection import get_session
from db.models import Job, Application
from config import (
    NAUKRI_EMAIL, NAUKRI_PASSWORD, BROWSER_DATA_DIR,
    DAILY_LIMITS, RESUME_DIR,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# SELECTORS — Update these after manual observation (Task 10, Step 1).
# These are best-effort defaults based on reference implementations.
# Run headed mode first and adjust as needed.
# ──────────────────────────────────────────────────────────
SELECTORS = {
    "login_email": "input[placeholder*='Email' i], input[name='username']",
    "login_password": "input[type='password']",
    "login_submit": "button[type='submit']:has-text('Login')",
    "apply_button": "button:has-text('Apply'), a:has-text('Apply')",
    "resume_upload": "input[type='file']",
    "submit_button": "button:has-text('Submit'), button:has-text('Apply')",
    "success_indicator": "text='Application Submitted', text='Successfully Applied'",
}

NAUKRI_BROWSER_DIR = os.path.join(BROWSER_DATA_DIR, "naukri")


class NaukriApplier(BaseApplier):
    platform = "naukri"

    async def ensure_logged_in(self, context, page) -> bool:
        """Check if logged in, attempt login if not. Returns True if logged in."""
        await page.goto("https://www.naukri.com/mnjuser/homepage", wait_until="domcontentloaded")
        await page.wait_for_timeout(random_delay(2, 4) * 1000)

        # If we see the homepage dashboard, we're logged in
        if "homepage" in page.url and "login" not in page.url:
            logger.info("Already logged in to Naukri")
            return True

        # Not logged in — attempt login
        logger.info("Logging in to Naukri...")
        await page.goto("https://www.naukri.com/nlogin/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(random_delay(2, 4) * 1000)

        try:
            await human_type(page, SELECTORS["login_email"], NAUKRI_EMAIL)
            await human_type(page, SELECTORS["login_password"], NAUKRI_PASSWORD)
            await human_click(page, SELECTORS["login_submit"])
            await page.wait_for_timeout(random_delay(3, 6) * 1000)

            # Verify login succeeded
            if "login" in page.url.lower():
                logger.error("Login failed — still on login page")
                return False

            logger.info("Successfully logged in to Naukri")
            return True

        except PlaywrightTimeout:
            logger.error("Login timed out")
            return False

    async def apply(self, page, job: dict) -> dict:
        """Apply to a single Naukri job. Returns result dict."""
        job_id = str(job["id"])
        result = {"status": "failed", "error_log": None, "screenshot_path": None}

        try:
            # Navigate to job page
            await page.goto(job["url"], wait_until="domcontentloaded")
            await page.wait_for_timeout(random_delay(2, 5) * 1000)

            # Look for apply button
            apply_btn = page.locator(SELECTORS["apply_button"]).first
            if not await apply_btn.is_visible():
                result["error_log"] = "Apply button not found or not visible"
                result["screenshot_path"] = await self.take_screenshot(page, job_id, "no_apply_btn")
                return result

            await human_click(page, SELECTORS["apply_button"])
            await page.wait_for_timeout(random_delay(2, 5) * 1000)

            # Handle resume upload if file input is visible
            file_input = page.locator(SELECTORS["resume_upload"])
            if await file_input.count() > 0 and await file_input.first.is_visible():
                resume_path = os.path.join(RESUME_DIR, f"{job.get('resume_variant', 'backend')}.pdf")
                if os.path.exists(resume_path):
                    await file_input.first.set_input_files(resume_path)
                    await page.wait_for_timeout(random_delay(1, 3) * 1000)
                    logger.info(f"Uploaded resume: {resume_path}")

            # Click submit
            submit_btn = page.locator(SELECTORS["submit_button"]).first
            if await submit_btn.is_visible():
                await human_click(page, SELECTORS["submit_button"])
                await page.wait_for_timeout(random_delay(3, 6) * 1000)

            # Check for success
            success = page.locator(SELECTORS["success_indicator"])
            if await success.count() > 0:
                result["status"] = "submitted"
                result["screenshot_path"] = await self.take_screenshot(page, job_id, "success")
                logger.info(f"Successfully applied to {job['title']} at {job['company']}")
            else:
                result["error_log"] = "Submit clicked but no success confirmation found"
                result["screenshot_path"] = await self.take_screenshot(page, job_id, "no_confirmation")

        except PlaywrightTimeout as e:
            result["error_log"] = f"Timeout: {str(e)}"
            result["screenshot_path"] = await self.take_screenshot(page, job_id, "timeout")

        except Exception as e:
            result["error_log"] = f"Unexpected error: {str(e)}"
            try:
                result["screenshot_path"] = await self.take_screenshot(page, job_id, "error")
            except Exception:
                pass

        return result


async def run_naukri_applier(limit: int = None):
    """Main entry point: apply to ready_to_apply Naukri jobs.

    Args:
        limit: Max jobs to apply to this session (defaults to DAILY_LIMITS['naukri'])
    """
    if limit is None:
        limit = DAILY_LIMITS["naukri"]

    session = get_session()
    applier = NaukriApplier()

    try:
        # Check how many already applied today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        today_count = (
            session.query(Application)
            .join(Job)
            .filter(
                Job.ats_type == "naukri",
                Application.submitted_at >= today_start,
            )
            .count()
        )

        remaining = limit - today_count
        if remaining <= 0:
            logger.info(f"Daily Naukri limit reached ({today_count}/{limit})")
            return

        # Get jobs to apply to
        jobs = (
            session.query(Job)
            .filter(Job.status == "ready_to_apply", Job.ats_type == "naukri")
            .order_by(Job.claude_score.desc().nullslast())
            .limit(remaining)
            .all()
        )

        if not jobs:
            logger.info("No Naukri jobs ready to apply")
            return

        # Shuffle for anti-detection (don't apply in score order)
        random.shuffle(jobs)
        logger.info(f"Applying to {len(jobs)} Naukri jobs (limit={remaining})")

        # Launch browser
        os.makedirs(NAUKRI_BROWSER_DIR, exist_ok=True)
        user_agent = get_random_user_agent()
        viewport = get_random_viewport()

        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=NAUKRI_BROWSER_DIR,
                headless=False,  # Use headed mode until stable
                user_agent=user_agent,
                viewport=viewport,
            )

            page = browser.pages[0] if browser.pages else await browser.new_page()

            # Ensure logged in
            if not await applier.ensure_logged_in(browser, page):
                logger.error("Could not log in to Naukri. Aborting session.")
                await browser.close()
                return

            session_start = datetime.now()
            applied_count = 0

            for job in jobs:
                # Check session time limit
                elapsed = (datetime.now() - session_start).total_seconds() / 60
                if elapsed >= MAX_SESSION_MINUTES:
                    logger.info(f"Session time limit reached ({elapsed:.0f} min). Stopping.")
                    break

                job_data = {
                    "id": job.id,
                    "url": job.url,
                    "title": job.title,
                    "company": job.company,
                    "resume_variant": job.resume_variant or "backend",
                }

                result = await applier.apply(page, job_data)

                # Save application record
                resume_path = os.path.join(RESUME_DIR, f"{job_data['resume_variant']}.pdf")
                app = Application(
                    job_id=job.id,
                    status=result["status"],
                    resume_path=resume_path,
                    error_log=result.get("error_log"),
                    screenshot_path=result.get("screenshot_path"),
                )
                session.add(app)

                # Update job status
                job.status = result["status"]
                session.commit()

                applied_count += 1
                logger.info(
                    f"[{applied_count}/{len(jobs)}] {result['status']}: "
                    f"{job.title} @ {job.company}"
                )

                # Wait between applications
                if applied_count < len(jobs):
                    gap = get_application_gap()
                    logger.info(f"Waiting {gap:.0f}s before next application...")
                    await page.wait_for_timeout(gap * 1000)

            await browser.close()

        logger.info(f"Session complete. Applied to {applied_count} jobs.")

    except Exception as e:
        logger.error(f"Naukri applier session error: {e}")
        raise
    finally:
        session.close()
