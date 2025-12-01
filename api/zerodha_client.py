"""
Zerodha API client for fetching portfolio data.
"""
import threading
from typing import List, Dict, Any, Tuple, Optional
from logging_config import logger


class ZerodhaAPIClient:
    """Client for Zerodha KiteConnect API operations."""
    
    def __init__(self, auth_manager, holdings_service, sip_service):
        """Initialize the client with required service dependencies.
        
        Args:
            auth_manager: AuthenticationManager instance
            holdings_service: HoldingsService instance
            sip_service: SIPService instance
        """
        self.auth_manager = auth_manager
        self.holdings_service = holdings_service
        self.sip_service = sip_service
    
    def fetch_account_data(
        self, 
        account_config: Dict[str, Any], 
        force_login: bool = False
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Fetch holdings and SIPs for a single account.
        
        Args:
            account_config: Account configuration dict with name and credentials
            force_login: Force new login even if cached token exists
        
        Returns:
            Tuple of (stock_holdings, mf_holdings, sips)
        """
        try:
            kite = self.auth_manager.authenticate(account_config, force_login)
            stock_holdings, mf_holdings = self.holdings_service.fetch_holdings(kite)
            sips = self.sip_service.fetch_sips(kite)
            return stock_holdings, mf_holdings, sips
        except Exception as e:
            logger.exception("Error fetching data for account %s: %s", 
                           account_config.get('name'), e)
            raise
    
    def fetch_all_accounts_data(
        self, 
        accounts_config: List[Dict[str, Any]], 
        force_login: bool = False
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
        """Fetch holdings and SIPs for all accounts in parallel.
        
        Args:
            accounts_config: List of account configuration dicts
            force_login: Force new login even if cached tokens exist
        
        Returns:
            Tuple of (merged_stock_holdings, merged_mf_holdings, merged_sips, error_message)
            error_message is None if no errors occurred
        """
        all_stock_holdings = [None] * len(accounts_config)
        all_mf_holdings = [None] * len(accounts_config)
        all_sips = [None] * len(accounts_config)
        error_occurred = None
        threads = []

        def _fetch_for_account(idx: int, account_config: Dict[str, Any]):
            """Fetch data for a single account (thread target)."""
            nonlocal error_occurred
            account_name = account_config["name"]
            
            try:
                stock_holdings, mf_holdings, sips = self.fetch_account_data(
                    account_config, force_login
                )
                
                # Add account information to each holding/SIP
                self.holdings_service.add_account_info(stock_holdings, account_name)
                self.holdings_service.add_account_info(mf_holdings, account_name)
                self.sip_service.add_account_info(sips, account_name)
                
                # Store results
                all_stock_holdings[idx] = stock_holdings
                all_mf_holdings[idx] = mf_holdings
                all_sips[idx] = sips
            except Exception as e:
                logger.error("Error fetching holdings for %s: %s", account_name, e)
                error_occurred = str(e)

        # Launch threads for parallel fetching
        for idx, account_config in enumerate(accounts_config):
            t = threading.Thread(
                target=_fetch_for_account, 
                args=(idx, account_config), 
                daemon=True
            )
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Merge results from all accounts
        merged_stocks, merged_mfs = self.holdings_service.merge_holdings(
            all_stock_holdings, all_mf_holdings
        )
        merged_sips = self.sip_service.merge_items(all_sips)

        return merged_stocks, merged_mfs, merged_sips, error_occurred
