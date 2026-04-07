"""
database.py — SQLite setup and all DB queries for the Web3 Lead Gen Bot
"""

import sqlite3
import os
import logging
from datetime import datetime
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "leads.db")
logger = logging.getLogger(__name__)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name        TEXT NOT NULL,
            description         TEXT,
            website             TEXT,
            twitter             TEXT,
            discord             TEXT,
            telegram_link       TEXT,
            chains              TEXT,
            token_ticker        TEXT,
            token_contract      TEXT,
            team_size           TEXT,
            funding_stage       TEXT,
            funding_amount      TEXT,
            funding_date        TEXT,
            funding_investors   TEXT,
            recent_news         TEXT,
            dune_presence       TEXT DEFAULT 'none',
            dune_presence_flag  TEXT DEFAULT '🔴 None',
            liveness            TEXT DEFAULT 'active',
            liveness_flag       TEXT DEFAULT '🟢 Active',
            contact_twitter     TEXT,
            contact_linkedin    TEXT,
            contact_email       TEXT,
            contact_analytics   TEXT,
            lead_score          INTEGER DEFAULT 0,
            pitch_angle         TEXT,
            source              TEXT,
            status              TEXT DEFAULT 'new',
            first_seen          TEXT,
            last_updated        TEXT,
            last_delivered      TEXT,
            delivered_count     INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS scrape_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT,
            status      TEXT,
            leads_found INTEGER DEFAULT 0,
            error_msg   TEXT,
            scraped_at  TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS digest_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            leads_sent  INTEGER,
            sent_at     TEXT
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialised at %s", DB_PATH)


# ── LEAD CRUD ──────────────────────────────────────────────────────────────

def upsert_lead(lead: dict) -> bool:
    """Insert new lead or update existing one (match on project_name + website).
    Returns True if new lead was inserted, False if existing was updated."""
    conn = get_connection()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()

    # Check duplicate
    c.execute(
        "SELECT id FROM leads WHERE LOWER(project_name) = LOWER(?) OR (website != '' AND website = ?)",
        (lead.get("project_name", ""), lead.get("website", ""))
    )
    row = c.fetchone()

    if row:
        # Update existing — refresh enrichment data but keep status
        c.execute("""
            UPDATE leads SET
                description=?, website=?, twitter=?, discord=?, telegram_link=?,
                chains=?, token_ticker=?, token_contract=?, team_size=?,
                funding_stage=?, funding_amount=?, funding_date=?, funding_investors=?,
                recent_news=?, dune_presence=?, dune_presence_flag=?,
                liveness=?, liveness_flag=?, contact_twitter=?, contact_linkedin=?,
                contact_email=?, contact_analytics=?, lead_score=?, pitch_angle=?,
                source=?, last_updated=?
            WHERE id=?
        """, (
            lead.get("description"), lead.get("website"), lead.get("twitter"),
            lead.get("discord"), lead.get("telegram_link"), lead.get("chains"),
            lead.get("token_ticker"), lead.get("token_contract"), lead.get("team_size"),
            lead.get("funding_stage"), lead.get("funding_amount"), lead.get("funding_date"),
            lead.get("funding_investors"), lead.get("recent_news"), lead.get("dune_presence"),
            lead.get("dune_presence_flag"), lead.get("liveness"), lead.get("liveness_flag"),
            lead.get("contact_twitter"), lead.get("contact_linkedin"), lead.get("contact_email"),
            lead.get("contact_analytics"), lead.get("lead_score"), lead.get("pitch_angle"),
            lead.get("source"), now, row["id"]
        ))
        conn.commit()
        conn.close()
        return False
    else:
        c.execute("""
            INSERT INTO leads (
                project_name, description, website, twitter, discord, telegram_link,
                chains, token_ticker, token_contract, team_size, funding_stage,
                funding_amount, funding_date, funding_investors, recent_news,
                dune_presence, dune_presence_flag, liveness, liveness_flag,
                contact_twitter, contact_linkedin, contact_email, contact_analytics,
                lead_score, pitch_angle, source, status, first_seen, last_updated
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            lead.get("project_name"), lead.get("description"), lead.get("website"),
            lead.get("twitter"), lead.get("discord"), lead.get("telegram_link"),
            lead.get("chains"), lead.get("token_ticker"), lead.get("token_contract"),
            lead.get("team_size"), lead.get("funding_stage"), lead.get("funding_amount"),
            lead.get("funding_date"), lead.get("funding_investors"), lead.get("recent_news"),
            lead.get("dune_presence", "none"), lead.get("dune_presence_flag", "🔴 None"),
            lead.get("liveness", "active"), lead.get("liveness_flag", "🟢 Active"),
            lead.get("contact_twitter"), lead.get("contact_linkedin"), lead.get("contact_email"),
            lead.get("contact_analytics"), lead.get("lead_score", 0), lead.get("pitch_angle"),
            lead.get("source"), "new", now, now
        ))
        conn.commit()
        conn.close()
        return True


def get_pending_leads(limit: int = 15, min_leads: int = 5):
    """Get leads not yet acted on, sorted by score desc."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM leads
        WHERE status = 'new' AND liveness != 'inactive'
        ORDER BY lead_score DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_top_leads(limit: int = 5):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM leads
        WHERE status = 'new' AND liveness != 'inactive'
        ORDER BY lead_score DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_leads_by_category(category: str, limit: int = 10):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM leads
        WHERE status = 'new'
          AND liveness != 'inactive'
          AND (LOWER(description) LIKE ? OR LOWER(chains) LIKE ? OR LOWER(project_name) LIKE ?)
        ORDER BY lead_score DESC
        LIMIT ?
    """, (f"%{category.lower()}%", f"%{category.lower()}%", f"%{category.lower()}%", limit))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def mark_lead(lead_id: int, status: str):
    """Mark a lead as pitched / interested / not_interested."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE leads SET status=?, last_updated=? WHERE id=?",
        (status, datetime.utcnow().isoformat(), lead_id)
    )
    conn.commit()
    conn.close()


def mark_leads_delivered(lead_ids: list):
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    c = conn.cursor()
    for lid in lead_ids:
        c.execute(
            "UPDATE leads SET last_delivered=?, delivered_count=delivered_count+1 WHERE id=?",
            (now, lid)
        )
    conn.commit()
    conn.close()


def get_lead_by_name(name: str) -> Optional[dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM leads WHERE LOWER(project_name) LIKE ? LIMIT 1",
              (f"%{name.lower()}%",))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_stats() -> dict:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as total FROM leads")
    total = c.fetchone()["total"]
    c.execute("SELECT COUNT(*) as pending FROM leads WHERE status='new'")
    pending = c.fetchone()["pending"]
    c.execute("SELECT COUNT(*) as pitched FROM leads WHERE status='pitched'")
    pitched = c.fetchone()["pitched"]
    c.execute("SELECT scraped_at FROM scrape_log ORDER BY id DESC LIMIT 1")
    last_scrape = c.fetchone()
    conn.close()
    return {
        "total": total,
        "pending": pending,
        "pitched": pitched,
        "last_scrape": last_scrape["scraped_at"] if last_scrape else "Never"
    }


def log_scrape(source: str, status: str, leads_found: int = 0, error_msg: str = None):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO scrape_log (source, status, leads_found, error_msg, scraped_at) VALUES (?,?,?,?,?)",
        (source, status, leads_found, error_msg, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def log_digest(leads_sent: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO digest_log (leads_sent, sent_at) VALUES (?,?)",
        (leads_sent, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
