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
    """Run the integration test for the news update generator."""
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
    
    # Create fake search results (one per category)
    search_results = [
        {
            "query": "Latest shipping industry news",
            "results": [{
                "content": "Global shipping rates have increased by 15% in the past month due to ongoing tensions in the Red Sea. Several major shipping companies have announced plans to reroute vessels around the Cape of Good Hope, adding approximately 10-14 days to shipping times between Asia and Europe. Industry analysts predict these disruptions could continue for several months, putting additional pressure on global supply chains and potentially increasing costs for consumers."
            }],
            "citations": ["https://www.maritime-news.com/shipping-rates-increase", "https://www.supply-chain-weekly.com/red-sea-disruptions"]
        },
        {
            "query": "Latest commodity market trends",
            "results": [{
                "content": "Oil prices have stabilized around $85 per barrel after recent volatility. Meanwhile, precious metals continue their upward trend with gold reaching new all-time highs above $2,400 per ounce as investors seek safe-haven assets amid economic uncertainty. Agricultural commodities have shown mixed performance, with wheat prices rising due to weather concerns in key growing regions while corn prices have declined due to expectations of a record harvest in major producing countries."
            }],
            "citations": ["https://www.commodity-insights.com/oil-stabilization", "https://www.gold-market-analysis.org/new-highs"]
        },
        {
            "query": "Recent central bank decisions and monetary policy",
            "results": [{
                "content": "The Federal Reserve has signaled it may begin cutting interest rates later this year, with markets now expecting between two and three 25-basis-point cuts in 2025. The European Central Bank has already begun its easing cycle with a cut in June, while the Bank of Japan has moved in the opposite direction, raising rates for the first time in 17 years as it exits its negative interest rate policy. These divergent policy paths are creating new dynamics in currency markets and global capital flows."
            }],
            "citations": ["https://www.central-bank-watch.com/fed-signals", "https://www.monetary-policy-review.org/global-divergence"]
        },
        {
            "query": "Latest macroeconomic indicators and forecasts",
            "results": [{
                "content": "Global economic growth is expected to reach 3.1% in 2025, slightly above previous forecasts. Inflation continues to moderate in most developed economies, though core services inflation remains sticky. Labor markets are showing signs of cooling, with job openings declining but unemployment rates still near historic lows in many countries. Consumer spending has remained resilient despite higher interest rates, but there are early signs of stress in certain consumer segments as pandemic savings are depleted."
            }],
            "citations": ["https://www.economic-outlook.org/global-forecast-2025", "https://www.inflation-tracker.com/services-stickiness"]
        },
        {
            "query": "Recent developments in global trade agreements and tariffs",
            "results": [{
                "content": "Negotiations for the Indo-Pacific Economic Framework (IPEF) have accelerated, with participants aiming to finalize agreements by the end of the year. Meanwhile, tensions between major economies persist, with new tariffs imposed on critical minerals and semiconductor-related products. The World Trade Organization has warned that the rising trend of protectionist measures could reduce global GDP by up to 1% over the next five years if current trajectories continue."
            }],
            "citations": ["https://www.trade-policy-institute.org/ipef-negotiations", "https://www.wto-analysis.com/protectionism-impact"]
        }
    ]
    
    # Maximum words for summaries
    max_words = 50
    
    log_info("Starting news update section generation...")
    
    # Call the function we're testing
    news_section = generate_news_update_section(
        client=client,
        search_results=search_results,
        investment_principles=investment_principles,
        categories=categories,
        max_words=max_words
    )
    
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
