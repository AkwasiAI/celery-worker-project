#!/usr/bin/env python3
"""Integration test for executive summary generation and extraction."""
import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

from portfolio_generator.prompts_config import EXECUTIVE_SUMMARY_DETAILED_PROMPT
from portfolio_generator.modules.structured_section_generator import extract_structured_parts, generate_structured_executive_summary

# Load environment variables (including API keys)
load_dotenv()

# Sample fake web search results
FAKE_SEARCH_RESULTS = """
### Search Results for "latest shipping rates"

#### Source 1: Maritime Industry Report (2025-04-29)
Tanker shipping rates reached a 5-year high in April 2025, with VLCC rates averaging $75,000/day on key routes. Analysts attribute this to increased ton-mile demand due to geopolitical tensions and longer trade routes.

#### Source 2: Bloomberg (2025-04-28) 
Dry bulk shipping rates have seen moderate recovery, with the Baltic Dry Index reaching 2,450 points, up 15% from last month. Chinese steel production and Australian iron ore exports are cited as key drivers.

#### Source 3: Financial Times (2025-04-30)
Container shipping rates on Asia-Europe routes showed stability at $3,500/TEU, while transpacific routes experienced a 7% increase to $4,200/TEU, according to Xeneta data. Carriers are successfully managing capacity ahead of peak season.

### Search Results for "energy market outlook 2025"

#### Source 1: IEA Monthly Report (2025-04-15)
The International Energy Agency projects Brent crude oil prices to average $82-88/barrel for the remainder of 2025, with potential upside risk from OPEC+ production discipline and Middle East tensions.

#### Source 2: Energy Intelligence Group (2025-04-22)
Natural gas prices are expected to remain elevated in Europe at €35-40/MWh due to continued competition with Asian buyers for LNG cargoes. US natgas prices forecasted at $3.50-4.00/MMBtu.

#### Source 3: Goldman Sachs Research (2025-04-25)
Energy transition spending is projected to reach $1.8 trillion in 2025, with particular growth in battery storage, hydrogen infrastructure, and grid expansion projects.
"""

# Sample system prompt for testing
TEST_SYSTEM_PROMPT = """You are a professional investment analyst focused on shipping, energy, and commodities markets.
Your task is to generate an executive summary for an investment portfolio report."""

async def test_executive_summary_generation():
    """Test executive summary generation and extraction."""
    print("Starting executive summary integration test...")
    
    # Create OpenAI client
    client = OpenAI()
    
    # Format executive summary prompt with current date and year
    current_date = datetime.now().strftime("%B %d, %Y")
    current_year = datetime.now().year
    exec_summary_prompt = EXECUTIVE_SUMMARY_DETAILED_PROMPT.format(
        current_date=current_date,
        current_year=current_year,
        total_word_count=500
    )
    
    print(f"Testing with model: gpt-4o")
    
    # Generate structured executive summary
    try:
        # Create a modified version of the generate_structured_executive_summary function to capture raw output
        from portfolio_generator.modules.structured_section_generator import generate_structured_executive_summary as original_gen_func
        
        # Simulate the API call to get raw response for testing extraction
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": TEST_SYSTEM_PROMPT},
                {"role": "user", "content": exec_summary_prompt + (f"\n\nHere is the latest information from web searches that should inform your analysis:\n\n{FAKE_SEARCH_RESULTS}" if FAKE_SEARCH_RESULTS else "")}
            ],
            temperature=0.7,
            max_completion_tokens=4000
        )
        
        # Save the raw response for testing extraction separately
        raw_model_output = response.choices[0].message.content
        
        # Now call the actual function normally
        structured_response = await generate_structured_executive_summary(
            client=client,
            system_prompt=TEST_SYSTEM_PROMPT,
            user_prompt=exec_summary_prompt,
            search_results=FAKE_SEARCH_RESULTS,
            previous_sections={},
            target_word_count=500,
            model="o4-mini"
        )
        
        print("\n=== RESULT WITH o4-mini ===")
        print(f"Summary length: {len(structured_response.summary)} characters")
        print(f"Portfolio positions: {len(structured_response.portfolio_positions)} items")
        
        # Print a sample of the summary and positions
        print("\nSummary (first 300 chars):")
        print(structured_response.summary[:300] + "...")
        
        if structured_response.portfolio_positions:
            print("\nFirst 3 portfolio positions:")
            for pos in structured_response.portfolio_positions[:3]:
                print(f"  - {pos.asset} ({pos.position_type}): {pos.allocation_percent}%, {pos.time_horizon}, {pos.confidence_level}")
        
        # Test extraction separately on the raw model output
        # Save raw output to a file for inspection
        with open("test_executive_summary_raw.md", "w") as f:
            f.write(raw_model_output)
        
        summary_text, positions_json = extract_structured_parts(raw_model_output)
        
        print("\n=== EXTRACTION TEST (on raw output) ===")
        print(f"Successfully extracted text of {len(summary_text)} characters")
        
        positions = json.loads(positions_json)
        print(f"Successfully extracted {len(positions)} portfolio positions")
        
        # Save the result to a file for inspection
        with open("test_executive_summary_result.md", "w") as f:
            f.write(structured_response.summary)
        print("\nSaved full result to test_executive_summary_result.md")
        
    except Exception as e:
        print(f"Error during test: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
    print("\nTest completed.")

if __name__ == "__main__":
    asyncio.run(test_executive_summary_generation())
