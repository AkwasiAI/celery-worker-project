"""Web search functionality using the Perplexity API."""
import asyncio
import requests
import time
from typing import List, Dict, Any, Optional
from openai import OpenAI
from portfolio_generator.modules.logging import log_info


class PerplexitySearch:
    """
    Class to handle web searches using the Perplexity API.

    Usage:
        - Accepts a list of queries (in category order).
        - Returns a list of results in the same order.
        - To ensure correct slicing by category, always build your query list and category index list together.
    """
    
    def __init__(self, api_key: str):
        """Initialize with Perplexity API key."""
        self.api_key = api_key.strip('"\'')
        self.api_url = "https://api.perplexity.ai/chat/completions"
        
    async def search(self, queries: List[str], investment_principles: str = "") -> List[Dict[str, Any]]:
        """
        Search the web using Perplexity API for the given queries, with Orasis investment principles context.
        
        Args:
            queries: List of search queries to execute
            investment_principles: String with Orasis Capital's investment principles
        Returns:
            List of search result objects
        """
        tasks = [self._search_single_query(query, investment_principles) for query in queries]
        return await asyncio.gather(*tasks)
    
    async def _search_single_query(self, query: str, investment_principles: str = "") -> Dict[str, Any]:
        """Execute a search for a single query using OpenAI client with Perplexity, with Orasis investment principles in the system prompt."""
        # Validate the query to prevent 400 errors
        if not query or query.strip() == "":
            error_msg = "Query is empty"
            print(f"Skipping search due to invalid query: {error_msg}")
            return {
                "query": query, 
                "results": [],
                "citations": [],
                "error": "invalid_query",
                "message": error_msg
            }
            
        try:
            # Create messages for the search query
            # Use Perplexity's recommended deep research mode by specifying a domain filter in the system prompt
            allowed_domains = [
                "bloomberg.com",           # Bloomberg: Global / Macro news
                "aljazeera.com",           # Aljazeera: Global / Geopolitics
                "reuters.com",             # Reuters: Global / Macro news
                "lloydslist.com",          # Lloyd's List: Shipping News
                "ft.com",                  # Financial Times: Global / Macro news
                "seatrade-maritime.com",   # Seatrade Maritime News
                "kpler.com",               # Kpler: Commodities reports
                "clarksons.com",           # Clarkson's
                "iea.org",                 # International Energy Agency
                "spglobal.com",            # S&P Global
            ]
            domain_filter_instruction = (
                "You are an expert research assistant for Orasis Capital. Your job is to provide factual, unbiased, and up-to-date information strictly from the specified authoritative sources. "
                "Prioritize clarity, conciseness, and accuracy. All findings and summaries must be aligned with Orasis Capital's investment principles, which are provided below. "
                "Cite sources clearly and only include information that is well-supported by the cited material. Maintain a professional, analytical, and objective tone throughout your responses."
                f"\n\nOrasis Capital Investment Principles:\n{investment_principles}"
            )
            messages = [
                {
                    "role": "system",
                    "content": domain_filter_instruction
                },
                {
                    "role": "user",
                    "content": query
                }
            ]
            
            # Build the payload for the Perplexity API
            payload = {
                "temperature": 0.2,
                "top_p": 0.9,
                "return_images": False,
                "return_related_questions": False,
                "top_k": 0,
                "stream": False,
                "presence_penalty": 0,
                "frequency_penalty": 1,
                "web_search_options": {"search_context_size": "high"},
                "model": "sonar-deep-research",
                "messages": messages,
                "search_domain_filter": allowed_domains,
                "search_recency_filter": "day"
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Implement retry logic with exponential backoff
            max_retries = 3
            retry_delay = 2  # seconds initial delay
            response = None
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    print(f"Perplexity API request attempt {attempt+1}/{max_retries} for query: '{query[:30]}...'")
                    response = requests.post(self.api_url, json=payload, headers=headers)
                    
                    # Handle different status codes appropriately
                    if response.status_code >= 500:  # Server errors (retry these)
                        response.raise_for_status()  # This will trigger the exception to retry
                    elif response.status_code >= 400:  # Client errors (don't retry these)
                        print(f"Client error {response.status_code}: {response.text[:200]}...")
                        # Create a custom exception to break out of retry loop but still capture the error
                        raise requests.exceptions.HTTPError(f"Client error {response.status_code}: {response.reason}", response=response)
                    else:  # Success
                        # If successful, break out of retry loop
                        break
                        
                except requests.exceptions.HTTPError as e:
                    last_exception = e
                    if response.status_code >= 500 and attempt < max_retries - 1:  # Only retry server errors
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        print(f"Server error on attempt {attempt+1}: {e}. Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:  # Client errors should not be retried
                        print(f"Client error on attempt {attempt+1}: {e}. Not retrying.")
                        break
                        
                except requests.exceptions.RequestException as e:  # Network errors, connection issues, etc.
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        print(f"Request error on attempt {attempt+1}: {e}. Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
            
            # If all retries failed or we got an unrecoverable error, handle it gracefully
            if response is None or response.status_code >= 400:
                error_msg = str(last_exception) if last_exception else f"Failed with status code {response.status_code}"
                print(f"All attempts failed for query '{query[:30]}...': {error_msg}")
                return {
                    "query": query, 
                    "results": [],
                    "citations": [],
                    "error": "api_error",
                    "message": error_msg
                }
                
            # Process the successful response
            try:
                response_json = response.json()
            except ValueError as e:
                print(f"Failed to parse JSON response: {e}")
                return {
                    "query": query, 
                    "results": [],
                    "citations": [],
                    "error": "json_parse_error",
                    "message": str(e)
                }
            # Extract the response content
            response_content = response_json["choices"][0]["message"]["content"]
            
            # Try to extract relevant sources from the response (assuming response_content contains a list of sources/articles)
            # If response_content is a string, you may need to parse JSON or adapt based on actual API output
            sources = []
            citations = response_json.get("citations", [])
            log_info(citations)
            if citations:
                for url in citations:
                    sources.append({
                        "title": "Citations",
                        "url": url,
                        "content": response_content,
                        "raw_content": response_content
                    })
            else:
                print(response_json)
                sources.append({
                    "title": "Perplexity Search Result",
                    "url": "https://perplexity.ai/search",
                    "content": response_content,
                    "raw_content": response_content
                })
            return {
                "query": query,
                "results": sources,
                "citations": citations
            }
            
        except Exception as e:
            error_msg = f"Exception searching '{query}': {str(e)}"
            print(error_msg)
            return {
                "query": query, 
                "results": [],
                "citations": [],
                "error": "exception",
                "message": error_msg
            }


def format_search_results(search_results: List[Dict], max_chars_per_source: int = 4000) -> str:
    """
    Format search results into a string for the model.
    
    Args:
        search_results: List of search result objects
        max_chars_per_source: Maximum characters to include per source
        
    Returns:
        Formatted string with search results
    """
    if not search_results:
        return "No search results found."
        
    # Collect all results
    sources_list = []
    for response in search_results:
        sources_list.extend(response.get('results', []))
    
    # Deduplicate by URL
    unique_sources = {source['url']: source for source in sources_list}
    
    # Format output
    formatted_text = "Content from sources:\n"
    for i, source in enumerate(unique_sources.values(), 1):
        formatted_text += f"{'='*80}\n"  # Section separator
        formatted_text += f"Source: {source['title']}\n"
        formatted_text += f"URL: {source['url']}\n"
        formatted_text += f"Most relevant content: {source['content']}\n"
        
        # Add raw content if available
        raw_content = source.get('raw_content', '')
        if raw_content and len(raw_content) > max_chars_per_source:
            raw_content = raw_content[:max_chars_per_source] + "... [truncated]"
        if raw_content:
            formatted_text += f"Full content:\n{raw_content}\n"
            
        formatted_text += f"{'='*80}\n\n"
        
    return formatted_text
