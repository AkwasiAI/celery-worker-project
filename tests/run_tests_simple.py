#!/usr/bin/env python
"""
Simple test runner for portfolio generator tests.
Uses Python's built-in unittest framework to handle async tests properly.
"""
import unittest
import sys
import os
import argparse


def run_tests(test_pattern=None, verbose=1):
    """
    Run all tests or tests matching a specific pattern.
    
    Args:
        test_pattern: Optional pattern to match test names
        verbose: Verbosity level (0-2)
    """
    # Add the project root to the Python path to ensure imports work correctly
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    
    # Set up the test loader
    loader = unittest.TestLoader()
    
    # Discover and load tests
    if test_pattern:
        suite = loader.loadTestsFromName(test_pattern)
    else:
        suite = loader.discover(os.path.dirname(__file__), pattern="test_*.py")
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=verbose)
    result = runner.run(suite)
    
    # Return True if all tests passed
    return result.wasSuccessful()


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
    print(f"Running tests{' matching ' + args.test_pattern if args.test_pattern else ''}...\n")
    
    # Run the tests
    success = run_tests(args.test_pattern, args.verbose)
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)
