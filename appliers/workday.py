"""Playwright applier for Workday career sites, using "Use My Last
Application" to reuse a previously-submitted profile instead of filling
every field from scratch.

STATUS: skeleton, same as appliers/naukri.py was before its first live run.
The SELECTORS below are best-guess defaults built from Workday's common
data-automation-id attributes (these tend to be more stable across
different Workday tenants than hand-picked CSS classes, since Workday
generates them from its own component library -- but "more stable" is not
"guaranteed", so verify them on your first headed run before trusting them,
same as Task 13 did for Naukri).

TODO before this is real (deliberately left undone rather than guessed):
  - Filling in a MATCHED screening answer. Right now the applier detects
    and reports unmatched questions (see _match_answer) but does not yet
    fill in matched ones -- Workday renders questions as text inputs,
    radio groups, and dropdowns differently, and guessing the wrong
    interaction for each would either fail silently or file a wrong
    answer. Fill this in once you've seen the real question types on a
    headed run.

Submission model: this stops one screen before Submit by default
(config.WORKDAY_AUTO_SUBMIT[employer] = False) and marks the job
"awaiting_review". You finish it by logging into the employer's own
Workday candidate portal separately and clicking Submit on the saved
in-progress application -- Workday keeps drafts server-side, so this does
not require reusing the bot's own browser session.
"""
import os
import logging
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
    WORKDAY_EMPLOYERS, WORKDAY_CREDENTIALS, WORKDAY_AUTO_SUBMIT,
    SCREENING_ANSWERS, BROWSER_DATA_DIR, DAILY_LIMITS, RESUME_DIR,
)

logger = logging.getLogger(__name__)

MAX_FORM_STEPS = 10  # hard cap so a stuck/unexpected flow can't loop forever

# SELECTORS -- update after manual observation (mirrors appliers/naukri.py's
# Task 10 note). Workday's data-automation-id values are commonly reused
# across tenants; still confirm on Mastercard's actual site before relying
# on this.
SELECTORS = {
    "apply_button": "[data-automation-id='adventureButton']",
    "use_last_application": "text='Use My Last Application'",
    "login_email": "[data-automation-id='email']",
    "login_password": "[data-automation-id='password']",
    "login_submit": "[data-automation-id='signInSubmitButton']",
    "next_button": "[data-automation-id='bottom-navigation-next-button']",
    "submit_button": "[data-automation-id='bottom-navigation-next-button']",  # becomes "Submit" on the Review step
    "question_labels": "[data-automation-id='formLabel']",
    "review_step_heading": "text='Review'",
}


class WorkdayApplier(BaseApplier):
    platform = "workday"

    def __init__(self, employer_key: str):
        self.employer_key = employer_key
        self.creds = WORKDAY_CREDENTIALS.get(employer_key, {})
        self.auto_submit = WORKDAY_AUTO_SUBMIT.get(employer_key, False)

    async def ensure_logged_in(self, page) -> bool:
        email = self.creds.get("email")
        password = self.creds.get("password")

        login_field = page.locator(SELECTORS["login_email"]).first
        if await login_field.count() == 0:
            return True  # already authenticated (persisted browser session)

        if not email or not password:
            logger.error(
                f"No credentials configured for Workday employer '{self.employer_key}' -- "
                f"set WORKDAY_{self.employer_key.upper()}_EMAIL / _PASSWORD in .env"
            )
            return False

        try:
            await human_type(page, SELECTORS["login_email"], email)
            await human_type(page, SELECTORS["login_password"], password)
            await human_click(page, SELECTORS["login_submit"])
            await page.wait_for_timeout(random_delay(3, 6) * 1000)
            return await page.locator(SELECTORS["login_email"]).count() == 0
        except PlaywrightTimeout:
            logger.error("Workday login timed out")
            return False

    @staticmethod
    def _match_answer(question_text: str):
        q = question_text.lower()
        for pattern, answer in SCREENING_ANSWERS.items():
            if pattern.lower() in q:
                return answer
        return None

    async def apply(self, page, job: dict) -> dict:
        job_id = str(job["id"])
        result = {"status": "failed", "error_log": None, "screenshot_path": None}

        try:
            await page.goto(job["url"], wait_until="domcontentloaded")
            await page.wait_for_timeout(random_delay(2, 5) * 1000)

            apply_btn = page.locator(SELECTORS["apply_button"]).first
            if await apply_btn.count() == 0:
                result["error_log"] = "Apply button not found -- job may be closed or selector is stale"
                result["screenshot_path"] = await self.take_screenshot(page, job_id, "no_apply_btn")
                return result

            await human_click(page, SELECTORS["apply_button"])
            await page.wait_for_timeout(random_delay(2, 4) * 1000)

            if not await self.ensure_logged_in(page):
                result["error_log"] = "Login failed or credentials missing"
                result["screenshot_path"] = await self.take_screenshot(page, job_id, "login_failed")
                return result

            use_last = page.locator(SELECTORS["use_last_application"]).first
            if await use_last.count() == 0 or not await use_last.is_visible():
                result["error_log"] = "\"Use My Last Application\" option not found -- needs manual application"
                result["screenshot_path"] = await self.take_screenshot(page, job_id, "no_use_last_app")
                return result

            await human_click(page, SELECTORS["use_last_application"])
            await page.wait_for_timeout(random_delay(2, 4) * 1000)

            # Walk forward through the multi-step form. Stop (don't guess)
            # on the first screening question we don't recognize.
            for _ in range(MAX_FORM_STEPS):
                await page.wait_for_timeout(random_delay(1, 2) * 1000)

                labels = page.locator(SELECTORS["question_labels"])
                unmatched = []
                for i in range(await labels.count()):
                    label_text = (await labels.nth(i).text_content() or "").strip()
                    if not label_text:
                        continue
                    if self._match_answer(label_text) is None:
                        unmatched.append(label_text)
                    # NOTE: filling a matched answer is a TODO -- see module
                    # docstring. We only detect + report for now.

                if unmatched:
                    result["error_log"] = (
                        "Unrecognized screening question(s), needs manual answer: "
                        + "; ".join(unmatched[:5])
                    )
                    result["screenshot_path"] = await self.take_screenshot(page, job_id, "unknown_question")
                    return result

                review_heading = page.locator(SELECTORS["review_step_heading"]).first
                if await review_heading.count() > 0 and await review_heading.is_visible():
                    break

                next_btn = page.locator(SELECTORS["next_button"]).first
                if await next_btn.count() == 0:
                    result["error_log"] = "Next button not found -- form flow may have changed"
                    result["screenshot_path"] = await self.take_screenshot(page, job_id, "no_next_btn")
                    return result
                await human_click(page, SELECTORS["next_button"])

            if not self.auto_submit:
                result["status"] = "awaiting_review"
                result["screenshot_path"] = await self.take_screenshot(page, job_id, "ready_to_submit")
                logger.info(f"Filled application for {job['title']} -- left on Review step for you to submit")
                return result

            await human_click(page, SELECTORS["submit_button"])
            await page.wait_for_timeout(random_delay(2, 4) * 1000)
            result["status"] = "submitted"
            result["screenshot_path"] = await self.take_screenshot(page, job_id, "success")

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


async def run_workday_applier(employer_key: str, limit: int = None):
    """Apply to ready_to_apply Workday jobs for one configured employer."""
    if limit is None:
        limit = DAILY_LIMITS.get("workday", 15)

    cfg = WORKDAY_EMPLOYERS[employer_key]
    company_name = cfg.get("company_name", employer_key)
    browser_dir = os.path.join(BROWSER_DATA_DIR, f"workday_{employer_key}")

    session = get_session()
    applier = WorkdayApplier(employer_key)

    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = (
            session.query(Application)
            .join(Job)
            .filter(Job.ats_type == "workday", Job.company == company_name,
                    Application.submitted_at >= today_start)
            .count()
        )
        remaining = limit - today_count
        if remaining <= 0:
            logger.info(f"Daily Workday limit reached for {company_name} ({today_count}/{limit})")
            return

        jobs = (
            session.query(Job)
            .filter(Job.status == "ready_to_apply", Job.ats_type == "workday",
                    Job.company == company_name)
            .order_by(Job.claude_score.desc().nullslast())
            .limit(remaining)
            .all()
        )
        if not jobs:
            logger.info(f"No {company_name} Workday jobs ready to apply")
            return

        os.makedirs(browser_dir, exist_ok=True)
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=browser_dir,
                headless=False,  # headed until this has proven stable, same as Naukri
                user_agent=get_random_user_agent(),
                viewport=get_random_viewport(),
            )
            page = browser.pages[0] if browser.pages else await browser.new_page()

            session_start = datetime.now()
            applied_count = 0

            for job in jobs:
                elapsed = (datetime.now() - session_start).total_seconds() / 60
                if elapsed >= MAX_SESSION_MINUTES:
                    logger.info(f"Session time limit reached ({elapsed:.0f} min). Stopping.")
                    break

                job_data = {
                    "id": job.id, "url": job.url, "title": job.title,
                    "company": job.company, "resume_variant": job.resume_variant or "backend",
                }
                result = await applier.apply(page, job_data)

                if result["status"] == "awaiting_review":
                    # No Application row yet -- nothing was submitted. Just
                    # move the job into the review queue.
                    job.status = "awaiting_review"
                else:
                    resume_path = os.path.join(RESUME_DIR, f"{job_data['resume_variant']}.pdf")
                    session.add(Application(
                        job_id=job.id, status=result["status"], resume_path=resume_path,
                        error_log=result.get("error_log"), screenshot_path=result.get("screenshot_path"),
                    ))
                    job.status = result["status"]

                session.commit()
                applied_count += 1
                logger.info(f"[{applied_count}/{len(jobs)}] {result['status']}: {job.title} @ {job.company}")

                if applied_count < len(jobs):
                    gap = get_application_gap()
                    logger.info(f"Waiting {gap:.0f}s before next application...")
                    await page.wait_for_timeout(gap * 1000)

            try:
                await browser.close()
            except Exception:
                pass

        logger.info(f"Session complete. Processed {applied_count} {company_name} jobs.")

    except Exception as e:
        logger.error(f"Workday applier session error ({employer_key}): {e}")
        raise
    finally:
        session.close()
