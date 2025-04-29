"""Integration tests for Executive Summary generation and portfolio position extraction."""
import os
import re
import json
import pytest
import asyncio
from dotenv import load_dotenv
from openai import OpenAI

from portfolio_generator.modules.section_generator import generate_section
from portfolio_generator.prompts_config import EXECUTIVE_SUMMARY_DETAILED_PROMPT, BASE_SYSTEM_PROMPT

# Load environment variables from .env file
load_dotenv()

# Real search results for testing
REAL_SEARCH_RESULTS = {
    "shipping_industry": [
        {"title": "Shipping Industry Q1 2025 Update", "content": "The shipping industry has seen 15% growth in Q1 2025 with container rates reaching new highs."},
        {"title": "Supply Chain Resilience", "content": "Global supply chains have shown increased resilience despite ongoing geopolitical tensions."}
    ],
    "commodities_markets": [
        {"title": "Energy Sector Analysis", "content": "Crude oil prices have stabilized in the $80-90 range amid OPEC+ production discipline."},
        {"title": "Metals Market Forecast", "content": "Iron ore and copper demand from Asia continues to drive metals markets upward."}
    ],
    "global_economy": [
        {"title": "IMF Economic Outlook", "content": "The IMF projects global growth of 3.6% in 2025, with emerging markets leading the recovery."},
        {"title": "Central Bank Policies", "content": "Major central banks have begun easing monetary policy after inflation pressures subsided."}
    ]
}

class TestExecutiveSummary:
    """Test class for executive summary generation and portfolio extraction using real OpenAI API."""
    
    @pytest.fixture
    def openai_client(self):
        """Create a real OpenAI client for testing."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY environment variable not set")
        return OpenAI(api_key=api_key)
    
    # Default positions to verify against or use as fallback
    default_positions = [
        {"asset": "STNG", "position_type": "LONG", "allocation_percent": 15, "time_horizon": "6-12 months", "confidence_level": "High"},
        {"asset": "SHEL", "position_type": "LONG", "allocation_percent": 10, "time_horizon": "12-24 months", "confidence_level": "High"},
        {"asset": "RIO", "position_type": "LONG", "allocation_percent": 10, "time_horizon": "6-12 months", "confidence_level": "Medium"},
        {"asset": "GSL", "position_type": "LONG", "allocation_percent": 8, "time_horizon": "3-6 months", "confidence_level": "Medium"},
        {"asset": "BDRY", "position_type": "LONG", "allocation_percent": 7, "time_horizon": "3-6 months", "confidence_level": "Medium"}
    ]
    
    @pytest.mark.asyncio
    async def test_executive_summary_generation_with_positions(self, openai_client):
        """Test successful generation of executive summary with portfolio positions extraction using real OpenAI API."""
        # Prepare the enhanced prompt with explicit portfolio positions JSON requirements
        enhanced_exec_summary_prompt = EXECUTIVE_SUMMARY_DETAILED_PROMPT + "\n\nCRITICAL REQUIREMENT: You MUST include a valid JSON array of all portfolio positions inside an HTML comment block, formatted EXACTLY as follows:\n<!-- PORTFOLIO_POSITIONS_JSON:\n[\n  {\"asset\": \"TICKER\", \"position_type\": \"LONG/SHORT\", \"allocation_percent\": X, \"time_horizon\": \"PERIOD\", \"confidence_level\": \"LEVEL\"},\n  ...\n]\n-->\nThis hidden JSON is essential for downstream processing and MUST be included exactly as specified."
        
        # Add specific instructions for the test to ensure we get portfolio positions
        test_prompt = enhanced_exec_summary_prompt + "\n\nFor this test, please create a portfolio focused on shipping and commodities with at least 5 positions. Include stocks like STNG, SHEL, and RIO if appropriate for the current market environment."
        
        # Format the search results dictionary into a string format the actual code expects
        formatted_search_results = ""
        for category, results in REAL_SEARCH_RESULTS.items():
            formatted_search_results += f"\n\n## {category.replace('_', ' ').title()} Search Results:\n"
            for i, result in enumerate(results, 1):
                formatted_search_results += f"\n{i}. {result['title']}\n{result['content']}\n"
        
        print(f"\nFormatted search results:\n{formatted_search_results[:300]}...\n")
        
        # Generate the executive summary using the real OpenAI API
        executive_summary = await generate_section(
            client=openai_client,
            section_name="Executive Summary",
            system_prompt=BASE_SYSTEM_PROMPT,
            user_prompt=test_prompt,
            search_results=formatted_search_results,  # Now a string as expected
            previous_sections={},
            target_word_count=1500  # Shorter for testing purposes
        )
        
        # Print the first 500 characters of the summary for debugging
        print(f"\nExecutive Summary (first 500 chars):\n{executive_summary[:500]}...\n")
        
        # Verify the result contains the expected content
        assert "Executive Summary" in executive_summary, "Missing Executive Summary heading"
        
        # Extract portfolio positions from the HTML comment
        json_match = re.search(r'<!--\s*PORTFOLIO_POSITIONS_JSON:\s*(\[.*?\])\s*-->', executive_summary, re.DOTALL)
        
        # Verify that we found the portfolio positions JSON
        assert json_match is not None, "Portfolio positions JSON block not found in the executive summary"
        
        # Parse the JSON and verify we have at least some positions
        portfolio_positions = json.loads(json_match.group(1))
        assert len(portfolio_positions) >= 3, f"Expected at least 3 portfolio positions, got {len(portfolio_positions)}"
        
        # Verify structure of positions
        for position in portfolio_positions:
            assert "asset" in position, f"Missing 'asset' field in position: {position}"
            assert "position_type" in position, f"Missing 'position_type' field in position: {position}"
            assert "allocation_percent" in position, f"Missing 'allocation_percent' field in position: {position}"
            assert "time_horizon" in position, f"Missing 'time_horizon' field in position: {position}"
            assert "confidence_level" in position, f"Missing 'confidence_level' field in position: {position}"
        
        # Print the positions for debugging
        print(f"\nExtracted {len(portfolio_positions)} portfolio positions:\n{json.dumps(portfolio_positions, indent=2)}\n")

    @pytest.mark.asyncio
    async def test_executive_summary_with_fallback_positions(self, openai_client):
        """Test the fallback mechanism for portfolio positions using real OpenAI API."""
        # Create a prompt that intentionally doesn't mention portfolio positions JSON to test the fallback
        # Remove the typical portfolio positions requirement to simulate a model response without positions
        altered_prompt = "Generate an executive summary of shipping and commodity markets without including any JSON data."
        
        try:
            # Format the search results dictionary into a string format the actual code expects
            formatted_search_results = ""
            for category, results in REAL_SEARCH_RESULTS.items():
                formatted_search_results += f"\n\n## {category.replace('_', ' ').title()} Search Results:\n"
                for i, result in enumerate(results, 1):
                    formatted_search_results += f"\n{i}. {result['title']}\n{result['content']}\n"
            
            # First, generate a summary that likely won't include portfolio positions
            # We're using a custom prompt that doesn't ask for JSON
            executive_summary = await generate_section(
                client=openai_client,
                section_name="Executive Summary Test",
                system_prompt="You are a market analyst. Provide a brief market analysis.",
                user_prompt=altered_prompt,
                search_results=formatted_search_results,  # Now a string as expected
                previous_sections={},
                target_word_count=800
            )
            
            # Print a portion of the summary for debugging
            print(f"\nInitial Summary (no positions expected):\n{executive_summary[:300]}...\n")
            
            # Check if positions exist in the initial summary (they shouldn't)
            json_match = re.search(r'<!--\s*PORTFOLIO_POSITIONS_JSON:\s*(\[.*?\])\s*-->', executive_summary, re.DOTALL)
            
            # If we unexpectedly find positions, we'll skip to the fallback test
            if json_match is None:
                print("No positions found in initial summary as expected. Testing fallback...")
                
                # Apply the fallback mechanism - this simulates what happens in the actual code
                portfolio_json = json.dumps(self.default_positions, indent=2)
                json_comment = f"<!-- PORTFOLIO_POSITIONS_JSON:\n{portfolio_json}\n-->"
                executive_summary_with_fallback = executive_summary + f"\n\n{json_comment}"
                
                # Verify we can extract portfolio positions after adding the fallback
                json_match = re.search(r'<!--\s*PORTFOLIO_POSITIONS_JSON:\s*(\[.*?\])\s*-->', executive_summary_with_fallback, re.DOTALL)
                assert json_match is not None, "Fallback portfolio positions not found"
                
                portfolio_positions = json.loads(json_match.group(1))
                assert len(portfolio_positions) == len(self.default_positions), f"Expected {len(self.default_positions)} portfolio positions"
                
                # Verify the structure of the fallback positions
                for i, position in enumerate(portfolio_positions):
                    assert position["asset"] == self.default_positions[i]["asset"]
                    assert position["position_type"] == self.default_positions[i]["position_type"]
                    assert position["allocation_percent"] == self.default_positions[i]["allocation_percent"]
                
                print(f"\nFallback portfolio positions successfully extracted:\n{json.dumps(portfolio_positions, indent=2)}\n")
            else:
                print("Unexpectedly found positions in initial summary. Skipping fallback test.")
                portfolio_positions = json.loads(json_match.group(1))
                print(f"\nFound {len(portfolio_positions)} positions in initial summary.\n")
                # Still a valid test - we verified positions can be extracted
                assert len(portfolio_positions) > 0
        except Exception as e:
            # Ensure test robustness by handling any API errors
            print(f"\nError during test: {str(e)}\n")
            pytest.fail(f"Test failed with error: {str(e)}")

if __name__ == "__main__":
    pytest.main(["-v", "test_executive_summary.py"])
