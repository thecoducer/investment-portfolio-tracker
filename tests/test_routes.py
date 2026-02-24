"""
Unit tests for routes.py (Flask route definitions).
"""
import json
import unittest
from unittest.mock import PropertyMock, patch

from app.routes import _create_json_response_no_cache, app_callback, app_ui


class TestCallbackServer(unittest.TestCase):
    """Test callback server endpoints."""

    def setUp(self):
        self.client = app_callback.test_client()
        app_callback.testing = True

    def test_callback_success(self):
        """Test successful OAuth callback."""
        with patch('app.routes.auth_manager.set_request_token') as mock_set_token:
            response = self.client.get('/callback?request_token=test_token_123')

            self.assertEqual(response.status_code, 200)
            mock_set_token.assert_called_once_with('test_token_123')
            self.assertIn(b'success', response.data.lower())

    def test_callback_error(self):
        """Test OAuth callback without request token."""
        response = self.client.get('/callback')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'error', response.data.lower())


class TestUIServerRoutes(unittest.TestCase):
    """Test UI server endpoints."""

    def setUp(self):
        self.client = app_ui.test_client()
        app_ui.testing = True

    def test_status_endpoint(self):
        """Test /status endpoint returns correct structure."""
        with patch('app.services.state_manager') as mock_state, \
             patch('app.services.session_manager') as mock_session, \
             patch('app.services.format_timestamp') as mock_format, \
             patch('app.services.is_market_open_ist') as mock_market, \
             patch('app.services.app_config') as mock_config:

            mock_config.accounts = []
            type(mock_state).last_error = PropertyMock(return_value=None)
            type(mock_state).portfolio_state = PropertyMock(return_value='updated')
            type(mock_state).nifty50_state = PropertyMock(return_value='updated')
            type(mock_state).physical_gold_state = PropertyMock(return_value='updated')
            type(mock_state).fixed_deposits_state = PropertyMock(return_value='updated')
            type(mock_state).portfolio_last_updated = PropertyMock(return_value=None)
            type(mock_state).nifty50_last_updated = PropertyMock(return_value=None)
            type(mock_state).physical_gold_last_updated = PropertyMock(return_value=None)
            type(mock_state).fixed_deposits_last_updated = PropertyMock(return_value=None)
            type(mock_state).waiting_for_login = PropertyMock(return_value=False)

            mock_session.get_validity.return_value = {}
            mock_format.return_value = None
            mock_market.return_value = False

            response = self.client.get('/status')

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('portfolio_state', data)
            self.assertIn('session_validity', data)
            self.assertEqual(response.headers.get('Cache-Control'), 'no-cache, no-store, must-revalidate')

    def test_stocks_data_endpoint(self):
        """Test /stocks_data endpoint returns sorted stocks."""
        from app.cache import cache
        original = cache.stocks
        try:
            cache.stocks = [
                {"tradingsymbol": "INFY", "quantity": 10},
                {"tradingsymbol": "TCS", "quantity": 5},
            ]
            response = self.client.get('/stocks_data')

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["tradingsymbol"], "INFY")
        finally:
            cache.stocks = original

    def test_mf_holdings_data_endpoint(self):
        """Test /mf_holdings_data endpoint returns sorted MF holdings."""
        from app.cache import cache
        original = cache.mf_holdings
        try:
            cache.mf_holdings = [
                {"tradingsymbol": "MF2", "fund": "Fund B", "quantity": 100},
                {"tradingsymbol": "MF1", "fund": "Fund A", "quantity": 200},
            ]
            response = self.client.get('/mf_holdings_data')

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["fund"], "Fund A")
        finally:
            cache.mf_holdings = original

    def test_sips_data_endpoint(self):
        """Test /sips_data endpoint returns sorted SIPs."""
        from app.cache import cache
        original = cache.sips
        try:
            cache.sips = [
                {"tradingsymbol": "SIP2", "status": "inactive"},
                {"tradingsymbol": "SIP1", "status": "active"},
            ]
            response = self.client.get('/sips_data')

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["status"], "active")
        finally:
            cache.sips = original

    def test_portfolio_page(self):
        """Test root page renders."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'html', response.data.lower())
        # ensure gold card displays subtitle and toggle control
        self.assertIn(b'(ETFs + Physical)', response.data)
        self.assertIn(b'id="gold_breakdown_toggle"', response.data)
        # ensure toggle contains structural span for CSS graphic
        self.assertIn(b'class="icon-bar"', response.data)
        # toggle should no longer be an emoji
        self.assertNotIn(b'\xf0\x9f\x94\x80', response.data)  # not 🔀 or 📊 etc

    def test_nifty50_page(self):
        """Test /nifty50 page renders."""
        response = self.client.get('/nifty50')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'html', response.data.lower())

    def test_refresh_route_success(self):
        """Test /refresh endpoint triggers refresh."""
        with patch('app.cache.fetch_in_progress') as mock_event, \
             patch('app.fetchers.run_background_fetch') as mock_fetch, \
             patch('app.services.session_manager') as mock_session, \
             patch('app.services.app_config') as mock_config:

            mock_config.accounts = [{"name": "test"}]
            mock_event.is_set.return_value = False
            mock_session.is_valid.return_value = True

            response = self.client.post('/refresh')

            self.assertEqual(response.status_code, 202)
            data = json.loads(response.data)
            self.assertEqual(data['status'], 'started')
            mock_fetch.assert_called_once_with(force_login=False, is_manual=True)

    def test_refresh_route_conflict(self):
        """Test /refresh returns conflict when fetch in progress."""
        from app.cache import fetch_in_progress
        fetch_in_progress.set()
        try:
            response = self.client.post('/refresh')

            self.assertEqual(response.status_code, 409)
            data = json.loads(response.data)
            self.assertIn('error', data)
        finally:
            fetch_in_progress.clear()

    def test_refresh_route_needs_login(self):
        """Test /refresh detects expired sessions."""
        with patch('app.cache.fetch_in_progress') as mock_event, \
             patch('app.fetchers.run_background_fetch') as mock_fetch, \
             patch('app.services.session_manager') as mock_session, \
             patch('app.services.app_config') as mock_config:

            mock_config.accounts = [{"name": "test"}]
            mock_event.is_set.return_value = False
            mock_session.is_valid.return_value = False

            response = self.client.post('/refresh')

            self.assertEqual(response.status_code, 202)
            data = json.loads(response.data)
            self.assertTrue(data['needs_login'])
            mock_fetch.assert_called_once_with(force_login=True, is_manual=True)


class TestSSE(unittest.TestCase):
    """Test Server-Sent Events functionality."""

    def setUp(self):
        self.client = app_ui.test_client()
        app_ui.testing = True

    def test_events_endpoint(self):
        """Test /events SSE endpoint."""
        with patch('app.services.state_manager') as mock_state, \
             patch('app.services.session_manager') as mock_session, \
             patch('app.services.format_timestamp') as mock_format, \
             patch('app.services.is_market_open_ist') as mock_market, \
             patch('app.services.app_config') as mock_config:

            mock_config.accounts = []
            type(mock_state).last_error = PropertyMock(return_value=None)
            type(mock_state).portfolio_state = PropertyMock(return_value='updated')
            type(mock_state).nifty50_state = PropertyMock(return_value='updated')
            type(mock_state).physical_gold_state = PropertyMock(return_value='updated')
            type(mock_state).fixed_deposits_state = PropertyMock(return_value='updated')
            type(mock_state).portfolio_last_updated = PropertyMock(return_value=None)
            type(mock_state).nifty50_last_updated = PropertyMock(return_value=None)
            type(mock_state).physical_gold_last_updated = PropertyMock(return_value=None)
            type(mock_state).fixed_deposits_last_updated = PropertyMock(return_value=None)
            type(mock_state).waiting_for_login = PropertyMock(return_value=False)

            mock_session.get_validity.return_value = {}
            mock_format.return_value = None
            mock_market.return_value = True

            response = self.client.get('/events')

            self.assertEqual(response.status_code, 200)
            self.assertIn('text/event-stream', response.content_type)
            self.assertEqual(response.headers.get('Cache-Control'), 'no-cache')


class TestCreateJsonResponseNoCache(unittest.TestCase):
    """Test the _create_json_response_no_cache helper."""

    def test_without_sorting(self):
        data = [
            {"name": "B", "value": 2},
            {"name": "A", "value": 1},
            {"name": "C", "value": 3},
        ]

        with app_ui.app_context():
            response = _create_json_response_no_cache(data)
            self.assertEqual(response.headers.get('Cache-Control'), 'no-cache, no-store, must-revalidate')

    def test_with_sorting(self):
        data = [
            {"name": "B", "value": 2},
            {"name": "A", "value": 1},
            {"name": "C", "value": 3},
        ]

        with app_ui.app_context():
            response = _create_json_response_no_cache(data, sort_key="name")
            result_data = json.loads(response.data)
            self.assertEqual(result_data[0]["name"], "A")
            self.assertEqual(result_data[1]["name"], "B")
            self.assertEqual(result_data[2]["name"], "C")


if __name__ == '__main__':
    unittest.main()
