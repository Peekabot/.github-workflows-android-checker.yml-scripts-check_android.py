"""
Monitors NYS DOS via data.ny.gov Socrata API for new business filings
in Capital Region counties. New filings = market entry signals.
"""

import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from store import init_db, upsert_signal

CONFIG = json.loads((Path(__file__).parent.parent / "config.json").read_text())
COUNTIES = CONFIG["region"]["counties"]

SOCRATA_URL = "https://data.ny.gov/resource/ej5i-dqe8.json"

SERVICE_TERMS = [
    "service", "solution", "group", "contracting", "management",
    "consulting", "care", "clean", "build", "construct", "repair",
    "food", "catering", "landscap", "paint", "electric", "plumb",
]


def fetch_recent_filings(days_back=7):
    cutoff = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00")
    county_filter = " OR ".join(f"county='{c.upper()}'" for c in COUNTIES)
    params = {
        "$where": f"({county_filter}) AND date_of_initial_dos_filing_date > '{cutoff}'",
        "$limit": 500,
        "$order": "date_of_initial_dos_filing_date DESC",
    }
    try:
        resp = requests.get(SOCRATA_URL, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  DOS API error: {e}", file=sys.stderr)
        return []


def score_filing(entity: dict) -> int:
    name = (entity.get("current_entity_name") or "").lower()
    score = 2
    for term in SERVICE_TERMS:
        if term in name:
            score += 2
            break
    return score


def main():
    init_db()
    filings = fetch_recent_filings()
    print(f"  DOS filings fetched: {len(filings)}")

    count = 0
    for entity in filings:
        dos_id = entity.get("dos_id", "")
        if not dos_id:
            continue

        name   = entity.get("current_entity_name", "Unknown")
        county = entity.get("county", "")
        filed  = entity.get("date_of_initial_dos_filing_date", "")

        signal_id = hashlib.md5(f"dos-{dos_id}".encode()).hexdigest()
        title = f"New filing: {name} ({county} County)"
        body  = f"Type: {entity.get('entity_type', 'N/A')} | Filed: {filed[:10] if filed else 'N/A'}"
        url   = f"https://apps.dos.ny.gov/publicInquiry/EntityDisplay?entityId={dos_id}"

        upsert_signal(signal_id, "dos-filings", "demand", title, body, url, score_filing(entity))
        count += 1

    print(f"  DOS: {count} filings ingested")


if __name__ == "__main__":
    main()
