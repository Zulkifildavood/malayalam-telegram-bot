import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import APIError
import logging

from config import SHEET_ID

# Setup Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

try:
    sheet = client.open_by_key(SHEET_ID).sheet1
except Exception as e:
    logging.error(f"Error opening Google Sheet: {e}")
    raise e
