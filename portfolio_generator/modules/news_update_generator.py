"""News update section generator for portfolio reports with web search capabilities."""
import re
import asyncio
from typing import List, Dict, Any, Tuple
from openai import OpenAI
from portfolio_generator.modules.logging import log_info, log_warning, log_error

async def generate_news_update_section(client, search_results, categories, investment_principles="", model="o4-mini"):
    """Generate a news update section by category using web search results.
    
    Args:
        client: OpenAI client
        search_results: List of search results from web search
        categories: List of categories to include in the news update
        investment_principles: Investment principles to include in the prompt
        model: OpenAI model to use
        
    Returns:
        str: Generated news update section
    """
    log_info("Generating News Update section with web search capabilities...")
    section_md = ["# Latest Market News\n"]
    
    # Handle categories that can be either list of strings or list of tuples
    processed_categories = []
    for cat in categories:
        if isinstance(cat, tuple) and len(cat) >= 3:
            # This is the original format (cat_name, start_idx, end_idx)
            processed_categories.append((cat[0], cat[1], cat[2]))
        elif isinstance(cat, str):
            # This is a simple string category
            processed_categories.append((cat, 0, 0))  # Use dummy indices
        else:
            log_warning(f"Skipping invalid category format: {cat}")
    
    log_info(f"Processed {len(processed_categories)} categories for news update")
    
    # Check if we have any search results - handle both list and string formats
    if not search_results:
        log_warning("No search results available for News Update section")
        for cat_name, _, _ in processed_categories:
            section_md.append(f"## {cat_name}\n\n*No recent news available for {cat_name}. This section will be updated in the next report.*\n\n")
        return "\n".join(section_md)
    
    # Initialize variables for either format
    valid_results_count = 0
    all_formatted_results = ""
    
    # Handle string format (from format_search_results function)
    if isinstance(search_results, str):
        log_info("Processing pre-formatted search results string")
        all_formatted_results = search_results
        if all_formatted_results and all_formatted_results.strip():
            log_info(f"Using pre-formatted search results - length: {len(all_formatted_results)} chars")
            valid_results_count = all_formatted_results.count('---Result ')
        else:
            log_warning("Received empty pre-formatted search results string")
    
    # Handle list format (original)
    else:
        log_info(f"Processing search results list - {len(search_results)} items")
    
    # If it's not a string, process the list format
    if not isinstance(search_results, str):
        log_info(f"Using direct raw search results approach instead of field extraction")
        
        for i, result in enumerate(search_results):
            try:
                # Extract query for context
                query = result.get("query", f"Search query {i}")
                
                # Format the entire result dictionary as a string
                result_str = str(result)
                # Clean up the result string to make it more readable
                result_str = result_str.replace("{", "{\n  ").replace("', '", "',\n  '").replace("': '", "': ").replace("}", "\n}\n")
                
                # Add the formatted result to the consolidated string
                all_formatted_results += f"### {query} (Full Result)\n```\n{result_str}\n```\n\n"
                log_info(f"Added raw search result {i} for query '{query}' (approx {len(result_str)} chars)")
                valid_results_count += 1
            except Exception as e:
                log_warning(f"Error processing search result {i}: {e}")
        
        # Log the total content size
        log_info(f"Total raw search results content: {len(all_formatted_results)} characters from {valid_results_count} results")
    
    # Add a header if using the list format and nothing was found in the pre-formatted string
    if not isinstance(search_results, str) and all_formatted_results.strip():
        all_formatted_results = "\n\nWeb Search Results (current as of 2025):\n\n" + all_formatted_results
    
    # Only show a warning if we couldn't format any results at all
    if not all_formatted_results.strip():
        log_warning("No search results could be formatted for News Update section")
        for cat_name, _, _ in processed_categories:
            section_md.append(f"## {cat_name}\n\n*No recent news available for {cat_name}. This section will be updated in the next report.*\n\n")
        return "\n".join(section_md)
    
    # Generate content for each category
    for cat_name, _, _ in processed_categories:
        # Initialize category markdown section
        cat_md = ["\n"]
        
        try:
            # Create a more focused system prompt incorporating investment principles if available
            system_prompt = f"""You are an expert analyst synthesizing market news for an investment portfolio report. 
You need to identify key headlines related to the '{cat_name}' category and explain how each connects to investment principles.
Maintain a factual, analytical tone and focus on recent, impactful developments.

{investment_principles if investment_principles else ""}

If no relevant information is available for '{cat_name}', indicate this clearly."""
            
            # Create a user prompt that asks the model to extract headlines and relate them to investment principles
            # Following the pattern: state the prompt, add context, format example, repeat the prompt
            user_prompt = f"""TASK: Extract key headlines relevant to '{cat_name}' from market research data and explain how each relates to investment principles.

CONTEXT:
- You are preparing a news update section for an investment portfolio report
- This section focuses specifically on {cat_name}
- Format should be: headlines as subheadings, each with a ~50 word summary relating to investment principles
- Only include information directly related to {cat_name}
- Focus on 3-5 recent, impactful headlines with clear investment implications
- If insufficient information is available, use the placeholder message

FORMAT EXAMPLE (for Shipping sector):

## Shipping

### Shanghai ports close due to COVID
- This supply chain disruption creates potential investment opportunities in logistics alternatives and companies with robust distribution networks. Our principle of seeking discounted assets in temporary distress applies here, as affected shipping companies may become undervalued.

### LA fires close Port of Los Angeles
- The temporary capacity reduction aligns with our counter-cyclical investment approach. Companies with diversified shipping routes and contingency plans should outperform peers, supporting our investment principle of prioritizing operational resilience during market disruptions.

DATA:
{all_formatted_results}

TASK REPEATED:
From the above market research data, extract 3-5 key headlines relevant to '{cat_name}'. 

For each '{cat_name}' ensure that it has the Markdown heading(##). 

For each headline:
1. Present it as a Markdown subheading (###)
2. Follow with a ~50-word explanation of how it relates to our investment principles
3. Focus on investment implications, opportunities, or risks

==========
Repeat of Format Example: 

## Shipping

### Shanghai ports close due to COVID
- This supply chain disruption creates potential investment opportunities in logistics alternatives and companies with robust distribution networks. Our principle of seeking discounted assets in temporary distress applies here, as affected shipping companies may become undervalued.
==========

If you cannot find sufficient relevant information about '{cat_name}' in the data, respond with: 
"*No recent news available for {cat_name}. This section will be updated in the next report.*"
"""

            # Generate content for this category
            log_info(f"Generating content for category: {cat_name}")
            # Define base parameters that work with all models
            completion_params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
            
            # Check if it's an OpenAI model type that supports max tokens
            if "gpt" in model.lower() or model.startswith("gpt-"):
                completion_params["max_tokens"] = 500
                completion_params["temperature"] = 0.7  # GPT models support temperature

            log_info(f"Using model: {model} with custom parameters: {str(completion_params.keys())}")
            
            try:
                # Make the API call - handle both synchronous and asynchronous clients
                if hasattr(client.chat.completions.create, "__await__"):
                    # This is an async client
                    response = await client.chat.completions.create(**completion_params)
                else:
                    # This is a synchronous client
                    response = client.chat.completions.create(**completion_params)
            except Exception as e:
                log_warning(f"Error calling OpenAI API: {e}")
                raise
            
            # Extract the content
            content = response.choices[0].message.content
            
            # Verify that the content is not empty or just whitespace
            if content and content.strip():
                cat_md.append(content)
                log_info(f"Successfully generated content for category: {cat_name} ({len(content)} chars)")
            else:
                # Handle empty content
                log_warning(f"Generated empty content for category: {cat_name}")
                cat_md.append(f"*No recent news available for {cat_name}. This section will be updated in the next report.*")
            
        except Exception as e:
            log_warning(f"Error generating news update for {cat_name}: {e}")
            cat_md.append(f"*Error retrieving news for {cat_name}. This section will be updated in the next report.*\n\n")
        
        # Add this category to the section
        section_md.append("\n".join(cat_md))
    
    return "\n".join(section_md)