"""Playwright applier for Workday career sites, using "Use My Last
Application" to reuse a previously-submitted profile instead of filling
every field from scratch.

SELECTORS updated from live Mastercard Workday DOM observation (Sep 2026).
Form flow: My Information -> My Experience -> App Questions 1/2 ->
App Questions 2/2 -> Voluntary Disclosures (consent checkbox + Submit).
Questions are dropdowns (<select>); answers configured in
config.SCREENING_ANSWERS. Navigation button is "Save and Continue".

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

# SELECTORS -- updated from live Mastercard Workday DOM observation (Sep 2026).
# Workday's data-automation-id values are commonly reused across tenants.
SELECTORS = {
    "apply_button": "a:has-text('Apply'), button:has-text('Apply')",
    "use_last_application": "button:has-text('Use My Last Application')",
    "login_email": "[data-automation-id='email'], input[type='email']",
    "login_password": "[data-automation-id='password'], input[type='password']",
    "login_submit": "button:has-text('Sign In')",
    "save_and_continue": "button:has-text('Save and Continue')",
    "submit_button": "button:has-text('Submit')",
    "consent_checkbox": "input[type='checkbox']",
    "voluntary_disclosures_heading": "text='Voluntary Disclosures'",
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
        """Return the configured answer for a screening question, or None."""
        q = question_text.lower()
        for pattern, answer in SCREENING_ANSWERS.items():
            if pattern.lower() in q:
                return answer
        return None

    async def _try_answer_questions(self, page) -> list[str]:
        """Find question labels on the current step, attempt to fill matched
        answers via their associated dropdown/select. Returns a list of
        unmatched question labels (empty = all answered or no questions)."""
        # Workday renders questions as <label> followed by a sibling <select>
        # or a custom dropdown with data-automation-id. We look for labels
        # that contain our screening question text, then interact with the
        # nearest dropdown/select to set the answer.
        unmatched = []

        # Find all visible labels on the page
        labels = page.locator("label:visible")
        label_count = await labels.count()

        for i in range(label_count):
            label_el = labels.nth(i)
            label_text = (await label_el.text_content() or "").strip()
            if not label_text or len(label_text) < 10:
                continue  # skip tiny labels (e.g. "*")

            answer = self._match_answer(label_text)
            if answer is None:
                # Skip labels that are just step headings or field names
                # we don't care about (pre-filled from last application)
                skip_patterns = [
                    "indicates a required field", "work experience",
                    "job title", "company", "location", "how did you hear",
                    "my information", "my experience", "terms and conditions",
                    "consent", "voluntary disclosures",
                ]
                if any(sp in label_text.lower() for sp in skip_patterns):
                    continue
                unmatched.append(label_text)
                continue

            # Try to fill the answer — look for a <select> associated with
            # this label (via for= or as a sibling)
            try:
                label_for = await label_el.get_attribute("for")
                if label_for:
                    select_el = page.locator(f"#{label_for}")
                else:
                    # Fall back: find the nearest select/input after this label
                    parent = label_el.locator("..")
                    select_el = parent.locator("select, input[type='text']").first

                if await select_el.count() > 0:
                    tag = await select_el.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "select":
                        await select_el.select_option(label=answer)
                    else:
                        # Text input (e.g. desired salary)
                        await select_el.fill("")
                        await human_type(page, f"#{label_for}" if label_for else "input[type='text']", answer)
                    await page.wait_for_timeout(random_delay(0.5, 1.5) * 1000)
                    logger.debug(f"Answered: '{label_text[:60]}' -> '{answer}'")
                else:
                    # Might be a custom Workday dropdown widget — try clicking
                    # the label's parent container and selecting by text
                    parent = label_el.locator("..")
                    dropdown_btn = parent.locator("button, [role='listbox'], [role='combobox']").first
                    if await dropdown_btn.count() > 0:
                        await dropdown_btn.click()
                        await page.wait_for_timeout(random_delay(0.5, 1.0) * 1000)
                        option = page.locator(f"[role='option']:has-text('{answer}'), li:has-text('{answer}')").first
                        if await option.count() > 0:
                            await option.click()
                            await page.wait_for_timeout(random_delay(0.3, 0.8) * 1000)
                        else:
                            unmatched.append(f"{label_text} (could not find option '{answer}')")
                    else:
                        unmatched.append(f"{label_text} (no input found)")
            except Exception as e:
                logger.warning(f"Failed to fill answer for '{label_text[:60]}': {e}")
                unmatched.append(f"{label_text} (fill error)")

        return unmatched

    async def apply(self, page, job: dict) -> dict:
        job_id = str(job["id"])
        result = {"status": "failed", "error_log": None, "screenshot_path": None}

        try:
            await page.goto(job["url"], wait_until="domcontentloaded")
            await page.wait_for_timeout(random_delay(2, 5) * 1000)

            # Click Apply on the job detail page
            apply_btn = page.locator(SELECTORS["apply_button"]).first
            if await apply_btn.count() == 0:
                result["error_log"] = "Apply button not found -- job may be closed or selector is stale"
                result["screenshot_path"] = await self.take_screenshot(page, job_id, "no_apply_btn")
                return result

            await apply_btn.click()
            await page.wait_for_timeout(random_delay(2, 4) * 1000)

            # Handle login if needed
            if not await self.ensure_logged_in(page):
                result["error_log"] = "Login failed or credentials missing"
                result["screenshot_path"] = await self.take_screenshot(page, job_id, "login_failed")
                return result

            # "Start Your Application" modal — pick "Use My Last Application"
            use_last = page.locator(SELECTORS["use_last_application"]).first
            if await use_last.count() == 0 or not await use_last.is_visible():
                result["error_log"] = "\"Use My Last Application\" option not found -- needs manual application"
                result["screenshot_path"] = await self.take_screenshot(page, job_id, "no_use_last_app")
                return result

            await use_last.click()
            await page.wait_for_timeout(random_delay(3, 5) * 1000)

            # Walk through the multi-step form:
            # My Information -> My Experience -> App Q 1/2 -> App Q 2/2
            #   -> Voluntary Disclosures (has Submit button)
            for _ in range(MAX_FORM_STEPS):
                await page.wait_for_timeout(random_delay(1, 3) * 1000)

                # Check if we've reached Voluntary Disclosures (final pre-submit step)
                vol_heading = page.locator(SELECTORS["voluntary_disclosures_heading"]).first
                if await vol_heading.count() > 0 and await vol_heading.is_visible():
                    # Check the consent checkbox if not already checked
                    checkbox = page.locator(SELECTORS["consent_checkbox"]).first
                    if await checkbox.count() > 0:
                        is_checked = await checkbox.is_checked()
                        if not is_checked:
                            await checkbox.check()
                            await page.wait_for_timeout(random_delay(0.5, 1.5) * 1000)
                    break  # reached the final step

                # Try to answer any screening questions on this step
                unmatched = await self._try_answer_questions(page)
                if unmatched:
                    result["error_log"] = (
                        "Unrecognized screening question(s), needs manual answer: "
                        + "; ".join(unmatched[:5])
                    )
                    result["screenshot_path"] = await self.take_screenshot(page, job_id, "unknown_question")
                    return result

                # Click "Save and Continue" to advance
                save_btn = page.locator(SELECTORS["save_and_continue"]).first
                if await save_btn.count() == 0:
                    result["error_log"] = "Save and Continue button not found -- form flow may have changed"
                    result["screenshot_path"] = await self.take_screenshot(page, job_id, "no_save_btn")
                    return result
                await save_btn.click()
                await page.wait_for_timeout(random_delay(2, 4) * 1000)

            # We're on Voluntary Disclosures with consent checked
            if not self.auto_submit:
                result["status"] = "awaiting_review"
                result["screenshot_path"] = await self.take_screenshot(page, job_id, "ready_to_submit")
                logger.info(f"Filled application for {job['title']} -- left on Voluntary Disclosures for you to submit")
                return result

            # Auto-submit: click Submit
            submit_btn = page.locator(SELECTORS["submit_button"]).first
            if await submit_btn.count() == 0:
                result["error_log"] = "Submit button not found on Voluntary Disclosures"
                result["screenshot_path"] = await self.take_screenshot(page, job_id, "no_submit_btn")
                return result

            await submit_btn.click()
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
