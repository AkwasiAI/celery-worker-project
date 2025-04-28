#!/usr/bin/env python
"""
Simple test script to verify the report_generator functionality.
"""

import asyncio
import json
import sys
import os

# Add the parent directory to sys.path to ensure imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from portfolio_generator.modules.report_generator import generate_investment_portfolio

async def run_test():
    """
    Run a simple test of the report generator with dry_run and test_mode enabled.
    """
    print("Testing report_generator with dry_run and test_mode...")
    try:
        result = await generate_investment_portfolio(dry_run=True, test_mode=True)
        print(f"Test completed successfully!")
        print(f"Result: {json.dumps(result, indent=2)}")
        return True
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(run_test())
    sys.exit(0 if success else 1)
