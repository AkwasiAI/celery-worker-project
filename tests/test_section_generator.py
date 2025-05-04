#!/usr/bin/env python3
"""
Integration test for the generate_section function with real API calls.
This will test that the function correctly interacts with the OpenAI API.
"""

import asyncio
import os
from dotenv import load_dotenv
from openai import OpenAI

from portfolio_generator.modules.section_generator import generate_section
from portfolio_generator.modules.logging import log_info, log_success, log_error

# Load environment variables
load_dotenv()

async def test_generate_section():
    """Test the generate_section function with a real API call."""
    try:
        log_info("Starting integration test of generate_section...")
        
        # Initialize OpenAI client
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Create test inputs
        section_name = "Test Section"
        system_prompt = """You are an expert financial analyst creating a section for an investment report.
        Be concise, factual, and provide valuable insights. Focus on clarity and brevity."""
        
        user_prompt = """Create a brief analysis of the technology sector, focusing on major trends 
        and investment opportunities. Keep it short and concise, around 200 words."""
        
        # Test parameters
        target_word_count = 200
        
        # Call the function with real API
        log_info("Making API call to OpenAI...")
        content = await generate_section(
            client=client,
            section_name=section_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            target_word_count=target_word_count
        )
        
        # Check results
        if content:
            log_success("Generate section test completed successfully!")
            log_info("Generated content:")
            print("\n" + "-" * 80)
            print(content)
            print("-" * 80 + "\n")
            
            # Check word count
            word_count = len(content.split())
            log_info(f"Word count: {word_count} words")
            
            # Save to file for later inspection
            with open("test_section_output.md", "w") as f:
                f.write(content)
            log_info("Output saved to test_section_output.md")
            
            return True
        else:
            log_error("Generate section test failed to produce content")
            return False
            
    except Exception as e:
        log_error(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_generate_section())
