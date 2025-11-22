# Investment Portfolio Tracker

A Flask-based web application for tracking mutual fund and stock holdings from Zerodha brokerage accounts.

## Features

- **Multi-account support**: Track holdings across multiple Zerodha accounts
- **Session token caching**: Auto-login on restart using cached tokens
- **Real-time LTP updates**: Automatic stock price updates during market hours
- **Summary dashboard**: Combined view of total invested, current value, and P/L
- **Search & filter**: Quick search across symbols and accounts
- **Responsive UI**: Modern, clean dashboard interface

## Installation

### Prerequisites
- Python 3.8+
- Zerodha KiteConnect API credentials
- pip

### Setup

1. **Clone/Extract the project**
   ```bash
   cd portfolio_tracker
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your accounts**
   Edit `config.json` and update the `api_key_env` and `api_secret_env` fields to match your environment variable names.

4. **Set environment variables**
   ```bash
   export KITE_API_KEY_MAYUKH=your_api_key
   export KITE_API_SECRET_MAYUKH=your_api_secret
   export KITE_API_KEY_MOTHER=your_api_key
   export KITE_API_SECRET_MOTHER=your_api_secret
   ```

   Or create a `.env` file in the project root:
   ```
   KITE_API_KEY_MAYUKH=your_api_key
   KITE_API_SECRET_MAYUKH=your_api_secret
   KITE_API_KEY_MOTHER=your_api_key
   KITE_API_SECRET_MOTHER=your_api_secret
   ```

5. **Run the server**
   ```bash
   python server.py
   ```

6. **Access the dashboard**
   Open your browser and navigate to: `http://127.0.0.1:8000/holdings`

## Configuration

### config.json

- **accounts**: List of account configurations
  - `name`: Display name for the account
  - `api_key_env`: Environment variable name for API key
  - `api_secret_env`: Environment variable name for API secret

- **server**: Server configuration
  - `callback_host`: OAuth callback host (default: 127.0.0.1)
  - `callback_port`: OAuth callback port (default: 5000)
  - `ui_host`: UI server host (default: 127.0.0.1)
  - `ui_port`: UI server port (default: 8000)

- **timeouts**: Timeout configuration
  - `request_token_timeout_seconds`: Auth timeout (default: 180)
  - `ltp_fetch_interval_seconds`: Price update interval (default: 60)

- **features**: Feature flags
  - `enable_ltp_fetcher`: Enable real-time price updates (default: true)

## Architecture

- `server.py`: Main Flask application
- `utils.py`: Utility classes and functions
- `templates.py`: HTML template provider
- `static/styles.css`: Stylesheet
- `static/app.js`: Frontend JavaScript
- `config.json`: Configuration file
- `.session_cache.json`: Cached session tokens (auto-generated)

## Usage

### First Login
On first run, clicking "Refresh Holdings" will open your browser for KiteConnect OAuth login. After authentication, your token is cached locally.

### Subsequent Runs
If your token hasn't expired, the app uses the cached token silently. If expired, it will prompt for re-login.

### Real-time Updates
The dashboard automatically refreshes every 2 seconds. Stock prices update every minute during market hours.

### Search & Filter
Use the search box to filter holdings by symbol name or account.

## Security Notes

- Session tokens are cached locally in `.session_cache.json`
- Tokens are set to expire after ~24 hours
- Never commit `.session_cache.json` or `.env` to version control
- API keys/secrets should only be set via environment variables

## Troubleshooting

### "Missing API credentials" error
Ensure all environment variables defined in `config.json` are set. Check:
```bash
echo $KITE_API_KEY_MAYUKH
echo $KITE_API_SECRET_MAYUKH
```

### Token expired, login not triggered
Check the browser console for errors and ensure your `.env` file or environment variables are set.

### LTP not updating
Check that:
1. `enable_ltp_fetcher` is `true` in config.json
2. Market is open (9:15 AM to 3:30 PM IST on weekdays)
3. Stock symbols are valid

## Development

The codebase is structured for easy extension:
- Add new routes in `server.py`
- Add utilities in `utils.py`
- Modify styles in `static/styles.css`
- Update frontend logic in `static/app.js`

## License

This project is for personal use.
