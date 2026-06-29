"""
Scrapes public bid opportunities from NYS Contract Reporter RSS
and Capital Region municipal bid pages.
"""

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from store import init_db, upsert_signal

CONFIG = json.loads((Path(__file__).parent.parent / "config.json").read_text())

NYSCR_RSS  = "https://www.nyscr.ny.gov/rss/nyscr.rss"

# (url, source_key, base_domain)
MUNICIPAL_BID_PAGES = [
    ("https://www.albanyny.gov/Bids.aspx",                        "albany-bids",      "https://www.albanyny.gov"),
    ("https://www.schenectadyny.gov/bids",                        "schenectady-bids", "https://www.schenectadyny.gov"),
    ("https://www.troyny.gov/city-government/bids-rfps/",         "troy-bids",        "https://www.troyny.gov"),
    ("https://www.saratogaspringscity.com/bids",                  "saratoga-bids",    "https://www.saratogaspringscity.com"),
    ("https://www.albanycounty.com/departments/purchasing/bids",  "albany-county-bids", "https://www.albanycounty.com"),
]

REGION_TERMS = ["albany", "schenectady", "troy", "rensselaer", "capital region", "colonie", "saratoga", "guilderland", "latham"]
HIGH_VALUE   = CONFIG["keywords"]["services"] + CONFIG["keywords"]["high_value"]
BID_MARKERS  = ["bid", "rfp", "rfq", "proposal", "solicitation", "quote", "contract"]


def score_bid(title: str, body: str = "") -> int:
    text = (title + " " + body).lower()
    score = 5
    for term in HIGH_VALUE:
        if term in text:
            score += 3
            break
    return score


def fetch_nyscr() -> int:
    try:
        resp = requests.get(NYSCR_RSS, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception as e:
        print(f"  NYSCR error: {e}", file=sys.stderr)
        return 0

    count = 0
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link")  or "").strip()
        desc  = (item.findtext("description") or "").strip()
        combined = (title + " " + desc).lower()

        if not any(t in combined for t in REGION_TERMS):
            continue

        signal_id = hashlib.md5(link.encode()).hexdigest()
        upsert_signal(signal_id, "nyscr-rss", "demand", title, desc[:500], link, score_bid(title, desc))
        count += 1

    return count


def fetch_municipal_bids(page_url: str, source_key: str, base_domain: str) -> int:
    try:
        resp = requests.get(page_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        print(f"  {source_key} error: {e}", file=sys.stderr)
        return 0

    soup = BeautifulSoup(resp.text, "lxml")
    count = 0

    for link in soup.find_all("a", href=True):
        title = link.get_text(strip=True)
        href  = link["href"]
        if not title or len(title) < 8:
            continue

        lowered = (title + " " + href).lower()
        if not any(k in lowered for k in BID_MARKERS):
            continue

        url = href if href.startswith("http") else f"{base_domain}{href}"
        signal_id = hashlib.md5(f"{source_key}-{url}".encode()).hexdigest()
        upsert_signal(signal_id, source_key, "demand", title, "", url, score_bid(title))
        count += 1

    return count


def main():
    init_db()
    print(f"  NYSCR (Capital Region filter): {fetch_nyscr()} bids")
    for page_url, source_key, base_domain in MUNICIPAL_BID_PAGES:
        n = fetch_municipal_bids(page_url, source_key, base_domain)
        print(f"  {source_key}: {n} bids")


if __name__ == "__main__":
    main()
