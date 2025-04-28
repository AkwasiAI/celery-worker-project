"""Backward compatibility layer for news_update_generator module"""
# Import from the modules directory
from portfolio_generator.modules.news_update_generator import generate_news_update_section

# This file exists as a compatibility layer to ensure existing code still works.
# All functionality has been moved to portfolio_generator.modules.news_update_generator

# Original function signature preserved for backward compatibility
def generate_news_update_section(client, search_results, investment_principles, categories, max_words=50):
    """
    Generate the News Update section using the LLM for summaries and principle-based commentary.
    Args:
        client: OpenAI client
        search_results: List of search result dicts (from Perplexity)
        investment_principles: String with Orasis Capital's investment principles
        categories: List of (category_name, start_idx, end_idx)
        max_words: Maximum words for the summary
    Returns:
        Markdown string for the News Update section
    """
    # Delegate to the implementation in the modules directory
    from portfolio_generator.modules.news_update_generator import generate_news_update_section as _generate
    return _generate(client, search_results, investment_principles, categories, max_words)
