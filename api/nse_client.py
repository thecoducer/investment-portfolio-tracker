"""
NSE API client for fetching market data.
"""
import time
import requests
from typing import List, Dict, Any
from urllib.parse import quote
from logging_config import logger


class NSEAPIClient:
    """Client for NSE (National Stock Exchange) API operations."""
    
    def __init__(self):
        """Initialize the NSE API client with configuration."""
        self.base_url = 'https://www.nseindia.com'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        self.timeout = 10
        self.request_delay = 0.2  # Delay between requests to avoid rate limiting
    
    def _create_session(self) -> requests.Session:
        """Create and initialize an NSE session with cookies.
        
        Returns:
            Configured requests.Session instance
        """
        try:
            session = requests.Session()
            session.get(self.base_url, headers=self.headers, timeout=self.timeout)
            return session
        except Exception as e:
            logger.exception("Error creating NSE session: %s", e)
            raise
    
    def fetch_nifty50_symbols(self) -> List[str]:
        """Fetch Nifty 50 constituent symbols from NSE API.
        
        Returns:
            List of stock symbols in the Nifty 50 index
        """
        try:
            session = self._create_session()
            url = f'{self.base_url}/api/equity-stockIndices?index=NIFTY%2050'
            response = session.get(url, headers=self.headers, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                symbols = [
                    item.get('symbol')
                    for item in data.get('data', [])
                    if item.get('symbol') and item.get('symbol') != 'NIFTY 50'
                ]
                return symbols
            else:
                logger.warning("Failed to fetch Nifty 50 symbols: %s", response.status_code)
                return []
                
        except Exception as e:
            logger.exception("Error fetching Nifty 50 symbols: %s", e)
            return []
    
    def fetch_stock_quote(self, session: requests.Session, symbol: str) -> Dict[str, Any]:
        """Fetch quote data for a single stock symbol.
        
        Args:
            session: Requests session object with active NSE cookies
            symbol: Stock symbol to fetch
            
        Returns:
            Dictionary containing stock quote data
        """
        try:
            encoded_symbol = quote(symbol)
            url = f"{self.base_url}/api/quote-equity?symbol={encoded_symbol}"
            response = session.get(url, headers=self.headers, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                price_info = data.get('priceInfo', {})
                return {
                    'symbol': symbol,
                    'name': data.get('info', {}).get('companyName', symbol),
                    'ltp': price_info.get('lastPrice', 0),
                    'change': price_info.get('change', 0),
                    'pChange': price_info.get('pChange', 0),
                    'open': price_info.get('open', 0),
                    'high': price_info.get('intraDayHighLow', {}).get('max', 0),
                    'low': price_info.get('intraDayHighLow', {}).get('min', 0),
                    'close': price_info.get('previousClose', 0)
                }
            else:
                return self._empty_stock_data(symbol)
        except Exception as e:
            logger.exception("Error fetching %s: %s", symbol, e)
            return self._empty_stock_data(symbol)
        finally:
            time.sleep(self.request_delay)
    
    def _empty_stock_data(self, symbol: str) -> Dict[str, Any]:
        """Return empty stock data structure for error cases.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary with zero values for all price fields
        """
        return {
            'symbol': symbol,
            'name': symbol,
            'ltp': 0,
            'change': 0,
            'pChange': 0,
            'open': 0,
            'high': 0,
            'low': 0,
            'close': 0
        }
