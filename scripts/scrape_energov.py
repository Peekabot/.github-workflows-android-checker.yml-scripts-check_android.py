"""
Energov / Tyler Self-Service permit portal scraper for Capital Region.

Albany portal is an Angular SPA — uses Playwright to navigate and extract
recent permit activity. High signal for upcoming construction/reno/trade work.
"""

import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from store import init_db, upsert_signal

CONFIG = json.loads((Path(__file__).parent.parent / "config.json").read_text())

PORTALS = [
    {
        "name": "Albany",
        "url": "https://albanyny-energovpub.tylerhost.net/Apps/SelfService#/search",
        "source": "energov-albany",
    },
]

PERMIT_KEYWORDS = [
    "building", "electrical", "plumbing", "mechanical", "renovation",
    "addition", "construction", "grading", "excavation", "site work",
    "occupancy", "demolition", "roofing", "hvac", "rop",
]


def score_permit(permit_type: str, description: str = "") -> int:
    text = (permit_type + " " + description).lower()
    score = 7
    for kw in PERMIT_KEYWORDS:
        if kw in text:
            score += 2
            break
    return min(score, 12)


def scrape_with_playwright(portal: dict) -> int:
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("  Playwright not installed — skipping Energov.", file=sys.stderr)
        return 0

    count = 0
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%m/%d/%Y")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(portal["url"], timeout=30000, wait_until="networkidle")
            page.wait_for_selector("input, select, [placeholder]", timeout=15000)

            # Fill date filter if present
            date_inputs = page.query_selector_all(
                "input[type='date'], input[placeholder*='date' i], input[placeholder*='Date' i]"
            )
            if date_inputs:
                date_inputs[0].fill(cutoff)
                page.keyboard.press("Tab")

            # Submit search
            for label in ["Search", "search", "Submit", "Find"]:
                btn = page.query_selector(f"button:has-text('{label}')")
                if btn:
                    btn.click()
                    page.wait_for_load_state("networkidle", timeout=15000)
                    break

            rows = page.query_selector_all("table tbody tr, .result-row, [class*='result']")

            if not rows:
                # Fallback: pull text blocks that look like permit entries
                text_content = page.inner_text("body")
                lines = [l.strip() for l in text_content.splitlines() if len(l.strip()) > 20]
                for line in lines[:50]:
                    if any(kw in line.lower() for kw in PERMIT_KEYWORDS):
                        signal_id = hashlib.md5(f"{portal['name']}-{line}".encode()).hexdigest()
                        upsert_signal(signal_id, portal["source"], "demand",
                                      f"Permit signal: {line[:80]}", line[:300],
                                      portal["url"], score_permit(line))
                        count += 1
            else:
                for row in rows[:50]:
                    text = row.inner_text().strip()
                    if not text or len(text) < 10:
                        continue
                    cells = row.query_selector_all("td")
                    permit_type = cells[0].inner_text().strip() if cells else text[:60]
                    address     = cells[1].inner_text().strip() if len(cells) > 1 else ""
                    title = f"{permit_type} — {address}" if address else permit_type
                    signal_id = hashlib.md5(f"{portal['name']}-{text}".encode()).hexdigest()
                    upsert_signal(signal_id, portal["source"], "demand",
                                  title, text[:300], portal["url"],
                                  score_permit(permit_type, text))
                    count += 1

        except PWTimeout:
            print(f"  Energov timeout on {portal['name']} — SPA may not have loaded.", file=sys.stderr)
        except Exception as e:
            print(f"  Energov error on {portal['name']}: {e}", file=sys.stderr)
        finally:
            browser.close()

    return count


def main():
    init_db()
    total = 0
    for portal in PORTALS:
        n = scrape_with_playwright(portal)
        print(f"  Energov {portal['name']}: {n} permit signals")
        total += n
    print(f"Energov total: {total} signals")


if __name__ == "__main__":
    main()
