"""
Unit tests for server.py
"""
import unittest
from unittest.mock import Mock, MagicMock, patch, call, PropertyMock
import json
import threading
import time
from queue import Queue

from server import (
    app_callback, app_ui,
    broadcast_state_change,
    zerodha_client,
    run_background_fetch,
    start_server
)


class TestCallbackServer(unittest.TestCase):
    """Test callback server endpoints"""
    
    def setUp(self):
        """Set up test client"""
        self.client = app_callback.test_client()
        app_callback.testing = True
    
    def test_callback_success(self):
        """Test successful OAuth callback"""
        with patch('server.auth_manager.set_request_token') as mock_set_token:
            response = self.client.get('/callback?request_token=test_token_123')
            
            self.assertEqual(response.status_code, 200)
            mock_set_token.assert_called_once_with('test_token_123')
            self.assertIn(b'success', response.data.lower())
    
    def test_callback_error(self):
        """Test OAuth callback without request token"""
        response = self.client.get('/callback')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'error', response.data.lower())


class TestUIServerRoutes(unittest.TestCase):
    """Test UI server endpoints"""
    
    def setUp(self):
        """Set up test client"""
        self.client = app_ui.test_client()
        app_ui.testing = True
    
    def test_status_endpoint(self):
        """Test /status endpoint returns correct structure"""
        with patch('server.state_manager') as mock_state, \
             patch('server.session_manager') as mock_session, \
             patch('server.format_timestamp') as mock_format, \
             patch('server.is_market_open_ist') as mock_market, \
             patch.object(__import__('server', fromlist=['app_config']).app_config, 'accounts', []):
            
            # Mock state properties as actual attributes
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
    
    def test_holdings_data_endpoint(self):
        """Test /holdings_data endpoint"""
        with patch.object(__import__('server', fromlist=['cache']).cache, 'holdings', [
            {"tradingsymbol": "INFY", "quantity": 10},
            {"tradingsymbol": "TCS", "quantity": 5}
        ]):
            response = self.client.get('/holdings_data')
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(len(data), 2)
            # Check sorted by tradingsymbol
            self.assertEqual(data[0]["tradingsymbol"], "INFY")
    
    def test_mf_holdings_data_endpoint(self):
        """Test /mf_holdings_data endpoint"""
        with patch.object(__import__('server', fromlist=['cache']).cache, 'mf_holdings', [
            {"tradingsymbol": "MF2", "fund": "Fund B", "quantity": 100},
            {"tradingsymbol": "MF1", "fund": "Fund A", "quantity": 200}
        ]):
            response = self.client.get('/mf_holdings_data')
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(len(data), 2)
            # Check sorted by 'fund' field
            self.assertEqual(data[0]["fund"], "Fund A")
    
    def test_sips_data_endpoint(self):
        """Test /sips_data endpoint"""
        with patch.object(__import__('server', fromlist=['cache']).cache, 'sips', [
            {"tradingsymbol": "SIP2", "status": "inactive"},
            {"tradingsymbol": "SIP1", "status": "active"}
        ]):
            response = self.client.get('/sips_data')
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(len(data), 2)
            # Check sorted by status (active comes before inactive alphabetically)
            self.assertEqual(data[0]["status"], "active")
    
    def test_holdings_page(self):
        """Test /holdings page renders"""
        response = self.client.get('/holdings')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'html', response.data.lower())
    
    def test_refresh_route_success(self):
        """Test /refresh endpoint triggers refresh"""
        with patch('server.fetch_in_progress') as mock_event, \
             patch('server.run_background_fetch') as mock_fetch, \
             patch('server.session_manager.is_valid') as mock_valid, \
             patch.object(__import__('server', fromlist=['app_config']).app_config, 'accounts', [{"name": "test"}]):
            
            mock_event.is_set.return_value = False
            mock_valid.return_value = True
            
            response = self.client.post('/refresh')
            
            self.assertEqual(response.status_code, 202)
            data = json.loads(response.data)
            self.assertEqual(data['status'], 'started')
            mock_fetch.assert_called_once_with(force_login=False, is_manual=True)
    
    def test_refresh_route_conflict(self):
        """Test /refresh returns conflict when fetch in progress"""
        with patch('server.fetch_in_progress') as mock_event:
            mock_event.is_set.return_value = True
            
            response = self.client.post('/refresh')
            
            self.assertEqual(response.status_code, 409)
            data = json.loads(response.data)
            self.assertIn('error', data)
    
    def test_refresh_route_needs_login(self):
        """Test /refresh detects expired sessions"""
        with patch('server.fetch_in_progress') as mock_event, \
             patch('server.run_background_fetch') as mock_fetch, \
             patch('server.session_manager.is_valid') as mock_valid, \
             patch.object(__import__('server', fromlist=['app_config']).app_config, 'accounts', [{"name": "test"}]):
            
            mock_event.is_set.return_value = False
            mock_valid.return_value = False  # Session expired
            
            response = self.client.post('/refresh')
            
            self.assertEqual(response.status_code, 202)
            data = json.loads(response.data)
            self.assertTrue(data['needs_login'])
            mock_fetch.assert_called_once_with(force_login=True, is_manual=True)


class TestSSE(unittest.TestCase):
    """Test Server-Sent Events functionality"""
    
    def setUp(self):
        """Set up test client"""
        self.client = app_ui.test_client()
        app_ui.testing = True
    
    def test_events_endpoint(self):
        """Test /events SSE endpoint"""
        with patch('server.state_manager') as mock_state, \
             patch('server.session_manager') as mock_session, \
             patch('server.format_timestamp') as mock_format, \
             patch('server.is_market_open_ist') as mock_market, \
             patch.object(__import__('server', fromlist=['app_config']).app_config, 'accounts', []):
            
            # Mock all state properties as actual attributes
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
    
    def test_broadcast_state_change(self):
        """Test broadcast_state_change sends to all clients"""
        from server import broadcast_state_change
        
        with patch('server.sse_manager.clients', []) as mock_clients, \
             patch('server.state_manager') as mock_state, \
             patch('server.session_manager') as mock_session, \
             patch('server.format_timestamp') as mock_format, \
             patch('server.is_market_open_ist') as mock_market, \
             patch.object(__import__('server', fromlist=['app_config']).app_config, 'accounts', []):
            
            # Mock state using PropertyMock for attributes
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
            
            # Add mock clients
            queue1 = Queue()
            queue2 = Queue()
            mock_clients.extend([queue1, queue2])
            
            # Trigger broadcast
            broadcast_state_change()
            
            # Check messages sent to queues
            self.assertFalse(queue1.empty())
            self.assertFalse(queue2.empty())
            
            msg1 = json.loads(queue1.get_nowait())
            msg2 = json.loads(queue2.get_nowait())
            
            self.assertEqual(msg1['portfolio_state'], 'updated')
            self.assertEqual(msg2['portfolio_state'], 'updated')


class TestDataFetching(unittest.TestCase):
    """Test data fetching functions"""
    def test_fetch_account_holdings(self):
        """Test fetch_account_holdings function"""
        with patch('server.auth_manager.authenticate') as mock_auth, \
             patch('server.holdings_service.fetch_holdings') as mock_holdings, \
             patch('server.sip_service.fetch_sips') as mock_sips:
            
            mock_kite = Mock()
            mock_auth.return_value = mock_kite
            mock_holdings.return_value = ([{"stock": 1}], [{"mf": 1}])
            mock_sips.return_value = [{"sip": 1}]
            
            account_config = {"name": "test", "api_key_env": "TEST_KEY"}
            stocks, mfs, sips = zerodha_client.fetch_account_data(account_config)
            
            mock_auth.assert_called_once_with(account_config, False)
            mock_holdings.assert_called_once_with(mock_kite)
            mock_sips.assert_called_once_with(mock_kite)
            self.assertEqual(len(stocks), 1)
            self.assertEqual(len(mfs), 1)
            self.assertEqual(len(sips), 1)
    
    def test_fetch_account_holdings_force_login(self):
        """Test fetch_account_holdings with force_login"""
        with patch('server.auth_manager.authenticate') as mock_auth, \
             patch('server.holdings_service.fetch_holdings') as mock_holdings, \
             patch('server.sip_service.fetch_sips') as mock_sips:
            
            mock_auth.return_value = Mock()
            mock_holdings.return_value = ([], [])
            mock_sips.return_value = []
            
            account_config = {"name": "test"}
            zerodha_client.fetch_account_data(account_config, force_login=True)
            
            mock_auth.assert_called_once_with(account_config, True)
    
    def test_run_background_fetch(self):
        """Test run_background_fetch starts background threads"""
        with patch('server.threading.Thread') as mock_thread:
            mock_thread_instance = Mock()
            mock_thread.return_value = mock_thread_instance
            
            run_background_fetch(force_login=False)
            
            # Verify a thread was created and started
            mock_thread.assert_called()
            mock_thread_instance.start.assert_called_once()


class TestServerManagement(unittest.TestCase):
    """Test server management functions"""
    
    def test_start_server(self):
        """Test start_server creates daemon thread"""
        mock_app = Mock()
        mock_app.run = Mock()
        
        thread = start_server(mock_app, '127.0.0.1', 8000)
        
        self.assertIsInstance(thread, threading.Thread)
        self.assertTrue(thread.daemon)
        
        # Give thread time to start
        time.sleep(0.6)
        
        mock_app.run.assert_called_once_with(
            host='127.0.0.1',
            port=8000,
            debug=False,
            use_reloader=False
        )


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions"""
    
    def test_build_status_response(self):
        """Test _build_status_response helper"""
        from server import _build_status_response
        
        with patch('server.state_manager') as mock_state, \
             patch('server.session_manager') as mock_session, \
             patch('server.format_timestamp') as mock_format, \
             patch('server.is_market_open_ist') as mock_market:
            
            mock_state.last_error = "Test error"
            mock_state.portfolio_state = 'updated'
            mock_state.nifty50_state = 'updating'
            mock_state.portfolio_last_updated = 1234567890.0
            mock_state.nifty50_last_updated = None
            mock_format.side_effect = lambda x: f"formatted_{x}" if x else None
            mock_session.get_validity.return_value = {"Account1": True}
            mock_market.return_value = True
            
            response = _build_status_response()
            
            self.assertEqual(response['last_error'], "Test error")
            self.assertEqual(response['portfolio_state'], 'updated')
            self.assertEqual(response['nifty50_state'], 'updating')
            self.assertEqual(response['portfolio_last_updated'], 'formatted_1234567890.0')
            self.assertIsNone(response['nifty50_last_updated'])
            self.assertTrue(response['market_open'])
            self.assertEqual(response['session_validity'], {"Account1": True})
    
    def test_create_json_response_no_cache(self):
        """Test _create_json_response_no_cache helper"""
        from server import _create_json_response_no_cache, app_ui
        
        data = [
            {"name": "B", "value": 2},
            {"name": "A", "value": 1},
            {"name": "C", "value": 3}
        ]
        
        with app_ui.app_context():
            # Test without sorting
            response = _create_json_response_no_cache(data)
            self.assertEqual(response.headers.get('Cache-Control'), 'no-cache, no-store, must-revalidate')
            
            # Test with sorting
            response = _create_json_response_no_cache(data, sort_key="name")
            result_data = json.loads(response.data)
            self.assertEqual(result_data[0]["name"], "A")
            self.assertEqual(result_data[1]["name"], "B")
            self.assertEqual(result_data[2]["name"], "C")
    
    @patch('server.is_market_open_ist')
    @patch('server.fetch_in_progress')
    def test_should_auto_refresh_market_closed(self, mock_in_progress, mock_market_open):
        """Test _should_auto_refresh when market is closed"""
        from server import _should_auto_refresh, app_config
        
        with patch.object(app_config, 'auto_refresh_outside_market_hours', False):
            mock_market_open.return_value = False
            mock_in_progress.is_set.return_value = False
            
            should_run, reason = _should_auto_refresh()
            
            self.assertFalse(should_run)
            self.assertIn("market closed", reason)
    
    @patch('server.is_market_open_ist')
    @patch('server.fetch_in_progress')
    def test_should_auto_refresh_in_progress(self, mock_in_progress, mock_market):
        """Test _should_auto_refresh when refresh in progress"""
        from server import _should_auto_refresh
        
        mock_market.return_value = True
        mock_in_progress.is_set.return_value = True
        
        should_run, reason = _should_auto_refresh()
        
        self.assertFalse(should_run)
        self.assertIn("manual refresh", reason)
    
    @patch('server._all_sessions_valid')
    @patch('server.fetch_in_progress')
    @patch('server.is_market_open_ist')
    def test_should_auto_refresh_allowed(self, mock_market_open, mock_in_progress, mock_sessions_valid):
        """Test _should_auto_refresh when refresh allowed"""
        from server import _should_auto_refresh
        
        mock_market_open.return_value = True
        mock_in_progress.is_set.return_value = False
        mock_sessions_valid.return_value = True
        
        should_run, reason = _should_auto_refresh()
        
        self.assertTrue(should_run)
        self.assertIsNone(reason)


class TestDataFetchingFunctions(unittest.TestCase):
    """Test data fetching functions"""
    
    @patch('server.zerodha_client')
    @patch('server.state_manager')
    @patch('server.fetch_in_progress')
    def test_fetch_portfolio_data_success(self, mock_event, mock_state, mock_client):
        """Test successful portfolio data fetch"""
        from server import fetch_portfolio_data
        
        mock_client.fetch_all_accounts_data.return_value = (
            [{'stock': 1}],
            [{'mf': 1}],
            [{'sip': 1}],
            None
        )
        
        with patch.object(__import__('server', fromlist=['app_config']).app_config, 'accounts', [{"name": "test"}]):
            fetch_portfolio_data(force_login=False)
        
        mock_event.set.assert_called_once()
        mock_state.set_portfolio_updating.assert_called_once()
        mock_state.set_portfolio_updated.assert_called_once()
        mock_event.clear.assert_called_once()
    
    @patch('server.zerodha_client')
    @patch('server.state_manager')
    @patch('server.fetch_in_progress')
    def test_fetch_portfolio_data_with_error(self, mock_event, mock_state, mock_client):
        """Test portfolio data fetch with error"""
        from server import fetch_portfolio_data
        
        mock_client.fetch_all_accounts_data.return_value = (
            [],
            [],
            [],
            "Test error"
        )
        
        with patch.object(__import__('server', fromlist=['app_config']).app_config, 'accounts', []):
            fetch_portfolio_data(force_login=False)
        
        mock_state.set_portfolio_updated.assert_called_with(error="Test error")
    
    @patch('server.threading.Thread')
    @patch('server.NSEAPIClient')
    @patch('server.state_manager')
    @patch('server.nifty50_fetch_in_progress')
    def test_fetch_nifty50_data_skips_if_in_progress(self, mock_event, mock_state, mock_nse, mock_thread):
        """Test fetch_nifty50_data skips if already in progress"""
        from server import fetch_nifty50_data
        
        mock_event.is_set.return_value = True
        
        fetch_nifty50_data()
        
        # Should return early without starting thread
        mock_thread.assert_not_called()


class TestNifty50Page(unittest.TestCase):
    """Test Nifty 50 page route"""
    
    def setUp(self):
        """Set up test client"""
        from server import app_ui
        self.client = app_ui.test_client()
        app_ui.testing = True
    
    def test_nifty50_page(self):
        """Test /nifty50 page renders"""
        response = self.client.get('/nifty50')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'html', response.data.lower())


class TestRefreshConflict(unittest.TestCase):
    """Test refresh conflict handling"""
    
    def setUp(self):
        """Set up test client"""
        from server import app_ui
        self.client = app_ui.test_client()
        app_ui.testing = True
    
    def test_refresh_route_needs_login(self):
        """Test /refresh detects expired sessions"""
        with patch('server.fetch_in_progress') as mock_event, \
             patch('server.run_background_fetch') as mock_fetch, \
             patch('server.session_manager.is_valid') as mock_valid, \
             patch.object(__import__('server', fromlist=['app_config']).app_config, 'accounts', [{"name": "test"}]):
            
            mock_event.is_set.return_value = False
            mock_valid.return_value = False  # Session expired
            
            response = self.client.post('/refresh')
            
            self.assertEqual(response.status_code, 202)
            data = json.loads(response.data)
            self.assertTrue(data['needs_login'])
            mock_fetch.assert_called_once_with(force_login=True, is_manual=True)


if __name__ == '__main__':
    unittest.main()
