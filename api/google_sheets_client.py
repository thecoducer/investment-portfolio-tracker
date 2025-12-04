"""
Google Sheets API client for fetching physical gold holdings data.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from logging_config import logger

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False
    logger.warning("Google Sheets API libraries not installed. Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")

try:
    from error_handler import retry_on_transient_error, ErrorHandler, APIError, NetworkError
    ERROR_HANDLING_AVAILABLE = True
except ImportError:
    ERROR_HANDLING_AVAILABLE = False


class GoogleSheetsClient:
    """Client for fetching data from Google Sheets."""
    
    # Define the scopes required for reading Google Sheets
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    
    def __init__(self, credentials_file: str = None):
        """Initialize Google Sheets client.
        
        Args:
            credentials_file: Path to service account credentials JSON file
        """
        self.credentials_file = credentials_file
        self.service = None
        
        if not GOOGLE_SHEETS_AVAILABLE:
            logger.warning("Google Sheets client initialized but required libraries are not available")
    
    def authenticate(self) -> bool:
        """Authenticate with Google Sheets API using service account.
        
        Returns:
            True if authentication successful, False otherwise
        """
        if not GOOGLE_SHEETS_AVAILABLE:
            logger.error("Cannot authenticate: Google Sheets libraries not installed")
            return False
        
        if not self.credentials_file:
            logger.error("No credentials file provided for Google Sheets authentication")
            return False
        
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_file, 
                scopes=self.SCOPES
            )
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Successfully authenticated with Google Sheets API")
            return True
        except Exception as e:
            logger.exception("Failed to authenticate with Google Sheets: %s", e)
            return False
    
    def fetch_sheet_data(
        self, 
        spreadsheet_id: str, 
        range_name: str,
        max_retries: int = 2
    ) -> Optional[List[List[Any]]]:
        """Fetch data from a Google Sheet with retry logic.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet (from the URL)
            range_name: The A1 notation range (e.g., 'Sheet1!A1:K100')
            max_retries: Maximum number of retry attempts for transient failures
        
        Returns:
            List of rows, where each row is a list of cell values.
            Returns None if fetch fails.
        """
        if not self.service:
            if not self.authenticate():
                return None
        
        if ERROR_HANDLING_AVAILABLE:
            try:
                @retry_on_transient_error(max_retries=max_retries, delay=1.0)
                def _fetch_with_retry():
                    return self._fetch_sheet_data_impl(spreadsheet_id, range_name)
                
                return _fetch_with_retry()
            except Exception as e:
                ErrorHandler.log_error(e, context="Google Sheets fetch")
                return None
        else:
            # Fallback to manual retry
            return self._fetch_sheet_data_impl(spreadsheet_id, range_name)
    
    def _fetch_sheet_data_impl(self, spreadsheet_id: str, range_name: str) -> Optional[List[List[Any]]]:
        """Internal implementation of sheet data fetching."""
        try:
            sheet = self.service.spreadsheets()
            result = sheet.values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                logger.info("No data found in sheet range: %s", range_name)
                return []
            
            logger.info("Fetched %d rows from Google Sheets", len(values))
            return values
            
        except HttpError as e:
            # Check if it's a transient error (5xx) or permanent (4xx)
            if hasattr(e, 'resp') and e.resp.status >= 500:
                # Transient error - raise to trigger retry
                if ERROR_HANDLING_AVAILABLE:
                    raise APIError(f"Google Sheets API error (transient)", status_code=e.resp.status, original_error=e)
                raise
            else:
                # Permanent error (4xx) - log and return None
                logger.error("Google Sheets API error (permanent): %s", e)
                return None
        except OSError as e:
            # Handle network-level errors (port exhaustion, connection issues, etc.)
            if e.errno == 49:  # Can't assign requested address
                logger.warning("Network error (port exhaustion or connection issue): %s - This is usually temporary", e)
            else:
                logger.warning("Network OS error: %s", e)
            # Raise to trigger retry mechanism
            if ERROR_HANDLING_AVAILABLE:
                raise NetworkError(f"Network connection error: {e}", original_error=e)
            raise
        except Exception as e:
            logger.exception("Error fetching data from Google Sheets: %s", e)
            raise
    
    def parse_physical_gold_data(
        self, 
        spreadsheet_id: str, 
        range_name: str = 'Sheet1!A:F'
    ) -> List[Dict[str, Any]]:
        """Fetch and parse physical gold holdings from Google Sheets.
        
        Expected columns:
        A: Date
        B: Type (Coin/Jewellery)
        C: Retail Outlet
        D: Purity
        E: Weight in gms
        F: IBJA PM rate per 1 gm
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            range_name: The range to fetch (default: entire sheet A:F)
        
        Returns:
            List of dictionaries with parsed gold holdings
        """
        raw_data = self.fetch_sheet_data(spreadsheet_id, range_name)
        
        if raw_data is None:
            return []
        
        if not raw_data or len(raw_data) < 2:
            logger.warning("Sheet has no data rows (only header or empty)")
            return []
        
        headers = raw_data[0]
        data_rows = raw_data[1:]
        
        holdings = []
        
        for idx, row in enumerate(data_rows, start=2):  # Start at 2 (row 1 is header)
            if not row or all(cell == '' for cell in row):
                continue
            
            try:
                while len(row) < 6:
                    row.append('')
                
                holding = {
                    'date': row[0] if len(row) > 0 else '',
                    'type': row[1] if len(row) > 1 else '',
                    'retail_outlet': row[2] if len(row) > 2 else '',
                    'purity': row[3] if len(row) > 3 else '',
                    'weight_gms': self._parse_number(row[4]) if len(row) > 4 else 0,
                    'bought_ibja_rate_per_gm': self._parse_number(row[5]) if len(row) > 5 else 0,
                    'row_number': idx
                }
                
                holdings.append(holding)
                
            except Exception as e:
                logger.warning("Error parsing row %d: %s", idx, e)
                continue
        
        logger.info("Parsed %d physical gold holdings from Google Sheets", len(holdings))
        return holdings
    
    def _parse_number(self, value: Any) -> float:
        """Parse a cell value to float, handling various formats.
        
        Args:
            value: Cell value (could be string, number, or empty)
        
        Returns:
            Parsed float value, or 0 if parsing fails
        """
        if value is None or value == '':
            return 0.0
        
        if isinstance(value, (int, float)):
            return float(value)
        
        # Remove currency symbols, commas, and whitespace
        if isinstance(value, str):
            cleaned = value.strip().replace('₹', '').replace(',', '').replace(' ', '')
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        
        return 0.0


class PhysicalGoldService:
    """Service for managing physical gold holdings data."""
    
    def __init__(self, google_sheets_client: GoogleSheetsClient):
        """Initialize service with Google Sheets client.
        
        Args:
            google_sheets_client: Authenticated GoogleSheetsClient instance
        """
        self.client = google_sheets_client
    
    def fetch_holdings(
        self, 
        spreadsheet_id: str, 
        range_name: str = 'Sheet1!A:F'
    ) -> List[Dict[str, Any]]:
        """Fetch physical gold holdings from Google Sheets.
        
        Args:
            spreadsheet_id: The Google Sheets spreadsheet ID
            range_name: The range to fetch (default: Sheet1!A:F)
        
        Returns:
            List of physical gold holdings with calculated P/L
        """
        holdings = self.client.parse_physical_gold_data(spreadsheet_id, range_name)
        
        # Calculate P/L for each holding (placeholder for now)
        for holding in holdings:
            # P/L calculation can be added later when you have current gold prices
            # For now, set to 0
            holding['current_value'] = 0
            holding['pl'] = 0
            holding['pl_pct'] = 0
        
        return holdings
    
    def calculate_totals(self, holdings: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate total investment and other metrics.
        
        Args:
            holdings: List of physical gold holdings
        
        Returns:
            Dictionary with total metrics
        """
        total_weight = sum(h.get('weight_gms', 0) for h in holdings)
        total_current_value = sum(h.get('current_value', 0) for h in holdings)
        total_pl = sum(h.get('pl', 0) for h in holdings)
        
        # Calculate invested based on IBJA rates
        total_invested = sum(
            h.get('weight_gms', 0) * h.get('bought_ibja_rate_per_gm', 0) 
            for h in holdings
        )
        total_pl_pct = (total_pl / total_invested * 100) if total_invested > 0 else 0
        
        return {
            'total_weight_gms': total_weight,
            'total_invested': total_invested,
            'total_current_value': total_current_value,
            'total_pl': total_pl,
            'total_pl_pct': total_pl_pct,
            'count': len(holdings)
        }
