#!/usr/bin/env python
"""
Integration test for the structured executive summary generator.
Tests the new approach using Pydantic validation and the o4-mini model.
"""
import os
import json
import asyncio
from dotenv import load_dotenv
from openai import OpenAI

from portfolio_generator.modules.logging import log_info, log_warning, log_error
from portfolio_generator.prompts_config import EXECUTIVE_SUMMARY_DETAILED_PROMPT, BASE_SYSTEM_PROMPT
from portfolio_generator.modules.search_utils import format_search_results
from portfolio_generator.modules.structured_section_generator import (
    generate_structured_executive_summary,
    ExecutiveSummaryResponse,
    PortfolioPosition,
    extract_structured_parts,
    generate_default_portfolio_positions
)

# Load environment variables from .env file
load_dotenv()

# Sample search results for testing - formatted according to the expected structure
SAMPLE_SEARCH_RESULTS = [
    {
        "query": "shipping industry trends 2025",
        "results": [
            {
                "title": "Shipping Industry Q1 2025 Update",
                "content": "The shipping industry has seen 15% growth in Q1 2025 with container rates reaching new highs. Dry bulk carriers have performed particularly well due to increased demand for raw materials from emerging markets."
            }
        ]
    },
    {
        "query": "global supply chain resilience",
        "results": [
            {
                "title": "Supply Chain Resilience Report",
                "content": "Global supply chains have shown increased resilience despite ongoing geopolitical tensions. Companies have invested in redundancy and digitalization to mitigate disruption risks."
            }
        ]
    },
    {
        "query": "energy markets forecast 2025",
        "results": [
            {
                "title": "Energy Sector Analysis Q2 2025",
                "content": "Crude oil prices have stabilized in the $80-90 range amid OPEC+ production discipline. Natural gas markets remain tight in Europe, while renewable energy capacity continues to expand globally."
            }
        ]
    },
    {
        "query": "metals market outlook",
        "results": [
            {
                "title": "Metals Market Forecast 2025",
                "content": "Iron ore and copper demand from Asia continues to drive metals markets upward. China's infrastructure spending and the global energy transition are supporting prices despite recessionary fears in some economies."
            }
        ]
    }
]

async def test_structured_executive_summary_generation():
    """
    Test the structured executive summary generation with Pydantic validation.
    """
    log_info("Starting test of structured executive summary generation...")
    
    # Initialize OpenAI client
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log_error("OPENAI_API_KEY environment variable not set")
        return False
    
    client = OpenAI(api_key=api_key)
    
    try:
        # Format search results
        formatted_search_results = format_search_results(SAMPLE_SEARCH_RESULTS)
        log_info(f"Formatted {len(SAMPLE_SEARCH_RESULTS)} search results")
        
        # Test the structured executive summary generator
        log_info("Generating structured executive summary with o4-mini model...")
        
        response = await generate_structured_executive_summary(
            client=client,
            system_prompt=BASE_SYSTEM_PROMPT,
            user_prompt=EXECUTIVE_SUMMARY_DETAILED_PROMPT,
            search_results=formatted_search_results,
            previous_sections={},
            target_word_count=1500,  # Shorter for testing
            model="o4-mini"
        )
        
        # Validate that we got a proper ExecutiveSummaryResponse
        assert isinstance(response, ExecutiveSummaryResponse), "Response is not an ExecutiveSummaryResponse"
        assert hasattr(response, "summary"), "Response missing summary field"
        assert hasattr(response, "portfolio_positions"), "Response missing portfolio_positions field"
        
        # Check that the summary is not empty
        assert response.summary, "Summary is empty"
        print(f"\nSummary excerpt (first 300 chars):\n{response.summary[:300]}...\n")
        
        # Check that we have portfolio positions
        assert response.portfolio_positions, "No portfolio positions returned"
        assert len(response.portfolio_positions) >= 5, f"Expected at least 5 positions, got {len(response.portfolio_positions)}"
        
        # Validate the first few positions
        print(f"\nValidated {len(response.portfolio_positions)} portfolio positions:\n")
        for i, position in enumerate(response.portfolio_positions[:5]):  # Show first 5 for brevity
            # Verify the position is a PortfolioPosition
            assert isinstance(position, PortfolioPosition), f"Position {i} is not a PortfolioPosition"
            
            # Test that the validations worked
            assert position.asset, f"Position {i} has empty asset"
            assert position.position_type in ["LONG", "SHORT"], f"Position {i} has invalid position_type: {position.position_type}"
            assert 0 <= position.allocation_percent <= 100, f"Position {i} has invalid allocation_percent: {position.allocation_percent}"
            
            # Print the position
            print(f"{i+1}. {position.asset} ({position.position_type}): {position.allocation_percent}% - {position.time_horizon} - {position.confidence_level}")
        
        # Test that the sum of allocations is approximately 100%
        total_allocation = sum(position.allocation_percent for position in response.portfolio_positions)
        print(f"\nTotal allocation: {total_allocation}%")
        assert 95 <= total_allocation <= 105, f"Total allocation should be approximately 100%, got {total_allocation}%"
        
        # Test the extract_structured_parts function independently with properly structured JSON
        test_content = """
        ```json
        {
          "summary": "Here's the executive summary...",
          "portfolio_positions": [
            {"asset": "STNG", "position_type": "LONG", "allocation_percent": 10, "time_horizon": "6-12 months", "confidence_level": "High"},
            {"asset": "SHEL", "position_type": "LONG", "allocation_percent": 5, "time_horizon": "12-24 months", "confidence_level": "High"}
          ]
        }
        ```
        """
        
        summary_text, positions_json = extract_structured_parts(test_content)
        assert summary_text, "Failed to extract summary text"
        assert positions_json, "Failed to extract positions JSON"
        assert "STNG" in positions_json, "Expected STNG in positions JSON"
        
        # Test the default portfolio positions generator
        default_json = generate_default_portfolio_positions()
        assert default_json, "Failed to generate default portfolio positions"
        default_positions = json.loads(default_json)
        assert len(default_positions) >= 10, f"Expected at least 10 default positions, got {len(default_positions)}"
        
        log_info("All tests passed!")
        return True
        
    except Exception as e:
        log_error(f"Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main function to run the tests."""
    success = await test_structured_executive_summary_generation()
    if success:
        print("\n✅ Structured executive summary generation tests passed!")
    else:
        print("\n❌ Structured executive summary generation tests failed!")

if __name__ == "__main__":
    asyncio.run(main())
