# Investment Portfolio Tracker

[![Tests](https://github.com/thecoducer/investment-portfolio-tracker/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/thecoducer/investment-portfolio-tracker/actions/workflows/tests.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A modern, modular Flask-based web application for tracking mutual fund and stock holdings from Zerodha brokerage accounts with real-time price updates.

## ✨ Features

- **Multi-account support**: Track holdings across multiple Zerodha accounts
- **Session token caching**: Auto-login on restart using cached session tokens with encryption
- **Server-Sent Events (SSE)**: Real-time status updates without polling
- **Smart loading**: Dashboard waits for backend data fetching to complete before rendering
- **Active SIPs tracking**: View all active SIPs (Systematic Investment Plans) with monthly total calculation
- **Interactive dashboard**: Modern UI with dark/light theme toggle
- **Privacy mode**: Hide sensitive data with blur effect for screen sharing
- **Search & filter**: Quick search across symbols and accounts with smart table visibility
- **Live animations**: Blur-fade indicators during data updates (disabled in privacy mode)
- **Combined analytics**: Aggregated view of stocks and mutual funds
- **NAV date tracking**: Shows when mutual fund NAV was last updated with relative dates (today, yesterday, X days ago)
- **Smart date formatting**: Intuitive date displays for SIP schedules (tomorrow, in X days)
- **Responsive design**: Clean, professional interface with smooth animations
- **Auto-refresh**: Configurable automatic refresh of all holdings data

## 📋 Prerequisites

Before running the application, make sure you have:

1. **Python 3.9 or higher** installed on your system
2. **Zerodha KiteConnect API credentials** ([Get them here](https://kite.trade/))
   - API Key
   - API Secret
   - **Redirect URL** (must be configured in your Kite app settings)
3. **Modern web browser** (Chrome, Firefox, Safari, Edge)

### Setting up Zerodha KiteConnect App

1. Visit [Kite Connect Developer Console](https://developers.kite.trade/)
2. Log in with your Zerodha credentials
3. Create a new app or use an existing one
4. In your app settings, configure the **Redirect URL**:
   ```
   http://127.0.0.1:5000/callback
   ```
   > **Important**: This URL must match exactly what's configured in `config.json` (default values shown above). If you change the `callback_host`, `callback_port`, or `callback_path` in your config, update the redirect URL accordingly.
   
5. Copy your **API Key** and **API Secret** - you'll need these for `config.json`

## ⚙️ Configuration (Required)

**Important:** You must configure your API credentials before running the application.

1. **Copy the example configuration:**
   ```bash
   cp config.json.example config.json
   ```

2. **Edit `config.json` with your Zerodha API credentials:**
   ```json
   {
     "accounts": [
       {
         "name": "YourAccountName",
         "api_key": "your_kite_api_key",
         "api_secret": "your_kite_api_secret"
       }
     ]
   }
   ```
   
   > **Note**: Ensure your KiteConnect app's redirect URL is set to `http://127.0.0.1:5000/callback` in the Zerodha developer console. If you modify the `callback_host`, `callback_port`, or `callback_path` in `config.json`, update the redirect URL in your Kite app accordingly.

3. **Never commit `config.json`** - It contains sensitive credentials and is gitignored by default.

### config.json Structure

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
    "callback_path": "/callback",
    "ui_host": "127.0.0.1",
    "ui_port": 8000
  },
  "timeouts": {
    "request_token_timeout_seconds": 180,
    "auto_refresh_interval_seconds": 60
  },
  "features": {
    "enable_auto_refresh": true
  }
}
```

### Configuration Options

**accounts**: Array of Zerodha account configurations
- `name`: Display name for the account
- `api_key`: Your Zerodha KiteConnect API key
- `api_secret`: Your Zerodha KiteConnect API secret

**server**: Server configuration
- `callback_host`: OAuth callback host (default: 127.0.0.1)
- `callback_port`: OAuth callback port (default: 5000)
- `callback_path`: OAuth callback path (default: /callback)
- `ui_host`: UI server host (default: 127.0.0.1)
- `ui_port`: UI server port (default: 8000)

> **Important**: The callback URL must match your Kite app's redirect URL setting. The default configuration uses `http://127.0.0.1:5000/callback`. If you change these values, update the redirect URL in your [Kite Connect app settings](https://developers.kite.trade/).

**timeouts**: Timing configuration
- `request_token_timeout_seconds`: OAuth timeout (default: 180)
- `auto_refresh_interval_seconds`: Automatic refresh interval (default: 60)

**features**: Feature toggles
- `enable_auto_refresh`: Enable automatic periodic refresh of all holdings data (default: true)

## 🚀 Quick Start

### One-Command Setup

After configuring your API credentials in `config.json`, simply run:

```bash
./start.sh
```

This script will:
- ✅ Check Python installation
- ✅ Validate your configuration
- ✅ Create virtual environment
- ✅ Install all dependencies
- ✅ Start the server
- ✅ Open dashboard in browser

**Dashboard URL**: `http://127.0.0.1:8000/holdings`

The dashboard will automatically open in your browser. If not, manually navigate to the URL above.

### Manual Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/thecoducer/investment-portfolio-tracker.git
   cd investment-portfolio-tracker
   ```

2. **Create configuration**
   ```bash
   cp config.json.example config.json
   ```
   
   Edit `config.json` and add your Zerodha API credentials:
   ```json
   {
     "accounts": [
       {
         "name": "YourAccount",
         "api_key": "your_kite_api_key",
         "api_secret": "your_kite_api_secret"
       }
     ]
   }
   ```

3. **Install dependencies**
   ```bash
   python3 -m venv run_server
   source run_server/bin/activate  # On Windows: run_server\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Run the server**
   ```bash
   python3 server.py
   ```

5. **Access the dashboard**
   Open your browser: `http://127.0.0.1:8000/holdings`

## 🏗️ Architecture

### Backend (Python/Flask)
```
├── server.py              # Main Flask application with SSE support
├── api/
│   ├── auth.py           # Authentication & OAuth flow
│   └── holdings.py       # Holdings data fetching & enrichment
├── utils.py              # State & session management with encryption
├── constants.py          # Application constants
└── templates/
    └── holdings.html     # Main dashboard HTML template
```

### Frontend (JavaScript/ES6)
```
├── static/
│   ├── css/
│   │   └── styles.css            # Application styles with dark/light themes
│   └── js/
│       ├── app.js                # Main application controller
│       ├── data-manager.js       # API data fetching
│       ├── table-renderer.js     # Table rendering with animations
│       ├── summary-manager.js    # Portfolio summary calculations
│       ├── theme-manager.js      # Dark/light theme switching
│       ├── visibility-manager.js # Privacy mode for data hiding
│       └── utils.js              # Formatters & calculators
```

## 🎯 Usage

### First Login
1. Click the "Refresh Holdings" button
2. Browser will open for Zerodha OAuth authentication
3. Log in and authorize the app
4. Token is cached securely with encryption for future use

### Subsequent Use
- Cached tokens are automatically used (valid for ~24 hours)
- Manual refresh if token expires
- Auto-refresh every 60 seconds (configurable)
- Real-time status updates via Server-Sent Events (SSE)

### Features in Action

**Search & Filter**: Type in the search box to filter holdings by symbol or account. Empty tables are automatically hidden.

**Theme Toggle**: Click the theme button (🌙/☀️) to switch between dark and light modes

**Privacy Mode**: Click the eye button (👁️) to blur sensitive financial data - perfect for screen sharing or presentations. Colors and animations are disabled in privacy mode.

**Active SIPs**: View all your systematic investment plans with:
- Fund name (displayed in uppercase)
- Monthly/quarterly installment amount
- Frequency and installment progress
- Status indicator (ACTIVE in green, PAUSED in yellow, CANCELLED in red)
- Next due date (shown as "Today", "Tomorrow", "In X days", or specific date)
- Total Monthly SIP Amount displayed as the last row in the table

**Real-time Updates**: Watch fields fade during refresh operations
- All numeric fields show blur-fade animation during updates
- Animation is disabled in privacy mode to maintain data security

**NAV Dates**: Mutual fund NAV shows relative date (today, yesterday, X days ago)

## 🔒 Security

- ⚠️ **Never commit `config.json`** - Contains sensitive API credentials
- ✅ Session tokens cached in `.session_cache.json` are **automatically encrypted** using machine-specific keys
- ✅ All sensitive files excluded via `.gitignore`
- ✅ OAuth flow for secure authentication
- ✅ Token auto-renewal when possible

**Encryption Details:**
- Session tokens are encrypted using Fernet (symmetric encryption)
- Encryption key is derived from machine-specific identifiers (hostname + architecture)
- Tokens stored in plain text in earlier versions will be automatically migrated to encrypted format
- Each machine generates its own unique encryption key

**Files to keep private:**
- `config.json` - API keys and secrets (plain text, manually protect with file permissions)
- `.session_cache.json` - Encrypted session tokens (auto-generated, gitignored)
- `.env` (if used)

## 🛠️ Development

### Project Structure
The codebase follows modular architecture with clear separation of concerns:

- **Backend services**: Authentication, holdings, LTP fetching
- **Frontend modules**: ES6 imports with dedicated managers
- **State management**: Centralized state handling
- **Configuration**: JSON-based config with validation

### Adding Features
1. **New API endpoints**: Add routes in `server.py`
2. **Backend logic**: Extend services in `api/` directory
3. **Frontend features**: Add modules in `static/js/`
4. **Styling**: Update `static/styles.css`

### Running Tests
```bash
# Activate virtual environment
source run_server/bin/activate

# Run the server
python3 server.py
```

## 📦 Dependencies

- `flask==2.3.3` - Web framework
- `kiteconnect==5.0.1` - Zerodha API client
- `requests==2.31.0` - HTTP library
- `python-dotenv==1.0.0` - Environment variable management
- `cryptography==46.0.0` - Session token encryption
- `zoneinfo` (Python 3.9+) - Timezone handling (built-in)

## 🐛 Troubleshooting

### Configuration Issues
```bash
./start.sh  # Will validate config and show specific errors
```

### Missing Dependencies
```bash
pip install -r requirements.txt --upgrade
```

### Token Expired
- Click "Refresh Holdings" to re-authenticate
- Check `.session_cache.json` exists and is readable

### Dashboard Shows "Updating" for Long Time
- This is normal on first server restart as backend fetches data from all accounts
- Accounts are fetched sequentially to avoid API rate limits
- Dashboard will automatically load once data is available
- Check browser console for any errors

### Port Already in Use
Edit `config.json` and change `ui_port` or `callback_port` to different values

## 📝 License

This project is for personal use. Feel free to fork and modify for your needs.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## 📧 Contact

For questions or support, please open an issue on GitHub.
