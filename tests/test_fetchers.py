"""
Unit tests for fetchers.py (data fetching and auto-refresh logic).
"""
import unittest
from unittest.mock import Mock, patch

from app.fetchers import (_compute_fd_summary, _should_auto_refresh,
                          fetch_nifty50_data, fetch_portfolio_data,
                          run_background_fetch)


class TestFetchPortfolioData(unittest.TestCase):
    """Test fetch_portfolio_data function."""

    @patch('app.fetchers.zerodha_client')
    @patch('app.fetchers.state_manager')
    @patch('app.fetchers.fetch_in_progress')
    def test_success(self, mock_event, mock_state, mock_client):
        mock_client.fetch_all_accounts_data.return_value = (
            [{'stock': 1}],
            [{'mf': 1}],
            [{'sip': 1}],
            None,
        )

        with patch('app.fetchers.app_config') as mock_config:
            mock_config.accounts = [{"name": "test"}]
            fetch_portfolio_data(force_login=False)

        mock_event.set.assert_called_once()
        mock_state.set_portfolio_updating.assert_called_once()
        mock_state.set_portfolio_updated.assert_called_once()
        mock_event.clear.assert_called_once()

    @patch('app.fetchers.cache')
    @patch('app.fetchers.zerodha_client')
    @patch('app.fetchers.state_manager')
    @patch('app.fetchers.fetch_in_progress')
    def test_with_error(self, mock_event, mock_state, mock_client, mock_cache):
        mock_client.fetch_all_accounts_data.return_value = (
            [], [], [], "Test error",
        )
        mock_cache.stocks = [{'old_stock': 1}]
        mock_cache.mf_holdings = [{'old_mf': 1}]
        mock_cache.sips = [{'old_sip': 1}]

        with patch('app.fetchers.app_config') as mock_config:
            mock_config.accounts = []
            fetch_portfolio_data(force_login=False)

        mock_state.set_portfolio_updated.assert_called_with(error="Test error")
        # Verify cache was NOT updated (old data preserved)
        self.assertEqual(mock_cache.stocks, [{'old_stock': 1}])
        self.assertEqual(mock_cache.mf_holdings, [{'old_mf': 1}])
        self.assertEqual(mock_cache.sips, [{'old_sip': 1}])

    @patch('app.fetchers.cache')
    @patch('app.fetchers.zerodha_client')
    @patch('app.fetchers.state_manager')
    @patch('app.fetchers.fetch_in_progress')
    def test_success_updates_cache(self, mock_event, mock_state, mock_client, mock_cache):
        mock_client.fetch_all_accounts_data.return_value = (
            [{'new_stock': 1}],
            [{'new_mf': 1}],
            [{'new_sip': 1}],
            None,
        )
        mock_cache.stocks = [{'old_stock': 1}]
        mock_cache.mf_holdings = [{'old_mf': 1}]
        mock_cache.sips = [{'old_sip': 1}]

        with patch('app.fetchers.app_config') as mock_config:
            mock_config.accounts = [{"name": "test"}]
            fetch_portfolio_data(force_login=False)

        # Verify cache WAS updated with new data
        self.assertEqual(mock_cache.stocks, [{'new_stock': 1}])
        self.assertEqual(mock_cache.mf_holdings, [{'new_mf': 1}])
        self.assertEqual(mock_cache.sips, [{'new_sip': 1}])


class TestFetchNifty50Data(unittest.TestCase):
    """Test fetch_nifty50_data function."""

    @patch('app.fetchers.threading.Thread')
    @patch('app.fetchers.state_manager')
    @patch('app.fetchers.nifty50_fetch_in_progress')
    def test_skips_if_in_progress(self, mock_event, mock_state, mock_thread):
        mock_event.is_set.return_value = True

        fetch_nifty50_data()

        mock_thread.assert_not_called()


class TestRunBackgroundFetch(unittest.TestCase):
    """Test run_background_fetch orchestration."""

    def test_starts_background_thread(self):
        with patch('app.fetchers.threading.Thread') as mock_thread:
            mock_instance = Mock()
            mock_thread.return_value = mock_instance

            run_background_fetch(force_login=False)

            mock_thread.assert_called()
            mock_instance.start.assert_called_once()


class TestShouldAutoRefresh(unittest.TestCase):
    """Test _should_auto_refresh decision logic."""

    @patch('app.fetchers.is_market_open_ist')
    @patch('app.fetchers.fetch_in_progress')
    def test_market_closed(self, mock_in_progress, mock_market_open):
        with patch('app.fetchers.app_config') as mock_config:
            mock_config.auto_refresh_outside_market_hours = False
            mock_market_open.return_value = False
            mock_in_progress.is_set.return_value = False

            should_run, reason = _should_auto_refresh()

            self.assertFalse(should_run)
            self.assertIn("market closed", reason)

    @patch('app.fetchers.is_market_open_ist')
    @patch('app.fetchers.fetch_in_progress')
    def test_in_progress(self, mock_in_progress, mock_market):
        mock_market.return_value = True
        mock_in_progress.is_set.return_value = True

        should_run, reason = _should_auto_refresh()

        self.assertFalse(should_run)
        self.assertIn("manual refresh", reason)

    @patch('app.fetchers._all_sessions_valid')
    @patch('app.fetchers.fetch_in_progress')
    @patch('app.fetchers.is_market_open_ist')
    def test_allowed(self, mock_market_open, mock_in_progress, mock_sessions_valid):
        mock_market_open.return_value = True
        mock_in_progress.is_set.return_value = False
        mock_sessions_valid.return_value = True

        should_run, reason = _should_auto_refresh()

        self.assertTrue(should_run)
        self.assertIsNone(reason)


class TestComputeFdSummary(unittest.TestCase):
    """Test FD summary computation."""

    def test_empty_deposits(self):
        self.assertEqual(_compute_fd_summary([]), [])

    def test_single_deposit(self):
        deposits = [
            {'bank_name': 'SBI', 'account': 'SB001', 'original_amount': 100000, 'current_value': 110000},
        ]
        result = _compute_fd_summary(deposits)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['bank'], 'SBI')
        self.assertEqual(result[0]['totalDeposited'], 100000)
        self.assertEqual(result[0]['totalCurrentValue'], 110000)
        self.assertEqual(result[0]['totalReturns'], 10000)

    def test_grouped_deposits(self):
        deposits = [
            {'bank_name': 'SBI', 'account': 'SB001', 'original_amount': 100000, 'current_value': 105000},
            {'bank_name': 'SBI', 'account': 'SB001', 'original_amount': 200000, 'current_value': 215000},
            {'bank_name': 'HDFC', 'account': 'HD001', 'original_amount': 50000, 'current_value': 52000},
        ]
        result = _compute_fd_summary(deposits)
        self.assertEqual(len(result), 2)

        sbi_group = next(g for g in result if g['bank'] == 'SBI')
        self.assertEqual(sbi_group['totalDeposited'], 300000)
        self.assertEqual(sbi_group['totalCurrentValue'], 320000)
        self.assertEqual(sbi_group['totalReturns'], 20000)


class TestZerodhaClientFetchAccountData(unittest.TestCase):
    """Test zerodha_client.fetch_account_data via services."""

    def test_fetch_account_data(self):
        from app.services import zerodha_client

        with patch('app.services.auth_manager.authenticate') as mock_auth, \
             patch('app.services.holdings_service.fetch_holdings') as mock_holdings, \
             patch('app.services.sip_service.fetch_sips') as mock_sips:

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

    def test_fetch_account_data_force_login(self):
        from app.services import zerodha_client

        with patch('app.services.auth_manager.authenticate') as mock_auth, \
             patch('app.services.holdings_service.fetch_holdings') as mock_holdings, \
             patch('app.services.sip_service.fetch_sips') as mock_sips:

            mock_auth.return_value = Mock()
            mock_holdings.return_value = ([], [])
            mock_sips.return_value = []

            account_config = {"name": "test"}
            zerodha_client.fetch_account_data(account_config, force_login=True)

            mock_auth.assert_called_once_with(account_config, True)


if __name__ == '__main__':
    unittest.main()
