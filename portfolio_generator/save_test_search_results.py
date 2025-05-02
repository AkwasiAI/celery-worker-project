#!/usr/bin/env python3
"""
Utility to save formatted search results for testing purposes.
This allows testing the news update generator with real search data.
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Tuple
from datetime import datetime
from openai import OpenAI
import dotenv

from portfolio_generator.modules.web_search import PerplexitySearch
from portfolio_generator.modules.logging import log_info, log_warning, log_error

# Load environment variables
dotenv.load_dotenv()

async def perform_web_searches_and_save_results(
    queries: List[str],
    categories: List[Tuple[str, int, int]] = None,
    output_file: str = None,
    investment_principles: str = ""
) -> List[Dict[str, Any]]:
    """
    Perform web searches for a list of queries and save the results to a file.
    
    Args:
        queries: List of search queries to execute
        output_file: Path to save the results (default: tests/search_results_{timestamp}.json)
        investment_principles: Optional investment principles to include in search context
        
    Returns:
        The search results that were saved
    """
    # Initialize Perplexity search client
    api_key = os.environ.get('PERPLEXITY_API_KEY')
    if not api_key:
        raise ValueError("PERPLEXITY_API_KEY environment variable is required")
    
    log_info(f"Initializing PerplexitySearch with API key")
    search_client = PerplexitySearch(api_key=api_key)
    
    # Execute the searches
    log_info(f"Performing {len(queries)} web searches with Perplexity API...")
    search_results = await search_client.search(queries, investment_principles)
    log_info(f"Completed {len(search_results)} web searches")
    
    # Process search results to ensure they are usable for news update generation
    processed_results = []
    
    if categories and len(categories) == len(search_results):
        for i, (category_name, _, _) in enumerate(categories):
            if i < len(search_results):
                # Create a new processed result that includes category information
                processed_result = {
                    "query": search_results[i].get("query", f"Query {i}"),
                    "category": category_name,
                    "results": [],
                }
                
                # Process each individual result in this search result
                if 'results' in search_results[i] and search_results[i]['results']:
                    for j, result in enumerate(search_results[i]['results']):
                        # Create a new result with a proper title based on category
                        new_result = {
                            "title": f"{category_name} {j+1}",  # Give unique title based on category
                            "url": result.get("url", "https://example.com"),
                            "content": result.get("content", ""),
                            "raw_content": result.get("raw_content", result.get("content", ""))
                        }
                        
                        # Add the processed result
                        processed_result["results"].append(new_result)
                        log_info(f"Processed result for '{category_name}': {new_result['title']}")
                
                # Add this processed result to our list
                processed_results.append(processed_result)
                log_info(f"Processed {len(processed_result['results'])} items for category: {category_name}")
    
        log_info(f"Processed {len(processed_results)} total search results with proper category assignments")
        search_results = processed_results
    
    # Determine output file path if not provided
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create tests directory if it doesn't exist
        tests_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests")
        os.makedirs(tests_dir, exist_ok=True)
        output_file = os.path.join(tests_dir, f"search_results_{timestamp}.json")
    
    # Save search results to file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            # Create a serializable dict with metadata
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "query_count": len(queries),
                "queries": queries,
                "search_results": search_results
            }
            json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            # Log some details about what we saved
            result_counts = {}
            for i, result in enumerate(search_results):
                category = result.get('category', f'Category {i}')
                count = len(result.get('results', []))
                result_counts[category] = count
                
            log_info(f"Results by category: {result_counts}")
        
        log_info(f"Search results saved to {output_file}")
        
        # Also save a summary file with just query and result lengths for quick reference
        summary_file = os.path.splitext(output_file)[0] + "_summary.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"Search results summary ({len(queries)} queries)\n")
            f.write("=" * 50 + "\n\n")
            for i, result in enumerate(search_results):
                query = queries[i] if i < len(queries) else "Unknown query"
                result_count = len(result.get("results", [])) if "results" in result else 0
                f.write(f"Query {i+1}: {query}\n")
                f.write(f"Results: {result_count} items\n")
                # Include a snippet of the first result if available
                if result_count > 0 and "content" in result["results"][0]:
                    content = result["results"][0]["content"]
                    snippet = content[:150] + "..." if len(content) > 150 else content
                    f.write(f"First result snippet: {snippet}\n")
                f.write("\n" + "-" * 40 + "\n\n")
        
        return search_results
    
    except Exception as e:
        log_error(f"Error saving search results: {e}")
        return search_results

async def main():
    """Main function to execute when running script directly."""
    # Define sample queries matching those used in the real portfolio generator
    queries = [
        "latest shipping rates VLCC Aframax Suezmax dry bulk tankers",
        "latest commodities market analysis gold oil steel iron ore",
        "central bank policies Federal Reserve ECB interest rates inflation",
        "latest macroeconomic data GDP inflation unemployment rate",
        "global trade tariffs supply chain disruptions China US"
    ]
    
    # Define categories matching those in the report_generator.py
    categories = [
        ("Shipping", 0, 1),
        ("Commodities", 1, 2),
        ("Central Bank Policies", 2, 3),
        ("Macroeconomic News", 3, 4),
        ("Global Trade & Tariffs", 4, 5)
    ]
    
    # Example investment principles
    investment_principles = """
    Orasis Capital focuses on global trade flow dynamics as a leading macroeconomic indicator,
    with particular attention to shipping, energy, and commodity markets.
    """
    
    # Perform searches and save results
    output_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "tests", 
        f"search_results_{datetime.now().strftime('%Y%m%d')}.json"
    )
    
    search_results = await perform_web_searches_and_save_results(
        queries=queries,
        categories=categories,
        output_file=output_file,
        investment_principles=investment_principles
    )
    
    print(f"\nSaved {len(search_results)} search results to {output_file}")
    print(f"You can now use this file to test the news update generator functionality")

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())
