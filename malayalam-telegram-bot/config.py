import os
import logging

# Logging config
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")

if not BOT_TOKEN or not SHEET_ID:
    raise ValueError("Missing environment variables. Please set TELEGRAM_BOT_TOKEN and GOOGLE_SHEET_ID.")

# Save credentials to file for Google Sheets
with open("credentials.json", "w") as f:
    f.write(os.environ["GOOGLE_CREDENTIALS_JSON"])

# Annotators and reviewers (replace with actual IDs)
ANNOTATORS = {123456789, 987654321, 1207889943}
REVIEWERS = {112233445, 998877665, 1207889943,509779274}
