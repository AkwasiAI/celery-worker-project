#!/usr/bin/env python3
"""
Integration test for the generate_section_with_web_search function.
"""

import os
import pytest

from portfolio_generator.modules.section_generator import generate_section_with_web_search
from portfolio_generator.prompts_config import BASE_SYSTEM_PROMPT

# Load environment variables

@pytest.mark.asyncio
async def test_web_search_integration(gemini_api_key):
    """Run an integration test of the web search-enabled section generator."""
    if not gemini_api_key:
        pytest.skip("No Gemini API key provided via --gemini-api-key.")
    os.environ["GEMINI_API_KEY"] = gemini_api_key

    section_name = "Global Economic Outlook"
    user_prompt = "Write a detailed analysis of the current global economic outlook."
    search_results = "Fake web search summary for test."
    previous_sections = {"Executive Summary": "This is an executive summary."}

    content = await generate_section_with_web_search(
        None,
        section_name,
        BASE_SYSTEM_PROMPT,
        user_prompt,
        search_results=search_results,
        previous_sections=previous_sections,
        target_word_count=50
    )
    assert isinstance(content, str)
    assert content.strip() != ""
    assert not content.startswith("Error:")

if __name__ == "__main__":
    pytest.main([__file__, "--gemini-api-key", "YOUR_API_KEY"])
