#!/usr/bin/env python
"""
Test runner for portfolio generator tests.
Executes all tests to verify modules can be imported and used correctly.
"""
import unittest
import sys
import os
import argparse
import asyncio


def run_tests(test_pattern=None, verbose=1):
    """
    Run all tests or tests matching a specific pattern.
    
    Args:
        test_pattern: Optional pattern to match test names
        verbose: Verbosity level (0-2)
    
    Returns:
        bool: True if all tests passed, False otherwise
    """
    # Add the project root to the Python path to ensure imports work correctly
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    
    # Discover and load tests
    loader = unittest.TestLoader()
    if test_pattern:
        suite = loader.loadTestsFromName(test_pattern)
    else:
        # Discover all tests in the tests directory
        suite = loader.discover(os.path.dirname(__file__), pattern="test_*.py")
    
    # Create a test runner
    runner = unittest.TextTestRunner(verbosity=verbose)
    
    # Run the tests
    print(f"Running tests{'matching ' + test_pattern if test_pattern else ''}...\n")
    result = runner.run(suite)
    
    # Return True if all tests passed, False otherwise
    return result.wasSuccessful()


class AsyncioTestRunner:
    """Custom test runner for asyncio tests."""
    
    def __init__(self, test_pattern=None, verbose=1):
        self.test_pattern = test_pattern
        self.verbose = verbose
    
    def run(self):
        """Run tests with asyncio support."""
        # Use asyncio.run which creates a new event loop and closes it at the end
        try:
            # For Python 3.7+
            return asyncio.run(self._run_async())
        except RuntimeError:
            # Fallback for when there might be an existing event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self._run_async())
                return result
            finally:
                loop.close()
    
    async def _run_async(self):
        """Run the tests asynchronously."""
        # Run the tests synchronously (they handle their own async)
        return run_tests(self.test_pattern, self.verbose)


if __name__ == "__main__":
    # Set up command-line arguments
    parser = argparse.ArgumentParser(description="Run tests for portfolio generator modules")
    parser.add_argument("--test", "-t", dest="test_pattern", 
                       help="Run tests matching this pattern (e.g. test_imports)")
    parser.add_argument("--verbose", "-v", action="count", default=1,
                       help="Increase verbosity (specify multiple times for more)")
    args = parser.parse_args()
    
    print("Portfolio Generator Module Tests")
    print("===============================\n")
    
    # Run the tests with asyncio support
    runner = AsyncioTestRunner(args.test_pattern, args.verbose)
    success = runner.run()
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)
