# Testing Guide

## Overview

The Investment Portfolio Tracker includes a comprehensive test suite covering:
- Unit tests for all utility functions
- API service tests with mocking
- Integration tests for complete workflows
- Edge case handling
- Constants validation

## Test Structure

```
tests/
├── __init__.py
├── test_utils.py          # Utils and helper functions
├── test_api_services.py   # API service layer tests
├── test_constants.py      # Constants validation
├── test_integration.py    # Integration and edge cases
└── run_tests.py           # Test runner script
```

## Running Tests

### Using unittest (built-in)

Run all tests:
```bash
python -m unittest discover tests
```

Or use the test runner:
```bash
python tests/run_tests.py
```

Run specific test module:
```bash
python tests/run_tests.py tests.test_utils
```

### Using pytest (recommended)

Install test dependencies:
```bash
pip install pytest pytest-cov pytest-mock
```

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=. --cov-report=html
```

Run specific test file:
```bash
pytest tests/test_utils.py
```

Run specific test:
```bash
pytest tests/test_utils.py::TestSessionManager::test_save_and_get_token
```

## Test Coverage

The test suite covers:

### Utils Module (test_utils.py)
- ✅ SessionManager: Token caching, expiry, multiple accounts
- ✅ StateManager: State transitions, combined states
- ✅ Config loading: Valid/invalid configs, validation
- ✅ Timestamp formatting: None values, timezones
- ✅ Market hours: Weekdays, weekends, trading hours

### API Services (test_api_services.py)
- ✅ HoldingsService: Fetch, merge, account enrichment, NAV dates
- ✅ LTPService: Symbol preparation, API calls, updates
- ✅ AuthenticationManager: Token caching, validation, OAuth flow

### Constants (test_constants.py)
- ✅ State constants validation
- ✅ HTTP status codes
- ✅ Exchange mappings
- ✅ Default configuration values

### Integration Tests (test_integration.py)
- ✅ Complete holdings workflow
- ✅ LTP update flow
- ✅ Multi-account merging
- ✅ State transitions
- ✅ Session persistence
- ✅ Error handling chains

### Edge Cases (test_integration.py)
- ✅ Empty holdings
- ✅ Zero quantity
- ✅ Negative prices
- ✅ Very large numbers
- ✅ Missing fields
- ✅ Unicode characters

## Writing New Tests

### Test Structure Template

```python
import unittest
from unittest.mock import Mock, patch

class TestYourFeature(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        pass
    
    def tearDown(self):
        """Clean up after tests"""
        pass
    
    def test_your_functionality(self):
        """Test description"""
        # Arrange
        expected = "expected_value"
        
        # Act
        result = your_function()
        
        # Assert
        self.assertEqual(result, expected)
```

### Mocking External Dependencies

```python
@patch('module.external_api')
def test_with_mock(self, mock_api):
    mock_api.return_value = "mocked_response"
    result = your_function()
    self.assertEqual(result, "expected")
```

### Testing Exceptions

```python
def test_invalid_input(self):
    with self.assertRaises(ValueError):
        invalid_function()
```

## Best Practices

1. **Isolation**: Each test should be independent
2. **Clarity**: Use descriptive test names
3. **Coverage**: Test both success and failure paths
4. **Mocking**: Mock external dependencies (APIs, files, time)
5. **Assertions**: Use specific assertions (assertEqual vs assertTrue)
6. **Cleanup**: Always clean up resources in tearDown
7. **Edge Cases**: Test boundary conditions and invalid inputs

## Continuous Integration

Add to your CI/CD pipeline:

```yaml
# Example for GitHub Actions
- name: Run Tests
  run: |
    pip install -r requirements.txt
    pytest --cov=. --cov-report=xml
```

## Test Maintenance

- Run tests before committing code
- Update tests when adding new features
- Keep test code clean and maintainable
- Review test coverage regularly
- Remove obsolete tests

## Troubleshooting

### Tests failing due to missing modules
```bash
pip install -r requirements.txt
```

### Import errors
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Timeout errors
Increase timeout values in test configuration or mock slow operations.

## Coverage Report

After running tests with coverage:
```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html  # View coverage report
```

Target: 80%+ code coverage for production code.
