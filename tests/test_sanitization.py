import os
import pytest
from portfolio_generator.modules.report_generator import sanitize_report_content_with_gemini


def test_sanitize_report_content_with_gemini_integration(gemini_api_key):
    """Integration test for Gemini sanitization helper."""
    if not gemini_api_key:
        pytest.skip("No Gemini API key provided via --gemini-api-key.")
    # Set env var for Gemini client
    os.environ["GEMINI_API_KEY"] = gemini_api_key

    # Fake Markdown report to sanitize
    fake_report = (
        "# Test Report\n\n"
        "| Column1 | Column2 |\n"
        "|---|---|\n"
        "| Value1 | Value2 |\n" 
    )

    # Run sanitization synchronously
    sanitized = sanitize_report_content_with_gemini(fake_report)

    # Basic assertions
    assert isinstance(sanitized, str)
    # Content preserved
    assert "# Test Report" in sanitized
    assert "| Column1 | Column2 |" in sanitized
    # Sanitization should at least return something different or properly formatted
    assert sanitized.strip() != fake_report.strip()
