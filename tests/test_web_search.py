#!/usr/bin/env python3
"""
Integration test for the generate_section_with_web_search function.
"""

import asyncio
import os
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

from portfolio_generator.modules.section_generator import generate_section_with_web_search
from portfolio_generator.prompts_config import BASE_SYSTEM_PROMPT
from portfolio_generator.modules.logging import log_info, log_warning, log_error, log_success

# Load environment variables
load_dotenv()

async def test_web_search_integration():
    """Run an integration test of the web search-enabled section generator."""
    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Create fake section name
    section_name = "Global Economic Outlook"
    
    # Create fake user prompt
    user_prompt = """
    Write a detailed analysis of the current global economic outlook, with specific focus on:
    1. Major economic indicators and trends
    2. Regional economic performance (US, EU, China, emerging markets)
    3. Trade patterns and disruptions
    4. Impact on shipping and commodities markets
    5. Policy responses from central banks
    
    Include specific data points and focus on implications for investors in the shipping and commodities sectors.
    """
    
    # Get the real system prompt with formatting
    current_year = datetime.now().year
    next_year = current_year + 1
    total_word_count = 1500
    # Set priority period for news to 'week' for testing purposes
    priority_period = "week"
    
    system_prompt = BASE_SYSTEM_PROMPT.format(
        total_word_count=total_word_count,
        current_year=current_year,
        next_year=next_year,
        priority_period=priority_period
    )
    
    # Create fake previous sections
    previous_sections = {
        "Executive Summary": """
        # Executive Summary
        
        Orasis Capital Multi-Asset Portfolio – April 29, 2025
        
        The current global economic landscape presents a complex mix of challenges and opportunities for investors. While traditional markets in the US and Europe continue to show signs of slowing growth and monetary tightening, emerging economies in Asia and Africa are demonstrating resilience and increased trade activity. This divergence creates significant opportunities for targeted investments in shipping, commodities, and trade-focused assets.
        
        Our portfolio strategy emphasizes positioning in high-quality shipping assets, particularly in the tanker and LNG segments, where supply constraints and ton-mile expansion create favorable conditions. We also maintain selective exposure to commodity producers benefiting from renewed Asian demand, while maintaining tactical hedges against overvalued regions and sectors facing structural headwinds.
        
        | Asset/Ticker | Position Type | Allocation % | Time Horizon | Confidence Level |
        |--------------|--------------|--------------|--------------|-----------------|
        | HAFNIA | LONG | 8.5% | Medium-term (1q-6m) | High |
        | STNG | LONG | 7.2% | Medium-term (1q-6m) | High |
        | FRO | LONG | 6.4% | Medium-term (1q-6m) | High |
        | FLNG | LONG | 5.8% | Medium-long term (6m-1yr) | Moderate |
        | GOGL | LONG | 5.1% | Long-term (2-3yr) | Moderate |
        | RIO | LONG | 6.7% | Medium-long term (6m-1yr) | High |
        | BHP | LONG | 6.3% | Medium-long term (6m-1yr) | High |
        | SHEL | LONG | 5.6% | Long-term (2-3yr) | Moderate |
        | SPY | SHORT | 8.2% | Short-term (1m-1q) | Moderate |
        | MAERSK-B.CO | SHORT | 5.2% | Medium-term (1q-6m) | Moderate |
        """
    }
    
    # Fake search results (though these won't be used directly with web search)
    search_results = "These search results won't be used directly since the function will perform its own web searches."
    
    # Target word count
    target_word_count = 1000
    
    try:
        log_info("Starting integration test of web search-enabled section generator...")
        
        # Call the function
        section_content = await generate_section_with_web_search(
            client,
            section_name,
            system_prompt,
            user_prompt,
            search_results,
            previous_sections,
            target_word_count
        )
        
        # Check results
        if section_content and len(section_content.split()) > 100:
            log_success(f"Successfully generated section with {len(section_content.split())} words")
            print("\n===== SECTION CONTENT PREVIEW =====\n")
            print(section_content[:500] + "...\n")
            
            # Write to file for reference
            with open("web_search_test_output.md", "w") as f:
                f.write(section_content)
            log_info("Saved full output to web_search_test_output.md")
        else:
            log_error("Failed to generate adequate section content")
            print(section_content)
    
    except Exception as e:
        log_error(f"Test failed with error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_web_search_integration())
