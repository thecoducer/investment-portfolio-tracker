"""
Holdings management service.
"""
from typing import Dict, Any, List, Tuple
from datetime import datetime

from kiteconnect import KiteConnect
from requests.exceptions import ReadTimeout, ConnectionError
from .base_service import BaseDataService
from logging_config import logger


class HoldingsService(BaseDataService):
    """Service for fetching and managing holdings data."""
    
    def __init__(self):
        self.mf_instruments_cache = None
        self.mf_instruments_cache_time = None
    
    def fetch_holdings(self, kite: KiteConnect) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Fetch stock and MF holdings from KiteConnect.
        
        Args:
            kite: Authenticated KiteConnect instance
        
        Returns:
            Tuple of (stock_holdings, mf_holdings)
        
        Raises:
            ReadTimeout, ConnectionError: On network issues
            Exception: On other API errors
        """
        try:
            stock_holdings = kite.holdings() or []
            mf_holdings = kite.mf_holdings() or []
            self._add_nav_dates(mf_holdings, kite)
            return stock_holdings, mf_holdings
        except (ReadTimeout, ConnectionError) as e:
            logger.warning("Kite API timeout while fetching holdings: %s", str(e))
            raise
        except Exception as e:
            logger.exception("Unexpected error fetching holdings: %s", e)
            raise
    
    def _add_nav_dates(self, mf_holdings: List[Dict[str, Any]], kite: KiteConnect) -> None:
        """
        Add NAV date information to MF holdings by fetching instrument data.
        
        Args:
            mf_holdings: List of MF holdings to enrich
            kite: Authenticated KiteConnect instance
        """
        try:
            if not self.mf_instruments_cache:
                self.mf_instruments_cache = kite.mf_instruments()
                self.mf_instruments_cache_time = datetime.now()
            
            instruments_map = {
                inst['tradingsymbol']: inst 
                for inst in self.mf_instruments_cache
            }
            
            for holding in mf_holdings:
                symbol = holding.get('tradingsymbol')
                if symbol and symbol in instruments_map:
                    instrument = instruments_map[symbol]
                    # Set NAV date from instrument data if available
                    holding['last_price_date'] = instrument.get(
                        'last_price_date',
                        holding.get('last_price_date')
                    )
                else:
                    # Set to None if symbol not found in instruments
                    holding.setdefault('last_price_date', None)
                        
        except Exception as e:
            logger.exception("Error fetching MF instruments for NAV dates: %s", e)
            # Ensure all holdings have last_price_date field
            for holding in mf_holdings:
                holding.setdefault('last_price_date', None)
    
    def add_account_info(self, holdings: List[Dict[str, Any]], account_name: str) -> None:
        """Add account name and calculate invested amount for holdings.
        
        T1 quantity (unsettled shares) is added to the main quantity for accurate totals.
        Invested amount is calculated as: (quantity + t1_quantity) * average_price
        
        Args:
            holdings: List of holdings to enrich
            account_name: Name of the account
        """
        super().add_account_info(holdings, account_name)
        
        for holding in holdings:
            # Include T1 (unsettled) quantity in total quantity
            base_quantity = holding.get("quantity", 0)
            t1_quantity = holding.get("t1_quantity", 0)
            total_quantity = base_quantity + t1_quantity
            
            holding["quantity"] = total_quantity
            holding["invested"] = total_quantity * holding.get("average_price", 0)
    
    def merge_holdings(
        self,
        all_stock_holdings: List[List[Dict[str, Any]]],
        all_mf_holdings: List[List[Dict[str, Any]]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Merge holdings from multiple accounts.
        
        Args:
            all_stock_holdings: List of stock holdings lists
            all_mf_holdings: List of MF holdings lists
        
        Returns:
            Tuple of (merged_stock_holdings, merged_mf_holdings)
        """
        return self.merge_items(all_stock_holdings), self.merge_items(all_mf_holdings)
