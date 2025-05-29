"""Search utilities for the portfolio generator."""
from portfolio_generator.modules.logging import log_info, log_warning
from typing import List, Dict

SAVE_FILE_PATH_CONSOLIDATED = "consolidated_formatted_search_results.txt"
def format_search_results(search_results: List[str]) -> str:
    """
    Formats a list of search result strings into a numbered list.
    """
    if not search_results:
        return ""

    formatted_text = "\n\nWeb Search Results (current as of 2025):\n"

    for i, result in enumerate(search_results, 1):
        formatted_text += f"\n--- Result {i} ---\n{result.strip()}\n"

    try:
        with open(SAVE_FILE_PATH_CONSOLIDATED, "a", encoding="utf-8") as f:
            f.write(formatted_text)
        log_info(f"Appended formatted results to {SAVE_FILE_PATH_CONSOLIDATED}")
    except Exception as e:
        log_warning(f"Failed to write to {SAVE_FILE_PATH_CONSOLIDATED}: {e}")

    return formatted_text