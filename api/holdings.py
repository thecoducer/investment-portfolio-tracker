"""
Holdings management service.
"""
from typing import Dict, Any, List, Tuple
from datetime import datetime

from kiteconnect import KiteConnect
from .base_service import BaseDataService


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
        """
        stock_holdings = kite.holdings() or []
        mf_holdings = kite.mf_holdings() or []
        
        # Enrich MF holdings with NAV dates
        self._add_nav_dates(mf_holdings, kite)
        
        return stock_holdings, mf_holdings
    
    def _add_nav_dates(self, mf_holdings: List[Dict[str, Any]], kite: KiteConnect) -> None:
        """
        Add NAV date information to MF holdings by fetching instrument data.
        
        Args:
            mf_holdings: List of MF holdings to enrich
            kite: Authenticated KiteConnect instance
        """
        try:
            # Fetch MF instruments data (cached for performance)
            if not self.mf_instruments_cache:
                self.mf_instruments_cache = kite.mf_instruments()
                self.mf_instruments_cache_time = datetime.now()
            
            # Create a lookup dictionary by tradingsymbol
            instruments_map = {
                inst['tradingsymbol']: inst 
                for inst in self.mf_instruments_cache
            }
            
            # Add last_price_date to each holding
            for holding in mf_holdings:
                symbol = holding.get('tradingsymbol')
                if symbol and symbol in instruments_map:
                    instrument = instruments_map[symbol]
                    # The last_price_date from instruments API
                    if 'last_price_date' in instrument:
                        holding['last_price_date'] = instrument['last_price_date']
                    # Alternative: use last_price_date if available directly
                    elif 'last_price_date' in holding:
                        # Keep existing value if present
                        pass
                    else:
                        holding['last_price_date'] = None
                        
        except Exception as e:
            print(f"Error fetching MF instruments for NAV dates: {e}")
            # If we can't fetch instruments, just set None for all
            for holding in mf_holdings:
                if 'last_price_date' not in holding:
                    holding['last_price_date'] = None
    
    def add_account_info(self, holdings: List[Dict[str, Any]], account_name: str) -> None:
        """
        Add account name and calculate invested amount for holdings.
        Also adds T1 quantity to the main quantity for accurate totals.
        
        Args:
            holdings: List of holdings to enrich
            account_name: Name of the account
        """
        super().add_account_info(holdings, account_name)
        for holding in holdings:
            # Add T1 quantity (unsettled shares) to the main quantity
            base_quantity = holding.get("quantity", 0)
            t1_quantity = holding.get("t1_quantity", 0)
            total_quantity = base_quantity + t1_quantity
            
            # Update the quantity to include T1 shares
            holding["quantity"] = total_quantity
            
            # Calculate invested amount with total quantity
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
