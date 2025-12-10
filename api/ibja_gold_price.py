"""
Gold price fetching service from IBJA rates.
"""

import logging
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
from requests.exceptions import RequestException, Timeout, ConnectionError, HTTPError

logger = logging.getLogger(__name__)

try:
    from error_handler import handle_errors, ErrorHandler, NetworkError, APIError
    ERROR_HANDLING_AVAILABLE = True
except ImportError:
    ERROR_HANDLING_AVAILABLE = False
    logger.warning("Centralized error handling not available")


class GoldPriceService:
    """Service for fetching current gold prices from ibjarates.com"""
    
    BASE_URL = "https://ibjarates.com/"
    TIMEOUT = 20
    
    def __init__(self):
        """Initialize the gold price service."""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def fetch_gold_prices(self) -> Optional[Dict[str, any]]:
        """
        Fetch latest available gold prices for different purities.
        
        Returns:
            Dict with 'prices' key, or None if fetch fails
            Prices are per gram in INR.
            Example: {
                'prices': {
                    '999': {'am': 12855.0, 'pm': 12821.0},
                    '995': {'am': 12803.5, 'pm': 12770.0},
                    '916': {'am': 11775.2, 'pm': 11744.0}
                }
            }
        """
        try:
            return self._fetch_gold_prices_impl()
        except Exception as e:
            if ERROR_HANDLING_AVAILABLE:
                wrapped_error = ErrorHandler.wrap_external_api_error(e, "IBJA Gold Price API")
                ErrorHandler.log_error(wrapped_error, context="fetch_gold_prices")
            else:
                logger.error(f"Error fetching gold prices: {e}")
            return None
    
    def _fetch_gold_prices_impl(self) -> Optional[Dict[str, any]]:
        """Internal implementation of gold price fetching."""
        try:
            logger.info(f"Fetching gold prices from {self.BASE_URL}")
            
            response = requests.get(
                self.BASE_URL,
                headers=self.headers,
                timeout=self.TIMEOUT
            )
            
            if response.status_code != 200:
                logger.error(f"IBJA website returned status {response.status_code}")
                return None
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            purities = ['999', '995', '916', '750', '585']
            prices = {}
            
            for purity in purities:
                span_id = f'GoldRatesCompare{purity}'
                span_elem = soup.find('span', id=span_id)
                
                if span_elem:
                    try:
                        price_text = span_elem.get_text(strip=True)
                        price_per_gram = float(price_text)
                        
                        # Store as both AM and PM since the displayed price is current
                        # Prices are per gram
                        prices[purity] = {
                            'am': price_per_gram,
                            'pm': price_per_gram
                        }
                        
                        logger.debug(f"Gold {purity}: ₹{price_per_gram}/gram")
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"Failed to parse price for {purity}: {e}")
                        continue
                else:
                    logger.warning(f"Could not find span element for purity {purity}")
            
            if not prices:
                logger.error("No valid gold prices found in span elements")
                return None
            
            if prices:
                logger.info(f"Successfully fetched prices for {len(prices)} gold purities")
                return {
                    'prices': prices
                }
            else:
                logger.error("No valid gold prices found in table")
                return None
                
        except (Timeout, ConnectionError, HTTPError, RequestException) as e:
            raise
        except Exception as e:
            raise
    
    def get_24k_price(self, time_of_day: str = 'pm') -> Optional[float]:
        """
        Get the current 24K (999 purity) gold price.
        
        Args:
            time_of_day: 'am' or 'pm' (default: 'pm')
        
        Returns:
            Price per gram in INR, or None if unavailable
        """
        result = self.fetch_gold_prices()
        if not result or 'prices' not in result or '999' not in result['prices']:
            return None
        
        time_key = time_of_day.lower()
        if time_key not in ['am', 'pm']:
            logger.warning(f"Invalid time_of_day: {time_of_day}, using 'pm'")
            time_key = 'pm'
        
        return result['prices']['999'].get(time_key)
    
    def get_22k_price(self, time_of_day: str = 'pm') -> Optional[float]:
        """
        Get the current 22K (916 purity) gold price.
        
        Args:
            time_of_day: 'am' or 'pm' (default: 'pm')
        
        Returns:
            Price per gram in INR, or None if unavailable
        """
        result = self.fetch_gold_prices()
        if not result or 'prices' not in result or '916' not in result['prices']:
            return None
        
        time_key = time_of_day.lower()
        if time_key not in ['am', 'pm']:
            logger.warning(f"Invalid time_of_day: {time_of_day}, using 'pm'")
            time_key = 'pm'
        
        return result['prices']['916'].get(time_key)


# Singleton instance
_gold_price_service = None


def get_gold_price_service() -> GoldPriceService:
    """Get or create the singleton gold price service instance."""
    global _gold_price_service
    if _gold_price_service is None:
        _gold_price_service = GoldPriceService()
    return _gold_price_service


if __name__ == '__main__':
    """CLI interface for testing gold price fetching."""
    import sys
    
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    
    service = GoldPriceService()
    
    print("=" * 70)
    print("IBJA Gold Price Fetcher")
    print("=" * 70)
    
    result = service.fetch_gold_prices()
    
    if result and 'prices' in result:
        prices = result['prices']
        
        print(f"\n✅ Successfully fetched gold prices:\n")
        
        # Display all purities
        for purity in sorted(prices.keys(), key=lambda x: int(x), reverse=True):
            am = prices[purity]['am']
            pm = prices[purity]['pm']
            print(f"  Gold {purity} (per gram):")
            print(f"    AM (Opening): ₹{am:,.2f}")
            print(f"    PM (Closing): ₹{pm:,.2f}")
            print()
        
        # Highlight important purities
        print("-" * 70)
        print("\n📊 Key Prices:")
        
        price_24k = service.get_24k_price('pm')
        if price_24k:
            print(f"  24K Gold (999): ₹{price_24k:,.2f} per gram (PM)")
        
        price_22k = service.get_22k_price('pm')
        if price_22k:
            print(f"  22K Gold (916): ₹{price_22k:,.2f} per gram (PM)")
        
        print("\n" + "=" * 70)
    else:
        print("\n❌ Failed to fetch gold prices")
        print("=" * 70)
        sys.exit(1)
