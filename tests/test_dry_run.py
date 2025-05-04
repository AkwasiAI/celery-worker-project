#!/usr/bin/env python3
"""
Test script to perform a dry run of the generate_investment_portfolio function.
This will test all imports and functionality without actually uploading to Firestore.
"""

import asyncio
import os
from dotenv import load_dotenv

from portfolio_generator.modules.report_generator import generate_investment_portfolio
from portfolio_generator.modules.logging import log_info, log_success, log_error, log_warning

# Load environment variables
load_dotenv()

async def test_dry_run():
    """Run a dry run test of the generate_investment_portfolio function."""
    try:
        log_info("Starting dry run test of generate_investment_portfolio...")
        
        # Set test parameters
        test_mode = True   # Use mock data to avoid API calls
        dry_run = True     # Don't upload to Firestore
        priority_period = "week"  # Use the new parameter to prioritize recent news
        
        # Call the function
        result = await generate_investment_portfolio(
            test_mode=test_mode,
            dry_run=dry_run,
            priority_period=priority_period
        )
        
        # Check results
        if result and "report_content" in result:
            report_preview = result["report_content"][:200] + "..."
            log_success("Dry run completed successfully!")
            log_info(f"Report preview: {report_preview}")
            
            # Write report to file for inspection
            with open("dry_run_report.md", "w") as f:
                f.write(result["report_content"])
            log_info("Full report saved to dry_run_report.md")
            
            # Check if portfolio JSON was generated
            if "portfolio_json" in result and result["portfolio_json"]:
                log_success("Portfolio JSON was generated successfully")
            else:
                log_warning("Portfolio JSON was not generated or is empty")
                
            return True
        else:
            log_error("Dry run failed to generate report content")
            return False
            
    except Exception as e:
        log_error(f"Dry run test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_dry_run())
