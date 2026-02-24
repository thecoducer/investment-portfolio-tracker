"""
Google Sheets API client for fetching physical gold holdings data.
"""
from typing import Any, Dict, List

from ..constants import GOOGLE_SHEETS_SCOPES, GOOGLE_SHEETS_TIMEOUT
from ..error_handler import (APIError, DataError, ErrorHandler, NetworkError,
                             retry_on_transient_error)
from ..logging_config import logger

try:
    import httplib2
    from google.oauth2 import service_account
    from google_auth_httplib2 import AuthorizedHttp
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False
    logger.warning("Google Sheets API libraries not installed. Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")


class GoogleSheetsClient:
    """Client for fetching data from Google Sheets."""
    
    SCOPES = GOOGLE_SHEETS_SCOPES
    TIMEOUT_SECONDS = GOOGLE_SHEETS_TIMEOUT
    
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


class GoogleSheetsService:
    """Base class for services that fetch and parse data from Google Sheets."""

    entity_name: str = "items"

    def __init__(self, google_sheets_client: GoogleSheetsClient):
        """Initialize service with Google Sheets client."""
        self.client = google_sheets_client

    @staticmethod
    def _safe_get(row: List[Any], index: int, default: Any = '', parser=None) -> Any:
        """Safely get a cell value from a row with optional parsing.

        Args:
            row: Row data from Google Sheets
            index: Column index
            default: Default value if index is out of range
            parser: Optional callable to parse the value

        Returns:
            Parsed cell value, or default if index is out of range
        """
        if len(row) <= index:
            return default
        return parser(row[index]) if parser else row[index]

    def _parse_row(self, row: List[Any], idx: int) -> Dict[str, Any]:
        """Parse a single row. Subclasses must override this."""
        raise NotImplementedError

    def _fetch_and_parse(
        self,
        spreadsheet_id: str,
        range_name: str,
    ) -> List[Dict[str, Any]]:
        """Fetch sheet data and parse rows using the subclass parser.

        Args:
            spreadsheet_id: The Google Sheets spreadsheet ID
            range_name: The A1 notation range to fetch

        Returns:
            List of parsed row dictionaries
        """
        raw_data = self.client.fetch_sheet_data(spreadsheet_id, range_name)

        if not raw_data or len(raw_data) < 2:
            logger.info("No %s data found", self.entity_name)
            return []

        items = []
        for idx, row in enumerate(raw_data[1:], start=2):  # Skip header
            if not row or not any(row):
                continue
            try:
                items.append(self._parse_row(row, idx))
            except Exception as e:
                logger.warning("Error parsing %s row %d: %s", self.entity_name, idx, e)

        logger.info("Parsed %d %s", len(items), self.entity_name)
        return items


class PhysicalGoldService(GoogleSheetsService):
    """Service for managing physical gold holdings data."""

    entity_name = "physical gold holdings"

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
        return self._fetch_and_parse(spreadsheet_id, range_name)

    def _parse_row(self, row: List[Any], idx: int) -> Dict[str, Any]:
        g = self._safe_get
        p = GoogleSheetsClient.parse_number
        return {
            'date': g(row, 0),
            'type': g(row, 1),
            'retail_outlet': g(row, 2),
            'purity': g(row, 3),
            'weight_gms': g(row, 4, 0, p),
            'bought_ibja_rate_per_gm': g(row, 5, 0, p),
            'row_number': idx,
        }


class FixedDepositsService(GoogleSheetsService):
    """Service for managing fixed deposits data."""

    entity_name = "fixed deposits"

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
        return self._fetch_and_parse(spreadsheet_id, range_name)

    def _parse_row(self, row: List[Any], idx: int) -> Dict[str, Any]:
        g = self._safe_get
        p = GoogleSheetsClient.parse_number
        b = GoogleSheetsClient.parse_yes_no

        deposit = {
            'original_investment_date': g(row, 0),
            'reinvested_date': g(row, 1),
            'bank_name': g(row, 2),
            'deposit_year': g(row, 3, 0, p),
            'deposit_month': g(row, 4, 0, p),
            'deposit_day': g(row, 5, 0, p),
            'original_amount': g(row, 6, 0, p),
            'reinvested_amount': g(row, 7, 0, p),
            'interest_rate': g(row, 8, 0, p),
            'redeemed': g(row, 9, False, b),
            'account': g(row, 10),
        }

        # Validate required fields
        if not deposit['bank_name']:
            raise DataError("Missing bank name in fixed deposit row")

        if deposit['interest_rate'] <= 0:
            raise DataError(f"Invalid interest rate for deposit at {deposit['bank_name']}")

        return deposit
