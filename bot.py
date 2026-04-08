"""
bot.py — Telegram bot with all 7 commands + inline action buttons.
"""

import os
import logging
import asyncio
from dotenv import load_dotenv

# Load .env file if it exists (local development)
# On Railway/Render, variables are injected directly as environment variables
load_dotenv(override=False)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

from database import (
    init_db, get_pending_leads, get_top_leads,
    get_leads_by_category, mark_lead, get_lead_by_name, get_stats
)
from scheduler import start_scheduler, trigger_scrape_now

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

OWNER_ID = int(os.getenv("TELEGRAM_OWNER_ID", "0"))


# ── Auth guard ─────────────────────────────────────────────────────────────
def owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if OWNER_ID and update.effective_user.id != OWNER_ID:
            await update.message.reply_text("⛔ Unauthorised. This bot is private.")
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


# ── Lead formatter for Telegram ───────────────────────────────────────────
def format_lead_telegram(lead: dict) -> str:
    score = lead.get("lead_score", 0)
    score_emoji = "🟢" if score >= 75 else "🟡" if score >= 50 else "🔴"

    lines = [f"*{lead.get('project_name', 'Unknown')}*"]

    if lead.get("description"):
        lines.append(f"📝 {lead['description']}")

    lines.append("")
    lines.append("🔗 *Links*")
    if lead.get("website"):
        lines.append(f"🌐 {lead['website']}")
    if lead.get("twitter"):
        lines.append(f"🐦 {lead['twitter']}")
    if lead.get("discord"):
        lines.append(f"💬 {lead['discord']}")
    if lead.get("telegram_link"):
        lines.append(f"✈️ {lead['telegram_link']}")

    lines.append("")
    if lead.get("chains"):
        lines.append(f"⛓ *Chain:* {lead['chains']}")
    if lead.get("token_ticker"):
        lines.append(f"🪙 *Token:* {lead['token_ticker']}")
    if lead.get("team_size"):
        lines.append(f"👥 *Team Size:* {lead['team_size']}")

    funding_parts = []
    if lead.get("funding_amount"):
        funding_parts.append(lead["funding_amount"])
    if lead.get("funding_stage"):
        funding_parts.append(lead["funding_stage"])
    if lead.get("funding_date"):
        funding_parts.append(f"— {lead['funding_date']}")
    if lead.get("funding_investors"):
        funding_parts.append(f"({lead['funding_investors']})")
    if funding_parts:
        lines.append(f"💰 *Funding:* {' '.join(funding_parts)}")

    if lead.get("recent_news"):
        lines.append(f"📰 *Recent News:* {lead['recent_news']}")

    lines.append("")
    lines.append(f"📊 *Dune Presence:* {lead.get('dune_presence_flag', '🔴 None')}")
    lines.append(f"💓 *Liveness:* {lead.get('liveness_flag', '🟢 Active')}")
    lines.append(f"🎯 *Lead Score:* {score_emoji} {score}/100")

    contacts = []
    if lead.get("contact_twitter"):
        contacts.append(lead["contact_twitter"])
    if lead.get("contact_linkedin"):
        contacts.append(lead["contact_linkedin"])
    if lead.get("contact_email"):
        contacts.append(lead["contact_email"])
    if contacts:
        lines.append("")
        lines.append("📇 *Contacts:*")
        for c in contacts:
            for item in c.split(","):
                item = item.strip()
                if item:
                    lines.append(f"• {item}")

    if lead.get("pitch_angle"):
        lines.append("")
        lines.append(f"🚀 *Pitch:* _{lead['pitch_angle']}_")

    return "\n".join(lines)


def lead_action_keyboard(lead_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Pitched",       callback_data=f"action:pitched:{lead_id}"),
        InlineKeyboardButton("👍 Interested",    callback_data=f"action:interested:{lead_id}"),
        InlineKeyboardButton("👎 Not Interested",callback_data=f"action:not_interested:{lead_id}"),
    ]])


async def send_leads(update: Update, leads: list, title: str):
    """Send a list of leads as formatted Telegram messages."""
    if not leads:
        await update.message.reply_text(
            "😕 No leads found matching your criteria.\n"
            "Try /refresh to scrape fresh leads."
        )
        return

    await update.message.reply_text(
        f"*{title}*\n📦 Showing {len(leads)} lead(s):",
        parse_mode="Markdown"
    )

    for lead in leads:
        text = format_lead_telegram(lead)
        keyboard = lead_action_keyboard(lead["id"])
        try:
            await update.message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        except Exception as e:
            # Fallback without markdown if parsing fails
            logger.error("Markdown send failed for %s: %s", lead.get("project_name"), e)
            await update.message.reply_text(
                text.replace("*", "").replace("_", ""),
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )


# ══════════════════════════════════════════════════════════════════════════
#  BOT COMMANDS
# ══════════════════════════════════════════════════════════════════════════

@owner_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Welcome to Web3 Lead Gen Bot!*\n\n"
        "I hunt Web3 projects that need Dune Analytics dashboards and bring them to you.\n\n"
        "*Commands:*\n"
        "/leads — Top 10 leads right now\n"
        "/top — Top 5 highest scored leads\n"
        "/filter \\[category\\] — Filter by category or chain\n"
        "/refresh — Trigger a fresh scrape now\n"
        "/status — Scrape stats and DB summary\n"
        "/pitch \\[project\\] — Get pitch angle for a project\n\n"
        "📧 Daily digest sent to your email at 6:00 AM UTC"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


@owner_only
async def cmd_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Fetching your top leads...")
    leads = get_pending_leads(limit=10)
    await send_leads(update, leads, "🔍 Top 10 Leads")


@owner_only
async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⭐ Fetching top 5 highest scored leads...")
    leads = get_top_leads(limit=5)
    await send_leads(update, leads, "⭐ Top 5 Leads by Score")


@owner_only
async def cmd_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /filter \\[category or chain\\]\n\n"
            "Examples:\n"
            "/filter defi\n"
            "/filter base\n"
            "/filter nft\n"
            "/filter solana\n"
            "/filter dao",
            parse_mode="Markdown"
        )
        return

    category = " ".join(context.args).lower()
    await update.message.reply_text(f"🔍 Filtering leads for: *{category}*...", parse_mode="Markdown")
    leads = get_leads_by_category(category, limit=10)
    await send_leads(update, leads, f"🔍 Leads filtered by: {category}")


@owner_only
async def cmd_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔄 Starting fresh scrape of all sources...\n"
        "This may take a few minutes. I'll notify you when done."
    )
    trigger_scrape_now()


@owner_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_stats()
    text = (
        "📊 *Bot Status*\n\n"
        f"🗄 Total leads in DB: *{stats['total']}*\n"
        f"📬 Pending (not acted on): *{stats['pending']}*\n"
        f"✅ Pitched: *{stats['pitched']}*\n"
        f"🕒 Last scrape: `{stats['last_scrape']}`\n\n"
        "📧 Digest: daily at 6:00 AM UTC\n"
        "🔄 Re-scrape: every 24 hours"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


@owner_only
async def cmd_pitch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /pitch \\[project name\\]\n\nExample: /pitch Uniswap",
            parse_mode="Markdown"
        )
        return

    project_name = " ".join(context.args)
    lead = get_lead_by_name(project_name)

    if not lead:
        await update.message.reply_text(
            f"😕 No lead found for *{project_name}*.\n"
            f"Try /leads to see all available leads.",
            parse_mode="Markdown"
        )
        return

    pitch = lead.get("pitch_angle") or "No pitch angle generated yet. Try /refresh to re-enrich leads."
    score = lead.get("lead_score", 0)

    text = (
        f"🚀 *Pitch Angle for {lead['project_name']}*\n\n"
        f"{pitch}\n\n"
        f"🎯 Lead Score: *{score}/100*\n"
        f"📊 Dune Presence: {lead.get('dune_presence_flag','—')}\n"
        f"💓 Liveness: {lead.get('liveness_flag','—')}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ── Callback handler for action buttons ───────────────────────────────────
async def handle_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, action, lead_id = query.data.split(":")
        lead_id = int(lead_id)
        mark_lead(lead_id, action)

        action_labels = {
            "pitched": "✅ Marked as Pitched",
            "interested": "👍 Marked as Interested",
            "not_interested": "👎 Marked as Not Interested",
        }
        label = action_labels.get(action, "✅ Updated")

        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"{label} — removed from future digests", callback_data="done")
            ]])
        )
    except Exception as e:
        logger.error("Callback error: %s", e)
        await query.answer("Something went wrong. Please try again.")


async def handle_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Already acted on.")


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        # Print all available env var names to help debug
        available = [k for k in os.environ.keys() if not k.startswith("_")]
        logger.error("Available environment variables: %s", available)
        raise ValueError(
            "TELEGRAM_BOT_TOKEN not found in environment. "
            "Make sure it is set in Railway Variables tab."
        )

    # Initialise database
    init_db()
    logger.info("✅ Database ready")

    # Build bot app
    app = Application.builder().token(token).build()

    # Register commands
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("leads",   cmd_leads))
    app.add_handler(CommandHandler("top",     cmd_top))
    app.add_handler(CommandHandler("filter",  cmd_filter))
    app.add_handler(CommandHandler("refresh", cmd_refresh))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("pitch",   cmd_pitch))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(handle_action_callback, pattern=r"^action:"))
    app.add_handler(CallbackQueryHandler(handle_done_callback,   pattern=r"^done$"))

    logger.info("🚀 Bot is starting...")

    async def _post_init(app):
        # Start scheduler — passes app reference internally
        start_scheduler(app)
        logger.info("✅ Scheduler started")

        # Run initial scrape on first launch
        from database import get_stats
        stats = get_stats()
        if stats["total"] == 0:
            logger.info("First launch — triggering initial scrape...")
            trigger_scrape_now()

    app.post_init = _post_init
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
