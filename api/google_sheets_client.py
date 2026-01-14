"""
Google Sheets API client for fetching physical gold holdings data.
"""
from typing import List, Dict, Any, Optional
from logging_config import logger
from error_handler import retry_on_transient_error, ErrorHandler, APIError, NetworkError, DataError

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    import httplib2
    from google_auth_httplib2 import AuthorizedHttp
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False
    logger.warning("Google Sheets API libraries not installed. Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")


class GoogleSheetsClient:
    """Client for fetching data from Google Sheets."""
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    TIMEOUT_SECONDS = 20
    
    def __init__(self, credentials_file: str = None):
        """Initialize Google Sheets client.
        
        Args:
            credentials_file: Path to service account credentials JSON file
        """
        if not GOOGLE_SHEETS_AVAILABLE:
            raise ImportError("Google Sheets libraries not installed")
        
        if not credentials_file:
            raise ValueError("Credentials file is required")
            
        self.credentials_file = credentials_file
        self.credentials = None
        self.service = None
    
    def authenticate(self) -> bool:
        """Authenticate with Google Sheets API using service account.
        
        Returns:
            True if authentication successful
            
        Raises:
            Exception: If authentication fails
        """
        try:
            if not self.credentials:
                self.credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_file, 
                    scopes=self.SCOPES
                )
            
            # Create fresh HTTP client for each authentication to avoid SSL issues
            http = httplib2.Http(timeout=self.TIMEOUT_SECONDS, cache=None)
            authorized_http = AuthorizedHttp(self.credentials, http=http)
            
            self.service = build('sheets', 'v4', http=authorized_http, cache_discovery=False)
            logger.info("Successfully authenticated with Google Sheets API")
            return True
        except Exception as e:
            logger.exception("Failed to authenticate with Google Sheets")
            raise
    
    def fetch_sheet_data(
        self, 
        spreadsheet_id: str, 
        range_name: str,
        max_retries: int = 2
    ) -> List[List[Any]]:
        """Fetch data from a Google Sheet with retry logic.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            range_name: The A1 notation range (e.g., 'Sheet1!A1:K100')
            max_retries: Maximum retry attempts
        
        Returns:
            List of rows, where each row is a list of cell values
            
        Raises:
            Exception: If fetch fails after retries
        """
        # Re-authenticate before each fetch to get fresh HTTP connection
        self.authenticate()
        
        @retry_on_transient_error(max_retries=max_retries, delay=1.0)
        def _fetch():
            return self._fetch_sheet_data_impl(spreadsheet_id, range_name)
        
        try:
            return _fetch()
        except Exception as e:
            ErrorHandler.log_error(e, context=f"Fetching Google Sheets range {range_name}")
            raise
    
    def _fetch_sheet_data_impl(self, spreadsheet_id: str, range_name: str) -> List[List[Any]]:
        """Internal implementation of sheet data fetching.
        
        Raises:
            APIError: For HTTP errors
            NetworkError: For network/connection errors
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            logger.info("Fetched %d rows from Google Sheets range %s", len(values), range_name)
            return values
            
        except HttpError as e:
            if hasattr(e, 'resp') and e.resp.status >= 500:
                raise APIError(f"Google Sheets API transient error", status_code=e.resp.status, original_error=e)
            else:
                raise APIError(f"Google Sheets API error", status_code=e.resp.status if hasattr(e, 'resp') else None, original_error=e)
                
        except OSError as e:
            if e.errno == 49:
                logger.warning("Network port exhaustion - usually temporary")
            raise NetworkError(f"Network connection error: {e}", original_error=e)
            
        except Exception as e:
            logger.exception("Unexpected error fetching Google Sheets data")
            raise
    
    @staticmethod
    def parse_number(value: Any) -> float:
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
        
        if isinstance(value, str):
            cleaned = value.strip().replace('₹', '').replace(',', '').replace('%', '').replace(' ', '')
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        
        return 0.0
    
    @staticmethod
    def parse_yes_no(value: Any) -> bool:
        """Parse a cell value to boolean for Yes/No fields.
        
        Args:
            value: Cell value (e.g., 'Yes', 'No', 'Y', 'N')
        
        Returns:
            True if 'Yes', False otherwise
        """
        if value is None or value == '':
            return False
        
        if isinstance(value, str):
            return value.strip().lower() in ['yes', 'y', 'true', '1']
        
        return False


class PhysicalGoldService:
    """Service for managing physical gold holdings data."""
    
    def __init__(self, google_sheets_client: GoogleSheetsClient):
        """Initialize service with Google Sheets client."""
        self.client = google_sheets_client
    
    def fetch_holdings(
        self, 
        spreadsheet_id: str, 
        range_name: str = 'Sheet1!A:F'
    ) -> List[Dict[str, Any]]:
        """Fetch physical gold holdings from Google Sheets.
        
        Expected columns: Date, Type, Retail Outlet, Purity, Weight (gms), IBJA Rate
        
        Args:
            spreadsheet_id: The Google Sheets spreadsheet ID
            range_name: The range to fetch (default: Sheet1!A:F)
        
        Returns:
            List of physical gold holdings
        """
        raw_data = self.client.fetch_sheet_data(spreadsheet_id, range_name)
        
        if not raw_data or len(raw_data) < 2:
            logger.info("No physical gold data found")
            return []
        
        data_rows = raw_data[1:]  # Skip header
        holdings = []
        
        for idx, row in enumerate(data_rows, start=2):
            if not row or not any(row):
                continue
            
            try:
                holding = {
                    'date': row[0] if len(row) > 0 else '',
                    'type': row[1] if len(row) > 1 else '',
                    'retail_outlet': row[2] if len(row) > 2 else '',
                    'purity': row[3] if len(row) > 3 else '',
                    'weight_gms': GoogleSheetsClient.parse_number(row[4]) if len(row) > 4 else 0,
                    'bought_ibja_rate_per_gm': GoogleSheetsClient.parse_number(row[5]) if len(row) > 5 else 0,
                    'row_number': idx
                }
                holdings.append(holding)
            except Exception as e:
                logger.warning("Error parsing physical gold row %d: %s", idx, e)
        
        logger.info("Parsed %d physical gold holdings", len(holdings))
        return holdings


class FixedDepositsService:
    """Service for managing fixed deposits data."""
    
    def __init__(self, google_sheets_client: GoogleSheetsClient):
        """Initialize service with Google Sheets client."""
        self.client = google_sheets_client
    
    def fetch_deposits(
        self, 
        spreadsheet_id: str, 
        range_name: str = 'FixedDeposits!A:K'
    ) -> List[Dict[str, Any]]:
        """Fetch fixed deposits from Google Sheets.
        
        Expected columns: Deposited On, Where, Year, Month, Day, Till, 
                         Amount, Interest Rate, Maturity Amount, Redeemed?, Account
        
        Args:
            spreadsheet_id: The Google Sheets spreadsheet ID
            range_name: The range to fetch (default: FixedDeposits!A:K)
        
        Returns:
            List of fixed deposits
        """
        raw_data = self.client.fetch_sheet_data(spreadsheet_id, range_name)
        
        if not raw_data or len(raw_data) < 2:
            logger.info("No fixed deposits data found")
            return []
        
        data_rows = raw_data[1:]  # Skip header
        deposits = []
        
        for idx, row in enumerate(data_rows, start=2):
            if not row or not any(row):
                continue
            
            try:
                deposit = self._parse_deposit_row(row)
                deposits.append(deposit)
            except Exception as e:
                logger.warning("Error parsing fixed deposit row %d: %s", idx, e)
        
        logger.info("Parsed %d fixed deposits", len(deposits))
        return deposits
    
    def _parse_deposit_row(self, row: List[Any]) -> Dict[str, Any]:
        """Parse a single fixed deposit row.
        
        Args:
            row: Row data from Google Sheets
        
        Returns:
            Parsed deposit dictionary
            
        Raises:
            DataError: If required fields are missing or invalid
        """
        parse_num = GoogleSheetsClient.parse_number
        parse_bool = GoogleSheetsClient.parse_yes_no
        
        deposit = {
            'original_investment_date': row[0] if len(row) > 0 else '',
            'reinvested_date': row[1] if len(row) > 1 else '',
            'bank_name': row[2] if len(row) > 1 else '',
            'deposit_year': parse_num(row[3]) if len(row) > 2 else 0,
            'deposit_month': parse_num(row[4]) if len(row) > 3 else 0,
            'deposit_day': parse_num(row[5]) if len(row) > 4 else 0,
            'original_amount': parse_num(row[6]) if len(row) > 5 else '',
            'reinvested_amount': parse_num(row[7]) if len(row) > 6 else 0,
            'interest_rate': parse_num(row[8]) if len(row) > 7 else 0,
            'redeemed': parse_bool(row[9]) if len(row) > 9 else False,
            'account': row[10] if len(row) > 10 else ''
        }
        
        # Validate required fields
        if not deposit['bank_name']:
            raise DataError("Missing bank name in fixed deposit row")
        
        if deposit['interest_rate'] <= 0:
            raise DataError(f"Invalid interest rate for deposit at {deposit['bank_name']}")
        
        return deposit
