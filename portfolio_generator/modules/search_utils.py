"""Search utilities for the portfolio generator."""
from portfolio_generator.modules.logging import log_info, log_warning

def format_search_results(search_results):
    """Format search results for use in prompts.
    
    Args:
        search_results: The search results to format
        
    Returns:
        str: The formatted search results text
    """
    if not search_results:
        return ""
    
    # Filter results to only include those with actual content
    valid_results = [r for r in search_results 
                    if r.get("results") and len(r["results"]) > 0 and "content" in r["results"][0]]
    
    if not valid_results:
        log_warning("No valid search results to format - all results were empty or had errors")
        return ""
        
    formatted_text = "\n\nWeb Search Results (current as of 2025):\n"
    
    for i, result in enumerate(valid_results):
        query = result.get("query", "Unknown query")
        content = result["results"][0].get("content", "No content available")
        
        formatted_text += f"\n---Result {i+1}: {query}---\n{content}\n"
    
    log_info(f"Formatted {len(valid_results)} valid search results for use in prompts")
    return formatted_text
