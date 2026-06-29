"""
Orchestrates all scrapers then runs cross-reference and alerting.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import scrape_craigslist
import scrape_dos
import scrape_bids
import alert


def main():
    print("=== Capital Region OSINT Pipeline ===")

    print("\n[1/3] Craigslist (Albany)...")
    scrape_craigslist.main()

    print("\n[2/3] NYS DOS filings...")
    scrape_dos.main()

    print("\n[3/3] Bids & contracts...")
    scrape_bids.main()

    print("\n[Alerting]")
    alert.run_alerts()

    print("\nDone.")


if __name__ == "__main__":
    main()
