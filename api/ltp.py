"""
Last Traded Price (LTP) fetching service.
"""
from typing import List, Dict, Any

import requests

from constants import NSE_API_URL, EXCHANGE_NSE, EXCHANGE_BSE, EXCHANGE_SUFFIX, HTTP_OK


class LTPService:
    """Service for fetching real-time LTP data."""
    
    def __init__(self, api_url: str = NSE_API_URL):
        self.api_url = api_url
    
    def fetch_ltps(self, holdings: List[Dict[str, Any]], timeout: int = 10) -> Dict[str, float]:
        """
        Fetch LTP for all holdings.
        
        Args:
            holdings: List of holdings with tradingsymbol and exchange
            timeout: Request timeout in seconds
        
        Returns:
            Dictionary mapping symbol keys to LTP values
        """
        symbols = self._prepare_symbols(holdings)
        
        if not symbols:
            return {}
        
        try:
            url = f"{self.api_url}?symbols={','.join(symbols)}&res=num"
            response = requests.get(url, timeout=timeout)
            
            if response.status_code == HTTP_OK:
                return response.json()
        except Exception as e:
            print(f"Error fetching LTPs: {e}")
        
        return {}
    
    def update_holdings_with_ltp(self, holdings: List[Dict[str, Any]], ltp_data: Dict[str, float]) -> None:
        """
        Update holdings with fetched LTP data.
        
        Args:
            holdings: List of holdings to update
            ltp_data: Dictionary of LTP values
        """
        for holding in holdings:
            exchange = holding.get("exchange")
            symbol = holding.get("tradingsymbol")
            
            key = self._get_symbol_key(symbol, exchange)
            
            if key in ltp_data:
                holding["last_price"] = ltp_data[key].get("last_price", holding.get("last_price", 0))
    
    @staticmethod
    def _prepare_symbols(holdings: List[Dict[str, Any]]) -> List[str]:
        """Prepare symbol list for API request."""
        symbols = []
        for holding in holdings:
            symbol = holding.get("tradingsymbol")
            exchange = holding.get("exchange")
            
            suffix = EXCHANGE_SUFFIX.get(exchange, "")
            symbols.append(symbol + suffix)
        
        return symbols
    
    @staticmethod
    def _get_symbol_key(symbol: str, exchange: str) -> str:
        """Get the key used in LTP data dictionary."""
        suffix = EXCHANGE_SUFFIX.get(exchange, "")
        return symbol + suffix if suffix else symbol
