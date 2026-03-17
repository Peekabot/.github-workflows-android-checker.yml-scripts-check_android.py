import os, json
from datetime import datetime, date
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ── Sheet config ────────────────────────────────────────────────────────────

SCOPE = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/spreadsheets"]

SHEET_NAME = "OpenPantry"

# Column indices (1-based) shared by both tabs
COL = {
    "id": 1,
    "name": 2,
    "born": 3,
    "quantity": 4,   # grams on-hand (herbs) / starter weight (yeast)
    "last_event": 5, # last fed (yeast) / last scan (herb)
    "health": 6,
    "streak": 7,
    "notes": 8,
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_sheet():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(os.environ["G_SHEET_CREDS"]), SCOPE
    )
    gc = gspread.authorize(creds)
    return gc.open(SHEET_NAME)


def find_row(worksheet, asset_id):
    cell = worksheet.find(asset_id)
    if cell is None:
        raise ValueError(f"Asset {asset_id} not found in sheet")
    return cell.row


def notify(topic, message):
    requests.post(f"https://ntfy.sh/{topic}", data=message)


def today_str():
    return date.today().isoformat()


# ── Yeast starter logic ───────────────────────────────────────────────────────

def log_yeast(wb, asset_id, amount, notes=""):
    """
    Log a feeding event for a yeast starter (YST_xxx).
    Decrements on-hand weight, updates last_fed, increments streak.
    """
    ws = wb.worksheet("Starters")
    row = find_row(ws, asset_id)

    current_qty = float(ws.cell(row, COL["quantity"]).value or 0)
    streak = int(ws.cell(row, COL["streak"]).value or 0)
    last_event = ws.cell(row, COL["last_event"]).value or ""

    # Increment streak only if last event was yesterday or today
    today = date.today()
    if last_event:
        last_date = date.fromisoformat(last_event)
        days_gap = (today - last_date).days
        new_streak = streak + 1 if days_gap <= 1 else 1
    else:
        new_streak = 1

    new_qty = max(0, current_qty - amount)

    ws.update_cell(row, COL["quantity"], new_qty)
    ws.update_cell(row, COL["last_event"], today_str())
    ws.update_cell(row, COL["streak"], new_streak)
    if notes:
        ws.update_cell(row, COL["notes"], notes)

    name = ws.cell(row, COL["name"]).value
    notify(
        os.environ["NTFY_TOPIC"],
        f"[YST] {name} ({asset_id}) fed {amount}g | streak {new_streak} | remaining {new_qty}g"
    )
    print(f"Yeast: {asset_id} fed {amount}g, streak={new_streak}, remaining={new_qty}g")


# ── Herb / bonsai logic ───────────────────────────────────────────────────────

def log_herb(wb, asset_id, amount, notes=""):
    """
    Log a harvest or scan event for an herb/bonsai (ROS_xxx or similar).
    Decrements harvestable quantity, updates last_scan, increments streak.
    """
    ws = wb.worksheet("Herbs")
    row = find_row(ws, asset_id)

    current_qty = float(ws.cell(row, COL["quantity"]).value or 0)
    streak = int(ws.cell(row, COL["streak"]).value or 0)
    last_event = ws.cell(row, COL["last_event"]).value or ""

    today = date.today()
    if last_event:
        last_date = date.fromisoformat(last_event)
        days_gap = (today - last_date).days
        new_streak = streak + 1 if days_gap <= 1 else 1
    else:
        new_streak = 1

    new_qty = max(0, current_qty - amount)

    ws.update_cell(row, COL["quantity"], new_qty)
    ws.update_cell(row, COL["last_event"], today_str())
    ws.update_cell(row, COL["streak"], new_streak)
    if notes:
        ws.update_cell(row, COL["notes"], notes)

    name = ws.cell(row, COL["name"]).value
    notify(
        os.environ["NTFY_TOPIC"],
        f"[HERB] {name} ({asset_id}) harvested {amount}g | streak {new_streak} | remaining {new_qty}g"
    )
    print(f"Herb: {asset_id} harvested {amount}g, streak={new_streak}, remaining={new_qty}g")


# ── Router ────────────────────────────────────────────────────────────────────

ASSET_HANDLERS = {
    "YST": log_yeast,
    "ROS": log_herb,
    "LAV": log_herb,
    "THY": log_herb,
}


def route(wb, asset_id, amount, notes=""):
    prefix = asset_id.split("_")[0].upper()
    handler = ASSET_HANDLERS.get(prefix)
    if handler is None:
        raise ValueError(f"Unknown asset prefix '{prefix}' in ID '{asset_id}'")
    handler(wb, asset_id, amount, notes)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    asset_id = os.getenv("ASSET_ID", "ROS_001")
    amount = float(os.getenv("AMOUNT", "5"))
    notes = os.getenv("NOTES", "")

    wb = get_sheet()
    route(wb, asset_id, amount, notes)


if __name__ == "__main__":
    main()
