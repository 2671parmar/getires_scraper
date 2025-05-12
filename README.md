# SimpleTire Brand Scraper

This script scrapes brand information from SimpleTire's website and stores it in a Google Sheet.

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Set up Google Sheets API:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable the Google Sheets API
   - Create credentials (OAuth 2.0 Client ID)
   - Download the credentials JSON file and save it as `credentials.json` in the project directory

3. Create a Google Sheet and share it with the email address from your credentials

4. Update the `SPREADSHEET_ID` in the script with your Google Sheet ID (found in the URL of your sheet)

## Usage

Run the script:
```bash
python scraper.py
```

The script will:
1. Scrape brand information from SimpleTire
2. Process and clean the data
3. Upload the data to your Google Sheet 