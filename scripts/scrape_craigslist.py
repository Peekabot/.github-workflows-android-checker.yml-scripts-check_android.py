"""
Scrapes Albany Craigslist RSS feeds for demand signals (gigs) and talent signals (services).
"""

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from store import init_db, upsert_signal

CONFIG = json.loads((Path(__file__).parent.parent / "config.json").read_text())
REGION = CONFIG["region"]["craigslist_subdomain"]
KEYWORDS = CONFIG["keywords"]
BASE = f"https://{REGION}.craigslist.org"

# (path, category_type, label)
FEEDS = [
    ("/search/lbg?format=rss", "demand",  "labor-gigs"),
    ("/search/skg?format=rss", "demand",  "skilled-trades-gigs"),
    ("/search/cpg?format=rss", "demand",  "computer-gigs"),
    ("/search/hss?format=rss", "supply",  "household-services"),
    ("/search/sss?format=rss", "supply",  "skilled-trades-services"),
]


def score_text(text: str, category_type: str) -> int:
    text = text.lower()
    score = 1
    if category_type == "demand":
        for kw in KEYWORDS["services"]:
            if kw in text:
                score += 2
                break
        for kw in KEYWORDS["high_value"]:
            if kw in text:
                score += 3
                break
    else:
        for kw in KEYWORDS["services"]:
            if kw in text:
                score += 1
                break
    return score


def fetch_feed(path: str, category_type: str, label: str) -> int:
    url = BASE + path
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        print(f"  Error fetching {url}: {e}", file=sys.stderr)
        return 0

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        print(f"  XML parse error for {url}: {e}", file=sys.stderr)
        return 0

    count = 0
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link")  or "").strip()
        desc  = (item.findtext("description") or "").strip()

        signal_id = hashlib.md5(link.encode()).hexdigest()
        score = score_text(f"{title} {desc}", category_type)
        upsert_signal(signal_id, f"craigslist-{label}", category_type, title, desc[:500], link, score)
        count += 1

    return count


def main():
    init_db()
    total = 0
    for path, category_type, label in FEEDS:
        n = fetch_feed(path, category_type, label)
        print(f"  craigslist/{label}: {n}")
        total += n
    print(f"Craigslist total: {total} signals")


if __name__ == "__main__":
    main()
