#!/usr/bin/env python3
"""
Integration test for the generate_section_with_web_search function with real API calls.
This will test that the function correctly uses the web search capability.
"""

import asyncio
import os
from dotenv import load_dotenv
from openai import OpenAI

from portfolio_generator.modules.section_generator import generate_section_with_web_search
from portfolio_generator.modules.logging import log_info, log_success, log_error

# Load environment variables
load_dotenv()

async def test_generate_section_with_web_search():
    """Test the generate_section_with_web_search function with a real API call."""
    try:
        log_info("Starting integration test of generate_section_with_web_search...")
        
        # Initialize OpenAI client
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Create test inputs
        section_name = "Portfolio Holdings"
        system_prompt = """You are an expert financial analyst creating a comprehensive investment report.
        Use web search to find the latest information about market trends and investment opportunities.
        Provide your analysis based on current market conditions and recent news."""
        
        user_prompt = """Create an analysis of current shipping industry investment opportunities,
        focusing on major companies, market trends, and future outlook.
        Include specific stock recommendations with supporting rationale."""
        
        # Test parameters
        target_word_count = 300
        
        # Call the function with real API
        log_info("Making API call with web search...")
        content = await generate_section_with_web_search(
            client=client,
            section_name=section_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            target_word_count=target_word_count
        )
        
        # Check results
        if content:
            log_success("Web search section generation completed successfully!")
            log_info("Generated content:")
            print("\n" + "-" * 80)
            print(content)
            print("-" * 80 + "\n")
            
            # Check word count
            word_count = len(content.split())
            log_info(f"Word count: {word_count} words")
            
            # Save to file for later inspection
            with open("test_web_section_output.md", "w") as f:
                f.write(content)
            log_info("Output saved to test_web_section_output.md")
            
            return True
        else:
            log_error("Web search section generation failed to produce content")
            return False
            
    except Exception as e:
        log_error(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_generate_section_with_web_search())
