"""Main report generation functionality."""
import os
import json
import asyncio
import time
import re
from datetime import datetime
from openai import OpenAI

from portfolio_generator.modules.logging import log_info, log_warning, log_error, log_success
from portfolio_generator.modules.search_utils import format_search_results
from portfolio_generator.modules.section_generator import generate_section
from portfolio_generator.modules.portfolio_generator import generate_portfolio_json
from portfolio_generator.modules.report_upload import upload_report_to_firestore, generate_and_upload_alternative_report
from portfolio_generator.web_search import PerplexitySearch

async def generate_investment_portfolio(test_mode=False, dry_run=False):
    """Generate a comprehensive investment portfolio report through multiple API calls.
    
    Args:
        test_mode (bool): If True, run in test mode with minimal API calls
        dry_run (bool): If True, don't upload to Firestore
        
    Returns:
        dict: Report sections and metadata
    """
    # Initialize variables that might be referenced before assignment
    firestore_report_doc_id = None
    
    # Set target word count: 10,000 on Friday, else 3,000
    today = datetime.now().strftime('%A')
    total_word_count = 10000 if today == 'Friday' else 3000
    # Number of main report sections
    main_sections = 9  # executive_summary, global_economy, energy_markets, commodities, shipping, portfolio_items, benchmarking, risk_assessment, conclusion
    per_section_word_count = total_word_count // main_sections
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get API key from environment unless in test mode
    if test_mode:
        log_info("Running in test mode - using mock OpenAI client")
        # Create a simple mock client for test mode
        class MockOpenAI:
            def __init__(self):
                pass
                
            async def chat_completions_create(self, **kwargs):
                class MockResponse:
                    def __init__(self):
                        self.choices = [type('obj', (object,), {
                            'message': type('obj', (object,), {
                                'content': "This is a test response from the mock OpenAI client"
                            })
                        })]
                return MockResponse()
        
        client = MockOpenAI()
    else:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            log_error("OPENAI_API_KEY environment variable is not set!")
            return None
        
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)
    
    # Load Orasis investment principles from file before any use
    investment_principles = ""
    try:
        with open(os.path.join(os.path.dirname(__file__), "orasis_investment_principles.txt"), "r", encoding="utf-8") as f:
            investment_principles = f.read().strip()
    except Exception as e:
        log_warning(f"Could not load Orasis investment principles: {e}")
        investment_principles = ""

    # Initialize search client if available
    search_client = None
    
    # Load environment variables again to ensure they're available
    # Load and check Perplexity API key if available and not in test mode
    if test_mode:
        log_info("Running in test mode - skipping real web search")
        search_client = None
        # Create dummy formatted search results for test mode
        formatted_search_results = {
            "Global Trade": ["Test market data for global trade"],
            "Energy Markets": ["Test market data for energy markets"],
            "Commodities": ["Test market data for commodities"],
            "Shipping": ["Test market data for shipping industry"],
            "Central Bank Policies": ["Test market data for central bank policies"]
        }
    else:
        perplexity_api_key = os.environ.get("PERPLEXITY_API_KEY")
        if perplexity_api_key:
            log_info("PERPLEXITY_API_KEY found. Initializing web search...")
            # Strip any quotes that might be accidentally included
            if perplexity_api_key.startswith('"') and perplexity_api_key.endswith('"'):
                perplexity_api_key = perplexity_api_key[1:-1]
                log_info("Removing quotes from PERPLEXITY_API_KEY")

            # Initialize search client
            search_client = PerplexitySearch(perplexity_api_key)
            
            # Test the API key with a simple query
            test_query = ["test query"]
            log_info("Testing Perplexity API key with a simple query...")
            try:
                # Get investment principles from file
                investment_principles = ""
                try:
                    with open(os.path.join(os.path.dirname(__file__), "orasis_investment_principles.txt"), "r", encoding="utf-8") as f:
                        investment_principles = f.read()
                    log_info("Successfully loaded investment principles.")
                except Exception as e:
                    log_warning(f"Failed to load investment principles: {e}")

                test_results = await search_client.search(test_query, investment_principles)
                if test_results and len(test_results) > 0:
                    log_success("Web search initialized successfully!")
                else:
                    log_warning("Web search test returned no results. API might be rate-limited or key is invalid.")
                    search_client = None
            except Exception as e:
                log_error(f"Failed to initialize web search: {e}")
                import traceback
                log_error(traceback.format_exc())
                search_client = None
        else:
            log_warning("PERPLEXITY_API_KEY not set. Web search disabled.")
            search_client = None
    
    # Initialize search results if not already done in test mode
    if not test_mode:
        # Initialize search results
        search_results = []
        formatted_search_results = {}
    
    # If we have a working search client, perform web searches for market data
    if search_client:
        log_info("Performing web searches for market data...")
        
        # Define category order - maintaining the original structure
        category_order = [
            "Shipping",
            "Commodities",
            "Central Bank Policies",
            "Macroeconomic News",
            "Global Trade & Tariffs"
        ]
        
        # Define detailed queries with investment principles context - identical to original
        category_queries = {
            "Shipping": [f"Provide an in depth analysis of shipping news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: {investment_principles}"],
            "Commodities": [f"Provide an in depth analysis of commodities market news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: {investment_principles}"],
            "Central Bank Policies": [f"Provide an in depth analysis of central bank policy news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: {investment_principles}"],
            "Macroeconomic News": [f"Provide an in depth analysis of macroeconomic news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: {investment_principles}"],
            "Global Trade & Tariffs": [f"Provide an in depth analysis of global trade and tariffs news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: {investment_principles}"]
        }
        
        # Build the flat search_queries list and categories index list - exactly as in original
        categories = []
        search_queries = []
        start = 0
        for cat in category_order:
            queries = category_queries.get(cat, [])
            n = len(queries)
            end = start + n
            categories.append((cat, start, end))
            search_queries.extend(queries)
            start = end
        
        try:
            # Execute searches using identical approach as original
            log_info(f"Executing {len(search_queries)} web searches...")
            search_results = await search_client.search(search_queries, investment_principles)
            
            # Display detailed results of each web search for debugging - matching original logic
            for i, result in enumerate(search_results):
                result_str = str(result)
                
                # With the new API approach, check if the results list contains content
                if result.get("results") and len(result["results"]) > 0 and "content" in result["results"][0]:
                    content_preview = result["results"][0]["url"][:100]
                    log_success(f"Search {i+1} successful: '{result['query']}' → {content_preview}...")
                elif "error" in result:
                    log_error(f"Search {i+1} failed: {result.get('error', 'Unknown error')}")
                else:
                    log_warning(f"Search {i+1} returned empty or unexpected format: {result_str[:150]}")
            
            # Check the quality of search results - matching original logic
            successful_searches = sum(1 for r in search_results if r.get("results") and len(r["results"]) > 0 and "content" in r["results"][0])
            failed_searches = len(search_results) - successful_searches
            
            if failed_searches == len(search_results):
                log_error("All search queries failed to return useful content.")
                log_warning("Automatically continuing without web search data (containerized mode)")
            elif failed_searches > 0:
                log_warning(f"{failed_searches} out of {len(search_results)} searches failed to return useful content.")
            
            # Determine if we have usable search results - matching original logic
            has_errors = failed_searches > (len(search_results) / 2)  # More than half failed
            
            if has_errors:
                log_error("Found API authentication errors or empty results")
                error_sample = next((r for r in search_results if 'error' in str(r) or 'unauthorized' in str(r)), '')
                if error_sample:
                    log_error(f"Error sample: {error_sample}")
                else:
                    log_error("All search results were empty, indicating API key issues")
                log_warning("Automatically continuing without web search functionality (containerized mode)")
                formatted_search_results = ""
                log_warning("No valid search results. Report will not include current data.")
            else:
                # Try to use any non-empty results - matching original logic
                # Format search results if available, otherwise provide empty string
                formatted_search_results = format_search_results(search_results) if search_results else ""
                if formatted_search_results:
                    log_success(f"Successfully formatted search results for use in prompts")
                else:
                    log_warning("No valid search results obtained. Report will not include current data.")
        except Exception as e:
            log_error(f"Exception during web search: {e}")
            formatted_search_results = ""
            log_warning("Web search exception. Report will not include current data.")
        
        log_info(f"Completed {len(search_results)} successful searches out of {len(search_queries)} queries")
    else:
        log_warning("No search client available. Proceeding without web search data.")
    
    # Search results already formatted in the try-except block above
    
    # Start generating the report
    log_info("Starting report generation...")
    
    # Initialize storage for generated sections
    report_sections = {}
    
    # Define the current date
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Define base system prompt exactly as in the original implementation
    base_system_prompt = f"""You are a professional investment analyst at Orasis Capital, a hedge fund specializing in global macro and trade-related assets.
Your task is to create detailed investment portfolio analysis with data-backed research and specific source citations.

IMPORTANT CLIENT CONTEXT - GEORGE (HEDGE FUND OWNER):
George, the owner of Orasis Capital, has specified the following investment preferences:

1. Risk Tolerance: Both high-risk opportunities and balanced investments with a mix of defensive and growth-oriented positions.

2. Time Horizon Distribution:
   - 30% of portfolio: 1 month to 1 quarter (short-term)
   - 30% of portfolio: 1 quarter to 6 months (medium-term)
   - 30% of portfolio: 6 months to 1 year (medium-long term)
   - 10% of portfolio: 2 to 3 year trades (long-term)

3. Investment Strategy: Incorporate both leverage and hedging strategies, not purely cash-based. Include both long and short positions as appropriate based on market analysis. George wants genuine short recommendations based on fundamental weaknesses, not just hedges.

4. Regional Focus: US, Europe, and Asia, with specific attention to global trade shifts affecting China, Asia, Middle East, and Africa. The portfolio should have positions across all major regions.

5. Commodity Interests: Wide range including crude oil futures, natural gas, metals, agricultural commodities, and related companies.

6. Shipping Focus: Strong emphasis on various shipping segments including tanker, dry bulk, container, LNG, LPG, and offshore sectors.

7. Credit Exposure: Include G7 10-year government bonds, high-yield shipping bonds, and corporate bonds of commodities companies.

8. ETF & Indices: Include major global indices (Dow Jones, S&P 500, NASDAQ, European indices, Asian indices) and other tradeable ETFs.

INVESTMENT THESIS:
Orasis Capital's core strategy is to capitalize on global trade opportunities, with a 20-year track record in shipping-related investments. The fund identifies shifts in global trade relationships that impact countries and industries, analyzing whether these impacts are manageable. Key focuses include monitoring changes in trade policies from new governments, geopolitical developments, and structural shifts in global trade patterns.

The firm believes trade flows are changing, with China, Asia, the Middle East, and Africa gaining more investment and trade volume compared to traditional areas like the US and Europe. Their research approach uses shipping (90% of global trade volume) as a leading indicator for macro investments, allowing them to identify shifts before they become widely apparent.

IMPORTANT CONSTRAINTS:
1. The ENTIRE report must be NO MORE than {total_word_count} words total. Optimize your content accordingly.
2. You MUST include a comprehensive summary table in the Executive Summary section.
3. Ensure all assertions are backed by specific data points or sources.
4. Use current data from 2024-2025 where available.
5. EXTREMELY IMPORTANT: Approximately 20% of the portfolio positions MUST be short positions based on fundamental analysis of overvalued, vulnerable, or declining assets."""
    
    # 1. Generate Executive Summary - match original user prompt exactly
    log_info("Generating executive summary section...")
    exec_summary_prompt = f"""Generate an executive summary for the investment portfolio report.

Include current date ({current_date}) and the title format specified previously.
Summarize the key findings, market outlook, and high-level portfolio strategy.
Keep it clear, concise, and data-driven with specific metrics.

CRITICAL REQUIREMENT: You MUST include a comprehensive summary table displaying ALL portfolio positions (strictly limited to 20-25 total positions).
This table MUST be properly formatted in markdown and include columns for:
- Asset/Ticker (must be a real, verifiable ticker listed on a major stock exchange such as NYSE or Oslo Stock Exchange; do NOT invent or use fake/unlisted tickers)
- Position Type (Long/Short)
- Allocation % (must sum to 100%)
- Time Horizon
- Confidence Level

IMPORTANT: Only use genuine tickers from legitimate exchanges. Do NOT invent or use any fake or unlisted tickers.

Immediately after the markdown table, output a valid JSON array of all portfolio positions INSIDE an HTML comment block (so it is hidden from the report). Use the following structure:
<!-- PORTFOLIO_POSITIONS_JSON:
[
  {{"asset": ..., "position_type": ..., "allocation_percent": ..., "time_horizon": ..., "confidence_level": ...}},
  ...
]
-->
This JSON must NOT be visible in the rendered report; it is only for internal processing.
Remember that the entire report must not exceed {total_word_count} words total. This summary should be concise but comprehensive.

After the table and JSON, include a brief overview of asset allocations by category (shipping, commodities, energy, etc.)."""
    
    # Initialize section tracking variables
    total_sections = 10  # Total number of sections in the report
    completed_sections = 0
    
    # Generate Executive Summary using the base system prompt exactly as in the original
    report_sections["Executive Summary"] = await generate_section(
        client,
        "Executive Summary",
        base_system_prompt,
        exec_summary_prompt,
        formatted_search_results,
        None,
        per_section_word_count
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Executive Summary")
    
    # Parse portfolio from executive summary - matching original implementation 
    log_info("Extracting portfolio positions from executive summary...")
    
    # Extract portfolio positions JSON from executive summary using the HTML comment format
    # exactly as done in the original implementation
    portfolio_positions = []
    portfolio_json = None
    json_match = re.search(r'<!--\s*PORTFOLIO_POSITIONS_JSON:\s*(\[.*?\])\s*-->', report_sections["Executive Summary"], re.DOTALL)
    if json_match:
        try:
            portfolio_positions = json.loads(json_match.group(1))
            portfolio_json = json.dumps(portfolio_positions, indent=2)
            log_info(f"Successfully extracted {len(portfolio_positions)} portfolio positions from executive summary.")
        except Exception as e:
            log_warning(f"Failed to parse portfolio positions JSON from executive summary: {e}")
    else:
        log_warning("No portfolio positions JSON found in executive summary output.")
    
    # 2. Generate Global Trade & Economy section
    global_economy_prompt = f"""Write a concise but comprehensive analysis (aim for approximately {per_section_word_count} words) of Global Trade & Economy as part of a macroeconomic outlook section.
Include:
- Regional breakdowns and economic indicators with specific figures
- GDP growth projections by region with exact percentages
- Trade flow statistics with exact volumes and year-over-year changes
- Container throughput at major ports with specific TEU figures
- Supply chain metrics and logistics indicators
- Currency valuations and impacts on trade relationships
- Trade agreements and policy changes with implementation timelines
- Inflation rates across major economies with comparisons

Format in markdown starting with:
## Global Trade & Economy
"""

    report_sections["Global Trade & Economy"] = await generate_section(
        client,
        "Global Trade & Economy",
        base_system_prompt,
        global_economy_prompt,
        formatted_search_results,
        {"Executive Summary": report_sections["Executive Summary"]},
        per_section_word_count
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Global Trade & Economy")
    
    # 3. Generate Energy Markets section
    energy_markets_prompt = f"""Write a detailed analysis (aim for approximately {per_section_word_count} words) of Energy Markets as part of an investment portfolio report.
Include:
- Oil markets: production, demand, and price forecasts with specific data points
- Natural gas markets: regional analysis and price dynamics
- Renewable energy growth and investment opportunities with specific companies
- Energy transition trends and policy impacts
- Geopolitical factors affecting energy markets
- Supply constraints and infrastructure developments
- Commodity trader positioning in energy markets

Format in markdown starting with:
## Energy Markets
"""

    report_sections["Energy Markets"] = await generate_section(
        client,
        "Energy Markets",
        base_system_prompt,
        energy_markets_prompt,
        formatted_search_results,
        {"Executive Summary": report_sections["Executive Summary"], "Global Trade & Economy": report_sections["Global Trade & Economy"]},
        per_section_word_count
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Energy Markets")
    
    # 4. Generate Commodities section
    commodities_prompt = f"""Write a detailed analysis (aim for approximately {per_section_word_count} words) of Commodities Markets as part of an investment portfolio report.
Include:
- Precious metals market analysis (gold, silver, platinum) with specific price targets
- Industrial metals outlook (copper, aluminum, nickel) with supply/demand figures
- Agricultural commodities trends and price forecasts
- Soft commodities market dynamics
- Commodity-specific factors driving price movements
- Seasonal patterns and historical context
- Warehousing and inventory levels with specific data points

Format in markdown starting with:
## Commodities Markets
"""

    report_sections["Commodities Markets"] = await generate_section(
        client,
        "Commodities Markets",
        base_system_prompt,
        commodities_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Executive Summary", "Global Trade & Economy", "Energy Markets"]},
        per_section_word_count
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Commodities Markets")
    
    # 5. Generate Shipping section
    shipping_prompt = f"""Write a detailed analysis (aim for approximately {per_section_word_count} words) of the Shipping Industry as part of an investment portfolio report.
Include:
- Container shipping market dynamics with specific freight rates
- Dry bulk shipping trends and key routes with rate data
- Tanker market analysis and oil shipping routes
- Major shipping companies performance and outlook with specific companies
- Port congestion and logistics bottlenecks with wait time statistics
- Fleet capacity and orderbook analysis with specific tonnage figures
- Shipping regulation changes and environmental initiatives
- Charter rate trends and forecasts with specific rate ranges

Format in markdown starting with:
## Shipping Industry
"""

    report_sections["Shipping Industry"] = await generate_section(
        client,
        "Shipping Industry",
        base_system_prompt,
        shipping_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Executive Summary", "Global Trade & Economy", "Energy Markets", "Commodities Markets"]},
        per_section_word_count
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Shipping Industry")
    
    # 6. Generate Portfolio Holdings section
    portfolio_prompt = f"""Write a detailed analysis (aim for approximately {per_section_word_count} words) of the current Portfolio Holdings as part of an investment portfolio report.
Include:
- Individual analysis of key positions with specific entry rationales
- Sector allocation strategy and rationale
- Geographic exposure analysis
- Position sizing methodology
- Risk management approach for current holdings
- Expected holding periods and exit strategies for major positions
- Recent portfolio changes and the rationale behind them
- Correlation analysis between holdings

Format in markdown starting with:
## Portfolio Holdings
"""

    report_sections["Portfolio Holdings"] = await generate_section(
        client,
        "Portfolio Holdings",
        base_system_prompt,
        portfolio_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Executive Summary", "Global Trade & Economy", "Energy Markets", "Commodities Markets", "Shipping Industry"]},
        per_section_word_count
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Portfolio Holdings")
    
    # 7. Generate Benchmarking & Performance section
    benchmarking_prompt = f"""Write a detailed analysis (aim for approximately {per_section_word_count} words) of Portfolio Benchmarking & Performance as part of an investment portfolio report.
Include:
- Performance comparison to relevant benchmarks with specific percentage figures
- Attribution analysis by sector and asset class
- Risk-adjusted return metrics (Sharpe, Sortino, etc.) with specific values
- Volatility analysis compared to markets
- Drawdown analysis and recovery periods
- Factor exposure analysis (value, momentum, quality, etc.)
- Historical performance in similar market environments
- Performance of specific investment themes within the portfolio

Format in markdown starting with:
## Benchmarking & Performance
"""

    report_sections["Benchmarking & Performance"] = await generate_section(
        client,
        "Benchmarking & Performance",
        base_system_prompt,
        benchmarking_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Executive Summary", "Portfolio Holdings"]},
        per_section_word_count
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Benchmarking & Performance")
    
    # 8. Generate Risk Assessment section
    risk_prompt = f"""Write a detailed analysis (aim for approximately {per_section_word_count} words) of Risk Assessment as part of an investment portfolio report.
Include:
- Key risk factors facing the portfolio with probability estimates
- Stress test scenarios and potential portfolio impacts with specific percentage figures
- Correlation matrices during stress periods
- Liquidity risk analysis for each asset class
- Scenario analysis for different market environments
- Geopolitical risk factors and potential market impacts
- Regulatory risks affecting portfolio holdings
- Tail risk hedging strategies employed in the portfolio

Format in markdown starting with:
## Risk Assessment
"""

    report_sections["Risk Assessment"] = await generate_section(
        client,
        "Risk Assessment",
        base_system_prompt,
        risk_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Executive Summary", "Global Trade & Economy", "Portfolio Holdings"]},
        per_section_word_count
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Risk Assessment")
    
    # 9. Generate Conclusion & Outlook section
    conclusion_prompt = f"""Write a concise conclusion and outlook (aim for approximately {per_section_word_count} words) for an investment portfolio report.
Include:
- Summary of key portfolio positioning and investment thesis
- Forward-looking market expectations with timeframes
- Upcoming catalysts to monitor with specific dates where possible
- Potential portfolio adjustments to consider
- Long-term strategic themes guiding investment decisions
- Tactical opportunities on the horizon
- Key risks to the investment outlook
- Final investment recommendations and action items

Format in markdown starting with:
## Conclusion & Outlook
"""

    report_sections["Conclusion & Outlook"] = await generate_section(
        client,
        "Conclusion & Outlook",
        base_system_prompt,
        conclusion_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Executive Summary", "Global Trade & Economy", "Energy Markets", "Portfolio Holdings", "Risk Assessment"]},
        per_section_word_count
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Conclusion & Outlook")
    
    # 10. Generate References & Sources section
    references_prompt = """Create a properly formatted references and sources section for the investment portfolio report. 
Include:
- Economic data sources
- Market research reports referenced
- Financial news sources
- Academic papers or journal articles (if referenced)
- Government and central bank publications
- Industry reports and white papers

Format in markdown starting with:
## References & Sources
"""

    report_sections["References & Sources"] = await generate_section(
        client,
        "References & Sources",
        base_system_prompt,
        references_prompt,
        formatted_search_results,
        {},
        per_section_word_count // 3  # Shorter section
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: References & Sources")
    
    # Combine all sections into a single report
    report_content = f"""# Investment Portfolio Report
**Date: {current_date}**

"""
    
    # Define the section order
    section_order = [
        "Executive Summary",
        "Global Trade & Economy",
        "Energy Markets",
        "Commodities Markets",
        "Shipping Industry",
        "Portfolio Holdings",
        "Benchmarking & Performance",
        "Risk Assessment",
        "Conclusion & Outlook",
        "References & Sources"
    ]
    
    # Add sections in order
    for section in section_order:
        if section in report_sections:
            report_content += report_sections[section] + "\n\n"
    
    log_info("Report generation complete!")
    
    # Calculate total word count
    total_words = len(report_content.split())
    log_info(f"Total report word count: {total_words}")
    
    # Extract portfolio data from the report
    log_info("Extracting portfolio data from generated report sections...")
    # --- News Update Section (LLM-powered) ---
    from portfolio_generator.news_update_generator import generate_news_update_section
    categories = [
        ("Shipping", 0, 5),
        ("Commodities", 5, 10),
        ("Central Bank Policies", 10, 15),
        ("Macroeconomic News", 15, 20),
        ("Global Trade & Tariffs", 20, 25)
    ]
    try:
        with open(os.path.join(os.path.dirname(__file__), "orasis_investment_principles.txt"), "r") as f:
            investment_principles = f.read().strip()
            
        category_order = [
            "Shipping",
            "Commodities", 
            "Central Bank Policies",
            "Macroeconomic News",
            "Global Trade & Tariffs"
        ]
        category_queries = {
            "Shipping": [f"Provide an in depth analysis of shipping news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: " + investment_principles],
            "Commodities": [f"Provide an in depth analysis of commodities market news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: " + investment_principles],
            "Central Bank Policies": [f"Provide an in depth analysis of central bank policy news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: " + investment_principles],
            "Macroeconomic News": [f"Provide an in depth analysis of macroeconomic news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: " + investment_principles],
            "Global Trade & Tariffs": [f"Provide an in depth analysis of global trade and tariffs news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: " + investment_principles]
        }
            
        # Build the flat search_queries list and categories index list
        search_queries = []
        for cat_name in category_order:
            search_queries.extend(category_queries[cat_name])
            
        # Generate the news update section
        from portfolio_generator.modules.news_update_generator import generate_news_update_section
        
        # Convert to the format expected by the news update generator
        if formatted_search_results and isinstance(formatted_search_results, dict):
            search_results_list = [{'query': k, 'results': [{'content': v}]} for k, v in formatted_search_results.items()]
        else:
            search_results_list = []
        
        news_section = await asyncio.to_thread(
            generate_news_update_section,
            client=client,
            search_results=search_results_list,
            investment_principles=investment_principles,
            categories=categories
        )
        
        # Append news section to report
        if news_section:
            report_content += "\n\n## Latest Market News\n" + news_section
            log_info("Added news update section to report")
    except Exception as e:
        log_error(f"Error generating news update section: {e}")
    
    # Generate portfolio JSON
    try:
        # Default empty portfolio for fallback
        default_portfolio = {
            "data": {
                "report_date": current_date,
                "assets": []
            }
        }
        
        # Generate portfolio JSON using the full report content as source of truth
        portfolio_json = await generate_portfolio_json(
            client, 
            default_portfolio.get("data", {}).get("assets", []),
            current_date,
            report_content,
            search_client,
            formatted_search_results
        )
        
        log_info("Generated portfolio weights JSON")
        
    except Exception as e:
        log_error(f"Error generating portfolio JSON: {e}")
        portfolio_json = json.dumps(default_portfolio)
    
    # Write portfolio JSON to file for debugging
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "portfolio_weights.json"), "w") as f:
            f.write(portfolio_json)
        log_info("Saved portfolio weights to file portfolio_weights.json")
    except Exception as e:
        log_warning(f"Failed to save portfolio weights to file: {e}")
    
    # Write report to file
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "investment_report.md"), "w", encoding="utf-8") as f:
            f.write(report_content)
        log_success("Saved report to file investment_report.md")
    except Exception as e:
        log_error(f"Failed to save report to file: {e}")
    
    # Upload to Firestore if available
    try:
        # Import here to avoid circular imports
        from portfolio_generator.modules.report_upload import FIRESTORE_AVAILABLE
        
        if FIRESTORE_AVAILABLE:
            # Upload the report to Firestore if not in dry_run mode
            if not dry_run:
                log_info("Uploading report to Firestore...")
                try:
                    # Call upload_report_to_firestore with correct parameters
                    # Function expects (report_content, portfolio_json, doc_id=None)
                    firestore_report_doc_id = await upload_report_to_firestore(
                        report_content,
                        portfolio_json
                    )
                    log_success(f"Successfully uploaded report to Firestore with ID: {firestore_report_doc_id}")
                    
                    # Generate and upload alternative report for ePubs
                    await generate_and_upload_alternative_report(report_sections, firestore_report_doc_id, "Investment Report")
                    
                    log_success("Report generation completed successfully!")
                except Exception as e:
                    log_error(f"Failed to upload report to Firestore: {e}")
                    import traceback
                    log_error(traceback.format_exc())
            else:
                log_info("Dry run mode: Skipping upload to Firestore")
                log_success("Report generation completed successfully (dry run mode)!")
                log_warning("Failed to upload report to Firestore")
        else:
            log_warning("Firestore not available. Skipping upload.")
            
    except Exception as e:
        log_error(f"Error during Firestore upload: {e}")
    
    # Return the report content
    return {
        "report_content": report_content,
        "portfolio_json": portfolio_json,
        "firestore_report_doc_id": firestore_report_doc_id
    }
