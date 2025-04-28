"""News update section generator for portfolio reports."""
import re
from openai import OpenAI

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
    section_md = ["# News Update\n"]

    for cat_name, start, end in categories:
        cat_md = [f"### {cat_name}\n"]
        news_number = 1
        
        # Check if we have any search results for this category
        has_results = False
        for i in range(start, end):
            if i < len(search_results):
                has_results = True
                break
        
        # If no results for this category, generate a placeholder entry
        if not has_results and cat_name:
            placeholder_news = f"{news_number}. Latest {cat_name} Trends\nSummary: Current market data and trends in {cat_name}.\nCommentary: Monitoring developments in {cat_name} remains essential for our investment strategy."
            cat_md.append(placeholder_news)
            news_number += 1
        
        # Process actual search results if available
        for i in range(start, end):
            if i < len(search_results):
                result = search_results[i]
                query = result.get("query", f"Query {i+1}")
                content = ""
                if result.get("results") and len(result["results"]) > 0:
                    content = result["results"][0].get("content", "No content available")
                else:
                    content = "No content available for query: " + query

                # Use citations field directly
                citations_list = result.get("citations", [])
                citations_md_str = ", ".join(f"[Source]({url})" for url in citations_list)

                # LLM prompt and call logic (synchronous)
                system_prompt = f"""
You are an expert investment analyst at Orasis Capital. The following are the Orasis Capital investment principles:

{investment_principles}

For each news item, write:
1. The title of the news item.
2. A concise summary (~50 words) of the news content.
3. A brief commentary (2-3 sentences) relating the news to the above investment principles.
All statements must be explicitly grounded in the investment principles and the provided news content.
Use a professional, insightful tone.

Where possible, reference and include relevant citations as markdown links from the provided citations list below.

<Citations>
{citations_md_str if citations_md_str else 'None'}
</Citations>
"""
                user_prompt = f"""
<News Query>
{query}
</News Query>

<News Content>
{content}
</News Content>

<Investment Principles>
{investment_principles}
</Investment Principles>

<Task>
- First, generate a concise, informative title for this news item (no more than 7 words).
- Next, summarize the news in no more than {max_words} words.
- Then, provide a brief commentary (2-3 sentences) on how this news relates to the investment principles.
- Do not include citations or sources in the output.

Format (follow exactly):
Title: <Your generated title>
Commentary: <Your commentary>
"""
                try:
                    response = client.responses.create(
                        model="o3",
                        instructions=system_prompt,
                        input=user_prompt,
                        reasoning={"effort": "high"}
                    )
                    text = response.output[1].content[0].text
                except Exception as e:
                    text = f"Title: [Error generating title]\nSummary: [Error generating summary]\nCommentary: [Error generating commentary]\nCitations: [Error generating citations]"
                
                title, commentary = "", ""
                title_match = re.search(r"Title:\s*(.*)", text, re.IGNORECASE)
                commentary_match = re.search(r"Commentary:\s*(.*)", text, re.IGNORECASE)

                if title_match:
                    title = title_match.group(1).strip()
                if commentary_match:
                    commentary = commentary_match.group(1).strip()

                news_item = f"{news_number}. {title}\nCommentary: {commentary}"
                cat_md.append(news_item)
                news_number += 1
        section_md.extend(cat_md)

    # Flatten and join markdown
    section_md_flat = []
    for group in section_md:
        if isinstance(group, list):
            section_md_flat.extend(group)
        else:
            section_md_flat.append(group)
    return "\n".join(section_md_flat)
