import os, json, requests
import myfitnesspal
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai

def main():
    # Get asset from event (or default to ROS_001)
    asset_id = os.getenv('ASSET_ID', 'ROS_001')
    amount = int(os.getenv('AMOUNT', '5'))

    # Log to MFP
    mfp = myfitnesspal.Client(os.environ['MFP_USER'], password=os.environ['MFP_PASS'])
    today = mfp.get_date(2026, 3, 15)  # Update to dynamic date
    today.meals[0].add_food('Rosemary', amount)

    # Update Sheet
    scope = ["https://spreadsheets.google.com/feeds"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(os.environ['G_SHEET_CREDS']), scope)
    gs = gspread.authorize(creds)
    sheet = gs.open("OpenPantry").sheet1
    cell = sheet.find(asset_id)
    current = float(sheet.cell(cell.row, 4).value)
    sheet.update_cell(cell.row, 4, current - amount)

    # Notify
    requests.post(f"https://ntfy.sh/{os.environ['NTFY_TOPIC']}",
                  data=f"✅ {asset_id}: {amount}g logged")

if __name__ == "__main__":
    main()
