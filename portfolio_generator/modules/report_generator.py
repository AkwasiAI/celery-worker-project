"""Main report generation functionality."""
import os
import json
import asyncio
import time
import re
from datetime import datetime, timezone, timedelta
from openai import OpenAI

from portfolio_generator.prompts_config import (EXECUTIVE_SUMMARY_DETAILED_PROMPT,
    SHIPPING_INDUSTRY_PROMPT, CONCLUSION_OUTLOOK_PROMPT, REFERENCES_SOURCES_PROMPT, 
    RISK_ASSESSMENT_PROMPT, GLOBAL_TRADE_ECONOMY_PROMPT, PORTFOLIO_HOLDINGS_PROMPT,
    ENERGY_MARKETS_PROMPT, COMMODITIES_MARKETS_PROMPT, BENCHMARKING_PERFORMANCE_PROMPT,
    BASE_SYSTEM_PROMPT, PERFORMANCE_ANALYSIS_PROMPT, ALLOCATION_CHANGES_PROMPT, INSIGHTS_CHANGES_PROMPT,
    SANITISATION_SYSTEM_PROMPT, SANITISATION_USER_PROMPT)
from portfolio_generator.modules.logging import log_info, log_warning, log_error, log_success
from portfolio_generator.modules.search_utils import format_search_results
from portfolio_generator.modules.section_generator import generate_section, generate_section_with_web_search
from portfolio_generator.modules.structured_section_generator import generate_structured_executive_summary
from portfolio_generator.modules.portfolio_generator import generate_portfolio_json
from portfolio_generator.modules.report_upload import upload_report_to_firestore
from portfolio_generator.web_search import PerplexitySearch
from google.cloud import firestore
from portfolio_generator.firestore_downloader import FirestoreDownloader
from portfolio_generator.firestore_uploader import FirestoreUploader
from google.cloud.firestore_v1.base_query import FieldFilter
import os
from google import genai
from google.genai import types
from portfolio_generator.modules.another import run_full_news_agent
from portfolio_generator.modules.portfolio_generation_agent2 import generate_portfolio_executive_summary_sync
from portfolio_generator.modules.news_update_generator import generate_news_update_section
from portfolio_generator.modules.utils import news_digest_json_to_markdown, clean_markdown_block
from portfolio_generator.modules.reward_eval_runner import evaluate_yesterday, predict_tomorrow
from portfolio_generator.modules.alternative_portfolio_generator import generate_and_upload_alternative_report


# New helper for Gemini sanitization, using the google-genai SDK
def sanitize_report_content_with_gemini(report_content: str) -> str:
    """
    Sanitize Markdown content using the Google Gemini API.

    Args:
        report_content: The markdown string to be sanitized.

    Returns:
        The sanitized markdown string, or the original content if sanitization fails or is skipped.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        log_warning("GEMINI_API_KEY not set; skipping sanitization")
        return report_content

    try:
        # instantiate the new genai client
        client = genai.Client(api_key=api_key)

        # Prepare prompts
        system_prompt = SANITISATION_SYSTEM_PROMPT
        user_prompt = SANITISATION_USER_PROMPT.format(report_content=report_content)

        # Build the generation config
        generation_config = types.GenerateContentConfig(
            response_mime_type="text/plain"
        )

        log_info("Sending content to Gemini for sanitization…")
        response = client.models.generate_content(
            model="gemini-2.5-pro-preview-05-06",
            contents=[system_prompt, user_prompt],
            config=generation_config,
        )

        # If we got back text, return it; otherwise fall back
        sanitized = response.text or report_content
        log_info("Report content successfully sanitized with Gemini.")
        return sanitized

    except Exception as e:
        log_warning(f"Error sanitizing report content with Gemini: {e}")
        return report_content


async def generate_investment_portfolio(test_mode=False, dry_run=False, priority_period="month"):

    """Generate a comprehensive investment portfolio report through multiple API calls.
    
    Args:
        test_mode (bool): If True, run in test mode with minimal API calls
        dry_run (bool): If True, don't upload to Firestore
        priority_period (str): Time period to prioritize for news (e.g., "week", "month", "quarter")
        
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
        # Create a more comprehensive mock client for test mode
        class MockOpenAI:
            def __init__(self):
                self.responses = self  # For compatibility with the OpenAI client structure
                
            async def chat_completions_create(self, **kwargs):
                class MockResponse:
                    def __init__(self):
                        self.choices = [type('obj', (object,), {
                            'message': type('obj', (object,), {
                                'content': "This is a test response from the mock OpenAI client"
                            })
                        })]
                return MockResponse()
            
            def create(self, **kwargs):
                # Enhanced mock response for news update and other sections
                if "News Update" in kwargs.get("input", ""):
                    return type('obj', (object,), {
                        'output': [None, type('obj', (object,), {
                            'content': [type('obj', (object,), {
                                'text': "Title: Test Market News\nSummary: This is a test summary of market news. Markets moved on various factors.\nCommentary: The news aligns with our investment principles by focusing on long-term value.\nCitations: None"
                            })]
                        })]
                    })
                else:
                    return type('obj', (object,), {
                        'output': [None, type('obj', (object,), {
                            'content': [type('obj', (object,), {
                                'text': "This is a test response from the mock OpenAI client"
                            })]
                        })]
                    })
        
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
                    with open(os.path.join(os.path.dirname(__file__), "orasis_investment_principles.txt"), "r") as f:
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
            "Global Trade & Tariffs",
            "Geopolitical Events"
        ]
        
        # # Define detailed queries with investment principles context - identical to original
        # category_queries = {
        #     "Shipping": [f"Provide an in depth analysis of shipping news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: {investment_principles}"],
        #     "Commodities": [f"Provide an in depth analysis of commodities market news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: {investment_principles}"],
        #     "Central Bank Policies": [f"Provide an in depth analysis of central bank policy news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: {investment_principles}"],
        #     "Macroeconomic News": [f"Provide an in depth analysis of macroeconomic news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: {investment_principles}"],
        #     "Global Trade & Tariffs": [f"Provide an in depth analysis of global trade and tariffs news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: {investment_principles}"],
        #     "Geopolitical Events": [f"Provide an in depth analysis of geopolitical events news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: {investment_principles}"]
        # }
        
        # Build the flat search_queries list and categories index list - exactly as in original
        # categories = []
        # search_queries = []
        # start = 0
        # for cat in category_order:
        #     queries = category_queries.get(cat, [])
        #     n = len(queries)
        #     end = start + n
        #     categories.append((cat, start, end))
        #     search_queries.extend(queries)
        #     start = end


        # try:
        #     evaluate_yesterday()
        #     log_success("Successfully evaluated yesterday's update")
        # except Exception as e:
        #     log_error(f"Exception running the 100 ticker evals: {e}")

        # try:
        #     predict_tomorrow()
        #     log_success("Successfully Forecasted tomorrow's update")
        # except Exception as e:
        #     log_error(f"Exception running the 100 ticker evals: {e}")
        
        try:
            # Execute searches using identical approach as original
            # log_info(f"Executing {len(search_queries)} web searches...")
            llm_corpora = await run_full_news_agent()
            # Generate the news section - directly await the async function
            news_section = news_digest_json_to_markdown()
            search_results = list(llm_corpora.values())
            formatted_search_results = format_search_results(search_results) if search_results else ""

            # Display detailed results of each web search for debugging - matching original logic
            # for i, result in enumerate(search_results):
            #     result_str = str(result)
                
            #     # With the new API approach, check if the results list contains content
            #     if result.get("results") and len(result["results"]) > 0 and "content" in result["results"][0]:
            #         content_preview = result["results"][0]["url"][:100]
            #         log_success(f"Search {i+1} successful: '{result['query']}' → {content_preview}...")
            #     elif "error" in result:
            #         log_error(f"Search {i+1} failed: {result.get('error', 'Unknown error')}")
            #     else:
            #         log_warning(f"Search {i+1} returned empty or unexpected format: {result_str[:150]}")
            
            # Check the quality of search results - matching original logic
            successful_searches = len(search_results)
            failed_searches = 0 #len(search_results) - successful_searches
            
            if failed_searches == len(search_results):
                log_error("All search queries failed to return useful content.")
                log_warning("Automatically continuing without web search data (containerized mode)")
            elif failed_searches > 0:
                log_warning(f"{failed_searches} out of {len(search_results)} searches failed to return useful content.")
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
        
        log_info(f"Completed {len(search_results)} successful searches out of {len(category_order)} queries")
    else:
        log_warning("No search client available. Proceeding without web search data.")
    
    # Search results already formatted in the try-except block above
    
    # Start generating the report
    log_info("Starting report generation...")
    
    # Initialize storage for generated sections
    report_sections = {}
    
    # Define the current timestamp (date and time)
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Define base system prompt using the imported prompt
    current_year = datetime.now().year
    next_year = current_year + 1
    # Use the passed in priority_period parameter
    base_system_prompt = BASE_SYSTEM_PROMPT.format(
        total_word_count=total_word_count,
        current_year=current_year,
        next_year=next_year,
        priority_period=priority_period,
        current_date = current_date

    )
    
    # 1. Generate Executive Summary - using the imported prompt
    log_info("Generating executive summary section...")
    current_year = datetime.now().year
    exec_summary_prompt = EXECUTIVE_SUMMARY_DETAILED_PROMPT.format(
        current_date=current_date,
        total_word_count=total_word_count,
        current_year=current_year
    )
    
    # Initialize section tracking variables
    total_sections = 12  # Total number of sections in the report
    completed_sections = 0
    
    # Generate Executive Summary using the structured generator with Pydantic validation
    log_info("Generating Executive Summary with structured schema and o4-mini model...")
    try:
        # Create a more focused system prompt specifically for executive summary generation
        # executive_summary_system_prompt = """You are an expert investment analyst creating a structured portfolio executive summary. 
        #     Your primary task is to generate a well-formatted investment portfolio with asset positions, allocation percentages, 
        #     and a forward-looking market analysis. 

        #     YOU MUST FOLLOW THE USER'S INSTRUCTIONS EXACTLY to create a valid portfolio summary. 
        #     Do not create a news analysis or describe current events - create a forward-looking portfolio.

        #     You MUST include a table of portfolio positions AND hidden JSON in HTML comments."""
        
        # Separate and limit the search results to prevent them from dominating the prompt
        if formatted_search_results and isinstance(formatted_search_results, str):
            log_info("Processing search results for executive summary...")
            
#             # Extract only small snippets of market data from the search results
#             extracted_market_insights = """
# *** REFERENCE MARKET INSIGHTS (DO NOT COPY DIRECTLY) ***

# Use these high-level market trends ONLY to inform your portfolio construction:
# """
            
#             # Split by newlines and extract only short key insights
#             search_lines = formatted_search_results.split('\n')
#             extracted_lines = []
            
#             # Add just enough market context without overwhelming the prompt
#             energy_added = shipping_added = commodity_added = geopolitical_added = False
#             for line in search_lines[:20]:  # Limit to first 20 lines
#                 if ('energy' in line.lower() or 'oil' in line.lower()) and not energy_added:
#                     extracted_lines.append("- Energy markets: " + line[:60] + "...")
#                     energy_added = True
#                 elif ('shipping' in line.lower() or 'tanker' in line.lower()) and not shipping_added:
#                     extracted_lines.append("- Shipping rates: " + line[:60] + "...")
#                     shipping_added = True
#                 elif ('commodity' in line.lower() or 'metal' in line.lower()) and not commodity_added:
#                     extracted_lines.append("- Commodities: " + line[:60] + "...")
#                     commodity_added = True
#                 elif ('geopolitical' in line.lower() or 'event' in line.lower()) and not geopolitical_added:
#                     extracted_lines.append("- Geopolitical events: " + line[:60] + "...")
#                     geopolitical_added = True
            
#             if extracted_lines:
#                 extracted_market_insights += "\n" + "\n".join(extracted_lines) + "\n\n"
#             else:
#                 extracted_market_insights += "\n- Limited market data available. Focus on diversified portfolio construction.\n\n"
                
#             # Add strong reminder about task priority
#             extracted_market_insights += """CRITICAL: Your primary task is to create a FORWARD-LOOKING INVESTMENT PORTFOLIO with positions in a table and JSON format.
# DO NOT create a news article or summary about global trade & tariffs or any other topic.
# Focus on proper portfolio construction as specified in the instructions."""
            
#             log_info("Created focused market insights for executive summary guidance")
#         else:
#             extracted_market_insights = """No market data available. Create a diversified portfolio based on 
# forward-looking expectations for energy, shipping, and commodity markets."""
        
#         # Combine the executive summary prompt with the extracted insights
#         complete_exec_summary_prompt = exec_summary_prompt + "\n\n" + extracted_market_insights
        
        # Use the structured executive summary generator with focused prompts
        log_info("Generating executive summary with strict portfolio focus...")


        # structured_response = await generate_structured_executive_summary(
        #     client=client,
        #     system_prompt=executive_summary_system_prompt,  # Use the focused system prompt
        #     user_prompt=complete_exec_summary_prompt,
        #     search_results=None,  # Don't pass raw search results directly
        #     previous_sections={},  # Empty dictionary for previous sections
        #     target_word_count=per_section_word_count,
        #     model="o4-mini"
        # )

        firebase_downloader = FirestoreDownloader()
        previous_portfolio = firebase_downloader.get_latest("portfolio_weights")

        # structured_response = await generate_portfolio_executive_summary(
        #                     llm_corpus_content=formatted_search_results, # Replace with your actual data
        #                     previous_portfolio_data=previous_portfolio, # Replace with your actual data
        #                     fully_formatted_base_prompt=base_system_prompt,
        #                     fully_formatted_exec_detailed_prompt=exec_summary_prompt,
        #                     max_iterations=2,
        #                 )
        
        log_info("Trying to pull George's feedback from The Scratchpad where it lives")

        try:
            db = firestore.Client(project="hedgefundintelligence", database="hedgefundintelligence")
            docs = db.collection("feedback-scratchpad").where("is_latest", "==", True).limit(1).stream()
            doc = next(docs, None)

            george_feedback = ""
            if doc:
                data = doc.to_dict()
                ts = data.get("timestamp")
                if ts:
                    # If timestamp is string, parse as ISO8601
                    if isinstance(ts, str):
                        try:
                            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        except Exception:
                            ts = None  # Fallback if parsing fails
                    # If timestamp is datetime, use as is
                    if isinstance(ts, datetime):
                        now = datetime.now(timezone.utc)
                        if now - ts < timedelta(hours=24):
                            george_feedback = data.get("scratchpad")

            log_success("successfully pulled George's Feedback!!")
        except Exception as e:
            log_error("I couldn't pull George's feedback, continuing without it.")
            george_feedback = ""

        
        structured_response = await generate_portfolio_executive_summary_sync(
                            llm_corpus_content=formatted_search_results,
                            previous_portfolio_data=previous_portfolio,
                            fully_formatted_base_prompt=base_system_prompt,
                            fully_formatted_exec_detailed_prompt=exec_summary_prompt,
                            georges_latest_feedback=george_feedback, # Pass George's feedback
                            # google_api_key=GEMINI_API_KEY, # Use the one loaded at the top for standalone
                            # log_file_path=standalone_log_file,
                            max_iterations=2, 
                        )

        
        # Store the markdown summary in the report sections
        report_sections["Executive Summary - Comprehensive Portfolio Summary"] = clean_markdown_block(structured_response["summary"])
        
        # Extract the validated portfolio positions
        # portfolio_positions = [position.dict() for position in structured_response.portfolio_positions]
        # portfolio_json = json.dumps(portfolio_positions, indent=2)

        portfolio_json = structured_response["portfolio_positions"]
        portfolio_positions = json.loads(portfolio_json)
        
        # Log success with position details
        log_info(f"Successfully generated structured Executive Summary with {len(portfolio_positions)} validated portfolio positions.")

        with open('scratchpads/portfolio_gen_scratchpad.json', 'r') as f:
            portfolio_scratchpad = json.load(f)

        log_info(f"Successfully got the portfolio scratchpad, There are: {len(portfolio_scratchpad)} conversations inside")
        # # Add the JSON back to the executive summary for backwards compatibility with any code that expects it there
        # json_comment = f"<!-- PORTFOLIO_POSITIONS_JSON:\n{portfolio_json}\n-->"
        # report_sections["Executive Summary - Comprehensive Portfolio Summary"] += f"\n\n{json_comment}"
        
        # Increment the completed sections counter
        completed_sections += 1
        log_info(f"Completed section {completed_sections}/{total_sections}: Executive Summary - Comprehensive Portfolio Summary")
        
    except Exception as e:
        log_error(f"Error in structured Executive Summary - Comprehensive Portfolio Summary generation: {str(e)}")
        log_warning("Falling back to standard Executive Summary - Comprehensive Portfolio Summary generation...")
        
        # Fallback to the previous approach if the structured generator fails
        enhanced_exec_summary_prompt = exec_summary_prompt + "\n\nCRITICAL REQUIREMENT: You MUST include a valid JSON array of all portfolio positions inside an HTML comment block, formatted EXACTLY as follows:\n<!-- PORTFOLIO_POSITIONS_JSON:\n[\n  {\"asset\": \"TICKER\", \"position_type\": \"LONG/SHORT\", \"allocation_percent\": X, \"time_horizon\": \"PERIOD\", \"confidence_level\": \"LEVEL\"},\n  ...\n]\n-->\nThis hidden JSON is essential for downstream processing and MUST be included exactly as specified, even when using web search."
        
        # Generate Executive Summary using standard generation without web search as fallback
        report_sections["Executive Summary - Comprehensive Portfolio Summary"] = await generate_section_with_web_search(
            client=client,
            section_name="Executive Summary - Comprehensive Portfolio Summary",
            system_prompt=base_system_prompt,
            user_prompt=enhanced_exec_summary_prompt,
            search_results=formatted_search_results,
            previous_sections={},
            target_word_count=per_section_word_count,
            investment_principles=investment_principles
        )
        
        # Parse portfolio from executive summary using the original approach
        log_info("Extracting portfolio positions from fallback executive summary...")
        
        # Extract portfolio positions JSON from executive summary using the HTML comment format
        portfolio_positions = []
        portfolio_json = None
        json_match = re.search(r'<!--\s*PORTFOLIO_POSITIONS_JSON:\s*(\[.*?\])\s*-->', report_sections["Executive Summary - Comprehensive Portfolio Summary"], re.DOTALL)
        
        if json_match:
            try:
                portfolio_positions = json.loads(json_match.group(1))
                portfolio_json = json.dumps(portfolio_positions, indent=2)
                log_info(f"Successfully extracted {len(portfolio_positions)} portfolio positions from fallback executive summary - Comprehensive Portfolio Summary.")
            except Exception as e:
                log_warning(f"Failed to parse portfolio positions JSON from fallback executive summary - Comprehensive Portfolio Summary: {e}")
                raise  # Re-raise to trigger the default positions
        else:
            log_warning("No portfolio positions JSON found in fallback executive summary - Comprehensive Portfolio Summary.")
            raise ValueError("No portfolio positions found in executive summary - Comprehensive Portfolio Summary")
            
    except Exception as e:
        log_warning(f"Fallback extraction failed: {str(e)}. Generating default portfolio positions...")
        # Generate default portfolio positions as final fallback
        try:
            # Create a minimal set of default portfolio positions
            default_positions = [
                {"asset": "STNG", "position_type": "LONG", "allocation_percent": 15, "time_horizon": "6-12 months", "confidence_level": "High"},
                {"asset": "SHEL", "position_type": "LONG", "allocation_percent": 10, "time_horizon": "12-24 months", "confidence_level": "High"},
                {"asset": "RIO", "position_type": "LONG", "allocation_percent": 10, "time_horizon": "6-12 months", "confidence_level": "Medium"},
                {"asset": "GSL", "position_type": "LONG", "allocation_percent": 8, "time_horizon": "3-6 months", "confidence_level": "Medium"},
                {"asset": "BDRY", "position_type": "LONG", "allocation_percent": 7, "time_horizon": "3-6 months", "confidence_level": "Medium"},
                {"asset": "BHP", "position_type": "LONG", "allocation_percent": 6, "time_horizon": "6-12 months", "confidence_level": "Medium"},
                {"asset": "VALE", "position_type": "LONG", "allocation_percent": 6, "time_horizon": "6-12 months", "confidence_level": "Medium"},
                {"asset": "DAC", "position_type": "LONG", "allocation_percent": 5, "time_horizon": "3-6 months", "confidence_level": "Medium"},
                {"asset": "TTE", "position_type": "LONG", "allocation_percent": 5, "time_horizon": "12-24 months", "confidence_level": "Medium"},
                {"asset": "GOLD", "position_type": "LONG", "allocation_percent": 5, "time_horizon": "12-24 months", "confidence_level": "Medium"},
                {"asset": "GOGL", "position_type": "LONG", "allocation_percent": 5, "time_horizon": "3-6 months", "confidence_level": "Medium"},
                {"asset": "MAERSK-B.CO", "position_type": "SHORT", "allocation_percent": 4, "time_horizon": "3-6 months", "confidence_level": "Medium"},
                {"asset": "SBLK", "position_type": "LONG", "allocation_percent": 4, "time_horizon": "3-6 months", "confidence_level": "Medium"},
                {"asset": "CMRE", "position_type": "LONG", "allocation_percent": 3, "time_horizon": "3-6 months", "confidence_level": "Medium"},
                {"asset": "CLF", "position_type": "LONG", "allocation_percent": 3, "time_horizon": "6-12 months", "confidence_level": "Medium"},
            ]
            
            portfolio_positions = default_positions
            portfolio_json = json.dumps(portfolio_positions, indent=2)
            log_info(f"Generated default portfolio with {len(portfolio_positions)} positions.")
            
            # Insert the portfolio positions JSON into the executive summary
            json_comment = f"<!-- PORTFOLIO_POSITIONS_JSON:\n{portfolio_json}\n-->"
            report_sections["Executive Summary - Comprehensive Portfolio Summary"] += f"\n\n{json_comment}"
        except Exception as e:
            log_error(f"Failed to generate default portfolio positions: {e}")
    
    # 2. Generate Global Trade & Economy section
    global_economy_prompt = GLOBAL_TRADE_ECONOMY_PROMPT.format(per_section_word_count=per_section_word_count)

    report_sections["Global Trade & Economy"] = await generate_section_with_web_search(
        client,
        "Global Trade & Economy",
        base_system_prompt,
        global_economy_prompt,
        formatted_search_results,
        {"Executive Summary - Comprehensive Portfolio Summary": report_sections["Executive Summary - Comprehensive Portfolio Summary"]},
        per_section_word_count,
        investment_principles=investment_principles
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Global Trade & Economy")
    
    # 3. Generate Energy Markets section
    energy_markets_prompt = ENERGY_MARKETS_PROMPT.format(per_section_word_count=per_section_word_count)

    report_sections["Energy Markets"] = await generate_section_with_web_search(
        client,
        "Energy Markets",
        base_system_prompt,
        energy_markets_prompt,
        formatted_search_results,
        {"Executive Summary - Comprehensive Portfolio Summary": report_sections["Executive Summary - Comprehensive Portfolio Summary"], "Global Trade & Economy": report_sections["Global Trade & Economy"]},
        per_section_word_count,
        investment_principles=investment_principles
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Energy Markets")
    
    # 4. Generate Commodities section
    commodities_prompt = COMMODITIES_MARKETS_PROMPT.format(per_section_word_count=per_section_word_count)

    report_sections["Commodities Markets"] = await generate_section_with_web_search(
        client,
        "Commodities Markets",
        base_system_prompt,
        commodities_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Executive Summary - Comprehensive Portfolio Summary", "Global Trade & Economy", "Energy Markets"]},
        per_section_word_count,
        investment_principles=investment_principles
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Commodities Markets")
    
    # 5. Generate Shipping section
    shipping_prompt = SHIPPING_INDUSTRY_PROMPT.format(per_section_word_count=per_section_word_count)

    report_sections["Shipping Industry"] = await generate_section_with_web_search(
        client,
        "Shipping Industry",
        base_system_prompt,
        shipping_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Executive Summary - Comprehensive Portfolio Summary", "Global Trade & Economy", "Energy Markets", "Commodities Markets"]},
        per_section_word_count,
        investment_principles=investment_principles
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Shipping Industry")
    
    # 6. Generate Portfolio Holdings section
    portfolio_prompt = PORTFOLIO_HOLDINGS_PROMPT.format(per_section_word_count=per_section_word_count)

    # Use named parameters for the Portfolio Holdings section to avoid parameter order confusion
    report_sections["Portfolio Holdings"] = await generate_section_with_web_search(
        client=client,
        section_name="Portfolio Holdings",
        system_prompt=base_system_prompt,
        user_prompt=portfolio_prompt,
        search_results=formatted_search_results,
        previous_sections={k: report_sections[k] for k in ["Executive Summary - Comprehensive Portfolio Summary", "Global Trade & Economy", "Energy Markets", "Commodities Markets", "Shipping Industry"]},
        target_word_count=per_section_word_count,
        investment_principles=investment_principles
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Portfolio Holdings")
    
    # 7. Generate Benchmarking & Performance section
    benchmarking_prompt = BENCHMARKING_PERFORMANCE_PROMPT.format(per_section_word_count=per_section_word_count)

    report_sections["Benchmarking & Performance"] = await generate_section_with_web_search(
        client,
        "Benchmarking & Performance",
        base_system_prompt,
        benchmarking_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Executive Summary - Comprehensive Portfolio Summary", "Portfolio Holdings"]},
        per_section_word_count,
        investment_principles=investment_principles
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Benchmarking & Performance")
    
    # 8. Generate Risk Assessment section
    risk_prompt = RISK_ASSESSMENT_PROMPT.format(per_section_word_count=per_section_word_count)

    report_sections["Risk Assessment"] = await generate_section_with_web_search(
        client,
        "Risk Assessment",
        base_system_prompt,
        risk_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Executive Summary - Comprehensive Portfolio Summary", "Global Trade & Economy", "Portfolio Holdings"]},
        per_section_word_count,
        investment_principles=investment_principles
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Risk Assessment")
    
    # 9. Generate Conclusion & Outlook section
    conclusion_prompt = CONCLUSION_OUTLOOK_PROMPT.format(per_section_word_count=per_section_word_count)

    report_sections["Conclusion & Outlook"] = await generate_section_with_web_search(
        client,
        "Conclusion & Outlook",
        base_system_prompt,
        conclusion_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Executive Summary - Comprehensive Portfolio Summary", "Global Trade & Economy", "Energy Markets", "Portfolio Holdings", "Risk Assessment"]},
        per_section_word_count,
        investment_principles=investment_principles
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Conclusion & Outlook")
    
    # 10. Generate References & Sources section
    references_prompt = REFERENCES_SOURCES_PROMPT

    report_sections["References & Sources"] = await generate_section_with_web_search(
        client,
        "References & Sources",
        base_system_prompt,
        references_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Executive Summary - Comprehensive Portfolio Summary", "Global Trade & Economy", "Energy Markets", "Portfolio Holdings", "Risk Assessment", "Conclusion & Outlook"]},
        per_section_word_count,
        investment_principles=investment_principles
    )
    
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: References & Sources")

    # 11. Generate Allocation section
    # Load previous allocation weights from Firestore
    prev_allocation_weights = FirestoreDownloader().get_latest("portfolio_weights")
    allocation_prompt = ALLOCATION_CHANGES_PROMPT.format(
        old_portfolio_weights=prev_allocation_weights,
        current_portfolio_weights=portfolio_json
    )
    report_sections["Executive Summary - Allocation"] = await generate_section_with_web_search(
        client,
        "Executive Summary - Allocation",
        base_system_prompt,
        allocation_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Executive Summary - Comprehensive Portfolio Summary", "Global Trade & Economy", "Energy Markets", "Portfolio Holdings", "Risk Assessment", "Conclusion & Outlook"]},
        target_word_count=50,
        investment_principles=investment_principles
    )
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Allocation")

    # 12. Generate Insights section
    insights_prompt = INSIGHTS_CHANGES_PROMPT.format(
        old_portfolio_weights=prev_allocation_weights,
        current_portfolio_weights=portfolio_json
    )
    report_sections["Executive Summary - Insights"] = await generate_section_with_web_search(
        client,
        "Executive Summary - Insights",
        base_system_prompt,
        insights_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Executive Summary - Comprehensive Portfolio Summary", "Global Trade & Economy", "Energy Markets", "Portfolio Holdings", "Risk Assessment", "Conclusion & Outlook", "Executive Summary - Allocation"]},
        target_word_count=50,
        investment_principles=investment_principles
    )
    completed_sections += 1
    log_info(f"Completed section {completed_sections}/{total_sections}: Executive Summary - Insights")
    
    # Combine all sections into a single report
    report_content = f"""# Standard Report
**Date and time last ran: {current_date}, @ {datetime.now().strftime('%H:%M:%S')} (Athens Time).**

"""
    
    log_info("Report generation complete!")
    
    # Calculate total word count
    total_words = len(report_content.split())
    log_info(f"Total report word count: {total_words}")
    
    # Extract portfolio data from the report
    log_info("Extracting portfolio data from generated report sections...")
    # --- News Update Section (LLM-powered) ---
    
    # Define news categories order
    category_order = [
        "Shipping",
        "Commodities", 
        "Central Bank Policies",
        "Global Trade",
        "Energy Markets",
        "Geopolitical Events"
    ]
    
    # Use category_order to create a simpler categories structure with one entry per category
    categories = []
    for index, category in enumerate(category_order):
        # Each category now just points to a single entry in the search results
        categories.append((category, index, index + 1))
    try:
        with open(os.path.join(os.path.dirname(__file__), "orasis_investment_principles.txt"), "r") as f:
            investment_principles = f.read().strip()
            
        category_order = [
            "Shipping",
            "Commodities", 
            "Central Bank Policies",
            "Macroeconomic News",
            "Global Trade & Tariffs",
            "Geopolitical Events"
        ]
        category_queries = {
            "Shipping": [f"Provide an in depth analysis of shipping news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: " + investment_principles],
            "Commodities": [f"Provide an in depth analysis of commodities market news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: " + investment_principles],
            "Central Bank Policies": [f"Provide an in depth analysis of central bank policy news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: " + investment_principles],
            "Macroeconomic News": [f"Provide an in depth analysis of macroeconomic news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: " + investment_principles],
            "Global Trade & Tariffs": [f"Provide an in depth analysis of global trade and tariffs news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: " + investment_principles],
            "Geopolitical Events": [f"Provide an in depth analysis of geopolitical events news within the last 24 hours from now (as of {datetime.now().strftime('%B %Y')}) in light of the following investment principles: " + investment_principles]
        }
            
        # Build the flat search_queries list and categories index list
        # search_queries = []
        # for cat_name in category_order:
        #     search_queries.extend(category_queries[cat_name])
        
        # Generate the news update section
        
        # Prepare search results in the correct format for the news update generator
        search_results_list = []
        if formatted_search_results and isinstance(formatted_search_results, dict):
            # Create one search result per category using the main category query
            for cat_name in category_order:
                # Get the first query for this category
                if cat_name in category_queries and category_queries[cat_name]:
                    main_query = category_queries[cat_name][0]
                    # Check if we have search results for this query
                    if main_query in formatted_search_results:
                        search_results_list.append({
                            'query': main_query,
                            'results': [{'content': formatted_search_results[main_query]}],
                            'citations': []  # Add empty citations list
                        })
                    else:
                        # Add dummy results if none found
                        search_results_list.append({
                            'query': f"Latest {cat_name} trends",
                            'results': [{'content': f"No search results found for {cat_name}"}],
                            'citations': []
                        })
                else:
                    # Fallback if category has no queries defined
                    search_results_list.append({
                        'query': f"Latest {cat_name} trends",
                        'results': [{'content': f"No search queries defined for {cat_name}"}],
                        'citations': []
                    })
        
        # Prepare categories in the correct format (tuple of name, start_idx, end_idx)
        # formatted_categories = []
        # start_idx = 0
        # for cat_name in category_order:
        #     cat_queries = category_queries[cat_name]
        #     end_idx = start_idx + len(cat_queries)
        #     formatted_categories.append((cat_name, start_idx, end_idx))
        #     start_idx = end_idx
        
        # new_categories_akwasi = ["Shipping","Commodities","Central Bank Policies","Macroeconomic News","Global Trade & Tariffs","Geopolitical Events"]
        
        # Store news section in report_sections dictionary
        if news_section:
            report_sections["Latest Market News"] = "\n" + news_section
            log_info("Added news update section to report_sections dictionary")
    except Exception as e:
        log_error(f"Error generating news update section: {e}")
    
    # Define the section order
    section_order = [
        "Latest Market News",
        "Executive Summary - Allocation",
        "Executive Summary - Insights",
        "Executive Summary - Comprehensive Portfolio Summary",
        # "Global Trade & Economy",
        # "Energy Markets",
        # "Commodities Markets",
        # "Shipping Industry",
        # "Conclusion & Outlook",
        # "References & Sources"
    ]
    
    # Add sections in order
    for section in section_order:
        if section in report_sections:
            report_content += report_sections[section] + "\n\n"
    
    portfolio_json = ""

    # Generate portfolio JSON
    try:
        # Default empty portfolio for fallback
        default_portfolio = {
            "data": {
                "report_date": current_date,
                "assets": []
            }
        }

        old_portfolio_weights = firebase_downloader.get_latest("portfolio_weights")
        
        log_info(f"Old portfolio weights: {old_portfolio_weights}")
        # Generate portfolio JSON using the full report content as source of truth
        portfolio_json = await generate_portfolio_json(
            client,
            default_portfolio.get("data", {}).get("assets", []),
            current_date,
            report_content,
            investment_principles,
            old_portfolio_weights,
            search_client,
            formatted_search_results
        )

        # method to calculate benchmark metrics using portfolio_json
        from portfolio_generator.modules.benchmark_metrics import calculate_benchmark_metrics
        calculated_metrics_json = await calculate_benchmark_metrics(
            client,
            portfolio_json,
            current_date
        )
        log_info(f"Calculated benchmark metrics: {calculated_metrics_json}")

        # portfolio_json = portfolio_positions
        log_info("Using already generated portfolio weights JSON")

        # upload calculated metrics to firestore under a new collection called "benchmark_metrics"
        from portfolio_generator.modules.report_upload import FirestoreUploader
        uploader_bm = FirestoreUploader()
        bm_col = uploader_bm.db.collection("benchmark_metrics")
        # Mark previous benchmark_metrics docs as not latest
        try:
            bm_q = bm_col.filter("doc_type", "==", "benchmark_metrics").filter("is_latest", "==", True)
        except AttributeError:
            bm_q = bm_col.where(filter=FieldFilter("doc_type", "==", "benchmark_metrics")).where(filter=FieldFilter("is_latest", "==", True))
        for doc in bm_q.stream():
            bm_col.document(doc.id).update({"is_latest": False})
        bm_ref = bm_col.document()
        bm_ref.set({
            "metrics_json": calculated_metrics_json,
            "doc_type": "benchmark_metrics",
            "file_format": "json",
            "timestamp": firestore.SERVER_TIMESTAMP,
            "is_latest": True,
            "source_report_id": firestore_report_doc_id,
            "created_at": datetime.now(timezone.utc)
        })
        log_success(f"Benchmark metrics uploaded with id: {bm_ref.id}")
    except Exception as e:
        log_error(f"Error generating portfolio JSON: {e}")
        portfolio_json = json.dumps(default_portfolio)

    try:

        # log_info("Currently combining news content")
        # news_blocks = []
        # for topic, text in llm_corpora.items():
        #     header = f"======= {topic} ======="
        #     body = text.strip()
        #     news_blocks.append(f"{header}\n{body}\n")

        # news_text = "\n".join(news_blocks)  

        # log_info("Completed combining news content") 

        # upload news scratchpad to firestore, under a new collection called "news_scratchpad"
        uploader_nc = FirestoreUploader()
        nc_col = uploader_nc.db.collection("news_scratchpad")
        try:
            nc_q = nc_col.filter("doc_type", "==", "news_scratchpad").filter("is_latest", "==", True)
        except AttributeError:
            nc_q = nc_col.where(filter=FieldFilter("doc_type", "==", "news_scratchpad")).where(filter=FieldFilter("is_latest", "==", True))
        for doc in nc_q.stream():
            nc_col.document(doc.id).update({"is_latest": False})
        nc_ref = nc_col.document()
        nc_ref.set({
            "llm_corpora_json": llm_corpora,
            "doc_type": "news_scratchpad",
            "file_format": "json",
            "timestamp": firestore.SERVER_TIMESTAMP,
            "is_latest": True,
            "source_report_id": firestore_report_doc_id,
            "created_at": datetime.now(timezone.utc),
            "total_content": news_section

        })
        log_success(f"Benchmark metrics uploaded with id: {nc_ref.id}")
    except Exception as e:
        log_error(f"Error uploading the news scratchpad to Firebase: {e}")


    try:
        log_info("Currently combining portfolio content")

        portfolio_blocks = []
        for entry in portfolio_scratchpad:
            for key in ["actor", "message", "feedback", "decision_text", "output_markdown"]:
                if key in entry and entry[key]:
                    header = f"======= {entry.get('actor', key)} ======="
                    body = entry[key].strip()
                    portfolio_blocks.append(f"{header}\n{body}\n")

        portfolio_text = "\n".join(portfolio_blocks)

        log_info("Completed combining portfolio content")


        # upload portfolio scratchpad to firestore, under a new collection called "portfolio_scratchpad"
        uploader_ps = FirestoreUploader()
        pscol = uploader_ps.db.collection("portfolio_scratchpad")
        try:
            psq = pscol.filter("doc_type", "==", "portfolio_scratchpad").filter("is_latest", "==", True)
        except AttributeError:
            psq = pscol.where(filter=FieldFilter("doc_type", "==", "portfolio_scratchpad")).where(filter=FieldFilter("is_latest", "==", True))
        for doc in psq.stream():
            pscol.document(doc.id).update({"is_latest": False})
        psref = pscol.document()
        psref.set({
            "portfolio_scratchpad_json": portfolio_scratchpad,
            "doc_type": "portfolio_scratchpad",
            "file_format": "json",
            "timestamp": firestore.SERVER_TIMESTAMP,
            "is_latest": True,
            "source_report_id": firestore_report_doc_id,
            "created_at": datetime.now(timezone.utc),
            "total_content": portfolio_text
        })
        log_success(f"Benchmark metrics uploaded with id: {psref.id}")
    except Exception as e:
        log_error(f"Error uploading the news scratchpad to Firebase: {e}")


    # adding feedback to the report
    try:
        db = firestore.Client(project="hedgefundintelligence", database="hedgefundintelligence")
        docs = db.collection("feedback-scratchpad").where("is_latest", "==", True).limit(1).stream()
        doc = next(docs, None)

        george_feedback = ""
        if doc:
            data = doc.to_dict()
            ts = data.get("timestamp")
            if ts:
                # If timestamp is string, parse as ISO8601
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        ts = None  # Fallback if parsing fails
                # If timestamp is datetime, use as is
                if isinstance(ts, datetime):
                    now = datetime.now(timezone.utc)
                    if now - ts < timedelta(hours=24):
                        george_feedback = data.get("scratchpad")

                        from portfolio_generator.modules.feedback_summarizer import FeedbackSummarizer
                        summarizer = FeedbackSummarizer()
                        result = summarizer.process_feedback_text(george_feedback)

                        report_content = result + report_content
                    else:
                        log_warning("George had no feedback in the last 24 hours")
                        result = None
    except Exception as e:
        log_error(f"Failed to save portfolio weights to file: {e}")




    # sanitize report content via Gemini
    report_content = sanitize_report_content_with_gemini(report_content)
    
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

                    try:
                        uploader = FirestoreUploader(database="hedgefundintelligence")
                        db = uploader.db
                        alt_weights = db.collection('report-alternatives') \
                            .where('doc_type', '==', 'portfolio-weights-alternative') \
                            .where('is_latest', '==', True)

                        for doc in alt_weights.stream():
                            print(doc.id, doc.to_dict())

                        old_alternative_portfolio_weights = doc.to_dict()["content"]
                        log_success(f"Successfully Pulled Old Alternative portfolio weights")
                    except:
                        old_alternative_portfolio_weights = ""
                        log_warning("Could not pull Old Alternative portfolio weights")
                    
                    # Generate and upload alternative report for ePubs
                    _, new_alt_weights, new_alt_report = await generate_and_upload_alternative_report(
                        current_report_content_md = report_content,
                        current_report_firestore_id = firestore_report_doc_id,
                        gemini_model_name="gemini-2.5-pro-preview-05-06",
                        google_api_key=os.environ.get("GEMINI_API_KEY"),
                        investment_principles_str=investment_principles,
                        llm_news_corpus_str=formatted_search_results,
                        previous_report_portfolio_json_str=old_alternative_portfolio_weights
                    )
                    from portfolio_generator.modules.alt_sections_creator import create_alt_sections
                    
                    risk_content_alt  = await create_alt_sections(client, formatted_search_results, new_alt_report, investment_principles, new_alt_weights, old_alternative_portfolio_weights)
                    
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
    
    # Create and upload Risk & Benchmark report
    try:

        # 11. Generate Performance analysis section 

        # Fetch from firestore most recent portfolio weights.
        firestore_downloader = FirestoreDownloader()
        old_portfolio_weights = firestore_downloader.get_latest("portfolio_weights")
        
        performance_prompt = PERFORMANCE_ANALYSIS_PROMPT.format(per_section_word_count=per_section_word_count, old_portfolio_weights=old_portfolio_weights, current_portfolio_weights=portfolio_json)

        report_sections["Performance Analysis"] = await generate_section_with_web_search(
            client,
            "Performance Analysis",
            base_system_prompt,
            performance_prompt,
            formatted_search_results,
            {k: report_sections[k] for k in ["Executive Summary - Comprehensive Portfolio Summary", "Global Trade & Economy", "Energy Markets", "Commodities Markets", "Shipping Industry", "Portfolio Holdings", "Risk Assessment", "Conclusion & Outlook"]},
            per_section_word_count,
            investment_principles=investment_principles
        )
    
        
        risk_sections = ["Portfolio Holdings", "Performance Analysis", "Benchmarking & Performance", "Risk Assessment"]
        risk_content = ""
        for sec in risk_sections:
            if sec in report_sections:
                risk_content += report_sections[sec] + "\n\n"
        if risk_content:
            uploader_rb = FirestoreUploader()
            rb_col = uploader_rb.db.collection("risk_and_benchmark")
            # Mark existing as not latest
            try:
                rb_q = rb_col.filter("doc_type", "==", "risk_and_benchmark").filter("is_latest", "==", True)
            except AttributeError:
                rb_q = rb_col.where(filter=FieldFilter("doc_type", "==", "risk_and_benchmark")).where(filter=FieldFilter("is_latest", "==", True))
            for doc in rb_q.stream():
                rb_col.document(doc.id).update({"is_latest": False})
            rb_ref = rb_col.document()
            rb_ref.set({
                "content": risk_content,
                "doc_type": "risk_and_benchmark",
                "file_format": "markdown",
                "timestamp": firestore.SERVER_TIMESTAMP,
                "is_latest": True,
                "source_report_id": firestore_report_doc_id,
                "created_at": datetime.now(timezone.utc)
            })
            log_success(f"Risk & Benchmark report uploaded with id: {rb_ref.id}")
    except Exception as e_rb:
        log_warning(f"Failed to upload Risk & Benchmark report: {e_rb}")

    # Generate and upload PDF version of the report

    try:
        # Import the PDF service
        from portfolio_generator.modules.pdf_report.report_pdf_service import ReportPDFService

        # Only run PDF generation if we have report sections
        if report_content:
            pdf_service = ReportPDFService(bucket_name="reportpdfhedgefundintelligence")
            
            log_info("Generating PDF report...")
            
            pdf_result = pdf_service.generate_and_upload_pdf(
                report_sections=report_content,
                report_date=current_date,
                upload_to_gcs=not dry_run and not test_mode,
                keep_local_copy=test_mode
            )
            
            if pdf_result.get('gcs_path'):
                log_success(f"PDF uploaded to: {pdf_result['gcs_path']}")
            
            if pdf_result.get('local_path'):
                log_info(f"PDF saved locally: {pdf_result['local_path']}")
                
    except Exception as e:
        log_error(f"PDF generation failed: {e}")
        
        # Continue execution - PDF generation failure shouldn't stop the report

    try:
        # Import the PDF service
        from portfolio_generator.modules.pdf_report.report_pdf_service import ReportPDFService

        # Only run PDF generation if we have report sections
        if report_content:
            pdf_service = ReportPDFService(bucket_name="altreportpdfhedgefundintelligence")
            
            log_info("Generating PDF report...")
            
            pdf_result = pdf_service.generate_and_upload_pdf(
                report_sections=new_alt_report,
                report_date=current_date,
                upload_to_gcs=not dry_run and not test_mode,
                keep_local_copy=test_mode
            )
            
            if pdf_result.get('gcs_path'):
                log_success(f"PDF uploaded to: {pdf_result['gcs_path']}")
            
            if pdf_result.get('local_path'):
                log_info(f"PDF saved locally: {pdf_result['local_path']}")
                
    except Exception as e:
        log_error(f"PDF generation failed: {e}")

    try:

        # List of your JSON files
        files_to_delete = [
                    "scratchpads/portfolio_gen_scratchpad.json",
                    "news_human_digests.json",
                    "news_llm_corpora.json",
                    "processed_seen_urls.json"
                           ]

        for file in files_to_delete:
            if os.path.exists(file):
                os.remove(file)
                print(f"Deleted: {file}")
            else:
                print(f"File not found, skipping: {file}")
        log_success(f"Successfully cleared old files: digests and scratchpad")
    except Exception as e_rb:
        log_warning(f"Failed to Clear existing digests and scratchpad")
    
    # Return the report content
    return {
        "report_content": report_content,
        "portfolio_json": portfolio_json,
        "firestore_report_doc_id": firestore_report_doc_id
    }