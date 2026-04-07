"""
email_sender.py — Builds and sends the HTML daily digest email via Gmail SMTP.
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

logger = logging.getLogger(__name__)


def _score_color(score: int) -> str:
    if score >= 75:
        return "#16A34A"   # green
    elif score >= 50:
        return "#D97706"   # amber
    else:
        return "#DC2626"   # red


def _lead_card_html(lead: dict) -> str:
    score = lead.get("lead_score", 0)
    score_color = _score_color(score)

    twitter_link = ""
    if lead.get("twitter"):
        handle = lead["twitter"].lstrip("@")
        twitter_link = f'<a href="https://twitter.com/{handle}" style="color:#1DA1F2;text-decoration:none;">🐦 {lead["twitter"]}</a>'

    discord_link = ""
    if lead.get("discord"):
        discord_link = f'<a href="{lead["discord"]}" style="color:#5865F2;text-decoration:none;">💬 Discord</a>'

    telegram_link = ""
    if lead.get("telegram_link"):
        telegram_link = f'<a href="{lead["telegram_link"]}" style="color:#229ED9;text-decoration:none;">✈️ Telegram</a>'

    website_link = ""
    if lead.get("website"):
        website_link = f'<a href="{lead["website"]}" style="color:#6366F1;text-decoration:none;">🌐 Website</a>'

    links_row = " &nbsp;|&nbsp; ".join(filter(None, [website_link, twitter_link, discord_link, telegram_link]))

    # Contacts
    contacts_html = ""
    contact_parts = []
    if lead.get("contact_twitter"):
        for handle in lead["contact_twitter"].split(","):
            handle = handle.strip().lstrip("@")
            if handle:
                contact_parts.append(f'<a href="https://twitter.com/{handle}" style="color:#1DA1F2;text-decoration:none;">@{handle}</a>')
    if lead.get("contact_linkedin"):
        for url in lead["contact_linkedin"].split(","):
            url = url.strip()
            if url:
                contact_parts.append(f'<a href="{url}" style="color:#0A66C2;text-decoration:none;">LinkedIn</a>')
    if lead.get("contact_email"):
        contact_parts.append(f'<a href="mailto:{lead["contact_email"]}" style="color:#6B7280;">{lead["contact_email"]}</a>')
    if lead.get("contact_analytics"):
        contact_parts.append(f'<span style="color:#374151;">📊 {lead["contact_analytics"]}</span>')

    if contact_parts:
        contacts_html = f"""
        <tr>
            <td style="padding:6px 0 0 0;">
                <span style="font-weight:600;color:#111827;">📇 Contacts:</span><br/>
                {"<br/>".join(f"• {c}" for c in contact_parts)}
            </td>
        </tr>"""

    funding_text = ""
    if lead.get("funding_amount") or lead.get("funding_stage"):
        parts = []
        if lead.get("funding_amount"):
            parts.append(lead["funding_amount"])
        if lead.get("funding_stage"):
            parts.append(lead["funding_stage"])
        if lead.get("funding_date"):
            parts.append(f"— {lead['funding_date']}")
        if lead.get("funding_investors"):
            parts.append(f"({lead['funding_investors']})")
        funding_text = " ".join(parts)

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="
        background:#ffffff;
        border:1px solid #E5E7EB;
        border-left:4px solid {score_color};
        border-radius:8px;
        margin-bottom:20px;
        padding:0;
    ">
      <tr>
        <td style="padding:16px 20px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <!-- Header row: name + score -->
            <tr>
              <td style="vertical-align:middle;">
                <span style="font-size:17px;font-weight:700;color:#0D1117;">
                  {lead.get("project_name","Unknown")}
                </span>
                &nbsp;
                <span style="font-size:12px;color:#6B7280;">
                  via {lead.get("source","—")}
                </span>
              </td>
              <td align="right" style="vertical-align:middle;">
                <span style="
                  background:{score_color};
                  color:white;
                  font-weight:700;
                  font-size:13px;
                  padding:3px 10px;
                  border-radius:20px;
                ">🎯 {score}/100</span>
              </td>
            </tr>
            <!-- Description -->
            <tr>
              <td colspan="2" style="padding:6px 0 4px 0;color:#374151;font-size:13px;">
                📝 {lead.get("description","—")}
              </td>
            </tr>
            <!-- Links -->
            <tr>
              <td colspan="2" style="padding:4px 0;font-size:13px;">
                🔗 <strong>Links</strong>&nbsp; {links_row if links_row else "—"}
              </td>
            </tr>
            <!-- Meta fields -->
            <tr>
              <td colspan="2" style="padding:8px 0 0 0;font-size:13px;line-height:1.8;">
                {"<span>⛓ <strong>Chain:</strong> " + lead.get("chains","—") + "</span><br/>" if lead.get("chains") else ""}
                {"<span>🪙 <strong>Token:</strong> " + lead.get("token_ticker","—") + "</span><br/>" if lead.get("token_ticker") else ""}
                {"<span>👥 <strong>Team Size:</strong> " + str(lead.get("team_size","—")) + "</span><br/>" if lead.get("team_size") else ""}
                {"<span>💰 <strong>Funding:</strong> " + funding_text + "</span><br/>" if funding_text else ""}
                {"<span>📰 <strong>Recent News:</strong> " + lead.get("recent_news","—") + "</span><br/>" if lead.get("recent_news") else ""}
              </td>
            </tr>
            <!-- Flags -->
            <tr>
              <td colspan="2" style="padding:8px 0 0 0;font-size:13px;line-height:1.9;">
                <span>📊 <strong>Dune Presence:</strong> {lead.get("dune_presence_flag","🔴 None")}</span><br/>
                <span>💓 <strong>Liveness:</strong> {lead.get("liveness_flag","🟢 Active")}</span>
              </td>
            </tr>
            <!-- Pitch angle -->
            {"<tr><td colspan='2' style='padding:10px 0 0 0;'><div style='background:#F0FDF4;border-left:3px solid #16A34A;padding:8px 12px;border-radius:4px;font-size:13px;color:#166534;'><strong>🚀 Pitch Angle:</strong> " + lead.get("pitch_angle","—") + "</div></td></tr>" if lead.get("pitch_angle") else ""}
            <!-- Contacts -->
            {contacts_html}
            <!-- Action buttons -->
            <tr>
              <td colspan="2" style="padding:12px 0 0 0;">
                <span style="font-size:11px;color:#9CA3AF;">Mark this lead:</span>&nbsp;
                <a href="mailto:{os.getenv('GMAIL_ADDRESS','')}?subject=LEAD_ACTION&body=lead_id={lead.get('id','')}&action=pitched"
                   style="background:#6366F1;color:white;padding:4px 10px;border-radius:4px;text-decoration:none;font-size:11px;margin-right:4px;">
                   ✅ Pitched
                </a>
                <a href="mailto:{os.getenv('GMAIL_ADDRESS','')}?subject=LEAD_ACTION&body=lead_id={lead.get('id','')}&action=interested"
                   style="background:#16A34A;color:white;padding:4px 10px;border-radius:4px;text-decoration:none;font-size:11px;margin-right:4px;">
                   👍 Interested
                </a>
                <a href="mailto:{os.getenv('GMAIL_ADDRESS','')}?subject=LEAD_ACTION&body=lead_id={lead.get('id','')}&action=not_interested"
                   style="background:#DC2626;color:white;padding:4px 10px;border-radius:4px;text-decoration:none;font-size:11px;">
                   👎 Not Interested
                </a>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    """


def build_digest_html(leads: list) -> str:
    today = datetime.utcnow().strftime("%A, %d %B %Y")
    cards_html = "\n".join(_lead_card_html(lead) for lead in leads)

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
</head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#F3F4F6;padding:30px 0;">
    <tr>
      <td align="center">
        <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;">

          <!-- HEADER -->
          <tr>
            <td style="background:#0D1117;border-radius:10px 10px 0 0;padding:28px 30px;">
              <table width="100%">
                <tr>
                  <td>
                    <div style="font-size:22px;font-weight:700;color:#ffffff;">
                      🔍 Web3 Lead Gen Digest
                    </div>
                    <div style="font-size:13px;color:#9CA3AF;margin-top:4px;">
                      {today} &nbsp;·&nbsp; {len(leads)} leads delivered
                    </div>
                  </td>
                  <td align="right">
                    <div style="background:#7C3AED;color:white;padding:6px 14px;border-radius:20px;font-size:12px;font-weight:600;">
                      Dune Analyst Edition
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- STATS BAR -->
          <tr>
            <td style="background:#1F2937;padding:12px 30px;">
              <table width="100%">
                <tr>
                  <td style="color:#D1D5DB;font-size:12px;">
                    📊 Sorted by Lead Score (highest first)
                    &nbsp;·&nbsp;
                    🔴 = High priority (no Dune presence)
                    &nbsp;·&nbsp;
                    Reply to mark leads as acted on
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- LEAD CARDS -->
          <tr>
            <td style="background:#F9FAFB;padding:24px 20px;">
              {cards_html}
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background:#0D1117;border-radius:0 0 10px 10px;padding:20px 30px;">
              <table width="100%">
                <tr>
                  <td style="color:#6B7280;font-size:11px;">
                    Web3 Lead Gen Bot &nbsp;·&nbsp; Powered by Gemini AI &nbsp;·&nbsp;
                    Next digest tomorrow at 6:00 AM UTC<br/>
                    To manage leads, message your Telegram bot.
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def send_digest_email(leads: list) -> bool:
    """Send the HTML digest email. Returns True on success."""
    gmail_address = os.getenv("GMAIL_ADDRESS")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    digest_email = os.getenv("DIGEST_EMAIL", gmail_address)

    if not gmail_address or not gmail_password:
        logger.error("Gmail credentials not set in environment variables")
        return False

    if not leads:
        logger.warning("No leads to send — skipping email digest")
        return False

    today = datetime.utcnow().strftime("%d %b %Y")
    subject = f"🔍 Web3 Lead Digest — {len(leads)} leads — {today}"

    html_body = build_digest_html(leads)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = digest_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_address, gmail_password)
            server.sendmail(gmail_address, digest_email, msg.as_string())
        logger.info("✅ Digest email sent to %s (%d leads)", digest_email, len(leads))
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail authentication failed — check GMAIL_APP_PASSWORD in .env")
        return False
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False
