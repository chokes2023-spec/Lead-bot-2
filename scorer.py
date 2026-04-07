"""
scorer.py — Lead scoring logic (0–100 points)

Scoring breakdown:
  Dune Presence:   none=40, minimal=25, decent=10, well_covered=0
  On-chain Activity: high=20, medium=10, low=5
  Funding Recency:   last_3mo=20, last_6mo=10, older=5
  Team Size:         <10=10, 10-30=5, 30+=0
  Project Recency:   <6mo=10, <1yr=5, older=0
"""

import re
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def score_dune_presence(presence: str) -> int:
    mapping = {
        "none": 40,
        "minimal": 25,
        "decent": 10,
        "well_covered": 0,
    }
    return mapping.get(str(presence).lower().replace("-", "_"), 25)


def score_onchain_activity(activity: str) -> int:
    mapping = {"high": 20, "medium": 10, "low": 5}
    return mapping.get(str(activity).lower(), 10)


def score_funding_recency(funding_date: str) -> int:
    if not funding_date:
        return 0
    try:
        # Try to parse date in common formats
        for fmt in ("%Y-%m-%d", "%b %Y", "%B %Y", "%Y", "%m/%Y"):
            try:
                dt = datetime.strptime(funding_date.strip(), fmt)
                break
            except ValueError:
                continue
        else:
            return 5  # Unknown date, give minimal points

        now = datetime.utcnow()
        delta = now - dt

        if delta <= timedelta(days=90):
            return 20
        elif delta <= timedelta(days=180):
            return 10
        else:
            return 5
    except Exception:
        return 5


def score_team_size(team_size: str) -> int:
    if not team_size:
        return 5
    # Extract number from strings like "~15", "15 people", "10-20"
    numbers = re.findall(r"\d+", str(team_size))
    if not numbers:
        return 5
    size = int(numbers[0])
    if size < 10:
        return 10
    elif size <= 30:
        return 5
    else:
        return 0


def score_project_recency(first_seen: str = None, funding_date: str = None) -> int:
    """Use funding date or first_seen as proxy for project age."""
    date_str = funding_date or first_seen
    if not date_str:
        return 0
    try:
        for fmt in ("%Y-%m-%d", "%b %Y", "%B %Y", "%Y", "%Y-%m-%dT%H:%M:%S.%f"):
            try:
                dt = datetime.strptime(date_str[:10], fmt[:len(date_str[:10])])
                break
            except ValueError:
                continue
        else:
            return 0

        now = datetime.utcnow()
        delta = now - dt
        if delta <= timedelta(days=180):
            return 10
        elif delta <= timedelta(days=365):
            return 5
        else:
            return 0
    except Exception:
        return 0


def calculate_score(lead: dict) -> int:
    """Calculate total lead score from 0–100."""
    score = 0

    score += score_dune_presence(lead.get("dune_presence", "none"))
    score += score_onchain_activity(lead.get("onchain_activity", "medium"))
    score += score_funding_recency(lead.get("funding_date", ""))
    score += score_team_size(lead.get("team_size", ""))
    score += score_project_recency(
        first_seen=lead.get("first_seen"),
        funding_date=lead.get("funding_date")
    )

    return min(score, 100)


def get_dune_flag(presence: str) -> str:
    mapping = {
        "none": "🔴 None",
        "minimal": "🟡 Minimal",
        "decent": "🟠 Decent",
        "well_covered": "🟢 Well-covered",
    }
    return mapping.get(str(presence).lower().replace("-", "_").replace(" ", "_"), "🔴 None")


def get_liveness_flag(liveness: str) -> str:
    mapping = {
        "active": "🟢 Active",
        "slow": "🟡 Slow",
        "inactive": "🔴 Inactive",
    }
    return mapping.get(str(liveness).lower(), "🟢 Active")
