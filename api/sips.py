"""
SIP (Systematic Investment Plan) management service.
"""
from typing import Dict, Any, List
from kiteconnect import KiteConnect
from .base_service import BaseDataService
from logging_config import logger


class SIPService(BaseDataService):
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
            logger.exception("Error fetching SIPs: %s", e)
            return []
