"""
scheduler.py — BackgroundScheduler for daily digest and 24h rescrape.
"""

import os
import logging
import asyncio
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler = None
_bot_app = None
_loop = None


def set_bot_app(app, loop):
    global _bot_app, _loop
    _bot_app = app
    _loop = loop


def _send_telegram_message(text):
    owner_id = os.getenv("TELEGRAM_OWNER_ID")
    if not owner_id or not _bot_app or not _loop:
        return
    try:
        asyncio.run_coroutine_threadsafe(
            _bot_app.bot.send_message(chat_id=int(owner_id), text=text),
            _loop
        )
    except Exception as e:
        logger.error("Failed to send Telegram alert: %s", e)


def _run_scrape_and_enrich():
    try:
        from scraper import run_all_scrapers
        from enricher import batch_enrich
        from scorer import calculate_score, get_dune_flag, get_liveness_flag
        from database import upsert_lead

        logger.info("Scheduled scrape starting...")
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

        logger.info("Scrape complete — %d total, %d new", len(enriched), new_count)
        _send_telegram_message(
            f"✅ Scrape complete!\n"
            f"📦 {len(enriched)} leads processed\n"
            f"🆕 {new_count} new leads added\n\n"
            f"Use /leads to see your top leads."
        )
    except Exception as e:
        logger.error("Scrape cycle failed: %s", e)
        _send_telegram_message(f"⚠️ Scrape cycle failed: {e}")


def _run_daily_digest():
    try:
        from database import get_pending_leads, mark_leads_delivered, log_digest
        from email_sender import send_digest_email

        logger.info("Daily digest job starting...")
        leads = get_pending_leads(limit=15)

        if len(leads) < 5:
            logger.warning("Fewer than 5 leads available (%d found)", len(leads))
            _send_telegram_message(
                f"⚠️ Only {len(leads)} leads available for digest.\n"
                f"Use /refresh to scrape more leads."
            )
            if not leads:
                return

        success = send_digest_email(leads)
        if success:
            ids = [lead["id"] for lead in leads]
            mark_leads_delivered(ids)
            log_digest(len(leads))
            _send_telegram_message(
                f"📧 Daily digest sent!\n"
                f"🎯 {len(leads)} leads delivered to your email."
            )
        else:
            _send_telegram_message("❌ Daily digest email failed. Check your Gmail credentials.")
    except Exception as e:
        logger.error("Daily digest failed: %s", e)
        _send_telegram_message(f"❌ Daily digest failed: {e}")


def start_scheduler(app):
    global _scheduler
    loop = asyncio.get_event_loop()
    set_bot_app(app, loop)

    digest_hour = int(os.getenv("DIGEST_HOUR", "6"))
    digest_minute = int(os.getenv("DIGEST_MINUTE", "0"))

    _scheduler = BackgroundScheduler(timezone="UTC")

    _scheduler.add_job(
        _run_daily_digest,
        CronTrigger(hour=digest_hour, minute=digest_minute, timezone="UTC"),
        id="daily_digest",
        name="Daily Lead Digest Email",
        replace_existing=True,
    )

    _scheduler.add_job(
        _run_scrape_and_enrich,
        IntervalTrigger(hours=24),
        id="scrape_cycle",
        name="24h Lead Scrape Cycle",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler started — digest at %02d:%02d UTC, rescrape every 24h", digest_hour, digest_minute)
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info("Scheduler stopped")


def trigger_scrape_now():
    t = threading.Thread(target=_run_scrape_and_enrich, daemon=True)
    t.start()


def trigger_digest_now():
    t = threading.Thread(target=_run_daily_digest, daemon=True)
    t.start()
