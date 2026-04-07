"""
enricher.py — Uses Google Gemini 1.5 Flash to enrich leads and generate pitch angles.
"""

import os
import json
import logging
import time
import re

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not installed. Enrichment will be skipped.")


def _get_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not GEMINI_AVAILABLE:
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")


def enrich_lead(raw_lead: dict) -> dict:
    """
    Given a raw lead dict from a scraper, use Gemini to:
    1. Fill in missing fields
    2. Assess Dune presence
    3. Assess on-chain activity level
    4. Assess liveness
    5. Generate a tailored pitch angle
    Returns the enriched lead dict.
    """
    model = _get_model()
    if not model:
        logger.warning("Gemini unavailable — skipping enrichment for %s", raw_lead.get("project_name"))
        return raw_lead

    prompt = f"""
You are a Web3 analyst assistant. Given the following raw data about a Web3 project,
enrich it and return a JSON object with ALL of the fields below filled in.

RAW PROJECT DATA:
{json.dumps(raw_lead, indent=2)}

Return ONLY a valid JSON object (no markdown, no explanation) with these exact fields:
{{
  "project_name": "...",
  "description": "One clear sentence describing what this project does",
  "website": "...",
  "twitter": "Twitter/X handle starting with @",
  "discord": "Discord invite link or empty string",
  "telegram_link": "Telegram group link or empty string",
  "chains": "Comma-separated list of chains e.g. Ethereum, Base",
  "token_ticker": "Token ticker with $ e.g. $ETH or empty string",
  "token_contract": "Contract address or empty string",
  "team_size": "Approximate team size e.g. ~15 or empty string",
  "funding_stage": "e.g. Seed, Series A, Bootstrapped, or empty string",
  "funding_amount": "e.g. $2M or empty string",
  "funding_date": "e.g. Jan 2025 or empty string",
  "funding_investors": "Comma-separated investor names or empty string",
  "recent_news": "One sentence summary of most recent news/announcement or empty string",
  "dune_presence": "One of: none, minimal, decent, well_covered",
  "dune_presence_flag": "One of: 🔴 None, 🟡 Minimal, 🟠 Decent, 🟢 Well-covered",
  "liveness": "One of: active, slow, inactive",
  "liveness_flag": "One of: 🟢 Active, 🟡 Slow, 🔴 Inactive",
  "onchain_activity": "One of: high, medium, low",
  "contact_twitter": "Founder or core team Twitter handles comma-separated",
  "contact_linkedin": "LinkedIn profile URLs comma-separated or empty string",
  "contact_email": "Public email or contact form URL or empty string",
  "contact_analytics": "Name/handle of person handling data or analytics on the team if known",
  "pitch_angle": "1-2 sentence tailored pitch for a Dune Analytics dashboard analyst. Be specific about what dashboard gaps exist. Examples: 'No TVL dashboard exists — pitch a treasury and liquidity tracking dashboard.' or 'Active NFT project with no holder distribution or sales volume dashboard.'"
}}

Rules:
- dune_presence should be 'none' unless you have strong evidence they have dashboards
- liveness should reflect recent on-chain, social, and GitHub signals
- pitch_angle must be specific and actionable, not generic
- If a field is unknown, use empty string not null
- Return ONLY the JSON object, nothing else
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Strip markdown code fences if present
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        enriched = json.loads(text)
        # Merge with original, enriched takes priority
        merged = {**raw_lead, **enriched}
        return merged
    except json.JSONDecodeError as e:
        logger.error("Gemini returned invalid JSON for %s: %s", raw_lead.get("project_name"), e)
        return raw_lead
    except Exception as e:
        logger.error("Gemini enrichment failed for %s: %s", raw_lead.get("project_name"), e)
        return raw_lead


def batch_enrich(leads: list, delay: float = 2.0) -> list:
    """Enrich a list of leads with a delay between each to respect rate limits."""
    enriched = []
    for i, lead in enumerate(leads):
        logger.info("Enriching lead %d/%d: %s", i+1, len(leads), lead.get("project_name", "?"))
        enriched.append(enrich_lead(lead))
        if i < len(leads) - 1:
            time.sleep(delay)
    return enriched
