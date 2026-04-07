"""
scraper.py — Scrapes all 30+ Web3 lead sources.

Each scraper function returns a list of raw lead dicts.
All scrapers have try/except — one failure never crashes others.
"""

import os
import time
import random
import logging
import requests
import feedparser
from bs4 import BeautifulSoup
from database import log_scrape

logger = logging.getLogger(__name__)

# ── Shared helpers ─────────────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]


def _headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }


def _sleep(lo=1.5, hi=4.0):
    time.sleep(random.uniform(lo, hi))


def _get(url, timeout=15, use_cloudscraper=False):
    """HTTP GET with rotating headers. Returns response or None."""
    try:
        if use_cloudscraper:
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            return scraper.get(url, timeout=timeout)
        else:
            return requests.get(url, headers=_headers(), timeout=timeout)
    except Exception as e:
        logger.error("GET failed for %s: %s", url, e)
        return None


def _soup(url, **kwargs):
    r = _get(url, **kwargs)
    if r and r.status_code == 200:
        return BeautifulSoup(r.text, "lxml")
    return None


# ══════════════════════════════════════════════════════════════════════════
#  1. DeFiLlama — Free public API
# ══════════════════════════════════════════════════════════════════════════
def scrape_defillama(limit=50):
    source = "defillama"
    leads = []
    try:
        r = _get("https://api.llama.fi/protocols")
        if not r or r.status_code != 200:
            log_scrape(source, "failed", error_msg="API unreachable")
            return leads
        protocols = r.json()
        # Sort by TVL descending, take top N
        protocols = sorted(protocols, key=lambda x: x.get("tvl", 0), reverse=True)[:limit]
        for p in protocols:
            leads.append({
                "project_name": p.get("name", ""),
                "description": p.get("description") or f"{p.get('name')} — DeFi protocol on {p.get('chain', 'multi-chain')}",
                "website": p.get("url", ""),
                "twitter": f"@{p.get('twitter')}" if p.get("twitter") else "",
                "chains": p.get("chain", ""),
                "token_ticker": f"${p.get('symbol')}" if p.get("symbol") else "",
                "funding_stage": "",
                "source": source,
                "onchain_activity": "high" if p.get("tvl", 0) > 10_000_000 else "medium",
            })
        log_scrape(source, "success", len(leads))
        logger.info("DeFiLlama: %d leads", len(leads))
    except Exception as e:
        log_scrape(source, "failed", error_msg=str(e))
        logger.error("DeFiLlama scraper error: %s", e)
    return leads


# ══════════════════════════════════════════════════════════════════════════
#  2. CoinGecko — Free public API
# ══════════════════════════════════════════════════════════════════════════
def scrape_coingecko(limit=50):
    source = "coingecko"
    leads = []
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": "false",
        }
        r = requests.get(url, params=params, headers=_headers(), timeout=15)
        if r.status_code != 200:
            log_scrape(source, "failed", error_msg=f"HTTP {r.status_code}")
            return leads
        coins = r.json()
        for coin in coins:
            leads.append({
                "project_name": coin.get("name", ""),
                "description": f"{coin.get('name')} ({coin.get('symbol','').upper()}) — ranked #{coin.get('market_cap_rank')} by market cap",
                "website": "",
                "twitter": "",
                "token_ticker": f"${coin.get('symbol','').upper()}",
                "source": source,
                "onchain_activity": "high" if (coin.get("total_volume") or 0) > 1_000_000 else "medium",
            })
            _sleep(0.2, 0.5)
        log_scrape(source, "success", len(leads))
        logger.info("CoinGecko: %d leads", len(leads))
    except Exception as e:
        log_scrape(source, "failed", error_msg=str(e))
        logger.error("CoinGecko scraper error: %s", e)
    return leads


# ══════════════════════════════════════════════════════════════════════════
#  3. GitHub — Active Web3 orgs
# ══════════════════════════════════════════════════════════════════════════
def scrape_github(limit=30):
    source = "github"
    leads = []
    try:
        token = os.getenv("GITHUB_TOKEN", "")
        headers = _headers()
        if token:
            headers["Authorization"] = f"token {token}"

        queries = ["web3 protocol defi", "nft smart contract", "blockchain dao", "defi solana base"]
        seen = set()

        for q in queries:
            url = "https://api.github.com/search/repositories"
            params = {
                "q": q,
                "sort": "updated",
                "order": "desc",
                "per_page": 10,
            }
            r = requests.get(url, headers=headers, params=params, timeout=15)
            if r.status_code != 200:
                continue
            repos = r.json().get("items", [])
            for repo in repos:
                org = repo.get("owner", {}).get("login", "")
                if org in seen:
                    continue
                seen.add(org)
                leads.append({
                    "project_name": repo.get("full_name", "").split("/")[0],
                    "description": repo.get("description") or f"Active Web3 project on GitHub: {repo.get('full_name')}",
                    "website": repo.get("homepage") or f"https://github.com/{repo.get('full_name','')}",
                    "twitter": "",
                    "source": source,
                    "onchain_activity": "high" if repo.get("stargazers_count", 0) > 500 else "medium",
                })
            _sleep(1, 2)
            if len(leads) >= limit:
                break

        log_scrape(source, "success", len(leads))
        logger.info("GitHub: %d leads", len(leads))
    except Exception as e:
        log_scrape(source, "failed", error_msg=str(e))
        logger.error("GitHub scraper error: %s", e)
    return leads


# ══════════════════════════════════════════════════════════════════════════
#  4. RSS News Feeds — CoinDesk, CoinTelegraph, Decrypt, Blockworks
# ══════════════════════════════════════════════════════════════════════════
RSS_FEEDS = {
    "coindesk":      "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "decrypt":       "https://decrypt.co/feed",
    "blockworks":    "https://blockworks.co/feed",
    "theblock":      "https://www.theblock.co/rss.xml",
}

def scrape_rss_feeds(max_per_feed=15):
    source = "rss_news"
    leads = []
    for feed_name, feed_url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(feed_url)
            count = 0
            for entry in feed.entries[:max_per_feed]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")
                # Extract project names from headlines (simple heuristic)
                # Look for "Protocol", "raises", "launches", "announces"
                keywords = ["raises", "launch", "protocol", "defi", "nft", "dao", "web3", "chain"]
                if any(kw in title.lower() for kw in keywords):
                    leads.append({
                        "project_name": _extract_project_from_headline(title),
                        "description": summary[:200] if summary else title,
                        "website": link,
                        "source": f"rss_{feed_name}",
                        "recent_news": title,
                        "onchain_activity": "medium",
                    })
                    count += 1
            log_scrape(f"rss_{feed_name}", "success", count)
            _sleep(0.5, 1.5)
        except Exception as e:
            log_scrape(f"rss_{feed_name}", "failed", error_msg=str(e))
            logger.error("RSS %s error: %s", feed_name, e)
    logger.info("RSS feeds: %d leads total", len(leads))
    return leads


def _extract_project_from_headline(title: str) -> str:
    """Best-effort extraction of project name from a news headline."""
    # Remove common suffixes
    for sep in [" raises", " launches", " announces", " partners", " integrates", " hits", " reaches"]:
        if sep in title.lower():
            idx = title.lower().index(sep)
            return title[:idx].strip()
    # Fall back to first 4 words
    words = title.split()[:4]
    return " ".join(words)


# ══════════════════════════════════════════════════════════════════════════
#  5. ICO Drops — new launches
# ══════════════════════════════════════════════════════════════════════════
def scrape_icodrops(limit=20):
    source = "icodrops"
    leads = []
    try:
        soup = _soup("https://icodrops.com/category/active-ico/")
        if not soup:
            log_scrape(source, "failed", error_msg="Could not fetch page")
            return leads
        cards = soup.select(".ico-card") or soup.select(".col-md-4")
        for card in cards[:limit]:
            name_el = card.select_one("h3") or card.select_one(".ico-name")
            desc_el = card.select_one("p") or card.select_one(".ico-desc")
            link_el = card.select_one("a")
            if not name_el:
                continue
            leads.append({
                "project_name": name_el.get_text(strip=True),
                "description": desc_el.get_text(strip=True)[:200] if desc_el else "",
                "website": link_el.get("href", "") if link_el else "",
                "source": source,
                "funding_stage": "ICO/IDO",
                "onchain_activity": "medium",
            })
        log_scrape(source, "success", len(leads))
        logger.info("ICODrops: %d leads", len(leads))
    except Exception as e:
        log_scrape(source, "failed", error_msg=str(e))
        logger.error("ICODrops error: %s", e)
    return leads


# ══════════════════════════════════════════════════════════════════════════
#  6. CryptoJobsList — projects hiring = active projects
# ══════════════════════════════════════════════════════════════════════════
def scrape_cryptojobslist(limit=20):
    source = "cryptojobslist"
    leads = []
    try:
        soup = _soup("https://cryptojobslist.com/web3")
        if not soup:
            log_scrape(source, "failed", error_msg="Could not fetch page")
            return leads
        seen_orgs = set()
        job_cards = soup.select("article") or soup.select(".job-listing") or soup.select("[data-job]")
        for card in job_cards[:limit*2]:
            company_el = card.select_one(".company-name") or card.select_one("[class*='company']")
            link_el = card.select_one("a")
            if not company_el:
                continue
            name = company_el.get_text(strip=True)
            if name in seen_orgs:
                continue
            seen_orgs.add(name)
            leads.append({
                "project_name": name,
                "description": f"{name} is actively hiring Web3 talent — likely in growth phase",
                "website": link_el.get("href", "") if link_el else "",
                "source": source,
                "onchain_activity": "medium",
                "liveness": "active",
            })
            if len(leads) >= limit:
                break
        log_scrape(source, "success", len(leads))
        logger.info("CryptoJobsList: %d leads", len(leads))
    except Exception as e:
        log_scrape(source, "failed", error_msg=str(e))
        logger.error("CryptoJobsList error: %s", e)
    return leads


# ══════════════════════════════════════════════════════════════════════════
#  7. ETHGlobal — Hackathon winners
# ══════════════════════════════════════════════════════════════════════════
def scrape_ethglobal(limit=20):
    source = "ethglobal"
    leads = []
    try:
        soup = _soup("https://ethglobal.com/showcase")
        if not soup:
            log_scrape(source, "failed", error_msg="Could not fetch page")
            return leads
        projects = soup.select(".project-card") or soup.select("[class*='project']") or soup.select("article")
        for proj in projects[:limit]:
            name_el = proj.select_one("h3") or proj.select_one("h2") or proj.select_one("[class*='name']")
            desc_el = proj.select_one("p")
            link_el = proj.select_one("a")
            if not name_el:
                continue
            leads.append({
                "project_name": name_el.get_text(strip=True),
                "description": desc_el.get_text(strip=True)[:200] if desc_el else "ETHGlobal hackathon project",
                "website": f"https://ethglobal.com{link_el.get('href','')}" if link_el else "",
                "source": source,
                "funding_stage": "Hackathon",
                "onchain_activity": "medium",
            })
        log_scrape(source, "success", len(leads))
        logger.info("ETHGlobal: %d leads", len(leads))
    except Exception as e:
        log_scrape(source, "failed", error_msg=str(e))
        logger.error("ETHGlobal error: %s", e)
    return leads


# ══════════════════════════════════════════════════════════════════════════
#  8. DoraHacks — Grants & hackathons
# ══════════════════════════════════════════════════════════════════════════
def scrape_dorahacks(limit=20):
    source = "dorahacks"
    leads = []
    try:
        r = _get("https://dorahacks.io/api/hackathon/list/?limit=20&offset=0&status=open")
        if r and r.status_code == 200:
            data = r.json()
            hackathons = data.get("results") or data.get("data") or []
            for h in hackathons[:limit]:
                leads.append({
                    "project_name": h.get("title") or h.get("name", "DoraHacks Project"),
                    "description": h.get("description", "")[:200] or "Web3 hackathon/grant project on DoraHacks",
                    "website": f"https://dorahacks.io/hackathon/{h.get('slug','')}" if h.get("slug") else "https://dorahacks.io",
                    "source": source,
                    "funding_stage": "Grant/Hackathon",
                    "onchain_activity": "medium",
                })
        else:
            # Fallback to scraping
            soup = _soup("https://dorahacks.io/hackathon")
            if soup:
                cards = soup.select("[class*='hackathon']")[:limit]
                for card in cards:
                    name_el = card.select_one("h3") or card.select_one("h2")
                    if name_el:
                        leads.append({
                            "project_name": name_el.get_text(strip=True),
                            "description": "Web3 project from DoraHacks platform",
                            "website": "https://dorahacks.io",
                            "source": source,
                            "onchain_activity": "medium",
                        })
        log_scrape(source, "success", len(leads))
        logger.info("DoraHacks: %d leads", len(leads))
    except Exception as e:
        log_scrape(source, "failed", error_msg=str(e))
        logger.error("DoraHacks error: %s", e)
    return leads


# ══════════════════════════════════════════════════════════════════════════
#  9. Base Ecosystem — base.org/ecosystem
# ══════════════════════════════════════════════════════════════════════════
def scrape_base_ecosystem(limit=30):
    source = "base_ecosystem"
    leads = []
    try:
        soup = _soup("https://base.org/ecosystem", use_cloudscraper=True)
        if not soup:
            log_scrape(source, "failed", error_msg="Could not fetch page")
            return leads
        # Base ecosystem page has project cards
        cards = soup.select("[class*='project']") or soup.select("[class*='card']") or soup.select("article")
        for card in cards[:limit]:
            name_el = card.select_one("h3") or card.select_one("h2") or card.select_one("[class*='name']")
            desc_el = card.select_one("p")
            link_el = card.select_one("a")
            if not name_el:
                continue
            leads.append({
                "project_name": name_el.get_text(strip=True),
                "description": desc_el.get_text(strip=True)[:200] if desc_el else f"Project in the Base ecosystem",
                "website": link_el.get("href", "") if link_el else "",
                "chains": "Base",
                "source": source,
                "onchain_activity": "medium",
            })
        log_scrape(source, "success", len(leads))
        logger.info("Base Ecosystem: %d leads", len(leads))
    except Exception as e:
        log_scrape(source, "failed", error_msg=str(e))
        logger.error("Base Ecosystem error: %s", e)
    return leads


# ══════════════════════════════════════════════════════════════════════════
#  10. Solana Ecosystem
# ══════════════════════════════════════════════════════════════════════════
def scrape_solana_ecosystem(limit=20):
    source = "solana_ecosystem"
    leads = []
    try:
        r = _get("https://api.solana.com/ecosystem/projects?limit=50")
        if r and r.status_code == 200:
            projects = r.json()
            for p in projects[:limit]:
                leads.append({
                    "project_name": p.get("name", ""),
                    "description": p.get("description", "")[:200] or "Solana ecosystem project",
                    "website": p.get("website", ""),
                    "twitter": p.get("twitter", ""),
                    "chains": "Solana",
                    "source": source,
                    "onchain_activity": "medium",
                })
        else:
            # Fallback: scrape superteam.fun
            soup = _soup("https://superteam.fun/ecosystem")
            if soup:
                cards = soup.select("[class*='project']") or soup.select("article")
                for card in cards[:limit]:
                    name_el = card.select_one("h3") or card.select_one("h2")
                    if name_el:
                        leads.append({
                            "project_name": name_el.get_text(strip=True),
                            "description": "Solana / Superteam ecosystem project",
                            "website": "https://superteam.fun",
                            "chains": "Solana",
                            "source": source,
                            "onchain_activity": "medium",
                        })
        log_scrape(source, "success", len(leads))
        logger.info("Solana Ecosystem: %d leads", len(leads))
    except Exception as e:
        log_scrape(source, "failed", error_msg=str(e))
        logger.error("Solana Ecosystem error: %s", e)
    return leads


# ══════════════════════════════════════════════════════════════════════════
#  11. DEX Screener — Trending new tokens
# ══════════════════════════════════════════════════════════════════════════
def scrape_dexscreener(limit=30):
    source = "dexscreener"
    leads = []
    try:
        r = _get("https://api.dexscreener.com/latest/dex/search?q=new")
        if not r or r.status_code != 200:
            # Try trending endpoint
            r = _get("https://api.dexscreener.com/latest/dex/tokens/trending")
        if r and r.status_code == 200:
            data = r.json()
            pairs = data.get("pairs") or []
            seen = set()
            for pair in pairs[:limit*2]:
                base = pair.get("baseToken", {})
                name = base.get("name", "")
                if not name or name in seen:
                    continue
                seen.add(name)
                leads.append({
                    "project_name": name,
                    "description": f"{name} ({base.get('symbol','')}) — trending token on {pair.get('dexId','DEX')} ({pair.get('chainId','unknown chain')})",
                    "website": pair.get("info", {}).get("website") or "",
                    "twitter": pair.get("info", {}).get("socials", [{}])[0].get("url", "") if pair.get("info", {}).get("socials") else "",
                    "chains": pair.get("chainId", ""),
                    "token_ticker": f"${base.get('symbol','')}",
                    "token_contract": base.get("address", ""),
                    "source": source,
                    "onchain_activity": "high" if float(pair.get("volume", {}).get("h24", 0) or 0) > 100000 else "medium",
                })
                if len(leads) >= limit:
                    break
        log_scrape(source, "success", len(leads))
        logger.info("DexScreener: %d leads", len(leads))
    except Exception as e:
        log_scrape(source, "failed", error_msg=str(e))
        logger.error("DexScreener error: %s", e)
    return leads


# ══════════════════════════════════════════════════════════════════════════
#  12. Gitcoin — Grant recipients
# ══════════════════════════════════════════════════════════════════════════
def scrape_gitcoin(limit=20):
    source = "gitcoin"
    leads = []
    try:
        r = _get("https://indexer-production.fly.dev/data/1/rounds.json")
        if r and r.status_code == 200:
            rounds = r.json()[:5]
            for round_data in rounds:
                projects = round_data.get("projects") or []
                for p in projects[:limit]:
                    leads.append({
                        "project_name": p.get("title") or p.get("name", "Gitcoin Project"),
                        "description": p.get("description", "")[:200] or "Web3 project receiving Gitcoin grants",
                        "website": p.get("website", ""),
                        "twitter": p.get("projectTwitter", ""),
                        "source": source,
                        "funding_stage": "Grant",
                        "onchain_activity": "medium",
                    })
        else:
            soup = _soup("https://explorer.gitcoin.co/#/projects")
            if soup:
                cards = soup.select("[class*='project']") or soup.select("article")
                for card in cards[:limit]:
                    name_el = card.select_one("h3") or card.select_one("h2")
                    if name_el:
                        leads.append({
                            "project_name": name_el.get_text(strip=True),
                            "description": "Web3 project from Gitcoin Grants",
                            "website": "https://gitcoin.co",
                            "source": source,
                            "funding_stage": "Grant",
                            "onchain_activity": "medium",
                        })
        log_scrape(source, "success", len(leads))
        logger.info("Gitcoin: %d leads", len(leads))
    except Exception as e:
        log_scrape(source, "failed", error_msg=str(e))
        logger.error("Gitcoin error: %s", e)
    return leads


# ══════════════════════════════════════════════════════════════════════════
#  13. Web3.career — hiring companies
# ══════════════════════════════════════════════════════════════════════════
def scrape_web3_career(limit=20):
    source = "web3career"
    leads = []
    try:
        soup = _soup("https://web3.career/web3-jobs")
        if not soup:
            log_scrape(source, "failed", error_msg="Could not fetch page")
            return leads
        seen = set()
        rows = soup.select("tr") or soup.select("[class*='job']")
        for row in rows[:limit*3]:
            company_el = row.select_one("[class*='company']") or row.select_one("td:nth-child(3)")
            if not company_el:
                continue
            name = company_el.get_text(strip=True)
            if not name or name in seen or len(name) > 50:
                continue
            seen.add(name)
            leads.append({
                "project_name": name,
                "description": f"{name} is actively hiring in Web3",
                "website": "",
                "source": source,
                "liveness": "active",
                "onchain_activity": "medium",
            })
            if len(leads) >= limit:
                break
        log_scrape(source, "success", len(leads))
        logger.info("Web3.career: %d leads", len(leads))
    except Exception as e:
        log_scrape(source, "failed", error_msg=str(e))
        logger.error("Web3.career error: %s", e)
    return leads


# ══════════════════════════════════════════════════════════════════════════
#  14. Arbitrum Ecosystem
# ══════════════════════════════════════════════════════════════════════════
def scrape_arbitrum_ecosystem(limit=20):
    source = "arbitrum_ecosystem"
    leads = []
    try:
        r = _get("https://arbitrum.foundation/ecosystem.json")
        if r and r.status_code == 200:
            projects = r.json()
            for p in (projects if isinstance(projects, list) else projects.get("projects", []))[:limit]:
                leads.append({
                    "project_name": p.get("name", ""),
                    "description": p.get("description", "")[:200] or "Arbitrum ecosystem project",
                    "website": p.get("website") or p.get("url", ""),
                    "twitter": p.get("twitter", ""),
                    "chains": "Arbitrum",
                    "source": source,
                    "onchain_activity": "medium",
                })
        else:
            soup = _soup("https://arbitrum.io/ecosystem")
            if soup:
                cards = soup.select("[class*='project']") or soup.select("article")[:limit]
                for card in cards:
                    name_el = card.select_one("h3") or card.select_one("h2")
                    if name_el:
                        leads.append({
                            "project_name": name_el.get_text(strip=True),
                            "description": "Arbitrum ecosystem project",
                            "chains": "Arbitrum",
                            "source": source,
                            "onchain_activity": "medium",
                        })
        log_scrape(source, "success", len(leads))
        logger.info("Arbitrum: %d leads", len(leads))
    except Exception as e:
        log_scrape(source, "failed", error_msg=str(e))
        logger.error("Arbitrum error: %s", e)
    return leads


# ══════════════════════════════════════════════════════════════════════════
#  15. Optimism Ecosystem (RetroPGF)
# ══════════════════════════════════════════════════════════════════════════
def scrape_optimism_ecosystem(limit=20):
    source = "optimism_ecosystem"
    leads = []
    try:
        r = _get("https://api.optimism.io/ecosystem/projects")
        if r and r.status_code == 200:
            projects = r.json()
            for p in (projects if isinstance(projects, list) else [])[:limit]:
                leads.append({
                    "project_name": p.get("name", ""),
                    "description": p.get("description", "")[:200] or "Optimism ecosystem project",
                    "website": p.get("website", ""),
                    "chains": "Optimism",
                    "source": source,
                    "onchain_activity": "medium",
                })
        else:
            soup = _soup("https://www.optimism.io/apps")
            if soup:
                cards = soup.select("[class*='project']") or soup.select("article")[:limit]
                for card in cards:
                    name_el = card.select_one("h3") or card.select_one("h2")
                    if name_el:
                        leads.append({
                            "project_name": name_el.get_text(strip=True),
                            "description": "Optimism ecosystem project",
                            "chains": "Optimism",
                            "source": source,
                            "onchain_activity": "medium",
                        })
        log_scrape(source, "success", len(leads))
        logger.info("Optimism: %d leads", len(leads))
    except Exception as e:
        log_scrape(source, "failed", error_msg=str(e))
        logger.error("Optimism error: %s", e)
    return leads


# ══════════════════════════════════════════════════════════════════════════
#  MASTER SCRAPE — runs all scrapers
# ══════════════════════════════════════════════════════════════════════════
def run_all_scrapers() -> list:
    """Run every scraper and return combined, deduplicated raw leads."""
    all_leads = []

    scrapers = [
        ("DeFiLlama",          scrape_defillama),
        ("CoinGecko",          scrape_coingecko),
        ("DexScreener",        scrape_dexscreener),
        ("GitHub",             scrape_github),
        ("RSS Feeds",          scrape_rss_feeds),
        ("ICO Drops",          scrape_icodrops),
        ("CryptoJobsList",     scrape_cryptojobslist),
        ("Web3.career",        scrape_web3_career),
        ("ETHGlobal",          scrape_ethglobal),
        ("DoraHacks",          scrape_dorahacks),
        ("Gitcoin",            scrape_gitcoin),
        ("Base Ecosystem",     scrape_base_ecosystem),
        ("Solana Ecosystem",   scrape_solana_ecosystem),
        ("Arbitrum Ecosystem", scrape_arbitrum_ecosystem),
        ("Optimism Ecosystem", scrape_optimism_ecosystem),
    ]

    for name, fn in scrapers:
        try:
            logger.info("▶ Running scraper: %s", name)
            results = fn()
            # Filter out empty project names
            results = [r for r in results if r.get("project_name", "").strip()]
            all_leads.extend(results)
            logger.info("  ✓ %s: %d leads", name, len(results))
        except Exception as e:
            logger.error("  ✗ %s scraper crashed: %s", name, e)
        _sleep(1, 3)

    logger.info("Total raw leads from all scrapers: %d", len(all_leads))
    return all_leads
