"""
scheduler.py — APScheduler jobs:
  1. Daily digest at 6:00 AM UTC
  2. Re-scrape all sources every 24 hours
"""

import os
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler = None
_bot_app = None   # set by bot.py after app is created


def set_bot_app(app):
    global _bot_app
    _bot_app = app


async def _run_scrape_and_enrich():
    """Full scrape + enrich + score + save cycle."""
    from scraper import run_all_scrapers
    from enricher import batch_enrich
    from scorer import calculate_score, get_dune_flag, get_liveness_flag
    from database import upsert_lead

    logger.info("⏰ Scheduled scrape starting...")
    raw_leads = run_all_scrapers()
    enriched = batch_enrich(raw_leads)

    new_count = 0
    for lead in enriched:
        lead["lead_score"] = calculate_score(lead)
        lead["dune_presence_flag"] = get_dune_flag(lead.get("dune_presence", "none"))
        lead["liveness_flag"] = get_liveness_flag(lead.get("liveness", "active"))
        is_new = upsert_lead(lead)
        if is_new:
            new_count += 1

    logger.info("⏰ Scrape complete — %d total, %d new", len(enriched), new_count)

    # Alert bot owner on Telegram
    if _bot_app:
        owner_id = os.getenv("TELEGRAM_OWNER_ID")
        if owner_id:
            try:
                await _bot_app.bot.send_message(
                    chat_id=int(owner_id),
                    text=f"✅ Scheduled scrape complete!\n"
                         f"📦 {len(enriched)} leads processed\n"
                         f"🆕 {new_count} new leads added\n\n"
                         f"Use /leads to see your top leads."
                )
            except Exception as e:
                logger.error("Failed to send Telegram scrape alert: %s", e)


async def _run_daily_digest():
    """Send the daily digest email."""
    from database import get_pending_leads, mark_leads_delivered, log_digest
    from email_sender import send_digest_email

    logger.info("⏰ Daily digest job starting...")
    leads = get_pending_leads(limit=15)

    if len(leads) < 5:
        logger.warning("Fewer than 5 leads available for digest (%d found)", len(leads))
        if _bot_app:
            owner_id = os.getenv("TELEGRAM_OWNER_ID")
            if owner_id:
                try:
                    await _bot_app.bot.send_message(
                        chat_id=int(owner_id),
                        text=f"⚠️ Daily digest warning: only {len(leads)} leads available (minimum is 5).\n"
                             f"Consider running /refresh to scrape more leads."
                    )
                except Exception:
                    pass
        if not leads:
            return

    success = send_digest_email(leads)
    if success:
        ids = [lead["id"] for lead in leads]
        mark_leads_delivered(ids)
        log_digest(len(leads))
        if _bot_app:
            owner_id = os.getenv("TELEGRAM_OWNER_ID")
            if owner_id:
                try:
                    await _bot_app.bot.send_message(
                        chat_id=int(owner_id),
                        text=f"📧 Daily digest sent!\n"
                             f"🎯 {len(leads)} leads delivered to your email."
                    )
                except Exception:
                    pass
    else:
        logger.error("Daily digest email failed to send")


def start_scheduler():
    global _scheduler
    digest_hour = int(os.getenv("DIGEST_HOUR", "6"))
    digest_minute = int(os.getenv("DIGEST_MINUTE", "0"))

    _scheduler = AsyncIOScheduler(timezone="UTC")

    # Daily digest at 6:00 AM UTC
    _scheduler.add_job(
        _run_daily_digest,
        CronTrigger(hour=digest_hour, minute=digest_minute, timezone="UTC"),
        id="daily_digest",
        name="Daily Lead Digest Email",
        replace_existing=True,
    )

    # Re-scrape every 24 hours
    _scheduler.add_job(
        _run_scrape_and_enrich,
        IntervalTrigger(hours=24),
        id="scrape_cycle",
        name="24h Lead Scrape Cycle",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("✅ Scheduler started — digest at %02d:%02d UTC, rescrape every 24h", digest_hour, digest_minute)
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info("Scheduler stopped")


async def trigger_scrape_now():
    """Manually trigger a full scrape cycle (called by /refresh command)."""
    await _run_scrape_and_enrich()


async def trigger_digest_now():
    """Manually trigger digest send."""
    await _run_daily_digest()
