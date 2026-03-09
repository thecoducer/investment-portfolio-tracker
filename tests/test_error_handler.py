"""
Unit tests for error_handler.py — custom exceptions, decorators, and utilities.
"""

import unittest
from unittest.mock import Mock, patch

from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

from app.error_handler import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    DataError,
    ErrorAggregator,
    ErrorCategory,
    ErrorHandler,
    NetworkError,
    PortfolioTrackerError,
    handle_errors,
    retry_on_transient_error,
    safe_api_call,
)

# ---------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------


class TestErrorCategory(unittest.TestCase):
    def test_all_members(self):
        expected = {"NETWORK", "API", "AUTHENTICATION", "DATA", "CONFIGURATION", "UNKNOWN"}
        self.assertEqual({e.name for e in ErrorCategory}, expected)

    def test_values(self):
        self.assertEqual(ErrorCategory.NETWORK.value, "network")
        self.assertEqual(ErrorCategory.API.value, "api")
        self.assertEqual(ErrorCategory.AUTHENTICATION.value, "authentication")
        self.assertEqual(ErrorCategory.DATA.value, "data")
        self.assertEqual(ErrorCategory.CONFIGURATION.value, "configuration")
        self.assertEqual(ErrorCategory.UNKNOWN.value, "unknown")


class TestPortfolioTrackerError(unittest.TestCase):
    def test_default_category(self):
        e = PortfolioTrackerError("oops")
        self.assertEqual(e.message, "oops")
        self.assertEqual(e.category, ErrorCategory.UNKNOWN)
        self.assertIsNone(e.original_error)
        self.assertEqual(str(e), "oops")

    def test_custom_category_and_original(self):
        orig = ValueError("inner")
        e = PortfolioTrackerError("msg", ErrorCategory.DATA, orig)
        self.assertEqual(e.category, ErrorCategory.DATA)
        self.assertIs(e.original_error, orig)


class TestNetworkError(unittest.TestCase):
    def test_category_is_network(self):
        e = NetworkError("timeout")
        self.assertEqual(e.category, ErrorCategory.NETWORK)
        self.assertIsNone(e.original_error)

    def test_with_original_error(self):
        orig = Timeout("t")
        e = NetworkError("timeout", original_error=orig)
        self.assertIs(e.original_error, orig)


class TestAPIError(unittest.TestCase):
    def test_category_is_api(self):
        e = APIError("bad response")
        self.assertEqual(e.category, ErrorCategory.API)
        self.assertIsNone(e.status_code)

    def test_with_status_code(self):
        e = APIError("bad", status_code=500)
        self.assertEqual(e.status_code, 500)


class TestAuthenticationError(unittest.TestCase):
    def test_category(self):
        e = AuthenticationError("no auth")
        self.assertEqual(e.category, ErrorCategory.AUTHENTICATION)


class TestDataError(unittest.TestCase):
    def test_category(self):
        e = DataError("parse fail")
        self.assertEqual(e.category, ErrorCategory.DATA)


class TestConfigurationError(unittest.TestCase):
    def test_category(self):
        e = ConfigurationError("missing key")
        self.assertEqual(e.category, ErrorCategory.CONFIGURATION)


# ---------------------------------------------------------------
# ErrorHandler static methods
# ---------------------------------------------------------------


class TestErrorHandlerWrap(unittest.TestCase):
    def test_timeout_wrapped(self):
        orig = Timeout("slow")
        wrapped = ErrorHandler.wrap_external_api_error(orig, "NSE")
        self.assertIsInstance(wrapped, NetworkError)
        self.assertIn("timeout", wrapped.message.lower())
        self.assertIs(wrapped.original_error, orig)

    def test_connection_error_wrapped(self):
        orig = ConnectionError("down")
        wrapped = ErrorHandler.wrap_external_api_error(orig, "Sheets")
        self.assertIsInstance(wrapped, NetworkError)
        self.assertIn("Sheets", wrapped.message)

    def test_http_error_wrapped_with_status(self):
        resp = Mock()
        resp.status_code = 503
        orig = HTTPError(response=resp)
        wrapped = ErrorHandler.wrap_external_api_error(orig, "API")
        self.assertIsInstance(wrapped, APIError)
        self.assertEqual(wrapped.status_code, 503)

    def test_http_error_no_response(self):
        orig = HTTPError()
        # HTTPError().response is None; hasattr returns True but
        # .status_code on None raises AttributeError — match that.
        resp = Mock()
        resp.status_code = None
        orig.response = resp
        wrapped = ErrorHandler.wrap_external_api_error(orig, "API")
        self.assertIsInstance(wrapped, APIError)
        self.assertIsNone(wrapped.status_code)

    def test_request_exception_wrapped(self):
        orig = RequestException("generic")
        wrapped = ErrorHandler.wrap_external_api_error(orig, "SVC")
        self.assertIsInstance(wrapped, NetworkError)

    def test_unknown_exception_wrapped(self):
        orig = RuntimeError("unknown")
        wrapped = ErrorHandler.wrap_external_api_error(orig, "SVC")
        self.assertIsInstance(wrapped, PortfolioTrackerError)
        self.assertIn("Unexpected", wrapped.message)


class TestErrorHandlerLog(unittest.TestCase):
    @patch("app.error_handler.logger")
    def test_log_network_error_uses_warning(self, mock_logger):
        e = NetworkError("net fail")
        ErrorHandler.log_error(e, "ctx")
        mock_logger.warning.assert_called_once()

    @patch("app.error_handler.logger")
    def test_log_api_error_5xx_uses_error(self, mock_logger):
        e = APIError("server err", status_code=502)
        ErrorHandler.log_error(e, "ctx")
        mock_logger.error.assert_called_once()

    @patch("app.error_handler.logger")
    def test_log_api_error_4xx_uses_warning(self, mock_logger):
        e = APIError("client err", status_code=400)
        ErrorHandler.log_error(e, "ctx")
        mock_logger.warning.assert_called_once()

    @patch("app.error_handler.logger")
    def test_log_api_error_no_status_uses_warning(self, mock_logger):
        e = APIError("api err")
        ErrorHandler.log_error(e, "ctx")
        mock_logger.warning.assert_called_once()

    @patch("app.error_handler.logger")
    def test_log_auth_error_uses_error(self, mock_logger):
        e = AuthenticationError("auth fail")
        ErrorHandler.log_error(e)
        mock_logger.error.assert_called_once()

    @patch("app.error_handler.logger")
    def test_log_config_error_uses_error(self, mock_logger):
        e = ConfigurationError("cfg fail")
        ErrorHandler.log_error(e, "setup")
        mock_logger.error.assert_called_once()

    @patch("app.error_handler.logger")
    def test_log_generic_exception_uses_exception(self, mock_logger):
        e = RuntimeError("boom")
        ErrorHandler.log_error(e, "somewhere")
        mock_logger.exception.assert_called_once()

    @patch("app.error_handler.logger")
    def test_log_no_context(self, mock_logger):
        e = NetworkError("net")
        ErrorHandler.log_error(e)
        mock_logger.warning.assert_called_once()


# ---------------------------------------------------------------
# retry_on_transient_error decorator
# ---------------------------------------------------------------


class TestRetryOnTransientError(unittest.TestCase):
    @patch("app.error_handler.time.sleep")
    def test_no_retry_on_success(self, mock_sleep):
        @retry_on_transient_error(max_retries=2)
        def ok():
            return "ok"

        self.assertEqual(ok(), "ok")
        mock_sleep.assert_not_called()

    @patch("app.error_handler.time.sleep")
    def test_retries_on_transient(self, mock_sleep):
        call_count = 0

        @retry_on_transient_error(max_retries=2, delay=0.1, backoff=2.0)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("retry me")
            return "ok"

        result = flaky()
        self.assertEqual(result, "ok")
        self.assertEqual(call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("app.error_handler.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep):
        @retry_on_transient_error(max_retries=1, delay=0.1)
        def always_fail():
            raise NetworkError("down")

        with self.assertRaises(NetworkError):
            always_fail()
        self.assertEqual(mock_sleep.call_count, 1)

    @patch("app.error_handler.time.sleep")
    def test_no_retry_on_4xx_api_error(self, mock_sleep):
        @retry_on_transient_error(max_retries=3)
        def client_error():
            raise APIError("not found", status_code=404)

        with self.assertRaises(APIError):
            client_error()
        mock_sleep.assert_not_called()

    @patch("app.error_handler.time.sleep")
    def test_retries_on_5xx_api_error(self, mock_sleep):
        call_count = 0

        @retry_on_transient_error(max_retries=1, delay=0.1)
        def server_error():
            nonlocal call_count
            call_count += 1
            raise APIError("server error", status_code=500)

        with self.assertRaises(APIError):
            server_error()
        self.assertEqual(call_count, 2)

    @patch("app.error_handler.time.sleep")
    def test_retries_on_os_error(self, mock_sleep):
        call_count = 0

        @retry_on_transient_error(max_retries=1, delay=0.01)
        def os_fail():
            nonlocal call_count
            call_count += 1
            raise OSError("socket err")

        with self.assertRaises(OSError):
            os_fail()
        self.assertEqual(call_count, 2)

    @patch("app.error_handler.time.sleep")
    def test_exponential_backoff(self, mock_sleep):
        @retry_on_transient_error(max_retries=3, delay=1.0, backoff=2.0)
        def fail():
            raise NetworkError("fail")

        with self.assertRaises(NetworkError):
            fail()
        delays = [c[0][0] for c in mock_sleep.call_args_list]
        self.assertEqual(delays, [1.0, 2.0, 4.0])

    def test_preserves_function_metadata(self):
        @retry_on_transient_error()
        def my_func():
            """My doc."""
            pass

        self.assertEqual(my_func.__name__, "my_func")
        self.assertEqual(my_func.__doc__, "My doc.")

    @patch("app.error_handler.time.sleep")
    def test_api_error_no_status_retries(self, mock_sleep):
        """APIError with no status_code should be retried (not treated as 4xx)."""
        call_count = 0

        @retry_on_transient_error(max_retries=1, delay=0.01)
        def api_fail():
            nonlocal call_count
            call_count += 1
            raise APIError("unknown api error")

        with self.assertRaises(APIError):
            api_fail()
        self.assertEqual(call_count, 2)


# ---------------------------------------------------------------
# handle_errors decorator
# ---------------------------------------------------------------


class TestHandleErrors(unittest.TestCase):
    @patch("app.error_handler.ErrorHandler.log_error")
    def test_returns_default_on_error(self, mock_log):
        @handle_errors(default_return=[])
        def fail():
            raise ValueError("oops")

        result = fail()
        self.assertEqual(result, [])

    def test_returns_result_on_success(self):
        @handle_errors(default_return=[])
        def ok():
            return [1, 2, 3]

        self.assertEqual(ok(), [1, 2, 3])

    @patch("app.error_handler.ErrorHandler.log_error")
    def test_wraps_non_portfolio_error(self, mock_log):
        @handle_errors(default_return=None)
        def fail():
            raise RuntimeError("raw")

        fail()
        # Should have been called with a wrapped error
        mock_log.assert_called_once()

    @patch("app.error_handler.ErrorHandler.log_error")
    def test_passes_portfolio_error_through(self, mock_log):
        @handle_errors(default_return=None, log_context="test")
        def fail():
            raise NetworkError("net")

        fail()
        args = mock_log.call_args
        self.assertIsInstance(args[0][0], NetworkError)

    @patch("app.error_handler.ErrorHandler.log_error")
    def test_preserve_cache_returns_cached(self, mock_log):
        class Service:
            _cache = ["cached_data"]

            @handle_errors(default_return=[], preserve_cache=True, cache_attr="_cache")
            def fetch(self):
                raise NetworkError("fail")

        svc = Service()
        result = svc.fetch()
        self.assertEqual(result, ["cached_data"])

    @patch("app.error_handler.ErrorHandler.log_error")
    def test_preserve_cache_returns_default_when_no_cached_value(self, mock_log):
        class Service:
            _cache = None

            @handle_errors(default_return=[], preserve_cache=True, cache_attr="_cache")
            def fetch(self):
                raise NetworkError("fail")

        svc = Service()
        result = svc.fetch()
        self.assertEqual(result, [])

    @patch("app.error_handler.ErrorHandler.log_error")
    def test_preserve_cache_no_attr(self, mock_log):
        """preserve_cache True but no cache_attr should return default."""

        @handle_errors(default_return="default", preserve_cache=True)
        def fail():
            raise RuntimeError("err")

        self.assertEqual(fail(), "default")

    def test_preserves_function_metadata(self):
        @handle_errors()
        def my_func():
            """My doc."""
            pass

        self.assertEqual(my_func.__name__, "my_func")


# ---------------------------------------------------------------
# safe_api_call
# ---------------------------------------------------------------


class TestSafeApiCall(unittest.TestCase):
    def test_success(self):
        result, error = safe_api_call(lambda x: x * 2, 5)
        self.assertEqual(result, 10)
        self.assertIsNone(error)

    def test_error(self):
        def fail():
            raise ValueError("nope")

        result, error = safe_api_call(fail)
        self.assertIsNone(result)
        self.assertIsInstance(error, ValueError)

    def test_with_kwargs(self):
        def fn(a, b=10):
            return a + b

        result, error = safe_api_call(fn, 5, b=20)
        self.assertEqual(result, 25)
        self.assertIsNone(error)


# ---------------------------------------------------------------
# ErrorAggregator
# ---------------------------------------------------------------


class TestErrorAggregator(unittest.TestCase):
    def test_empty(self):
        agg = ErrorAggregator()
        self.assertFalse(agg.has_errors())
        self.assertEqual(agg.get_summary(), "No errors")

    def test_single_error_with_context(self):
        agg = ErrorAggregator()
        agg.add(ValueError("bad value"), "parsing")
        self.assertTrue(agg.has_errors())
        self.assertIn("parsing", agg.get_summary())
        self.assertIn("bad value", agg.get_summary())

    def test_single_error_without_context(self):
        agg = ErrorAggregator()
        agg.add(ValueError("bad value"))
        summary = agg.get_summary()
        self.assertIn("bad value", summary)

    def test_multiple_errors(self):
        agg = ErrorAggregator()
        agg.add(ValueError("err1"), "ctx1")
        agg.add(RuntimeError("err2"), "ctx2")
        agg.add(OSError("err3"))
        summary = agg.get_summary()
        self.assertIn("Multiple errors occurred (3)", summary)
        self.assertIn("ctx1", summary)
        self.assertIn("err2", summary)

    @patch("app.error_handler.ErrorHandler.log_error")
    def test_log_all(self, mock_log):
        agg = ErrorAggregator()
        agg.add(ValueError("a"), "ctx_a")
        agg.add(RuntimeError("b"), "ctx_b")
        agg.log_all()
        self.assertEqual(mock_log.call_count, 2)


if __name__ == "__main__":
    unittest.main()
