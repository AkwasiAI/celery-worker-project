"""News update section generator for portfolio reports with web search capabilities."""
import re
import asyncio
from openai import OpenAI
from portfolio_generator.modules.logging import log_info, log_warning, log_error

async def generate_news_update_section(client, search_results, investment_principles, categories, max_words=50):
    """
    Generate the News Update section using the LLM with web search for up-to-date information.
    
    Args:
        client: OpenAI client
        search_results: List of search result dicts (from Perplexity)
        investment_principles: String with Orasis Capital's investment principles
        categories: List of (category_name, start_idx, end_idx)
        max_words: Maximum words for the summary
        
    Returns:
        Markdown string for the News Update section
    """
    log_info("Generating News Update section with web search capabilities...")
    section_md = ["# Latest Market News\n"]

    for cat_name, start, end in categories:
        cat_md = [f"## {cat_name}\n"]
        news_number = 1
        
        # Check if we have any search results for this category
        has_results = False
        for i in range(start, end):
            if i < len(search_results):
                has_results = True
                break
        
        # If no results for this category, generate a placeholder entry
        if not has_results and cat_name:
            log_info(f"No search results for {cat_name}, using placeholder")
            placeholder_news = f"{news_number}. Latest {cat_name} Trends\n\nSummary: Current market data and trends in {cat_name}.\n\nCommentary: Monitoring developments in {cat_name} remains essential for our investment strategy."
            cat_md.append(placeholder_news)
            news_number += 1
        
        # Process actual search results if available
        for i in range(start, end):
            if i < len(search_results):
                result = search_results[i]
                query = result.get("query", f"Market data for {cat_name}")
                content = ""
                if result.get("results") and len(result["results"]) > 0:
                    content = result["results"][0].get("content", "No content available")
                else:
                    content = f"No content available for {cat_name} market data"

                # Create a prompt that uses web search to get the latest information
                prompt = f"""
# Investment Market News Analysis

You are an expert investment analyst at Orasis Capital analyzing recent market news.

## Investment Principles
{investment_principles}

## News Details
Category: {cat_name}
Search Query: {query}

Initial Content: {content}

## Task
1. Search for the latest news and market data about {cat_name} (last 7 days if possible)
2. Generate a concise, informative title (no more than 10 words)
3. Summarize the key market developments in no more than {max_words} words
4. Provide a brief commentary (2-3 sentences) explaining the investment implications

## Required Format
Your response MUST follow this exact format:

Title: <Your generated title>
Summary: <Your detailed summary>
Commentary: <Your investment commentary>
"""

                try:
                    log_info(f"Generating news update for {cat_name} with web search...")
                    # Use GPT-4.1 with web search capabilities for up-to-date information
                    response = await asyncio.to_thread(
                        client.responses.create,
                        model="gpt-4.1",  # Using GPT-4.1 which supports web search
                        input=prompt,
                        tools=[{"type": "web_search_preview"}]  # Enable web search
                    )
                    
                    # Extract the text content from the response
                    if response and response.output and len(response.output) > 1:
                        text = response.output[1].content[0].text
                        log_info(f"Successfully generated news for {cat_name}")
                    else:
                        log_warning(f"Unexpected response format for {cat_name}")
                        text = f"Title: Latest {cat_name} Developments\nSummary: Unable to retrieve detailed information.\nCommentary: Ongoing monitoring remains essential."
                        
                except Exception as e:
                    log_error(f"Error generating news for {cat_name}: {str(e)}")
                    text = f"Title: {cat_name} Market Update\nSummary: Unable to retrieve market data at this time.\nCommentary: Continued monitoring of this sector is recommended."
                
                # Extract the formatted sections using regex
                title, summary, commentary = "", "", ""
                title_match = re.search(r"Title:\s*(.*?)(?:\n|$)", text, re.IGNORECASE | re.DOTALL)
                summary_match = re.search(r"Summary:\s*(.*?)(?:\nCommentary:|$)", text, re.IGNORECASE | re.DOTALL)
                commentary_match = re.search(r"Commentary:\s*(.*?)(?:\n|$)", text, re.IGNORECASE | re.DOTALL)

                if title_match:
                    title = title_match.group(1).strip()
                else:
                    title = f"Latest {cat_name} Trends"
                    
                if summary_match:
                    summary = summary_match.group(1).strip()
                else:
                    summary = f"Current market data for {cat_name}."
                    
                if commentary_match:
                    commentary = commentary_match.group(1).strip()
                else:
                    commentary = f"Monitoring developments in {cat_name} remains essential for our investment strategy."

                # Format the news item with proper spacing
                news_item = f"{news_number}. {title}\n\nSummary: {summary}\n\nCommentary: {commentary}"
                cat_md.append(news_item)
                news_number += 1
                
        section_md.extend(cat_md)
        section_md.append("\n")  # Add extra spacing between categories

    # Flatten and join markdown sections
    section_md_flat = []
    for group in section_md:
        if isinstance(group, list):
            section_md_flat.extend(group)
        else:
            section_md_flat.append(group)
            
    return "\n".join(section_md_flat)
