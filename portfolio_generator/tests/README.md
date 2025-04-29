# Portfolio Generator Tests

This directory contains integration tests for the portfolio generator functionality.

## Executive Summary Tests

The `test_executive_summary.py` file contains integration tests for the Executive Summary generation and portfolio positions extraction functionality. These tests use the real OpenAI API to ensure the system works as expected in production.

### Requirements

To run these tests, you need:

1. A valid OpenAI API key set in your environment
2. Python 3.8+ with pytest and pytest-asyncio installed

### Running the Tests

1. Make sure your `.env` file contains a valid `OPENAI_API_KEY`:

```
OPENAI_API_KEY=your_api_key_here
```

2. Run the tests with pytest:

```bash
# From the project root
python -m pytest -xvs portfolio_generator/tests/test_executive_summary.py
```

### Test Cases

1. **test_executive_summary_generation_with_positions**: Tests that the Executive Summary generation with the OpenAI API correctly includes portfolio positions in the specified JSON format.

2. **test_executive_summary_with_fallback_positions**: Tests the fallback mechanism for when the model doesn't include portfolio positions in the response.

## Notes

- These tests use real API calls and will count toward your OpenAI API usage quota.
- The tests include comprehensive error handling to ensure they remain robust.
- Debug output from the tests will show the generated content and extracted positions.
