"""
setup_sheet.py — One-time script to scaffold the OpenPantry Google Sheet.

Run once:
    G_SHEET_CREDS='...' python setup_sheet.py

Creates (or rewrites) the "Starters" and "Herbs" tabs with headers and
sample seed rows for YST_001/YST_002 and ROS_001/ROS_002.
"""

import json, os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_NAME = "OpenPantry"

# ── Tab schemas ───────────────────────────────────────────────────────────────

STARTERS_HEADERS = [
    "ID", "Name", "Type", "Weight_g", "Last_Fed", "Health_pct",
    "Streak", "Rise_h", "Flavor_Notes", "Born",
]

STARTERS_SEED = [
    ["YST_001", "Bread Pitt",  "Sourdough",    500, "2026-03-17", 96, 17, 4.5, "Tangy, fruity",  "2026-03-01"],
    ["YST_002", "Doughvid 70", "Rye starter",  300, "2026-03-16", 78,  7, 6.0, "Earthy, sour",   "2026-03-10"],
    ["YST_003", "Brad Neuer",  "Discard jar",  200, "2026-03-17",100,  3, "",  "Pancakes waiting","2026-03-15"],
]

HERBS_HEADERS = [
    "ID", "Name", "Species", "Harvest_g_avail", "Last_Scan", "Health_pct",
    "Streak", "Prune_Count", "Style", "Born",
]

HERBS_SEED = [
    ["ROS_001", "Rosie",      "Rosemary", 120, "2026-03-17", 98, 12,  8, "Upright",  "2025-06-01"],
    ["ROS_002", "Thornelius", "Rosemary",  80, "2026-03-16", 85,  5, 15, "Cascade",  "2024-03-10"],
    ["ROS_003", "Aromaticat", "Lavender",  60, "2026-03-17",100,  3,  2, "Informal", "2026-01-15"],
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_or_create_worksheet(spreadsheet, title, rows=100, cols=20):
    try:
        ws = spreadsheet.worksheet(title)
        ws.clear()
        print(f"  Cleared existing tab: {title}")
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)
        print(f"  Created new tab: {title}")
    return ws


def write_tab(spreadsheet, title, headers, seed_rows):
    ws = get_or_create_worksheet(spreadsheet, title)
    ws.append_row(headers, value_input_option="USER_ENTERED")
    for row in seed_rows:
        ws.append_row(row, value_input_option="USER_ENTERED")
    # Bold the header row
    ws.format("1:1", {"textFormat": {"bold": True}})
    print(f"  Wrote {len(seed_rows)} seed rows to {title}")
    return ws


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    creds_json = os.environ.get("G_SHEET_CREDS")
    if not creds_json:
        raise EnvironmentError("G_SHEET_CREDS env var is required")

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(creds_json), SCOPE
    )
    gc = gspread.authorize(creds)

    # Open or create the spreadsheet
    try:
        wb = gc.open(SHEET_NAME)
        print(f"Opened existing spreadsheet: {SHEET_NAME}")
    except gspread.exceptions.SpreadsheetNotFound:
        wb = gc.create(SHEET_NAME)
        print(f"Created new spreadsheet: {SHEET_NAME}")

    write_tab(wb, "Starters", STARTERS_HEADERS, STARTERS_SEED)
    write_tab(wb, "Herbs",    HERBS_HEADERS,    HERBS_SEED)

    # Remove default "Sheet1" if it exists and is empty
    try:
        default = wb.worksheet("Sheet1")
        wb.del_worksheet(default)
        print("  Removed default Sheet1")
    except gspread.exceptions.WorksheetNotFound:
        pass

    print(f"\nDone. Sheet URL: {wb.url}")


if __name__ == "__main__":
    main()
