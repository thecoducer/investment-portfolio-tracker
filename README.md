# Investment Portfolio Tracker

[![Tests](https://github.com/thecoducer/investment-portfolio-tracker/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/thecoducer/investment-portfolio-tracker/actions/workflows/tests.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A Flask-based web application for tracking mutual fund and stock holdings from Zerodha brokerage accounts with real-time updates and physical gold tracking via Google Sheets.

## Features

- Multi-account support with encrypted session caching
- Real-time updates via Server-Sent Events (SSE)
- Auto-refresh during market hours (9:00–16:30 IST) with optional 24/7 mode
- Interactive dashboard with dark/light theme and privacy mode
- Active SIPs tracking with smart date formatting
- **Physical Gold tracking** via Google Sheets integration
- Search and filter capabilities
- Nifty 50 live prices page
- Live IBJA gold price fetching for P/L calculations

## Prerequisites

1. **Python 3.9+**
2. **Zerodha KiteConnect API credentials** from [Kite Connect](https://developers.kite.trade/)
   - API Key and Secret
   - Redirect URL: `http://127.0.0.1:5000/callback`
3. **(Optional) Google Sheets API Service Account** for physical gold tracking
   - Service account JSON credentials
   - Google Sheets API enabled in Google Cloud Console

## Quick Start

1. **Configure API credentials:**
   ```bash
   cp config.json.example config.json
   # Edit config.json with your Zerodha API key and secret
   ```

2. **Run:**
   ```bash
   ./start.sh
   ```

3. **Access:** `http://127.0.0.1:8000/holdings`

## Configuration

Edit `config.json`:

```json
{
  "accounts": [
    {
      "name": "Account1",
      "api_key": "your_api_key",
      "api_secret": "your_api_secret"
    }
  ],
  "server": {
    "callback_host": "127.0.0.1",
    "callback_port": 5000,
    "ui_host": "127.0.0.1",
    "ui_port": 8000
  },
  "timeouts": {
    "request_token_timeout_seconds": 180,
    "auto_refresh_interval_seconds": 60
  },
  "features": {
    "auto_refresh_outside_market_hours": false,
    "physical_gold_enabled": true
  },
  "google_sheets": {
    "credentials_file": "google-credentials.json",
    "spreadsheet_id": "your_spreadsheet_id_here",
    "range": "Sheet1!A:K"
  }
}
```

**Important:** Ensure your Kite app's redirect URL matches `http://127.0.0.1:5000/callback`

## Google Sheets Setup (Optional - For Physical Gold Tracking)

If you want to track physical gold holdings, follow these steps to set up Google Sheets API access:

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Sheets API**:
   - Navigate to "APIs & Services" → "Library"
   - Search for "Google Sheets API"
   - Click "Enable"

### 2. Create a Service Account

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Fill in the service account details:
   - **Name**: `portfolio-tracker` (or any name)
   - **Description**: Service account for portfolio tracker
4. Click "Create and Continue"
5. Skip the optional permissions (click "Continue" → "Done")

### 3. Generate Service Account Key

1. Click on the created service account
2. Go to the "Keys" tab
3. Click "Add Key" → "Create new key"
4. Choose **JSON** format
5. Click "Create" - this downloads the credentials JSON file
6. Rename the file to `google-credentials.json` and place it in your project root directory

### 4. Create and Configure Google Sheet

1. Create a new Google Sheet or use an existing one
2. **Share the sheet** with the service account email:
   - Open your Google Sheet
   - Click "Share" button
   - Add the service account email (found in the JSON file, looks like `portfolio-tracker@project-name.iam.gserviceaccount.com`)
   - Give it **Viewer** permissions (read-only is sufficient)
3. Copy the **Spreadsheet ID** from the URL:
   - URL format: `https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit`
   - Copy the ID and add it to your `config.json`

### 5. Google Sheet Structure

Your Google Sheet must have the following columns in order (from Column A to F):

| Column | Header | Description | Example |
|--------|--------|-------------|---------||
| A | Date | Purchase date | 2024-01-15 |
| B | Type | Type of gold item | Coin, Bar, Jewellery |
| C | Retail Outlet | Store/dealer name | Tanishq, Malabar Gold |
| D | Purity | Gold purity | 999, 916, 22K, 24K |
| E | Weight in gms | Weight in grams | 10.5 |
| F | IBJA PM rate per 1 gm | IBJA rate when bought | 6543.21 |

**Important Notes:**
- The first row must contain headers (they can be any text)
- Data starts from row 2
- **Jewellery type items are automatically excluded** from P/L calculations
- Leave empty rows as they are (they'll be skipped)
- Numbers can include currency symbols (₹) and commas - they'll be parsed automatically

**Example Sheet Data:**

```
Date       | Type | Retail Outlet | Purity | Weight | IBJA Rate
-----------|------|---------------|--------|--------|----------
2024-01-15 | Coin | Tanishq       | 999    | 10.5   | 6543.21
2024-03-20 | Bar  | Malabar Gold  | 916    | 8.0    | 6012.00
```

### 6. Install Google Sheets Dependencies

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### 7. Enable Physical Gold Tracking

Update your `config.json`:

```json
{
  "features": {
    "physical_gold_enabled": true
  },
  "google_sheets": {
    "credentials_file": "google-credentials.json",
    "spreadsheet_id": "1a2b3c4d5e6f7g8h9i0j",
    "range": "Sheet1!A:K"
  }
}
```

### How It Works

- The application fetches gold holdings from your Google Sheet
- Latest IBJA gold prices are fetched from [ibjarates.com](https://ibjarates.com/)
- P/L is calculated automatically based on:
  - **24K (999 purity)**: Uses latest 999 IBJA PM rate
  - **22K (916 purity)**: Uses latest 916 IBJA PM rate
  - **Jewellery items**: Excluded from P/L calculations (displayed separately)
- Real-time price updates during market hours

## Security

- ⚠️ Never commit `config.json` or `google-credentials.json`
- Add both files to `.gitignore`
- Session tokens automatically encrypted using machine-specific keys
- OAuth flow for secure authentication
- Service account has read-only access to Google Sheets

## Development

### Running Tests
```bash
./run_tests.sh
```

155 tests | 84% coverage

### Project Structure
```
├── server.py              # Flask app
├── api/                   # Backend services
│   ├── auth.py
│   ├── zerodha_client.py
│   ├── nse_client.py
│   ├── holdings.py
│   └── sips.py
├── utils.py              # State & session management
├── static/js/            # Frontend modules
└── tests/                # Test suite
```

## Troubleshooting

- **Token expired:** Click "Refresh Holdings"
- **Port in use:** Change ports in `config.json`
- **Config errors:** Run `./start.sh` to validate

## License

MIT - For personal use.
