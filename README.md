# Web3 Lead Gen Bot 🔍

A fully automated Telegram bot that discovers, enriches, scores and delivers
high-quality Web3 project leads to a Dune Analytics dashboard analyst.

---

## Features

- Scrapes 15+ Web3 sources (DeFiLlama, CoinGecko, DEXScreener, GitHub, RSS news, hackathons, ecosystems & more)
- Enriches every lead with AI (Google Gemini 1.5 Flash) — fills missing fields, checks Dune presence, generates tailored pitch angles
- Scores and ranks leads 0–100 based on Dune presence, on-chain activity, funding recency, team size and project age
- Delivers leads on demand via Telegram bot commands
- Sends a daily HTML email digest at 6:00 AM UTC
- Re-scrapes all sources every 24 hours automatically
- SQLite storage — leads persist and re-appear until you act on them

---

## Setup Instructions

### Step 1 — Prerequisites

Make sure you have Python 3.10+ installed:
```bash
python --version
```

### Step 2 — Clone / download the project

Place all files in a folder called `web3_lead_bot/`

### Step 3 — Install dependencies

```bash
cd web3_lead_bot
pip install -r requirements.txt
playwright install chromium
```

### Step 4 — Create your .env file

```bash
cp .env.example .env
```

Then open `.env` and fill in all values:

```
TELEGRAM_BOT_TOKEN=     # From @BotFather on Telegram
TELEGRAM_OWNER_ID=      # Your Telegram user ID (message @userinfobot)
GEMINI_API_KEY=          # From aistudio.google.com
GMAIL_ADDRESS=larryojah11@gmail.com
GMAIL_APP_PASSWORD=      # See Gmail App Password setup below
GITHUB_TOKEN=            # Optional — from github.com/settings/tokens
DIGEST_EMAIL=larryojah11@gmail.com
```

### Step 5 — Gmail App Password Setup

1. Go to your Google Account → Security
2. Enable 2-Step Verification (required)
3. Go to Security → App Passwords
4. Select app: "Mail", device: "Other (custom name)" → type "Web3 Bot"
5. Click Generate — copy the 16-character password
6. Paste it as GMAIL_APP_PASSWORD in your .env file

### Step 6 — Get your Telegram Bot Token

1. Open Telegram → search @BotFather
2. Send /newbot
3. Name: `Web3 Lead Scout`
4. Username: `web3leadscout_bot` (must be unique)
5. Copy the token → paste as TELEGRAM_BOT_TOKEN in .env

### Step 7 — Get your Telegram Owner ID

1. Open Telegram → search @userinfobot
2. Send /start
3. Copy your ID number → paste as TELEGRAM_OWNER_ID in .env

### Step 8 — Run the bot locally

```bash
python bot.py
```

The bot will:
- Initialise the database
- Start the scheduler
- Run an initial scrape after 10 seconds (first launch only)
- Begin polling for Telegram messages

---

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message and command list |
| `/leads` | Get top 10 leads right now |
| `/top` | Get top 5 highest scored leads |
| `/filter defi` | Filter leads by category (defi, nft, dao, base, solana, etc.) |
| `/refresh` | Trigger a fresh scrape of all sources immediately |
| `/status` | Show last scrape time and total leads in database |
| `/pitch ProjectName` | Get AI pitch angle for a specific project |

---

## Deploy on Render.com (Free Hosting — Bot Runs 24/7)

### Step 1 — Push to GitHub

1. Create a new private GitHub repo
2. Push all files (DO NOT push your .env file — it's in .gitignore)

### Step 2 — Create a Render Web Service

1. Go to render.com → New → Web Service
2. Connect your GitHub repo
3. Settings:
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt && playwright install chromium`
   - **Start Command:** `python bot.py`
   - **Instance Type:** Free

### Step 3 — Add Environment Variables on Render

In your Render service → Environment tab, add all variables from your .env file:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_OWNER_ID
- GEMINI_API_KEY
- GMAIL_ADDRESS
- GMAIL_APP_PASSWORD
- GITHUB_TOKEN
- DIGEST_EMAIL

### Step 4 — Deploy

Click Deploy. Render will build and launch your bot.

> ⚠️ Note: Free Render instances sleep after 15 minutes of inactivity.
> To keep the bot alive 24/7, consider upgrading to Render's $7/month Starter plan,
> or use Railway.app (free $5/month credit) as an alternative.

---

## File Structure

```
web3_lead_bot/
├── bot.py              # Telegram bot — all commands and handlers
├── scraper.py          # All scraping logic (15+ sources)
├── enricher.py         # Gemini AI enrichment + pitch generation
├── scorer.py           # Lead scoring logic (0-100)
├── database.py         # SQLite setup and all DB queries
├── scheduler.py        # APScheduler — daily digest + 24h rescrape
├── email_sender.py     # Gmail SMTP HTML digest builder and sender
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
├── .gitignore          # Prevents secrets being committed
└── README.md           # This file
```

---

## Lead Scoring

| Signal | Condition | Points |
|--------|-----------|--------|
| Dune Presence | None | 40 |
| | Minimal (1-2 dashboards) | 25 |
| | Decent (several, gaps) | 10 |
| | Well-covered | 0 |
| On-chain Activity | High | 20 |
| | Medium | 10 |
| | Low | 5 |
| Funding Recency | Last 3 months | 20 |
| | Last 6 months | 10 |
| | Older | 5 |
| Team Size | Under 10 | 10 |
| | 10-30 | 5 |
| | 30+ | 0 |
| Project Age | Under 6 months | 10 |
| | Under 1 year | 5 |
| | Older | 0 |

---

## Troubleshooting

**Bot not responding:** Check TELEGRAM_BOT_TOKEN is correct in .env

**Email not sending:** 
- Make sure you're using an App Password (not your Gmail password)
- Make sure 2FA is enabled on your Google account

**Gemini errors:**
- Check your GEMINI_API_KEY is valid at aistudio.google.com
- Free tier allows 15 requests/minute — the enricher adds delays automatically

**Scraper returning 0 leads:**
- Some sites may be temporarily down
- Run /status to see last scrape logs
- Try /refresh to trigger a new scrape

---

## Support

Built for Dune Analytics dashboard analysts to automate their lead generation workflow.
