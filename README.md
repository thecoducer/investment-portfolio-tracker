# Investment Portfolio Tracker

[![Tests](https://github.com/thecoducer/investment-portfolio-tracker/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/thecoducer/investment-portfolio-tracker/actions/workflows/tests.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A Flask-based web application for tracking mutual fund and stock holdings from Zerodha brokerage accounts with real-time updates.

## Features

- Multi-account support with encrypted session caching
- Real-time updates via Server-Sent Events (SSE)
- Auto-refresh during market hours (9:00–16:30 IST) with optional 24/7 mode
- Interactive dashboard with dark/light theme and privacy mode
- Active SIPs tracking with smart date formatting
- Search and filter capabilities
- Nifty 50 live prices page

## Prerequisites

1. **Python 3.9+**
2. **Zerodha KiteConnect API credentials** from [Kite Connect](https://developers.kite.trade/)
   - API Key and Secret
   - Redirect URL: `http://127.0.0.1:5000/callback`

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
    "auto_refresh_outside_market_hours": false
  }
}
```

**Important:** Ensure your Kite app's redirect URL matches `http://127.0.0.1:5000/callback`

## Security

- ⚠️ Never commit `config.json`
- Session tokens automatically encrypted using machine-specific keys
- OAuth flow for secure authentication

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
