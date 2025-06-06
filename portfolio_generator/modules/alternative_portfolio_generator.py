# portfolio_alternative_generator.py (using ChatGoogleGenerativeAI)
import os
import json
from datetime import datetime
import logging
import time
import asyncio # Keep for async operations if any part becomes async
from typing import List, Dict, Any, Optional, Tuple
from datetime import timezone

# LangChain Google GenAI
from langchain_google_genai import ChatGoogleGenerativeAI

# Firestore and other utilities (assuming they are in accessible paths)
from google.cloud import firestore
from google.api_core.exceptions import NotFound as FirestoreNotFound
from portfolio_generator.firestore_uploader import FirestoreUploader # Your existing uploader
from portfolio_generator.modules.logging import log_info, log_warning, log_error, log_success
from google.cloud.firestore_v1.base_query import FieldFilter
from portfolio_generator.modules.portfolio_generation_agent2 import extract_structured_parts_from_llm_output, ProposerDraft


# Check if Firestore is available (as in your original code)
FIRESTORE_AVAILABLE = False
try:
    from openai import OpenAI
    openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    # from google.cloud import firestore # Already imported
    # from portfolio_generator.firestore_uploader import FirestoreUploader # Already imported
    FIRESTORE_AVAILABLE = True
except ImportError:
    firestore = None
    FirestoreUploader = None
    log_error("FirestoreUploader could not be imported. Firestore uploads will not work.")

# Placeholder for preferred tickers (load this from your config or pass as argument)
# This MUST be part of the prompt text given to the LLM.
PREFERRED_TICKERS_CSV_STRING_FOR_PROMPT = """
 Category,Ticker,Name
        US-Listed Shipping Companies,HAFNI.OL,"Hafnia Limited (Oslo Listing, Note: Category US-Listed is a mismatch. US OTC is HAFNF.)"
        US-Listed Shipping Companies,STNG,Scorpio Tankers Inc.
        US-Listed Shipping Companies,TRMD,TORM plc (ADR)
        US-Listed Shipping Companies,FRO,Frontline plc
        US-Listed Commodity Companies,ECO,"Ecolab Inc. (If Ecopetrol EC was intended, this needs changing)"
        US-Listed Shipping Companies,DHT,DHT Holdings, Inc.
        Non-US-Listed Shipping Companies,EURN.BR,Euronav NV
        US-Listed Shipping Companies,INSW,International Seaways, Inc.
        US-Listed Shipping Companies,NAT,Nordic American Tankers Limited
        US-Listed Shipping Companies,TEN,Tsakos Energy Navigation Limited
        US-Listed Shipping Companies,IMPP,Imperial Petroleum Inc.
        US-Listed Shipping Companies,PSHG,Performance Shipping Inc.
        US-Listed Shipping Companies,TORO,Toro Corp.
        US-Listed Shipping Companies,TNK,Teekay Tankers Ltd.
        US-Listed Shipping Companies,PXS,"Pyxis Tankers Inc. (Note: Became Toro Corp., likely delisted)"
        US-Listed Shipping Companies,TOPS,TOP Ships Inc.
        US-Listed Shipping Companies,DSX,Diana Shipping Inc.
        US-Listed Shipping Companies,GNK,Genco Shipping & Trading Limited
        US-Listed Shipping Companies,GOGL,Golden Ocean Group Limited
        US-Listed Shipping Companies,NMM,Navios Maritime Partners L.P.
        US-Listed Shipping Companies,SB,Safe Bulkers, Inc.
        US-Listed Shipping Companies,SBLK,Star Bulk Carriers Corp.
        US-Listed Shipping Companies,SHIP,Seanergy Maritime Holdings Corp.
        Non-US-Listed Shipping Companies,HSHP.OL,Himalaya Shipping Ltd.
        US-Listed Shipping Companies,EDRY,EuroDry Ltd.
        US-Listed Shipping Companies,CTRM,Castor Maritime Inc.
        US-Listed Shipping Companies,ICON,"Iconix Brand Group, Inc. (Note: If different ""ICON"" was intended, clarify)"
        US-Listed Shipping Companies,GLBS,Globus Maritime Limited
        US-Listed Shipping Companies,CMRE,Costamare Inc.
        US-Listed Shipping Companies,DAC,Danaos Corporation
        US-Listed Shipping Companies,GSL,Global Ship Lease, Inc.
        US-Listed Shipping Companies,ESEA,Euroseas Ltd.
        Non-US-Listed Shipping Companies,MPCC.OL,MPC Container Ships ASA
        US-Listed Shipping Companies,ZIM,ZIM Integrated Shipping Services Ltd.
        US-Listed Shipping Companies,SFL,SFL Corporation Ltd.
        Non-US-Listed Shipping Companies,MAERSK-B.CO,A.P. Møller - Mærsk A/S B
        Non-US-Listed Shipping Companies,BWLPG.OL,BW LPG Limited
        US-Listed Shipping Companies,LPG,Dorian LPG Ltd.
        US-Listed Commodity Companies,CCEC,"China Communications Construction Co. Ltd. (ADR is CCECF, HK is 1800.HK - Clarify if different CCEC was meant)"
        US-Listed Shipping Companies,GASS,StealthGas Inc.
        US-Listed Shipping Companies,DLNG,Dynagas LNG Partners LP
        Non-US-Listed Shipping Companies,AGAS.OL,Avance Gas Holding Ltd.
        Non-US-Listed Shipping Companies,ALNG.OL,Awilco LNG ASA
        US-Listed Shipping Companies,FLNG,FLEX LNG Ltd.
        US-Listed Offshore Energy Companies,RIG,Transocean Ltd.
        US-Listed Offshore Energy Companies,HLX,Helix Energy Solutions Group, Inc.
        US-Listed Shipping Companies,PRS,"ProSight Global, Inc. (Acquired/Delisted - Note: If different PRS was intended, clarify)"
        Non-US-Listed Offshore Energy Companies,SBMO.AS,SBM Offshore N.V.
        US-Listed Offshore Energy Companies,TDW,Tidewater Inc.
        US-Listed Commodity Companies,RIO,Rio Tinto Group plc (ADR)
        US-Listed Commodity Companies,BHP,BHP Group Limited (ADR)
        US-Listed Commodity Companies,VALE,Vale S.A. (ADR)
        US-Listed Commodity Companies,GLNCY,Glencore plc (ADR)
        US-Listed Commodity Companies,ADM,Archer-Daniels-Midland Company
        US-Listed Commodity Companies,WLMIY,"Wilh. Wilhelmsen Holding ASA (ADR)"
        US-Listed Commodity Companies,BG,Bunge Global SA
        US-Listed Commodity Companies,SHEL,Shell plc (ADR)
        US-Listed Commodity Companies,XOM,Exxon Mobil Corporation
        US-Listed Commodity Companies,CVX,Chevron Corporation
        US-Listed Commodity Companies,TTE,TotalEnergies SE (ADR)
        US-Listed Commodity Companies,WPM,Wheaton Precious Metals Corp.
        US-Listed Commodity Companies,GOLD,Barrick Gold Corporation
        US-Listed Commodity Companies,CLF,Cleveland-Cliffs Inc.
        US-Listed Commodity Companies,ALB,Albemarle Corporation
        US-Listed Commodity Companies,MOS,The Mosaic Company
        Shipping & Tanker ETFs,BDRY,Breakwave Dry Bulk Shipping ETF
        Shipping & Tanker ETFs,BWET,Breakwave Tanker Shipping ETF
        Indices,CCMP,NASDAQ Composite Index (FMP Standard: ^IXIC)
        Indices,CAC,CAC 40 Index (FMP Standard: ^FCHI)
        Indices,DAX,DAX Index (FMP Standard: ^GDAXI)
        Indices,IBEX,IBEX 35 Index (FMP Standard: ^IBEX)
        Indices,SMI,Swiss Market Index (FMP Standard: ^SSMI)
        Non-US-Listed Shipping Companies,2020.OL,2020 Bulkers Ltd.
        Non-US-Listed Shipping Companies,JIN.OL,Jinhui Shipping and Transportation Limited
        Non-US-Listed Shipping Companies,BELCO.OL,Belships ASA
        Non-US-Listed Shipping Companies,COOL.OL,Cool Company Ltd.
        Non-US-Listed Offshore Energy Companies,SPM.MI,Saipem S.p.A.
        Indices,^DJI,Dow Jones Industrial Average
        Indices,^GSPC,S&P 500 Index
        Indices,^GSPTSE,S&P/TSX Composite Index
        Indices,^MXX,IPC Mexico Index
        Indices,^BVSP,Bovespa Index (Brazil)
        Indices,^STOXX50E,EURO STOXX 50 Index
        Indices,^FTSE,FTSE 100 Index
        Indices,^N225,Nikkei 225 Index
        Indices,^HSI,Hang Seng Index
        Indices,^AXJO,S&P/ASX 200 Index
        Indices,^FTMIB,FTSE MIB Index (Italy)
        Indices,000300.SS,CSI 300 Index (Shanghai)
        Commodities,RBTA,Rotterdam Coal Futures (Generic Code)
        Commodities,CLA,Coal API 2 CIF ARA (Generic Code)
        Commodities,COA,Coal API 4 FOB Richards Bay (Generic Code)
        Commodities,QSA,Iron Ore Fe 62% CFR China (Generic Code)
        Commodities,XBA,Alumina FOB Australia (Generic Code)
        Commodities,HOA,Heating Oil Futures (Generic Code)
        Commodities,NGA,Natural Gas Futures (Generic Code)
        Commodities,TZTA,Carbon Emissions Allowances (Generic Code)
        Commodities,LMAHDS03,LME Aluminium High Grade Cash (Generic Code)
        Commodities,LMCADS03,LME Copper Grade A Cash (Generic Code)
        Commodities,LMNIDS03,LME Nickel Primary Cash (Generic Code)
        Commodities,IOEA,Iron Ore Fines 62% Fe, CFR China TSI (Generic Code)
"""

async def generate_full_alternative_report_llm(
    llm_client: ChatGoogleGenerativeAI,
    current_report_content_md: str,
    previous_report_portfolio_json_str: str, # JSON string of previous portfolio
    llm_news_corpus_str: str,
    investment_principles_str: str,
    preferred_tickers_prompt_list: str # The PREFERRED_TICKERS_CSV_STRING_FOR_PROMPT
) -> Optional[str]:
    """
    Generates the full alternative report markdown using an LLM.
    """
    prompt = f"""
    You are a world-class investment analyst tasked with creating an ALTERNATIVE version called 'Alternative Report' of an existing investment report called 'Standard Report'.
    Your goal is to present a different, yet plausible, investment strategy and portfolio based on the same underlying market information (news corpus) and company principles.
    The alternative report should NOT adhere to any previous portfolio retention strategy (e.g., a 60/40 rule). It's a fresh perspective.

    **Key Instructions for the Alternative Report:**
    1.  **Maintain Structure:** The alternative report MUST have the EXACT SAME SECTIONS and MARKDOWN HEADERS as the "Current Report Content" provided below. But you must change the title to Alternative Report.
    2.  **Executive Summary - News Update:** Rewrite this section word for word. There's almost nothing to change here!
    3.  **Alternative Portfolio:**
        *   Construct a new portfolio of 10-15 tickers.
        *   ALL tickers MUST be selected from the "PREFERRED_TICKERS List" provided.
        *   Allocations MUST sum exactly to 100.0%. Use one decimal place for percentages.
        *   Assign realistic time horizons (e.g., "1-3 months", "6-12 months", "1-2 years") and confidence levels ("High", "Medium", "Low").
    4.  **Update Key Sections:**
        *   **Executive Summary:** Rewrite this to reflect your alternative strategy, market outlook, and the new portfolio. Ensure it includes:
            *   A Markdown table for the new portfolio holdings.
            *   A hidden JSON block for these holdings: `<!-- PORTFOLIO_POSITIONS_JSON: [{{...}},...] -->`
            *   An "Asset Allocation Overview" based on your new portfolio.
    5.  **Static Content:** Sections of the "Current Report Content" that are purely factual (e.g., summaries of general news events from the LLM News Corpus, if present as distinct sections) should largely be preserved or minimally adapted if your alternative outlook doesn't change their direct relevance. Focus changes on analysis, strategy, and portfolio sections.
    6.  **Tone:** Professional, analytical, data-driven, and balanced, even if presenting a contrarian view.
    7.  **Grounding:** Your alternative strategy and rationales MUST be justifiable based on the "LLM News Corpus" and "Investment Principles" provided.

    **PREFERRED_TICKERS List (Use ONLY these for portfolio construction):**
    ```csv
    {PREFERRED_TICKERS_CSV_STRING_FOR_PROMPT}
    ```

    **INPUTS FOR YOUR ANALYSIS:**

    --- LLM NEWS CORPUS (Recent Market Insights) ---
    {llm_news_corpus_str[:10000]} 
    --- END LLM NEWS CORPUS ---

    --- ORASIS INVESTMENT PRINCIPLES ---
    {investment_principles_str[:3000]}
    --- END ORASIS INVESTMENT PRINCIPLES ---

    --- PREVIOUS REPORT'S PORTFOLIO (JSON - for historical context of what was held, not for retention) ---
    {previous_report_portfolio_json_str}
    --- END PREVIOUS REPORT'S PORTFOLIO ---

    --- CURRENT REPORT CONTENT (The report to rewrite with an alternative perspective) ---
    {current_report_content_md}
    --- END CURRENT REPORT CONTENT ---

    Now, generate the complete ALTERNATIVE report markdown:
    """
    print("Generating full alternative report via LLM...")
    print(f"Alternative report generation prompt (first 500 chars): {prompt[:500]}")
    try:
        # Using LangChain's invoke for ChatGoogleGenerativeAI
        response = await llm_client.ainvoke(prompt) # Use ainvoke for async
        alternative_report_md = response.content.strip()
        print("LLM generated alternative report content.")
        print(f"Alternative Report MD (first 500 chars):\n{alternative_report_md[:500]}")

        # Basic validation: Check for key components
        if "## Executive Summary" not in alternative_report_md or \
           "<!-- PORTFOLIO_POSITIONS_JSON:" not in alternative_report_md or \
           "## Detailed Portfolio Holdings & Analysis" not in alternative_report_md:
            print("Generated alternative report might be missing key structural components. Review output.")
        
        return alternative_report_md
    except Exception as e:
        log_error(f"Error generating full alternative report with LLM: {e}")
        return None

async def generate_change_rationale_scratchpad_llm(
    llm_client: ChatGoogleGenerativeAI,
    current_report_content_md: str, # Or just its portfolio
    alternative_report_content_md: str, # Or just its portfolio
    llm_news_corpus_str: str
) -> Optional[List[str]]:
    """
    Generates a scratchpad explaining differences between current and alternative reports.
    """
    # Extract portfolios for easier comparison in prompt (optional, LLM might do it)
    # This uses your existing helper function

    current_parsed: Optional[ProposerDraft] = extract_structured_parts_from_llm_output(current_report_content_md)
    alternative_parsed: Optional[ProposerDraft] = extract_structured_parts_from_llm_output(alternative_report_content_md)

    current_portfolio_for_prompt = current_parsed.portfolio_positions_json_str if current_parsed else "Could not parse current report portfolio."
    alternative_portfolio_for_prompt = alternative_parsed.portfolio_positions_json_str if alternative_parsed else "Could not parse alternative report portfolio."


    prompt = f"""
    You are an analyst comparing two investment reports: a "Current Report" and an "Alternative Report".
    Your task is to create a "Change Rationale Scratchpad". This scratchpad should be a list of bullet points,
    explaining the key differences in strategy, market outlook, and specific portfolio holdings between the two reports,
    and providing the primary reasons for these differences in the "Alternative Report".

    Reference the "LLM News Corpus" if specific news items influenced the alternative choices.

    **Current Report Portfolio (JSON):**
    {current_portfolio_for_prompt}

    **Alternative Report Portfolio (JSON):**
    {alternative_portfolio_for_prompt}

    **Key Sections from Current Report (for strategic context):**
    (Provide snippets of Executive Summary, Market Outlook, Strategy sections from current_report_content_md if helpful.
    For brevity, we'll assume the LLM can infer much from the portfolios and overall report structure.)
    {current_report_content_md[:2000]} 

    **Key Sections from Alternative Report (for strategic context):**
    {alternative_report_content_md[:2000]}

    **LLM News Corpus (Recent Market Insights that might have driven alternative choices):**
    {llm_news_corpus_str[:8000]}

    **Output Format:**
    Provide your output as a JSON array of strings, where each string is a bullet point for the scratchpad.
    Example:
    ```json
    [
        "- Alternative Report adopts a more defensive stance on equities due to heightened geopolitical risk signals in the news corpus, contrasting with the Current Report's neutral stance.",
        "- Switched from a LONG STNG (Current) to a SHORT STNG (Alternative) because recent news suggests tanker oversupply emerging in Q4.",
        "- Increased allocation to GOLD (Alternative) as a hedge against inflation, a risk highlighted more strongly in the Alternative Report's outlook."
    ]
    ```
    """
    print("Generating change rationale scratchpad via LLM...")
    print(f"Change rationale prompt (first 500 chars): {prompt[:500]}")
    try:
        response = await llm_client.ainvoke(prompt) # Use ainvoke for async
        content = response.content.strip()
        if content.strip().startswith("```json"):
            content = content.strip()[7:-3].strip()
        
        scratchpad_list = json.loads(content)
        if not isinstance(scratchpad_list, list) or not all(isinstance(item, str) for item in scratchpad_list):
            print("LLM did not return a valid JSON list of strings for scratchpad. Returning raw content.")
            return [content] # Fallback
            
        print(f"LLM generated change rationale scratchpad with {len(scratchpad_list)} points.")
        return scratchpad_list
    except Exception as e:
        log_error(f"Error generating change rationale scratchpad with LLM: {e}")
        return [f"Error generating scratchpad: {e}"]


async def generate_and_upload_alternative_report(
    current_report_content_md: str,
    current_report_firestore_id: str,
    # Removed openai_client, assuming gemini_model_name implies ChatGoogleGenerativeAI
    gemini_model_name: str = "gemini-1.5-pro-latest", # Or "gemini-1.0-pro", "gemini-1.5-flash" etc.
    google_api_key: Optional[str] = None, # For ChatGoogleGenerativeAI
    investment_principles_str: Optional[str] = None,
    llm_news_corpus_str: Optional[str] = None,
    previous_report_portfolio_json_str: Optional[str] = None, # Pass as JSON string
    preferred_tickers_list_for_prompt: str = PREFERRED_TICKERS_CSV_STRING_FOR_PROMPT # Use the global or pass specifically
):
    if not FIRESTORE_AVAILABLE:
        log_warning("Alternative report: Firestore is not available.")
        return None

    if not google_api_key:
        google_api_key = os.getenv("GOOGLE_API_KEY") # Try to get from env if not passed
    if not google_api_key:
        log_error("Google API Key not provided or found in environment for ChatGoogleGenerativeAI.")
        return None

    try:
        # Initialize ChatGoogleGenerativeAI client
        llm_client = ChatGoogleGenerativeAI(model=gemini_model_name, google_api_key=google_api_key, convert_system_message_to_human=True)
        # `convert_system_message_to_human=True` might be needed if prompts use system messages,
        # but for single user message prompts, it's often not critical.
    except Exception as e:
        log_error(f"Failed to initialize ChatGoogleGenerativeAI: {e}")
        return None
        
    investment_principles_str = investment_principles_str or ""
    llm_news_corpus_str = llm_news_corpus_str or "No specific news corpus provided for alternative generation."
    previous_report_portfolio_json_str = previous_report_portfolio_json_str or "{}" # Empty JSON object string

    print(f"Starting generation of alternative report for source ID: {current_report_firestore_id} using model {gemini_model_name}")

    # 1. Generate the full alternative report markdown
    alternative_report_md = await generate_full_alternative_report_llm(
        llm_client,
        current_report_content_md,
        previous_report_portfolio_json_str,
        llm_news_corpus_str,
        investment_principles_str,
        preferred_tickers_list_for_prompt
    )

    if not alternative_report_md:
        log_error("Failed to generate alternative report content from LLM.")
        return None

    # Import the portfolio generator to use generate_alternative_portfolio_weights
    from portfolio_generator.modules.portfolio_generator import generate_alternative_portfolio_weights
    from portfolio_generator.firestore_uploader import FirestoreUploader
    uploader = FirestoreUploader()
    db = uploader.db
    alt_collection = db.collection('report-alternatives')
    
    # Generate and upload alternative portfolio weights
    try:
        # Load investment principles for portfolio weighting
        try:
            principles_path = os.path.join(os.path.dirname(__file__), "orasis_investment_principles.txt")
            with open(principles_path, "r", encoding="utf-8") as f:
                investment_principles = f.read().strip()
        except Exception as e:
            log_warning(f"Could not load investment principles: {e}")
            investment_principles = ""
        # Generate alternative portfolio weights with investment principles

        log_info(f" Investment principles to be used for alternative portfolio weights : {investment_principles} ")
        # try:
        #     # Try new filter() syntax first
        #     weights_query = alt_collection.filter('doc_type', '==', 'portfolio-weights-alternative').filter('is_latest', '==', True)
        # except AttributeError:
        #     # Fall back to older where() syntax
        #     log_info("Using older Firestore where() method - consider upgrading google-cloud-firestore")
        #     weights_query = (
        #         alt_collection
        #         .where(filter=FieldFilter('doc_type', '==', 'portfolio-weights-alternative'))
        #         .where(filter=FieldFilter('is_latest', '==', True))
        #     )
        # existing_weights = list(weights_query.stream())
        
        # if existing_weights:
        #     for wdoc in existing_weights:
        #         alt_collection.document(wdoc.id).update({'is_latest': False})
                
        reports_ref = db.collection('portfolios')
        
        # Find the most recent report that is not the current one
        # Add compatibility layer for both old and new Firestore API versions
        try:
            # Try new filter() syntax first
            orig_query = reports_ref.filter('doc_type', '==', 'portfolio_weights').filter('is_latest', '==', True)
        except AttributeError:
            # Fall back to older where() syntax
            log_info("Using older Firestore where() method - consider upgrading google-cloud-firestore")
            orig_query = (
                reports_ref
                .where(filter=FieldFilter('doc_type', '==', 'portfolio_weights'))
                .where(filter=FieldFilter('is_latest', '==', True))
            )
            
        orig_docs = list(orig_query.stream())
        
        if orig_docs:
            orig = orig_docs[0]
            raw = orig.to_dict().get('content', {})
            
            if isinstance(raw, dict):
                orig_data = raw
            else:
                try:
                    orig_data = json.loads(raw)
                except Exception:
                    orig_data = {}
                    
            assets = orig_data.get('data', {}).get('assets', [])
            report_date = orig_data.get('data', {}).get('report_date', '')
        else:
            assets, report_date = [], ''
            
        alt_weights_json = await generate_alternative_portfolio_weights(
            openai_client,
            assets,
            alternative_report_md,
            investment_principles=investment_principles
        )

        current_date = datetime.now(timezone.utc)
        # method to calculate benchmark metrics using portfolio_json
        from portfolio_generator.modules.benchmark_metrics import calculate_benchmark_metrics
        calculated_metrics_json = await calculate_benchmark_metrics(
            openai_client,
            alt_weights_json,
            current_date
        )
        log_info(f"Calculated alternative benchmark metrics: {calculated_metrics_json}")

        # upload calculated metrics to firestore under a new collection called "benchmark_metrics-alternative"
        uploader_bm = FirestoreUploader()
        bm_col = uploader_bm.db.collection("benchmark_metrics-alternative")
        # Mark previous benchmark_metrics-alternative docs as not latest
        try:
            bm_q = bm_col.filter("doc_type", "==", "benchmark_metrics-alternative").filter("is_latest", "==", True)
        except AttributeError:
            bm_q = bm_col.where(filter=FieldFilter("doc_type", "==", "benchmark_metrics-alternative")).where(filter=FieldFilter("is_latest", "==", True))
        for doc in bm_q.stream():
            bm_col.document(doc.id).update({"is_latest": False})
        bm_ref = bm_col.document()
        bm_ref.set({
            "metrics_json": calculated_metrics_json,
            "doc_type": "benchmark_metrics-alternative",
            "file_format": "json",
            "timestamp": firestore.SERVER_TIMESTAMP,
            "is_latest": True,
            "source_report_id": current_report_firestore_id,
            "created_at": datetime.now(timezone.utc)
        })
        log_success(f"Alternative benchmark metrics uploaded with id: {bm_ref.id}")
        
        # Upload portfolio-weights-alternative to Firestore

        alt_weights_collection = db.collection('report-alternatives')

        existing_latest_alt_weights = list(alt_weights_collection.where(filter=FieldFilter('is_latest', '==', True)).stream())
        for doc in existing_latest_alt_weights:
            alt_weights_collection.document(doc.id).update({'is_latest': False})

        alt_weights_ref = alt_weights_collection.document()
        weights_payload = {
            'content': alt_weights_json,
            'doc_type': 'portfolio-weights-alternative',
            'file_format': 'json',
            'timestamp': firestore.SERVER_TIMESTAMP,
            'is_latest': True,
            'alternative_weights_id': alt_weights_ref.id,
            'source_report_id': current_report_firestore_id,
            'source_weights_id': orig.id if orig_docs else None,
            'created_at': datetime.now(timezone.utc)
        }
        
        log_info("Uploading alternative portfolio weights")
        alt_weights_ref.set(weights_payload)
        log_success(f"Alternative portfolio weights uploaded with id: {alt_weights_ref.id}")
        
    except Exception as w_err:
        log_error(f"Failed to upload alternative portfolio weights: {w_err}")

    # 3. Generate the Change Rationale Scratchpad
    change_rationale_scratchpad = await generate_change_rationale_scratchpad_llm(
        llm_client,
        current_report_content_md, # Pass full current report for context
        alternative_report_md,     # Pass full alternative report for context
        llm_news_corpus_str
    )
    change_rationale_scratchpad_json = json.dumps(change_rationale_scratchpad or ["Error in scratchpad generation."], indent=2)

    # 4. Upload to Firestore
    try:
        uploader = FirestoreUploader()
        db = uploader.db
        timestamp_now = datetime.now(timezone.utc)
        
        # Upload Alternative Report Content
        alt_reports_coll = db.collection('report-alternatives')
        # existing_latest_alt_reports = list(alt_reports_coll.where(filter=FieldFilter('is_latest', '==', True)).stream())
        # for doc in existing_latest_alt_reports:
        #     alt_reports_coll.document(doc.id).update({'is_latest': False})

        alt_report_doc_ref = alt_reports_coll.document()
        alt_report_payload = {
            'content': alternative_report_md,
            'doc_type': 'report-alternative', 'file_format': 'markdown',
            'timestamp': firestore.SERVER_TIMESTAMP, 'is_latest': True,
            'alternative_report_Id': alt_report_doc_ref.id,
            'source_report_id': current_report_firestore_id,
            'created_at': timestamp_now
        }
        alt_report_doc_ref.set(alt_report_payload)
        log_success(f"Alternative report uploaded to Firestore with doc ID: {alt_report_doc_ref.id}")


        # Upload Change Rationale Scratchpad
        alt_scratchpad_coll = db.collection('report-alternative-scratchpads')

        existing_latest_alt_sp = list(alt_scratchpad_coll.where(filter=FieldFilter('is_latest', '==', True)).stream())
        for doc in existing_latest_alt_sp:
            alt_scratchpad_coll.document(doc.id).update({'is_latest': False})

        alt_scratchpad_doc_ref = alt_scratchpad_coll.document()
        scratchpad_payload = {
            'scratchpad_content': change_rationale_scratchpad_json,
            'doc_type': 'alternative-scratchpad', 'file_format': 'json',
            'timestamp': firestore.SERVER_TIMESTAMP, 'is_latest': True,
            'alternative_scratchpad_id': alt_scratchpad_doc_ref.id,
            'source_report_id': current_report_firestore_id,
            'alternative_report_id': alt_report_doc_ref.id,
            'created_at': timestamp_now
        }
        alt_scratchpad_doc_ref.set(scratchpad_payload)
        log_success(f"Alternative report scratchpad uploaded with doc ID: {alt_scratchpad_doc_ref.id}")

        return alt_report_doc_ref.id, alt_weights_json, alternative_report_md # Return ID and scratchpad content

    except Exception as e:
        log_error(f"Error during Firestore upload for alternative report elements: {e}")
        return None, None