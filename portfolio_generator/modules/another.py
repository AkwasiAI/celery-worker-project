import os
import json
import datetime
import logging
import time # For retry sleep
from typing import List, Dict, Any, Set, TypedDict
from uuid import uuid4

import requests # For specific exception handling
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
# from langchain_openai import ChatOpenAI # OLD
from langchain_google_genai import ChatGoogleGenerativeAI # NEW
# from google.generativeai.types import HarmCategory, HarmBlockThreshold # Potentially needed for safety_settings
from exa_py import Exa
from dotenv import load_dotenv
import re

# Assuming hallucination_checker.py exists and has detect_hallucinations
# from hallucination_checker import detect_hallucinations
# Placeholder if the above is not available:
def detect_hallucinations(text, min_confidence=0.6):
    log.warning("Using placeholder detect_hallucinations. No actual check is performed.")
    return []

# --- Logging Setup ---
# logging.basicConfig(
#     filename="orasis_news_agent.log", # Changed log file name
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
#     filemode="w",
# )
log = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google.generativeai").setLevel(logging.INFO) # Can be noisy, adjust as needed
logging.getLogger("google.api_core").setLevel(logging.INFO)


# --- Config and Load ---
load_dotenv()
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # Kept for reference
EXA_API_KEY = os.getenv("EXA_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # NEW

if not EXA_API_KEY:
    log.error("EXA_API_KEY is missing. Please check your .env file.")
    raise ValueError("EXA_API_KEY is missing.")

if not GEMINI_API_KEY:
    log.error("GEMINI_API_KEY is missing. Gemini models will not be available.")
    raise ValueError("GEMINI_API_KEY is missing.")

# MODEL = ChatOpenAI(model="gpt-4o", temperature=0.0, api_key=OPENAI_API_KEY) # OLD

# Initialize Gemini Model for general tasks
MODEL = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro-preview-05-06", # Use "gemini-pro" if 1.5 is not available/needed
    temperature=0.0,
    GEMINI_API_KEY=GEMINI_API_KEY,
    # convert_system_message_to_human=True # Enable if system prompts seem less effective
    # safety_settings={ # Uncomment and adjust if default safety is too strict
    #     HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    #     HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    #     HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    #     HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    # }
)
log.info(f"LLM initialized with Google Gemini model: {MODEL.model}")

# Initialize a separate Gemini Model specifically for JSON output from the analyzer
# This leverages Gemini's native JSON mode for more reliable structured output.
MODEL_FOR_ANALYZER_JSON = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",
    temperature=0.0,
    GEMINI_API_KEY=GEMINI_API_KEY,
    generation_config={"response_mime_type": "application/json"}
)
log.info(f"LLM for JSON (analyzer) initialized with Google Gemini model: {MODEL_FOR_ANALYZER_JSON.model}")


exa = Exa(api_key=EXA_API_KEY)

TRUSTED_DOMAINS = [
    "bloomberg.com", "reuters.com", "ft.com", "tradewindsnews.com",
    "lloydslist.com", "hellenicshippingnews.com", "seatrade-maritime.com",
    "clarksons.com", "iea.org", "spglobal.com"
]
NEWS_CATEGORIES = [
    "Shipping",
    "Commodities",
    "Central Bank Policies",
    "Macroeconomic News",
    "Global Trade & Tariffs",
    "Geopolitical Events"
]
NEWS_PER_CATEGORY = 5
MAX_DAYS_LOOKBACK = 2 
HALLUCINATION_CHECK_ENABLED = False
MAX_ITERATION = 3 

DIGESTS_FILE = "news_human_digests.json" # Changed output file name
CORPORA_FILE = "news_llm_corpora.json"   # Changed output file name
SEEN_URLS_FILE = "processed_seen_urls.json" # Changed output file name

current_date_str = datetime.datetime.now().strftime("%Y-%m-%d")

def load_file(path):
    log.info(f"Loading file: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        log.error(f"File not found: {path}. Agent may not function as expected.")
        return f"Error: Content from {path} could not be loaded."

def iso_to_date_object(iso_str: str) -> datetime.date | None:
    if not iso_str:
        return None
    try:
        return datetime.datetime.fromisoformat(iso_str.replace('Z', '+00:00')).date()
    except ValueError:
        log.warning(f"Could not parse date string: {iso_str}")
        return None

INVESTMENT_PRINCIPLES = load_file("orasis_investment_principles.txt")
INSTRUMENT_LIST_TEXT = load_file("list_of_instruments.txt")

# --- Prompt Templates ---
# Prompts remain largely the same. Minor adjustments might be needed after testing Gemini's behavior.
# For INSTRUMENT_ANALYZER_PROMPT, since we use native JSON mode, the LLM should NOT
# be instructed to wrap its output in ```json ... ```. It should output raw JSON.
# The prompt already asks for strict JSON, which is good.

PLAN_PROMPT = """
You are an expert research planner.
Your goal is to devise a strategy to find {n_news} unique, late-breaking news stories for the "{category}" sector. Today's date is {current_date}.
These stories MUST come from the provided trusted news domains.
Each news story must be from a different article (unique URL).
The news should ideally provide context for investment decisions. While specific instruments are listed below for awareness, focus on generating broad queries for the category first.
Later stages will analyze relevance to specific instruments.

Investment Instruments (for awareness, do not make queries for each):
{instruments}

General Investment Principles:
{principles}

Focus on creating effective search queries for the "{category}" that leverage the trusted domains.
Summarize your plan and list 3-4 diverse, high-quality search queries. Ensure queries are specific enough to be useful but broad enough to find multiple items.
Example query format: "Latest global {category} developments"

Prefix each query with '- '.
"""

# For Gemini's native JSON mode, the model should output raw JSON.
# The prompt should guide it to produce the JSON structure without additional markdown.
INSTRUMENT_ANALYZER_PROMPT = """
You are a precise financial news analyst. Your task is to determine if the given news article is potentially impactful or relevant to any of the financial instruments in the provided list.
The news may not directly mention the instrument's name or ticker, but it could affect its sector, underlying commodity, related markets, or macroeconomic conditions relevant to these instruments.
Your entire response MUST be a single JSON object.

NEWS ARTICLE:
Headline: {article_headline}
Snippet: {article_snippet}
URL: {article_url}

LIST OF INSTRUMENTS (Ticker/Identifier    Name):
--- INSTRUMENT LIST START ---
{instrument_list_text}
--- INSTRUMENT LIST END ---

Based ONLY on the news article text provided and the list of instruments:
1.  Is this news article potentially impactful or relevant to ANY of the instruments in the list? (Value for "is_relevant" key: "YES" or "NO")
2.  If "YES", list the Ticker/Identifiers (e.g., "HAFNI NO", "STNG US", "CLA Comdty", "SPX Index") from the provided instrument list that are most likely to be affected or that this news provides important context for. List up to 5 relevant Ticker/Identifiers. Ensure the Tickers/Identifiers you list are EXACTLY as they appear in the "LIST OF INSTRUMENTS". If "NO", or no instruments are affected, the value for "affected_instruments" should be an empty list.

Desired JSON Output Structure:
{{
  "is_relevant": "string <YES_OR_NO>",
  "affected_instruments": ["array of strings <TICKERS_OR_EMPTY>"]
}}
"""


WRITER_PROMPT = """
You are a financial newswriter for an LLM reader.
Given the following research items (headlines, snippets, URLs, and identified relevant instruments), create a clear, concise, and well-structured news digest.
Produce exactly {n_news} news items for the "{category}" category. Each item must be distinct. Today's date is {current_date}.

For each news item, include:
- A short, impactful headline (wrap in ### <Headline>)
- A 50-word digest (human-readable, 1 paragraph). Focus on the key takeaway and its potential implication. If specific instruments were identified as relevant to this news item, subtly weave that context or implication into the digest if natural and concise. Do not just list the instruments. Ensure the digest reflects recency based on today's date.
- The **full source URL** for verification (Format: - citation: <full URL>)

Prioritize the most recent and impactful news from the provided content. Ensure all {n_news} items are present and correctly formatted. No Extras! Please do not add any additional notes, maintain the structure of the format. Your output will be directly processed. Do not say 'Here is your news ......' Just follow the structure of the format

Format for each item:
### <Headline>

<Digest (1 paragraph)>

- citation: <full URL>

RESEARCH CONTENT (Snippets, URLs, and relevant instruments if any):
{content}
"""

LLM_CORPUS_PROMPT = """
Below is the research corpus of raw, unformatted news items gathered for "{category}".
This includes direct text snippets, headlines, source URLs, and instrument relevance analysis from all articles gathered during the research phase for this category.
This corpus is intended for LLM ingestion and analysis.

RAW RESEARCH CONTENT:
{content}
"""

CRITIC_PROMPT = """
You are a meticulous review agent.
Critically evaluate the DRAFT news digest for the "{category}" category based on the following criteria. Today's date is {current_date}.
1.  **Quantity**: Does the draft contain exactly {n_news} unique news items? (This is crucial)
2.  **Relevance Context**: Does each digest subtly incorporate context related to relevant financial instruments IF such relevance was identified for its source article? The digest should not just list instruments but explain or imply the connection.
3.  **Recency**: Does each news item appear to be recent and not outdated, considering today's date?
4.  **Clarity & Conciseness**: Is each item clearly written, concise, and easy to understand?
5.  **URLs**:
    *   Are all source URLs present?
    *   Are all source URLs unique?
6.  **Unsupported Claims**: Are there any vague, ambiguous, or seemingly unsupported claims within the digests? (Be specific if you find any)
7.  **Formatting**: Does each item follow the required format (### Headline, Digest, - citation: URL)?
8.  **Hallucinations (if provided)**: Review any flagged hallucinations. Do they need removal or rephrasing?


If there are significant issues (e.g., wrong number of items, missing URLs, major unsupported claims, severe formatting errors, critical hallucinations requiring re-research, complete lack of instrument context where expected, clearly outdated news), reply with "NEEDS_MORE_RESEARCH" on the first line, followed by a bulleted list of specific issues.
If the issues are minor and can be fixed by rephrasing or small edits (e.g., minor formatting, slight ambiguity, improving instrument context, rephrasing a hallucinated sentence if context allows), provide a bulleted list of short, actionable suggestions to improve the draft. Number your suggestions if possible.
If the draft meets all criteria and no hallucinations were found or they are minor and easily fixable, reply with "All criteria met."

DRAFT NEWS DIGEST:
{digest}

HALLUCINATIONS (if any):
{hallucinations}
"""

REVISION_PROMPT = """
You are an expert revision writer.
Your task is to improve the DRAFT news digest based on the provided CRITIQUE and HALLUCINATION LIST. Today's date is {current_date}.

Follow these instructions:
1.  **Address Critique**: Carefully review each point in the CRITIQUE. Implement all actionable suggestions. Pay special attention to ensuring exactly {n_news} items if the source material allows, that instrument relevance (if identified for an article) is subtly woven into its digest, and that news items are recent.
2.  **Handle Hallucinations**:
    *   If hallucinations are flagged, try to rephrase the affected sentence(s) to be factual based on the RESEARCH CONTENT, or remove the specific unsupported claim if it cannot be verified.
    *   Do NOT introduce new information not present in the research.
3.  **Ensure Requirements**: The final digest must:
    *   Contain exactly {n_news} unique news items for the "{category}" category (if sufficient relevant source material was provided).
    *   Have a clear headline, a 50-word digest, and a unique, full source URL for each item.
    *   Be well-formatted as specified.
    *   Be factual and based on the provided RESEARCH CONTENT.
    *   Reflect recency appropriate for today's date.
4.  **Maintain Quality**: Improve clarity, conciseness, and remove any vague or unsupported statements.

If the CRITIQUE states "NEEDS_MORE_RESEARCH" due to insufficient *relevant* source articles, you may not be able to produce {n_news} items. In this case, revise the existing items as best as possible based on other critique points and hallucinations. Please do not add any additional notes, maintain the structure of the original draft. Your output will be directly processed. Do not say 'Here is your news ......' Just follow the structure of the original draft

CRITIQUE:
{critique}

HALLUCINATIONS:
{hallucinations}

ORIGINAL DRAFT DIGEST:
{original_digest}

FULL RESEARCH CONTENT (This is the analyzed raw research, including snippets, URLs, and instrument relevance flags/lists. Use this as your source of truth):
{research_content_block}

Note Again: Please do not add any additional notes, maintain the structure of the original draft. Your output will be directly processed. Do not say 'Here is your news ......' Just follow the structure of the original draft
"""

QUERY_REFINER_PROMPT = """
You are a research query refiner.
The previous search attempt for "{category}" news did not yield enough distinct, high-quality, *instrument-relevant* articles. Today's date is {current_date}.
The critique was: {critique}
The current search queries used were:
{queries}

Based on the critique (especially if it indicates a lack of relevant results or insufficient instrument-relevant content), suggest 1-3 new or refined search queries.
The goal is to expand or diversify results for "{category}" news from trusted domains, ideally finding content that might have stronger connections to financial instruments and is recent.
Consider:
- Broader terms related to the category that might uncover more articles.
- Different angles or sub-topics within the category.
- Keywords that indicate recent events, analyses, or market impacts.
- My advise is not to make it too long, else you won't find articles. Aim for less than 8 words.

The date range for the search will be expanded by one day. Your queries should focus on content.
List each new query on a new line, prefixed with '- '.
"""

# --- LangGraph State ---
class NewsAgentState(TypedDict):
    category: str
    plan: str
    search_queries: List[str]
    raw_research_results: List[Dict[str, Any]]
    research: List[Dict[str, Any]] 
    human_digest: str
    llm_corpus: str
    hallucinations: List[Dict[str, Any]]
    critique: str
    critique_lines: List[str]
    final_digest: str
    seen_urls: Set[str]
    current_date_lookback: int
    max_retries_reached: bool

# --- LangGraph Nodes ---

def plan_node(state: NewsAgentState) -> NewsAgentState:
    category = state['category']
    log.info(f"[{category}] Entering PLAN node")
    messages = [
        SystemMessage(content=PLAN_PROMPT.format(
            category=category,
            instruments=INSTRUMENT_LIST_TEXT[:2000], 
            principles=INVESTMENT_PRINCIPLES,
            n_news=NEWS_PER_CATEGORY,
            current_date=current_date_str 
        )),
        HumanMessage(content=f"Generate the plan and search queries. Trusted domains: {', '.join(TRUSTED_DOMAINS)}")
    ]
    response = MODEL.invoke(messages)
    queries = []
    in_query_section = False
    for line in response.content.splitlines():
        stripped_line = line.strip()
        if stripped_line.lower().startswith("search queries") or stripped_line.lower().startswith("suggested queries"):
            in_query_section = True
            continue
        if in_query_section and (stripped_line.startswith("- ") or stripped_line.startswith("• ")):
            query = stripped_line.lstrip("-• ").strip()
            if query:
                 queries.append(query)

    if not queries:
        queries = [f'latest top {category} news {datetime.date.today().isoformat()}']
        log.warning(f"[{category}] PLAN node could not extract specific queries, using default: {queries}")
    
    log.info(f"[{category}] PLAN node extracted queries: {queries}")
    return {
        **state,
        "plan": response.content,
        "search_queries": queries,
        "current_date_lookback": 1,
        "max_retries_reached": False,
        "raw_research_results": [],
    }

def research_node(state: NewsAgentState) -> NewsAgentState:
    category = state["category"]
    queries = state["search_queries"]
    accumulated_raw_articles = list(state.get("raw_research_results", []))
    urls_in_current_accumulation = {a['url'] for a in accumulated_raw_articles}
    today_date_obj = datetime.date.today()
    lookback_days = state.get("current_date_lookback", 1)
    start_published_date_str = (today_date_obj - datetime.timedelta(days=lookback_days - 1)).isoformat()
    start_published_date_obj = datetime.date.fromisoformat(start_published_date_str)
    end_published_date_str = today_date_obj.isoformat()

    log.info(f"[{category}] Entering RESEARCH node. Queries: {queries}. Date range: {start_published_date_str} to {end_published_date_str}.")
    log.info(f"[{category}] Global seen URLs count: {len(state['seen_urls'])}. Accumulated raw for this category: {len(accumulated_raw_articles)}.")
    
    node_max_retries_flag = False
    newly_fetched_this_call = []

    for query_idx, query in enumerate(queries):
        if len(accumulated_raw_articles) + len(newly_fetched_this_call) >= NEWS_PER_CATEGORY * 8:
             log.info(f"[{category}] Accumulated potential articles near safety limit ({NEWS_PER_CATEGORY * 8}), stopping further Exa queries for this round.")
             break
        
        log.info(f"[{category}] Processing query ({query_idx+1}/{len(queries)}): '{query}'")
        
        exa_retries = 3
        for attempt in range(exa_retries):
            try:
                results = exa.search_and_contents(
                    query,
                    text={"include_html_tags": False, "max_characters": 5000},
                    use_autoprompt=True,
                    num_results=20,
                    include_domains=TRUSTED_DOMAINS,
                    start_published_date=start_published_date_str,
                    end_published_date=end_published_date_str,
                )
                log.info(f"[{category}] Exa search for query '{query}' returned {len(results.results)} results (Attempt {attempt+1})")
                
                for r in results.results:
                    if r.url and r.text and \
                       r.url not in state["seen_urls"] and \
                       r.url not in urls_in_current_accumulation:
                        
                        article_date_obj = iso_to_date_object(r.published_date)
                        if article_date_obj and start_published_date_obj <= article_date_obj <= today_date_obj: # Ensure within range
                            new_article_data = {
                                "headline": r.title if r.title else "No Title Provided",
                                "snippet": r.text.strip(),
                                "url": r.url,
                                "published_date": r.published_date,
                                "is_instrument_relevant": False, 
                                "affected_instruments": []
                            }
                            newly_fetched_this_call.append(new_article_data)
                            urls_in_current_accumulation.add(r.url)
                        elif not article_date_obj:
                            log.warning(f"[{category}] Skipping article due to unparseable/missing date: {r.url}")
                break 
            
            except (requests.exceptions.RequestException, ConnectionResetError) as e:
                log.warning(f"[{category}] Network error during Exa search for query '{query}' (Attempt {attempt+1}/{exa_retries}): {e}")
                if attempt + 1 == exa_retries:
                    log.error(f"[{category}] Exa search failed after {exa_retries} retries for query '{query}'.")
                    node_max_retries_flag = True
                else:
                    time.sleep(1 * (2**attempt))
            except Exception as e:
                log.error(f"[{category}] Critical error during Exa search for query '{query}': {e}", exc_info=True)
                node_max_retries_flag = True
                break

    final_accumulated_raw_articles = accumulated_raw_articles + newly_fetched_this_call
    log.info(f"[{category}] RESEARCH node: {len(newly_fetched_this_call)} new articles fetched this call. Total raw for category now: {len(final_accumulated_raw_articles)}.")
    
    return {
        **state,
        "raw_research_results": final_accumulated_raw_articles,
        "research": [],
        "max_retries_reached": state.get("max_retries_reached", False) or node_max_retries_flag,
    }

def instrument_analyzer_node(state: NewsAgentState) -> NewsAgentState:
    category = state["category"]
    articles_to_analyze = state.get("raw_research_results", []) 
    log.info(f"[{category}] Entering INSTRUMENT ANALYZER node for {len(articles_to_analyze)} articles.")

    if not articles_to_analyze:
        log.info(f"[{category}] No raw articles to analyze for instrument relevance.")
        return state

    analyzed_articles_list = []
    instrument_list_for_prompt = INSTRUMENT_LIST_TEXT

    for i, article_data in enumerate(articles_to_analyze):
        log.info(f"[{category}] Analyzing article {i+1}/{len(articles_to_analyze)}: {article_data['url'][:70]}...")
        max_llm_retries = 2 
        analysis_succeeded = False
        
        # Ensure the article_data has these keys initialized to avoid KeyErrors if LLM fails early
        article_data.setdefault('is_instrument_relevant', False)
        article_data.setdefault('affected_instruments', [])

        for attempt in range(max_llm_retries):
            try:
                prompt_content = INSTRUMENT_ANALYZER_PROMPT.format(
                    article_headline=article_data['headline'],
                    article_snippet=article_data['snippet'][:2000],
                    article_url=article_data['url'],
                    instrument_list_text=instrument_list_for_prompt
                )
                messages = [HumanMessage(content=prompt_content)] 
                
                response = MODEL_FOR_ANALYZER_JSON.invoke(messages)
                
                raw_response_content = response.content # Get the raw string

                # --- More Robust JSON Extraction ---
                json_match = re.search(r"```json\s*([\s\S]*?)\s*```", raw_response_content, re.DOTALL)
                if json_match:
                    json_string = json_match.group(1).strip()
                    log.debug(f"[{category}] Extracted JSON using regex: {json_string[:100]}...")
                else:
                    # If no markdown fence, assume it's raw JSON or try stripping common prefixes/suffixes
                    json_string = raw_response_content.strip()
                    if json_string.startswith("```"): # Catch if only opening fence exists
                        json_string = json_string.lstrip("```").strip()
                    if json_string.endswith("```"):
                        json_string = json_string.rstrip("```").strip()
                    log.debug(f"[{category}] Assuming raw JSON or stripped non-regex: {json_string[:100]}...")
                # --- End Robust JSON Extraction ---
                
                if not json_string:
                    log.error(f"[{category}] JSON string is empty after extraction for article {article_data['url']}. Raw response: {raw_response_content}")
                    # Continue to next attempt or fail if max retries
                    if attempt + 1 < max_llm_retries:
                        time.sleep(1 * (2**attempt))
                        continue
                    else: # Max retries reached for this article
                        break # Go to the 'if not analysis_succeeded' block

                analysis_result = json.loads(json_string)
                
                article_data['is_instrument_relevant'] = analysis_result.get('is_relevant', 'NO').upper() == 'YES'
                affected_instruments_data = analysis_result.get('affected_instruments', [])
                article_data['affected_instruments'] = affected_instruments_data if isinstance(affected_instruments_data, list) else []
                
                analysis_succeeded = True
                log.debug(f"[{category}] Analyzed: {article_data['url'][:50]}... Relevant: {article_data['is_instrument_relevant']}, Affected: {article_data['affected_instruments']}")
                break 
            except json.JSONDecodeError as e:
                log.error(f"[{category}] Failed to parse JSON from LLM for article {article_data['url']} (attempt {attempt+1}/{max_llm_retries}): {e}. Cleaned string was: '{json_string[:200]}...' Raw response: {raw_response_content[:200]}")
            except Exception as e:
                log.error(f"[{category}] Error analyzing article {article_data['url']} (attempt {attempt+1}/{max_llm_retries}): {e}", exc_info=True)
            
            if attempt + 1 < max_llm_retries:
                time.sleep(1 * (2**attempt)) 

        # This assignment should happen regardless of success to ensure all original articles are carried forward
        analyzed_articles_list.append(article_data) 

    log.info(f"[{category}] INSTRUMENT ANALYZER node completed. {len(analyzed_articles_list)} articles processed/updated.")
    return {**state, "raw_research_results": analyzed_articles_list}


def select_digest_articles_node(state: NewsAgentState) -> NewsAgentState:
    category = state["category"]
    all_analyzed_articles = state.get("raw_research_results", []) 
    log.info(f"[{category}] Entering SELECT DIGEST ARTICLES node from {len(all_analyzed_articles)} analyzed articles.")

    instrument_relevant_articles = [a for a in all_analyzed_articles if a.get('is_instrument_relevant', False)]
    log.info(f"[{category}] Found {len(instrument_relevant_articles)} instrument-relevant articles from the accumulated pool.")

    def get_sort_key(article):
        date_obj = iso_to_date_object(article.get("published_date", ""))
        return date_obj if date_obj else datetime.date.min 

    instrument_relevant_articles.sort(key=get_sort_key, reverse=True)

    selected_for_digest = []
    current_global_seen_urls = set(state["seen_urls"]) 

    for article in instrument_relevant_articles:
        if len(selected_for_digest) >= NEWS_PER_CATEGORY:
            break
        if article["url"] not in current_global_seen_urls:
            selected_for_digest.append(article)
            current_global_seen_urls.add(article["url"])
    
    log.info(f"[{category}] SELECT DIGEST ARTICLES selected {len(selected_for_digest)} articles for human digest. Total global seen URLs now: {len(current_global_seen_urls)}")
    
    return {
        **state,
        "research": selected_for_digest, 
        "seen_urls": current_global_seen_urls
    }

def writer_node(state: NewsAgentState) -> NewsAgentState:
    category = state["category"]
    log.info(f"[{category}] Entering WRITER node")
    articles_for_digest = state["research"] 
    
    if not articles_for_digest and NEWS_PER_CATEGORY > 0:
        human_readable_content_block = "No relevant articles found for digest."
    else:
        human_readable_content_block = "\n\n".join(
            f"Headline: {a['headline']}\nSnippet: {a['snippet']}\nURL: {a['url']}\n"
            f"Identified Relevant Instruments: {', '.join(a.get('affected_instruments', [])) if a.get('affected_instruments') else 'None'}"
            for a in articles_for_digest
        )

    writer_llm_messages = [
        SystemMessage(content=WRITER_PROMPT.format(
            n_news=NEWS_PER_CATEGORY,
            category=category,
            content=human_readable_content_block,
            current_date=current_date_str
        )),
        HumanMessage(content="Please write the news digest based on the provided research content, incorporating instrument relevance where noted.")
    ]
    human_digest_response = MODEL.invoke(writer_llm_messages)
    log.info(f"[{category}] WRITER node generated human_digest.")

    full_analyzed_corpus_articles = state["raw_research_results"]
    if not full_analyzed_corpus_articles:
        llm_corpus_content_block = "No raw research articles were found or accumulated for this category."
    else:
        llm_corpus_content_block = "\n\n---\n\n".join(
            f"Source URL: {a['url']}\nHeadline: {a['headline']}\nPublished Date: {a.get('published_date', 'N/A')}\n"
            f"Instrument Relevant: {a.get('is_instrument_relevant', 'N/A')}\n"
            f"Affected Instruments: {', '.join(a.get('affected_instruments', [])) if a.get('affected_instruments') else 'None'}\n"
            f"\nFull Snippet:\n{a['snippet']}"
            for a in full_analyzed_corpus_articles
        )
    
    llm_corpus = LLM_CORPUS_PROMPT.format(category=category, content=llm_corpus_content_block)
    log.info(f"[{category}] WRITER node prepared LLM corpus (length: {len(llm_corpus)}) from {len(full_analyzed_corpus_articles)} raw articles.")
    
    return {
        **state,
        "human_digest": human_digest_response.content,
        "llm_corpus": llm_corpus
    }

def hallucination_node(state: NewsAgentState) -> NewsAgentState:
    category = state["category"]
    log.info(f"[{category}] Entering HALLUCINATION CHECK node")
    if not HALLUCINATION_CHECK_ENABLED:
        return {**state, "hallucinations": []}
    if not state['human_digest']:
        return {**state, "hallucinations": []}
    try:
        flagged = detect_hallucinations(state['human_digest'], min_confidence=0.6)
        log.info(f"[{category}] HALLUCINATION CHECK found {len(flagged)} potential hallucinations.")
        return {**state, "hallucinations": flagged}
    except Exception as e:
        log.error(f"[{category}] Error during hallucination check: {e}")
        return {**state, "hallucinations": []}

def critic_node(state: NewsAgentState) -> NewsAgentState:
    category = state["category"]
    log.info(f"[{category}] Entering CRITIC node")
    digest_to_critique = state["human_digest"]
    hallucinations = state.get("hallucinations", [])
    num_selected_for_digest = len(state.get("research", []))
    
    critique_llm_messages = [
        SystemMessage(content=CRITIC_PROMPT.format(
            n_news=NEWS_PER_CATEGORY,
            category=category,
            digest=digest_to_critique,
            current_date=current_date_str,
            hallucinations=json.dumps(hallucinations, indent=2) if hallucinations else "None provided."
        )),
        HumanMessage(content="Please provide your critique of the draft news digest.")
    ]
    
    response = MODEL.invoke(critique_llm_messages)
    raw_critique_content = response.content.strip()
    critique_lines_list = [line.strip() for line in raw_critique_content.splitlines() if line.strip()]
    
    critique_status = "NEEDS_IMPROVEMENT"
    if critique_lines_list:
        first_line_lower = critique_lines_list[0].lower()
        if "needs_more_research" in first_line_lower:
            critique_status = "NEEDS_MORE_RESEARCH"
        elif "all criteria met" in first_line_lower:
            critique_status = "ALL_CRITERIA_MET"

    if num_selected_for_digest < NEWS_PER_CATEGORY:
        shortage_message = (f"Underlying *instrument-relevant* research provided only {num_selected_for_digest} "
                            f"articles for the digest; target was {NEWS_PER_CATEGORY}.")
        if shortage_message not in critique_lines_list:
             critique_lines_list.insert(0, shortage_message)
        if critique_status != "NEEDS_MORE_RESEARCH":
            log.info(f"[{category}] Forcing critique to NEEDS_MORE_RESEARCH due to insufficient *instrument-relevant* "
                     f"articles selected for digest ({num_selected_for_digest}/{NEWS_PER_CATEGORY}).")
            critique_status = "NEEDS_MORE_RESEARCH"
        
    log.info(f"[{category}] CRITIC node. Status: {critique_status}. Critique: {raw_critique_content[:200]}...")
    return {
        **state,
        "critique": critique_status,
        "critique_lines": critique_lines_list
    }

def revision_node(state: NewsAgentState) -> NewsAgentState:
    category = state["category"]
    log.info(f"[{category}] Entering REVISION node. Critique status: {state['critique']}")
    if state["critique"] == "ALL_CRITERIA_MET":
        return {**state, "final_digest": state["human_digest"]}

    analyzed_raw_articles = state["raw_research_results"]
    if not analyzed_raw_articles:
        research_content_block_for_revision = "No raw research articles were found for this category."
    else:
        research_content_block_for_revision = "\n\n---\n\n".join(
            f"Source URL: {a['url']}\nHeadline: {a['headline']}\nPublished Date: {a.get('published_date', 'N/A')}\n"
            f"Instrument Relevant: {a.get('is_instrument_relevant', 'N/A')}\n"
            f"Affected Instruments: {', '.join(a.get('affected_instruments', [])) if a.get('affected_instruments') else 'None'}\n"
            f"\nFull Snippet:\n{a['snippet']}"
            for a in analyzed_raw_articles
        )

    revision_llm_messages = [
        SystemMessage(content=REVISION_PROMPT.format(
            n_news=NEWS_PER_CATEGORY, 
            category=category,
            critique="\n".join(state.get("critique_lines", ["No specific critique points provided."])),
            hallucinations=json.dumps(state.get("hallucinations", []), indent=2) if state.get("hallucinations") else "None",
            original_digest=state["human_digest"],
            research_content_block=research_content_block_for_revision,
            current_date=current_date_str
        )),
        HumanMessage(content="Please revise the news digest based on the critique, hallucinations, and full research content.")
    ]
    
    response = MODEL.invoke(revision_llm_messages)
    log.info(f"[{category}] REVISION node completed LLM revision.")
    return {**state, "final_digest": response.content}

def refiner_node(state: NewsAgentState) -> NewsAgentState:
    category = state["category"]
    log.info(f"[{category}] Entering QUERY REFINER node.")
    current_lookback = state.get("current_date_lookback", 1)
    new_lookback = min(current_lookback + 1, MAX_DAYS_LOOKBACK) 
    if new_lookback == current_lookback and current_lookback == MAX_DAYS_LOOKBACK:
        log.info(f"[{category}] Date lookback already at MAX_DAYS_LOOKBACK ({MAX_DAYS_LOOKBACK}). Not expanding further for date.")
    else:
        log.info(f"[{category}] Expanding date lookback from {current_lookback} to {new_lookback} days.")

    current_queries = state.get("search_queries", [])
    refiner_llm_messages = [
        SystemMessage(content=QUERY_REFINER_PROMPT.format(
            critique="\n".join(state.get("critique_lines", [])),
            queries="\n".join(current_queries),
            category=category,
            current_date=current_date_str
        )),
        HumanMessage(content="Suggest new or refined search queries.")
    ]
    response = MODEL.invoke(refiner_llm_messages)
    
    refined_queries = []
    for line in response.content.strip().splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("- ") or stripped_line.startswith("• "):
            query = stripped_line.lstrip("-• ").strip()
            if query:
                refined_queries.append(query)
    
    if not refined_queries:
        refined_queries = current_queries
    
    log.info(f"[{category}] QUERY REFINER node suggested queries: {refined_queries}")
    return {
        **state,
        "search_queries": refined_queries,
        "current_date_lookback": new_lookback,
    }

def should_continue(state: NewsAgentState) -> str:
    category = state['category']
    critique_status = state['critique']
    num_articles_for_digest = len(state.get('research', [])) 
    # current_date_lookback is how many days we've looked back *in the previous research attempt*.
    # It becomes the *next* lookback if refiner_node increments it.
    # For controlling iterations, we use it as a proxy for loop count here.
    # loop_iteration is current_date_lookback (1 for first pass, 2 after first refine, etc.)
    loop_iteration_count = state.get("current_date_lookback", 1) 
    max_retries_node = state.get('max_retries_reached', False)

    log.debug(f"[{category}] SHOULD_CONTINUE: Critique='{critique_status}', DigestArticles={num_articles_for_digest}, Iteration/Lookback={loop_iteration_count}, MaxRetries={max_retries_node}")

    needs_more_articles_for_digest = num_articles_for_digest < NEWS_PER_CATEGORY

    if max_retries_node and needs_more_articles_for_digest:
        log.warning(f"[{category}] Max retries in Exa/Analyzer and still not enough digest articles. Route: revise_node.")
        return "revise_node"

    if critique_status == "NEEDS_MORE_RESEARCH" and needs_more_articles_for_digest:
        # MAX_ITERATION is the total number of passes through research (initial + refinements)
        if loop_iteration_count < MAX_ITERATION:
            # Also check if date lookback can still be expanded
            can_expand_date = state.get("current_date_lookback", 1) < MAX_DAYS_LOOKBACK
            if can_expand_date or loop_iteration_count < MAX_ITERATION: # Allow refinement even if date is maxed, if iterations not maxed
                log.info(f"[{category}] Needs more digest articles ({num_articles_for_digest}/{NEWS_PER_CATEGORY}). "
                         f"Refinement iteration {loop_iteration_count + 1}/{MAX_ITERATION}. Route: refiner_node")
                return "refiner_node"
            else:
                log.info(f"[{category}] Needs more digest articles ({num_articles_for_digest}/{NEWS_PER_CATEGORY}) but max refinement iterations ({MAX_ITERATION}) and date lookback reached. Route: revise_node.")
                return "revise_node"
        else:
            log.info(f"[{category}] Needs more digest articles ({num_articles_for_digest}/{NEWS_PER_CATEGORY}) but max refinement iterations ({MAX_ITERATION}) reached. Route: revise_node.")
            return "revise_node"
            
    log.info(f"[{category}] Routing to revision_node. Critique: '{critique_status}'. DigestArticles: {num_articles_for_digest}.")
    return "revise_node"

# --- Graph Setup ---
def build_graph() -> StateGraph:
    builder = StateGraph(NewsAgentState)
    builder.add_node("planner_node", plan_node)
    builder.add_node("research_node", research_node)
    builder.add_node("instrument_analyzer_node", instrument_analyzer_node) 
    builder.add_node("select_digest_articles_node", select_digest_articles_node) 
    builder.add_node("writer_node", writer_node)
    builder.add_node("hallucinate_node", hallucination_node)
    builder.add_node("critic_node", critic_node)
    builder.add_node("refiner_node", refiner_node)
    builder.add_node("revise_node", revision_node)

    builder.set_entry_point("planner_node")
    builder.add_edge("planner_node", "research_node")
    builder.add_edge("research_node", "instrument_analyzer_node") 
    builder.add_edge("instrument_analyzer_node", "select_digest_articles_node") 
    builder.add_edge("select_digest_articles_node", "writer_node") 
    builder.add_edge("writer_node", "hallucinate_node")
    builder.add_edge("hallucinate_node", "critic_node")
    
    builder.add_conditional_edges(
        "critic_node",
        should_continue,
        {
            "refiner_node": "refiner_node",
            "revise_node": "revise_node"
        }
    )
    builder.add_edge("refiner_node", "research_node") 
    builder.add_edge("revise_node", END)
    
    graph = builder.compile()
    log.info("News agent graph compiled successfully (using Gemini).")
    return graph

# --- RUN THE AGENT FOR ALL CATEGORIES ---
import asyncio

async def run_full_news_agent():
    all_human_digests = {}
    all_llm_corpora = {}
    global_seen_urls = set()

    if os.path.exists(DIGESTS_FILE):
        try:
            with open(DIGESTS_FILE, "r", encoding="utf-8") as f: all_human_digests = json.load(f)
            log.info(f"Loaded {len(all_human_digests)} human digests from {DIGESTS_FILE}")
        except Exception: all_human_digests = {}
    
    if os.path.exists(CORPORA_FILE):
        try:
            with open(CORPORA_FILE, "r", encoding="utf-8") as f: all_llm_corpora = json.load(f)
            log.info(f"Loaded {len(all_llm_corpora)} LLM corpora from {CORPORA_FILE}")
        except Exception: all_llm_corpora = {}

    if os.path.exists(SEEN_URLS_FILE):
        try:
            with open(SEEN_URLS_FILE, "r", encoding="utf-8") as f: global_seen_urls = set(json.load(f))
            log.info(f"Loaded {len(global_seen_urls)} seen URLs from {SEEN_URLS_FILE}")
        except Exception: global_seen_urls = set()

    graph = build_graph()

    for category in NEWS_CATEGORIES:
        if category in all_human_digests and category in all_llm_corpora and \
           not(str(all_human_digests.get(category, "")).startswith("Error processing category")):
            log.info(f"==== Skipping category: {category} (already processed successfully) ====")
            print(f"\n=== Skipping {category} (already processed successfully) ===")
            continue

        log.info(f"==== Starting category: {category} ====")
        print(f"\n=== Processing {category} ===")
        
        initial_state = NewsAgentState(
            category=category, plan="", search_queries=[], raw_research_results=[], 
            research=[], human_digest="", llm_corpus="", hallucinations=[],
            critique="", critique_lines=[], final_digest="",
            seen_urls=set(global_seen_urls), current_date_lookback=1, max_retries_reached=False
        )
        
        final_state_for_category = None
        try:
            configuration = {"recursion_limit": 50} 
            async for step_output in graph.astream(initial_state, config=configuration):
                node_name = list(step_output.keys())[0]
                final_state_for_category = step_output[node_name]
                log.info(f"[{category}] Graph step output from '{node_name}'.")
        except Exception as e:
            log.error(f"[{category}] UNHANDLED ERROR during agent execution: {e}", exc_info=True)
            all_human_digests[category] = f"Error processing category: {str(e)}"
            all_llm_corpora[category] = f"Error processing category: {str(e)}"
        
        if final_state_for_category:
            global_seen_urls.update(final_state_for_category.get("seen_urls", set()))
            all_human_digests[category] = final_state_for_category.get("final_digest", "Error: No final digest produced.")
            all_llm_corpora[category] = final_state_for_category.get("llm_corpus", "Error: No LLM corpus produced.")
            log.info(f"==== Completed category: {category} ====")
        elif category not in all_human_digests: 
            log.error(f"==== Category {category} finished without a final state and no explicit error recorded. ====")
            all_human_digests[category] = "Error: Agent finished without a final state or explicit error."
            all_llm_corpora[category] = "Error: Agent finished without a final state or explicit error."

        try:
            with open(DIGESTS_FILE, "w", encoding="utf-8") as f: json.dump(all_human_digests, f, indent=2, ensure_ascii=False)
            with open(CORPORA_FILE, "w", encoding="utf-8") as f: json.dump(all_llm_corpora, f, indent=2, ensure_ascii=False)
            with open(SEEN_URLS_FILE, "w", encoding="utf-8") as f: json.dump(list(global_seen_urls), f, indent=2, ensure_ascii=False)
            log.info(f"Intermediate results saved for category {category}")
        except Exception as e:
            log.error(f"Error saving intermediate results after category {category}: {e}")

    log.info("All categories processed. Final results saved.")
    print("\nAll categories processed and final results saved.")
    
    if os.path.exists(CORPORA_FILE):
        try:
            with open(CORPORA_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return None
    return None

if __name__ == "__main__":
    if not os.path.exists("orasis_investment_principles.txt"):
        with open("orasis_investment_principles.txt", "w") as f: f.write("Focus on long-term value.")
    if not os.path.exists("list_of_instruments.txt"):
        with open("list_of_instruments.txt", "w") as f: f.write("HAFNI NO	Hafnia Ltd\nCLA Comdty	WTI CRUDE")
    asyncio.run(run_full_news_agent())