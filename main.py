import asyncio
import logging
import click
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Job Automation Pipeline - CLI"""
    pass


@cli.command()
@click.option("--source", default="naukri", help="Scraper source (naukri)")
@click.option("--keyword", required=True, help="Job search keyword")
@click.option("--location", default="", help="Job location filter")
@click.option("--max-results", default=500, help="Max results to fetch")
def scrape(source, keyword, location, max_results):
    """Scrape job listings from a source."""
    if source == "naukri":
        from scrapers.naukri import NaukriScraper, save_jobs_to_db

        scraper = NaukriScraper()
        jobs = scraper.fetch(keyword=keyword, location=location, max_results=max_results)
        inserted = save_jobs_to_db(jobs)
        click.echo(f"Scraped {len(jobs)} jobs, inserted {inserted} new jobs into DB.")
    else:
        click.echo(f"Source '{source}' not supported yet. Available: naukri")


@cli.command("filter")
def keyword_filter():
    """Run keyword pre-filter on scraped jobs."""
    from db.connection import get_session
    from filtering.keyword_filter import run_keyword_filter

    session = get_session()
    try:
        counts = run_keyword_filter(session)
        click.echo(f"Keyword filter: {counts['passed']} passed, {counts['failed']} failed")
    finally:
        session.close()


@cli.command()
def score():
    """Run Claude scorer on keyword-passed jobs."""
    from db.connection import get_session
    from filtering.claude_scorer import run_claude_scorer

    session = get_session()
    try:
        counts = run_claude_scorer(session)
        click.echo(
            f"Claude scoring: {counts['scored']} scored, "
            f"{counts['scored_low']} low, {counts['errors']} errors"
        )
    finally:
        session.close()


@cli.command("assign-resumes")
def assign_resumes():
    """Assign resume variants and route to apply queues."""
    from db.connection import get_session
    from resumes.router import run_resume_router

    session = get_session()
    try:
        counts = run_resume_router(session)
        click.echo(
            f"Resume routing: {counts['ready_to_apply']} ready to apply, "
            f"{counts['ready_for_manual_apply']} for manual apply"
        )
    finally:
        session.close()


@cli.command()
@click.option("--platform", default="naukri", help="Platform to apply on")
@click.option("--limit", default=None, type=int, help="Max applications this session")
def apply(platform, limit):
    """Run Playwright applier for a platform."""
    if platform == "naukri":
        from appliers.naukri import run_naukri_applier
        asyncio.run(run_naukri_applier(limit=limit))
    else:
        click.echo(f"Platform '{platform}' applier not built yet. Available: naukri")


@cli.command()
def stats():
    """Show pipeline dashboard."""
    from db.connection import get_session
    from tracking.dashboard import print_dashboard

    session = get_session()
    try:
        print_dashboard(session)
    finally:
        session.close()


@cli.command("manual-queue")
def manual_queue():
    """Show jobs ready for manual application (Tier 2)."""
    from db.connection import get_session
    from db.models import Job

    session = get_session()
    try:
        jobs = (
            session.query(Job)
            .filter(Job.status == "ready_for_manual_apply")
            .order_by(Job.claude_score.desc().nullslast())
            .all()
        )

        if not jobs:
            click.echo("No jobs in manual-apply queue.")
            return

        click.echo(f"\n{'=' * 80}")
        click.echo(f"  MANUAL APPLY QUEUE — {len(jobs)} jobs")
        click.echo(f"{'=' * 80}")
        for i, job in enumerate(jobs, 1):
            click.echo(f"\n  [{i}] {job.title} @ {job.company}")
            click.echo(f"      Score: {job.claude_score or 'N/A'}  |  Resume: {job.resume_variant or 'backend'}")
            click.echo(f"      URL: {job.url}")
            if job.claude_reason:
                click.echo(f"      Why: {job.claude_reason}")
        click.echo(f"\n{'=' * 80}\n")
    finally:
        session.close()


@cli.command("run-all")
@click.option("--keyword", required=True, help="Job search keyword")
@click.option("--location", default="", help="Location filter")
@click.option("--apply-limit", default=25, help="Max applications per run")
@click.option("--skip-apply", is_flag=True, help="Run pipeline without applying (dry run)")
def run_all(keyword, location, apply_limit, skip_apply):
    """Run the full pipeline: scrape > filter > score > route > apply > stats."""
    from scrapers.naukri import NaukriScraper, save_jobs_to_db
    from db.connection import get_session
    from filtering.keyword_filter import run_keyword_filter
    from filtering.claude_scorer import run_claude_scorer
    from resumes.router import run_resume_router
    from tracking.dashboard import print_dashboard

    click.echo("=== STEP 1: Scraping Naukri ===")
    scraper = NaukriScraper()
    jobs = scraper.fetch(keyword=keyword, location=location)
    inserted = save_jobs_to_db(jobs)
    click.echo(f"Scraped {len(jobs)} jobs, {inserted} new.\n")

    session = get_session()
    try:
        click.echo("=== STEP 2: Keyword Filter ===")
        kf = run_keyword_filter(session)
        click.echo(f"Passed: {kf['passed']}, Failed: {kf['failed']}\n")

        click.echo("=== STEP 3: Claude Scoring ===")
        cs = run_claude_scorer(session)
        click.echo(f"Scored: {cs['scored']}, Low: {cs['scored_low']}, Errors: {cs['errors']}\n")

        click.echo("=== STEP 4: Resume Routing ===")
        rr = run_resume_router(session)
        click.echo(f"Ready to apply: {rr['ready_to_apply']}, Manual: {rr['ready_for_manual_apply']}\n")
    finally:
        session.close()

    if not skip_apply:
        click.echo(f"=== STEP 5: Applying (limit={apply_limit}) ===")
        from appliers.naukri import run_naukri_applier
        asyncio.run(run_naukri_applier(limit=apply_limit))
    else:
        click.echo("=== STEP 5: Skipped (--skip-apply) ===\n")

    click.echo("=== STEP 6: Dashboard ===")
    session = get_session()
    try:
        print_dashboard(session)
    finally:
        session.close()


if __name__ == "__main__":
    cli()
