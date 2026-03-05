"""Unit tests for app.api.market_data – MarketDataClient."""
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
import threading

import requests
from requests.exceptions import ConnectionError, Timeout, RequestException

from app.api.market_data import MarketDataClient


class TestCreateSession(unittest.TestCase):
    @patch("app.api.market_data.requests.Session")
    def test_success(self, mock_session_cls):
        client = MarketDataClient()
        sess = client._create_session()
        self.assertIsNotNone(sess)
        mock_session_cls.return_value.get.assert_called_once()

    @patch("app.api.market_data.requests.Session")
    def test_timeout(self, mock_session_cls):
        mock_session_cls.return_value.get.side_effect = Timeout("slow")
        client = MarketDataClient()
        with self.assertRaises(Timeout):
            client._create_session()

    @patch("app.api.market_data.requests.Session")
    def test_connection_error(self, mock_session_cls):
        mock_session_cls.return_value.get.side_effect = ConnectionError("down")
        client = MarketDataClient()
        with self.assertRaises(ConnectionError):
            client._create_session()

    @patch("app.api.market_data.requests.Session")
    def test_generic_error(self, mock_session_cls):
        mock_session_cls.return_value.get.side_effect = RuntimeError("bang")
        client = MarketDataClient()
        with self.assertRaises(RuntimeError):
            client._create_session()


class TestFetchNifty50Symbols(unittest.TestCase):
    @patch.object(MarketDataClient, "_create_session")
    def test_success(self, mock_create):
        mock_sess = Mock()
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"symbol": "NIFTY 50"}, {"symbol": "INFY"}, {"symbol": "TCS"}]
        }
        mock_sess.get.return_value = mock_resp
        mock_create.return_value = mock_sess

        client = MarketDataClient()
        result = client.fetch_nifty50_symbols()
        self.assertEqual(result, ["INFY", "TCS"])

    @patch.object(MarketDataClient, "_create_session")
    def test_non_200(self, mock_create):
        mock_sess = Mock()
        mock_resp = Mock()
        mock_resp.status_code = 503
        mock_sess.get.return_value = mock_resp
        mock_create.return_value = mock_sess

        client = MarketDataClient()
        result = client.fetch_nifty50_symbols()
        self.assertEqual(result, [])

    @patch.object(MarketDataClient, "_create_session")
    def test_timeout(self, mock_create):
        mock_sess = Mock()
        mock_sess.get.side_effect = Timeout("slow")
        mock_create.return_value = mock_sess

        client = MarketDataClient()
        result = client.fetch_nifty50_symbols()
        self.assertEqual(result, [])

    @patch.object(MarketDataClient, "_create_session")
    def test_connection_error(self, mock_create):
        mock_sess = Mock()
        mock_sess.get.side_effect = ConnectionError("down")
        mock_create.return_value = mock_sess

        client = MarketDataClient()
        result = client.fetch_nifty50_symbols()
        self.assertEqual(result, [])

    @patch.object(MarketDataClient, "_create_session", side_effect=Exception("fail"))
    def test_generic_error(self, mock_create):
        client = MarketDataClient()
        result = client.fetch_nifty50_symbols()
        self.assertEqual(result, [])


class TestFetchStockQuote(unittest.TestCase):
    def setUp(self):
        self.client = MarketDataClient()
        self.client.request_delay = 0  # speed up tests

    def test_success(self):
        mock_sess = Mock()
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "info": {"companyName": "Infosys"},
            "priceInfo": {
                "lastPrice": 1500,
                "change": 10,
                "pChange": 0.67,
                "open": 1490,
                "previousClose": 1490,
                "intraDayHighLow": {"max": 1510, "min": 1480},
            }
        }
        mock_sess.get.return_value = mock_resp
        result = self.client.fetch_stock_quote(mock_sess, "INFY")
        self.assertEqual(result["ltp"], 1500)
        self.assertEqual(result["symbol"], "INFY")
        self.assertEqual(result["name"], "Infosys")

    def test_non_200(self):
        mock_sess = Mock()
        mock_resp = Mock()
        mock_resp.status_code = 404
        mock_sess.get.return_value = mock_resp
        result = self.client.fetch_stock_quote(mock_sess, "BAD")
        self.assertEqual(result["ltp"], 0)

    def test_timeout(self):
        mock_sess = Mock()
        mock_sess.get.side_effect = Timeout("slow")
        result = self.client.fetch_stock_quote(mock_sess, "INFY")
        self.assertEqual(result["ltp"], 0)

    def test_connection_error(self):
        mock_sess = Mock()
        mock_sess.get.side_effect = ConnectionError("err")
        result = self.client.fetch_stock_quote(mock_sess, "INFY")
        self.assertEqual(result["ltp"], 0)

    def test_request_exception(self):
        mock_sess = Mock()
        mock_sess.get.side_effect = RequestException("err")
        result = self.client.fetch_stock_quote(mock_sess, "INFY")
        self.assertEqual(result["ltp"], 0)

    def test_generic_exception(self):
        mock_sess = Mock()
        mock_sess.get.side_effect = RuntimeError("bang")
        result = self.client.fetch_stock_quote(mock_sess, "INFY")
        self.assertEqual(result["ltp"], 0)


class TestFetchStockQuotes(unittest.TestCase):
    def setUp(self):
        self.client = MarketDataClient()
        self.client.request_delay = 0

    @patch.object(MarketDataClient, "fetch_stock_quote")
    @patch.object(MarketDataClient, "_create_session")
    def test_batch_success(self, mock_create, mock_quote):
        mock_create.return_value = Mock()
        mock_quote.side_effect = [
            {"ltp": 100, "symbol": "A"},
            {"ltp": 200, "symbol": "B"},
        ]
        result = self.client.fetch_stock_quotes(["A", "B"])
        self.assertEqual(len(result), 2)

    def test_empty_symbols(self):
        result = self.client.fetch_stock_quotes([])
        self.assertEqual(result, {})

    @patch.object(MarketDataClient, "_create_session", side_effect=Exception("fail"))
    def test_session_creation_failure(self, mock_create):
        result = self.client.fetch_stock_quotes(["INFY"])
        self.assertEqual(result, {})

    @patch.object(MarketDataClient, "fetch_stock_quote")
    @patch.object(MarketDataClient, "_create_session")
    def test_cancel_event(self, mock_create, mock_quote):
        mock_create.return_value = Mock()
        cancel = threading.Event()
        cancel.set()  # cancel immediately
        result = self.client.fetch_stock_quotes(["A", "B"], cancel=cancel)
        self.assertEqual(result, {})

    @patch.object(MarketDataClient, "fetch_stock_quote")
    @patch.object(MarketDataClient, "_create_session")
    def test_with_timeout_override(self, mock_create, mock_quote):
        mock_create.return_value = Mock()
        mock_quote.return_value = {"ltp": 100, "symbol": "A"}
        result = self.client.fetch_stock_quotes(["A"], timeout=5)
        self.assertEqual(len(result), 1)
        # Timeout should be restored
        self.assertEqual(self.client.timeout, MarketDataClient().timeout)

    @patch.object(MarketDataClient, "fetch_stock_quote")
    @patch.object(MarketDataClient, "_create_session")
    def test_failed_symbols_logged(self, mock_create, mock_quote):
        mock_create.return_value = Mock()
        mock_quote.return_value = {"ltp": 0, "symbol": "BAD"}  # ltp=0 → failed
        result = self.client.fetch_stock_quotes(["BAD"])
        self.assertEqual(result, {})


class TestFetchMarketIndices(unittest.TestCase):
    @patch.object(MarketDataClient, "_fetch_yf_index")
    def test_returns_all_keys(self, mock_yf):
        client = MarketDataClient()
        result = client.fetch_market_indices()
        self.assertIn("nifty50", result)
        self.assertIn("sensex", result)
        self.assertIn("gold", result)


class TestFetchYfIndex(unittest.TestCase):
    @patch("app.api.market_data.requests.get")
    def test_success(self, mock_get):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "chart": {
                "result": [{
                    "meta": {"regularMarketPrice": 22000, "previousClose": 21900},
                    "indicators": {"quote": [{"close": [21950.0, 21975.0, 22000.0]}]}
                }]
            }
        }
        mock_get.return_value = mock_resp

        client = MarketDataClient()
        result = {}
        client._fetch_yf_index(result, "nifty50", "%5ENSEI", "NIFTY 50")
        self.assertEqual(result["nifty50"]["value"], 22000)
        self.assertAlmostEqual(result["nifty50"]["change"], 100)

    @patch("app.api.market_data.requests.get")
    def test_non_200(self, mock_get):
        mock_resp = Mock()
        mock_resp.status_code = 503
        mock_get.return_value = mock_resp

        client = MarketDataClient()
        result = {"nifty50": client._empty_index_data("NIFTY 50")}
        client._fetch_yf_index(result, "nifty50", "%5ENSEI", "NIFTY 50")
        self.assertEqual(result["nifty50"]["value"], 0)

    @patch("app.api.market_data.requests.get", side_effect=Timeout("slow"))
    def test_timeout(self, mock_get):
        client = MarketDataClient()
        result = {"nifty50": client._empty_index_data("NIFTY 50")}
        client._fetch_yf_index(result, "nifty50", "%5ENSEI", "NIFTY 50")
        self.assertEqual(result["nifty50"]["value"], 0)

    @patch("app.api.market_data.requests.get", side_effect=ConnectionError("err"))
    def test_connection_error(self, mock_get):
        client = MarketDataClient()
        result = {"nifty50": client._empty_index_data("NIFTY 50")}
        client._fetch_yf_index(result, "nifty50", "%5ENSEI", "NIFTY 50")
        self.assertEqual(result["nifty50"]["value"], 0)

    @patch("app.api.market_data.requests.get", side_effect=ValueError("parse"))
    def test_generic_error(self, mock_get):
        client = MarketDataClient()
        result = {"nifty50": client._empty_index_data("NIFTY 50")}
        client._fetch_yf_index(result, "nifty50", "%5ENSEI", "NIFTY 50")
        self.assertEqual(result["nifty50"]["value"], 0)

    @patch("app.api.market_data.requests.get")
    def test_empty_chart_result(self, mock_get):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"chart": {"result": []}}
        mock_get.return_value = mock_resp

        client = MarketDataClient()
        result = {"nifty50": client._empty_index_data("NIFTY 50")}
        client._fetch_yf_index(result, "nifty50", "%5ENSEI", "NIFTY 50")
        self.assertEqual(result["nifty50"]["value"], 0)


class TestEmptyIndexData(unittest.TestCase):
    def test_fields(self):
        result = MarketDataClient._empty_index_data("TEST")
        self.assertEqual(result["name"], "TEST")
        self.assertEqual(result["value"], 0)
        self.assertEqual(result["chart"], [])


class TestEmptyStockData(unittest.TestCase):
    def test_fields(self):
        client = MarketDataClient()
        result = client._empty_stock_data("SYM")
        self.assertEqual(result["symbol"], "SYM")
        self.assertEqual(result["ltp"], 0)


if __name__ == '__main__':
    unittest.main()
