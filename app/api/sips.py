"""
SIP (Systematic Investment Plan) management service.
"""
from typing import Any, Dict, List

from kiteconnect import KiteConnect
from requests.exceptions import ConnectionError, ReadTimeout

from ..logging_config import logger
from .base_service import BaseDataService


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
        except (ReadTimeout, ConnectionError) as e:
            logger.warning("Kite API timeout while fetching SIPs: %s", str(e))
            return []
        except Exception as e:
            logger.exception("Error fetching SIPs: %s", e)
            return []
