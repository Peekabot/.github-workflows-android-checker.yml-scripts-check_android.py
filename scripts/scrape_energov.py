"""
Energov / Tyler Self-Service permit portal signals for Capital Region.

Albany portal is Angular SPA - full table scrape needs browser automation (Selenium/Playwright).
For now: surfaces the portal as high-value demand signal + parses any static text.
Future: add Playwright job or local iOS/Pythonista agent for interactive search by address/zip.
"""

import hashlib
import json
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from store import init_db, upsert_signal

CONFIG = json.loads((Path(__file__).parent.parent / "config.json").read_text())

ENERGOV_ALBANY_SEARCH = "https://albanyny-energovpub.tylerhost.net/Apps/SelfService#/search"
ENERGOV_ALBANY_HOME = "https://albanyny-energovpub.tylerhost.net/Apps/SelfService#/home"

REGION_ZIPS = CONFIG["region"]["zip_codes"]

PERMIT_KEYWORDS = ["building", "electrical", "plumbing", "mechanical", "renovation", "addition", "construction", "grading", "excavation", "site work", "occupancy", "rop", "permit"]


def score_permit(text: str) -> int:
    t = text.lower()
    score = 7  # permits = strong upcoming work signal
    for kw in PERMIT_KEYWORDS:
        if kw in t:
            score += 2
            break
    if any(z in t for z in REGION_ZIPS):
        score += 1
    return min(score, 12)


def fetch_energov_portal() -> int:
    count = 0
    for url in [ENERGOV_ALBANY_HOME, ENERGOV_ALBANY_SEARCH]:
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (compatible; XtraHandsBot/1.0)"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            text = soup.get_text(separator=" ", strip=True)[:2000]

            if "permit" in text.lower() or "search" in text.lower() or "self service" in text.lower():
                title = f"Albany Energov Permit Portal - {url.split('#')[-1]}"
                desc = text[:400] + "... (SPA - use advanced search for Code Cases / ROPs by address or zip)"
                link = url
                signal_id = hashlib.md5(link.encode()).hexdigest()
                upsert_signal(signal_id, "energov-albany", "demand", title, desc, link, score_permit(text))
                count += 1
                print(f"  Captured portal signal from {url}")
        except Exception as e:
            print(f"  Energov fetch error for {url}: {e}", file=sys.stderr)
    return count


def main():
    init_db()
    print(f"  Energov Albany portal: {fetch_energov_portal()} signals (stub - SPA aware)")


if __name__ == "__main__":
    main()
