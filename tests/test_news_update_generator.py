#!/usr/bin/env python3
"""
Integration test for the news update generator.
Uses fake search results but real OpenAI API calls and investment principles.
"""
import os
import sys
import asyncio
from dotenv import load_dotenv
from openai import OpenAI

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from portfolio_generator.modules.news_update_generator import generate_news_update_section
from portfolio_generator.modules.logging import log_info, log_success, log_error


async def run_test():
    """Run the integration test for the news update generator using saved search results.
    
    This test uses real search results saved by the save_test_search_results.py script,
    which ensures we're testing with realistic data rather than simple test fixtures.
    """
    # Load environment variables (for OpenAI API key)
    load_dotenv()
    
    # Check if OpenAI API key is available
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log_error("OPENAI_API_KEY environment variable is not set!")
        return
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Load real investment principles
    try:
        principles_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            "portfolio_generator", 
            "modules", 
            "orasis_investment_principles.txt"
        )
        
        if not os.path.exists(principles_path):
            # Check alternate location
            principles_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                "portfolio_generator", 
                "orasis_investment_principles.txt"
            )
        
        with open(principles_path, "r") as f:
            investment_principles = f.read().strip()
            log_info(f"Loaded investment principles ({len(investment_principles)} chars)")
    except Exception as e:
        log_error(f"Failed to load investment principles: {e}")
        # Use a minimal set of principles for testing if file not found
        investment_principles = """
        1. Focus on long-term value creation
        2. Diversify across sectors and geographies
        3. Consider macroeconomic factors in investment decisions
        """
    
    # Create categories for news sections
    categories = [
        ("Shipping", 0, 1),
        ("Commodities", 1, 2),
        ("Central Bank Policies", 2, 3),
        ("Macroeconomic News", 3, 4),
        ("Global Trade & Tariffs", 4, 5)
    ]
    
    # Load the saved search results file
    import json
    search_results_path = os.path.join(os.path.dirname(__file__), "search_results_20250501.json")
    
    log_info(f"Loading search results from {search_results_path}")
    try:
        with open(search_results_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            search_results = data.get("search_results", [])
            if not search_results:
                log_error(f"No search results found in {search_results_path}")
                return
                
            log_info(f"Loaded {len(search_results)} search results")
            # Log categories and result counts
            for i, result in enumerate(search_results):
                category = result.get("category", "Unknown")
                count = len(result.get("results", []))
                log_info(f"Category '{category}': {count} results")
    except Exception as e:
        log_error(f"Error loading search results: {e}")
        # Fall back to fake data
        log_info("Falling back to fake search results")
        search_results = [
            {
                "query": "Latest shipping industry news",
                "category": "Shipping",
                "results": [{
                    "title": "Shipping 1",
                    "content": "Global shipping rates have increased by 15% in the past month due to ongoing tensions in the Red Sea."
                }]
            },
            {
                "query": "Latest commodity market trends",
                "category": "Commodities",
                "results": [{
                    "title": "Commodities 1",
                    "content": "Oil prices have stabilized around $85 per barrel after recent volatility."
                }]
            },
            {
                "query": "Recent central bank decisions",
                "category": "Central Bank Policies",
                "results": [{
                    "title": "Central Bank Policies 1",
                    "content": "The Federal Reserve has signaled it may begin cutting interest rates later this year."
                }]
            },
            {
                "query": "Latest macroeconomic indicators",
                "category": "Macroeconomic News",
                "results": [{
                    "title": "Macroeconomic News 1",
                    "content": "Global economic growth is expected to reach 3.1% in 2025, slightly above previous forecasts."
                }]
            },
            {
                "query": "Recent developments in global trade",
                "category": "Global Trade & Tariffs",
                "results": [{
                    "title": "Global Trade & Tariffs 1",
                    "content": "Negotiations for the Indo-Pacific Economic Framework have accelerated."
                }]
            }
        ]
    
    # Maximum words for summaries
    max_words = 50
    
    log_info("Starting news update section generation...")
    
    # Call the function we're testing
    try:
        log_info("Calling generate_news_update_section with real search data...")
        news_section = await generate_news_update_section(
            client=client,
            search_results=search_results,
            categories=categories,
            investment_principles=investment_principles,
            model="o4-mini"
        )
    except Exception as e:
        log_error(f"Error generating news update section: {e}")
        import traceback
        traceback.print_exc()
        return
    
    log_success("Successfully generated news update section")
    print("\n--- GENERATED NEWS UPDATE SECTION ---\n")
    print(news_section)
    print("\n--- END OF SECTION ---\n")
    
    # Save the output to a file for inspection
    output_file = os.path.join(os.path.dirname(__file__), "news_update_test_output.md")
    with open(output_file, "w") as f:
        f.write(news_section)
    
    log_info(f"Saved news update section to {output_file}")


if __name__ == "__main__":
    # Run the test
    asyncio.run(run_test())
