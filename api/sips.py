"""
SIP (Systematic Investment Plan) management service.
"""
from typing import Dict, Any, List
from kiteconnect import KiteConnect


class SIPService:
    """Service for fetching and managing SIP data."""
    
    def fetch_sips(self, kite: KiteConnect) -> List[Dict[str, Any]]:
        """
        Fetch all active and pending SIPs from KiteConnect.
        
        Args:
            kite: Authenticated KiteConnect instance
        
        Returns:
            List of SIP details
        """
        try:
            # Fetch all SIPs (passing None to get all SIPs)
            sips = kite.mf_sips() or []
            return sips
        except Exception as e:
            print(f"Error fetching SIPs: {e}")
            return []
    
    def add_account_info(self, sips: List[Dict[str, Any]], account_name: str) -> None:
        """
        Add account name to SIP data.
        
        Args:
            sips: List of SIPs to enrich
            account_name: Name of the account
        """
        for sip in sips:
            sip["account"] = account_name
    
    def merge_sips(self, all_sips: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Merge SIPs from multiple accounts.
        
        Args:
            all_sips: List of SIP lists from different accounts
        
        Returns:
            Merged list of all SIPs
        """
        merged = []
        for sips in all_sips:
            merged.extend(sips)
        return merged
