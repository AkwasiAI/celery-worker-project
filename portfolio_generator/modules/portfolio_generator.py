"""Portfolio JSON generation module."""
import json
import re
import asyncio
from datetime import datetime

from portfolio_generator.modules.logging import log_info, log_warning, log_error
from portfolio_generator.modules.data_extraction import extract_portfolio_data_from_sections, infer_region_from_asset
from portfolio_generator.modules.utils import is_placeholder_rationale


# async def generate_portfolio_json_old(client, assets_list, current_date, report_content, investment_principles="", old_portfolio_weights=None, search_client=None, search_results=None):
#     """Generate the structured JSON portfolio data based on report content.
    
#     The report content is treated as the source of truth for asset weights and allocations.
#     This function extracts asset information directly from the report content when possible,
#     using the assets_list as supplementary information.
    
#     Args:
#         client: OpenAI client
#         assets_list: List of assets from previous reports or default portfolio
#         current_date: Current date for the report
#         report_content: Full report content to extract data from
#         investment_principles: Investment principles to apply to asset selection and rationale
#         old_portfolio_weights: Previous portfolio weights to incorporate for comparisons
#         search_client: Optional search client for additional information
#         search_results: Optional search results to include
        
#     Returns:
#         str: JSON string with portfolio data
#     """
#     try:
#         log_info("Generating portfolio JSON from report content")
        
#         # Construct a prompt asking to generate portfolio JSON
#         system_prompt = f"""You are an expert financial analyst tasked with extracting and structuring portfolio data from investment reports.
#         Your goal is to identify all assets mentioned in the report and organize them into a structured JSON format. You must also identify positions that were removed from the previous portfolio.

#         {investment_principles if investment_principles else ""}

#         Use only the following categories: Shipping Equities/Credit, Commodities, ETFs, Equity Indices, Fixed Income.
#         Use only the following regions: North America, Europe, Asia, Latin America, Africa, Oceania. If the region is unclear, assign "Global".
#         """
        
#         gold_standard = """{
#           "portfolio": {
#             "date": "2025-05-01",
#             "assets": [
#               {
#                 "ticker": "AAPL",
#                 "name": "Apple Inc.",
#                 "position": "LONG",
#                 "weight": 0.08,
#                 "target_price": 225.50,
#                 "horizon": "12-18M",
#                 "rationale": "Apple's services growth and ecosystem lock-in provide resilient cash flows during market volatility, aligning with our principle of prioritizing companies with strong moats and recurring revenue streams.",
#                 "region": "North America",
#                 "sector": "Technology",
#                 "isNew": true/false  (boolean indicating if this is a new position not in the previous portfolio)
#                 "wasRemoved": true/false  (boolean indicating if this position was removed from the previous portfolio)
#               },
#               {
#                 "ticker": "WMT",
#                 "name": "Walmart Inc.",
#                 "position": "LONG",
#                 "weight": 0.05,
#                 "target_price": 82.75,
#                 "horizon": "6-12M",
#                 "rationale": "Walmart's defensive characteristics and e-commerce growth support our counter-cyclical investment approach during inflationary periods, providing portfolio stability while maintaining growth potential.",
#                 "region": "North America",
#                 "sector": "Consumer Staples",
#                 "isNew": true/false  (boolean indicating if this is a new position not in the previous portfolio)
#                 "wasRemoved": true/false  (boolean indicating if this position was removed from the previous portfolio)
#               },
#               {
#                 "ticker": "GS",
#                 "name": "Goldman Sachs Group Inc.",
#                 "position": "SHORT",
#                 "weight": 0.03,
#                 "target_price": 340.00,
#                 "horizon": "3-6M",
#                 "rationale": "Increased regulatory pressure and declining investment banking revenues run counter to our principle of targeting businesses with sustainable competitive advantages in growing markets.",
#                 "region": "North America",
#                 "sector": "Financials",
#                 "isNew": true/false  (boolean indicating if this is a new position not in the previous portfolio)
#                 "wasRemoved": true/false  (boolean indicating if this position was removed from the previous portfolio)
#               }
#             ],
#             "portfolio_stats": {
#               "total_assets": 15,
#               "avg_position_size": 0.067,
#               "sector_exposure": {
#                 "Technology": 0.32,
#                 "Healthcare": 0.18,
#                 "Consumer Staples": 0.15,
#                 "Financials": 0.12,
#                 "Energy": 0.10,
#                 "Industrials": 0.08,
#                 "Materials": 0.05
#               },
#               "regional_exposure": {
#                 "North America": 0.65,
#                 "Europe": 0.20,
#                 "Asia": 0.15
#               },
#               "investment_type_breakdown": {
#                 "LONG": 0.85,
#                 "SHORT": 0.15
#               }
#             }
#           }
#         }"""
        
#         user_prompt = f"""Generate a structured JSON object representing the current investment portfolio based on the provided report content.
#         After extracting the portfolio assets and statistics from the report content, ensure that the "wasRemoved" boolean is set to true for each asset that was in the prior portfolio weights but is not in the current report content. 
#         Use the Prior portfolio weights: to identify which assets were removed. 
        
#         The JSON should follow this format:
#         {{
#           "portfolio": {{
#             "date": "{current_date}",
#             "assets": [
#               {{
#                 "ticker": "TICKER",
#                 "name": "Full asset name",
#                 "position": "LONG or SHORT",
#                 "weight": 0.XX (decimal, not percentage),
#                 "target_price": XX.XX (numerical target price),
#                 "horizon": "6-12M or 3-6M or 12-18M or 18M+",
#                 "rationale": "Specific investment rationale tied to investment principles",
#                 "region": "Region name",
#                 "sector": "Sector name",
#                 "isNew": true/false  (boolean indicating if this is a new position not in the previous portfolio)
#                 "wasRemoved": true/false  (boolean indicating if this position was removed from the previous portfolio)  
#               }}
#             ],
#             "portfolio_stats": {{
#               "total_assets": XX (number of assets),
#               "avg_position_size": 0.XX (average position weight),
#               "sector_exposure": {{ "Sector1": 0.XX, "Sector2": 0.XX }},
#               "regional_exposure": {{ "Region1": 0.XX, "Region2": 0.XX }},
#               "investment_type_breakdown": {{ "LONG": 0.XX, "SHORT": 0.XX }}
#             }}
#           }}
#         }}
        
#         Here is a gold standard example of what the output should look like:
#         {gold_standard}
        
#         Report content:
#         {report_content}
        
#         Prior portfolio weights:
#         {old_portfolio_weights}
        
#         Include an "isNew" boolean for each asset: set to true if the asset ticker was not in the prior portfolio weights, otherwise false.
#         Include an "wasRemoved" boolean for each asset: set to true if the asset ticker was in the prior portfolio weights, otherwise false.
        
#         TASK REPEATED: Extract all portfolio assets and statistics from the report content and format them in the specified JSON structure.
        
#         IMPORTANT GUIDELINES:
#         1. Include ALL assets mentioned in the report
#         2. Calculate the sector_exposure, regional_exposure, and investment_type_breakdown based on asset weights
#         3. Positions must be either "LONG" or "SHORT" (uppercase)
#         4. Weights must sum to approximately 1.0
#         5. Only include valid numerical target prices when available
#         6. Horizons must be one of: "6-12M", "3-6M", "12-18M", or "18M+"
#         7. Regions must be one of: "North America", "Europe", "Asia", "Latin America", "Africa", "Oceania", or "Global" (use "Global" if unknown)
#         8. Each asset rationale should clearly connect to the investment principles
#         9. Ensure removed positions are marked as "wasRemoved": true and are at the end of the assets list
#         """

        
#         # Make the API call
#         response = await asyncio.to_thread(
#             client.chat.completions.create,
#             model="o4-mini",
#             messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
#         )
        
#         # Extract potential JSON from the response
#         generated_content = response.choices[0].message.content
        
#         # Try to find JSON in the response (may be wrapped in code blocks)
#         json_pattern = r'```(?:json)?\s*({[\s\S]*?})\s*```'
#         json_matches = re.findall(json_pattern, generated_content)
        
#         if json_matches:
#             # Use the first JSON block found
#             json_str = json_matches[0]
#             try:
#                 # Validate JSON by parsing it
#                 portfolio_data = json.loads(json_str)
#                 log_info("Successfully generated portfolio JSON data")
#                 return json.dumps(portfolio_data, indent=2)
#             except json.JSONDecodeError:
#                 log_error("Generated content contains invalid JSON")
#         else:
#             # Try to see if the whole response is valid JSON
#             try:
#                 portfolio_data = json.loads(generated_content)
#                 log_info("Successfully generated portfolio JSON data")
#                 return json.dumps(portfolio_data, indent=2)
#             except json.JSONDecodeError:
#                 log_error("Could not extract valid JSON from response")
#                 log_info(f"Original LLM content: {generated_content}")
#                 log_info("Attempting LLM fallback for better rationale responses")
#                 fallback_response = await asyncio.to_thread(
#                     client.chat.completions.create,
#                     model="o4-mini",
#                     messages=[
#                         {"role": "system", "content": system_prompt},
#                         {"role": "user", "content": f"The previous response did not parse as JSON:\n{generated_content}\nPlease regenerate a valid JSON portfolio following the original specification, with clear, principle-based rationales."}
#                     ]
#                 )
#                 fallback_content = fallback_response.choices[0].message.content
#                 log_info(f"LLM fallback response: {fallback_content}")
#                 try:
#                     fallback_data_json = json.loads(fallback_content)
#                     log_info("Successfully generated portfolio JSON data on fallback")
#                     return json.dumps(fallback_data_json, indent=2)
#                 except json.JSONDecodeError:
#                     log_error("Fallback LLM response contains invalid JSON")
        
#         # Fallback: direct extraction after AI methods
#         log_info("Falling back to direct extraction for portfolio JSON generation")
#         extracted_data = extract_portfolio_data_from_sections({}, current_date, report_content)
#         if extracted_data and 'assets' in extracted_data and len(extracted_data['assets']) > 0:
#             log_info(f"Successfully extracted {len(extracted_data['assets'])} assets via direct extraction fallback")
#             return extracted_data
        
#         # If everything else failed, create a basic structure with the assets list
#         fallback_data = {
#             "data": {
#                 "report_date": current_date,
#                 "assets": assets_list[:10] if assets_list else [],
#                 "portfolio_stats": {
#                     "total_assets": len(assets_list[:10]) if assets_list else 0,
#                     "avg_position_size": 0.1,
#                     "sector_exposure": {},
#                     "regional_exposure": {},
#                     "investment_type_breakdown": {}
#                 }
#             }
#         }
        
#         return json.dumps(fallback_data, indent=2)
        
#     except Exception as e:
#         log_error(f"Error generating JSON data: {e}")
#         return json.dumps({"status": "error", "message": str(e)}, indent=2)

async def generate_alternative_portfolio_weights(client, old_assets_list, alt_report_content, search_client=None, investment_principles=""):
    """Generate alternative portfolio weights JSON based on old weights and a markdown report.
    
    The alternative report content is treated as the source of truth for asset weights and allocations.
    This function will extract asset information directly from the report content when possible,
    falling back to a generative approach when extraction fails.
    
    Args:
        client: OpenAI client
        old_assets_list: List of assets from the original portfolio
        alt_report_content: Alternative report content to extract data from
        search_client: Optional search client for additional information
        investment_principles: Investment principles to apply to asset selection and rationale
        
    Returns:
        str: JSON string with alternative portfolio data
    """
    try:
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Prepare prompt components
        old_assets_json = json.dumps(old_assets_list, indent=2)
        system_prompt = f"""You are an expert financial analyst tasked with extracting and structuring portfolio data from investment reports.
Your goal is to identify all assets mentioned in the alternative report and organize them into a structured JSON format.
You are also to mark assets that are removed from the portfolio as "wasRemoved": true at the end of the assets list.

Here are the Orasis investment principles to guide your rationales:
{investment_principles if investment_principles else ""}

When explaining asset rationales, reference these principles explicitly and avoid vague statements like "Investment aligned with market outlook".
Use only the following categories: Shipping Equities/Credit, Commodities, ETFs, Equity Indices, Fixed Income.
Use only the following regions: North America, Europe, Asia, Latin America, Africa, Oceania. If the region is unclear, assign "Global".
"""
        gold_standard = """{
          "portfolio": {
            "date": "2025-05-01",
            "assets": [
              {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "position": "LONG",
                "weight": 0.08,
                "target_price": 225.50,
                "horizon": "12-18M",
                "rationale": "Apple's services growth and ecosystem lock-in provide resilient cash flows during market volatility, aligning with our principle of prioritizing companies with strong moats and recurring revenue streams.",
                "region": "North America",
                "sector": "Technology",
                "isNew": true,
                "wasRemoved": false
              },
              {
                "ticker": "WMT",
                "name": "Walmart Inc.",
                "position": "LONG",
                "weight": 0.05,
                "target_price": 82.75,
                "horizon": "6-12M",
                "rationale": "Walmart's defensive characteristics and e-commerce growth support our counter-cyclical investment approach during inflationary periods, providing portfolio stability while maintaining growth potential.",
                "region": "North America",
                "sector": "Consumer Staples",
                "isNew": false,
                "wasRemoved": false
              },
              {
                "ticker": "GS",
                "name": "Goldman Sachs Group Inc.",
                "position": "SHORT",
                "weight": 0.03,
                "target_price": 340.00,
                "horizon": "3-6M",
                "rationale": "Increased regulatory pressure and declining investment banking revenues run counter to our principle of targeting businesses with sustainable competitive advantages in growing markets.",
                "region": "North America",
                "sector": "Financials",
                "isNew": false,
                "wasRemoved": true
              },
              {
                "ticker": "TSLA",
                "name": "Tesla, Inc.",
                "position": "LONG",
                "weight": 0.08,
                "target_price": 225.50,
                "horizon": "12-18M",
                "rationale": "Apple's services growth and ecosystem lock-in provide resilient cash flows during market volatility, aligning with our principle of prioritizing companies with strong moats and recurring revenue streams.",
                "region": "North America",
                "sector": "Technology",
                "isNew": false,
                "wasRemoved": true
              },
              {
                "ticker": "JPM",
                "name": "JPMorgan Chase & Co.",
                "position": "LONG",
                "weight": 0.05,
                "target_price": 225.50,
                "horizon": "12-18M",
                "rationale": "JPMorgan's strong balance sheet and solid earnings provide a stable foundation for our counter-cyclical investment approach, aligning with our principle of targeting businesses with sustainable competitive advantages in growing markets.",
                "region": "North America",
                "sector": "ETFs",
                "isNew": false,
                "wasRemoved": true
              }
            ],
            "portfolio_stats": {
              "total_assets": 15,
              "avg_position_size": 0.067,
              "sector_exposure": {
                "Technology": 0.32,
                "Healthcare": 0.18,
                "Consumer Staples": 0.15,
                "Financials": 0.12,
                "Energy": 0.10,
                "Industrials": 0.08,
                "Materials": 0.05
              },
              "regional_exposure": {
                "North America": 0.65,
                "Europe": 0.20,
                "Asia": 0.15
              },
              "investment_type_breakdown": {
                "LONG": 0.85,
                "SHORT": 0.15
              }
            }
          }
        }"""
        
        user_prompt = f"""Generate a structured JSON object representing the alternative investment portfolio based on the provided alternative report content.

The JSON should follow this format:
{{
  "portfolio": {{
    "date": "{current_date}",
    "assets": [
      {{
        "ticker": "TICKER",
        "name": "Full asset name",
        "position": "LONG or SHORT",
        "weight": 0.XX (decimal, not percentage),
        "target_price": XX.XX (numerical target price),
        "horizon": "6-12M or 3-6M or 12-18M or 18M+",
        "rationale": "Specific investment rationale tied to investment principles",
        "region": "Region name",
        "sector": "Sector name",
        "isNew": true/false  (boolean indicating if this is a new position not in the previous portfolio)
        "wasRemoved": true/false  (boolean indicating if this position was removed from the previous portfolio)
      }}
    ],
    "portfolio_stats": {{
      "total_assets": XX (number of assets),
      "avg_position_size": 0.XX (average position weight),
      "sector_exposure": {{ "Sector1": 0.XX, "Sector2": 0.XX }},
      "regional_exposure": {{ "Region1": 0.XX, "Region2": 0.XX }},
      "investment_type_breakdown": {{ "LONG": 0.XX, "SHORT": 0.XX }}
    }}
  }}
}}

Here is a gold standard example:
{gold_standard}

Original portfolio asset list:
{old_assets_json}

Full alternative report content:
{alt_report_content}

Include an "isNew" boolean for each asset: set to true if the asset ticker was not in the prior portfolio weights, otherwise false.
Include an "wasRemoved" boolean for each asset: set to true if the asset ticker was in the prior portfolio weights, otherwise false.

Emphasis: Provide specific, principle-based rationales explicitly tied to the Orasis investment principles; avoid generic statements like "Investment aligned with market outlook".

TASK REPEATED: Extract all portfolio assets and statistics from the alternative report content and format them in the specified JSON structure.
Ensure that the "wasRemoved" boolean is set to true for assets that are not in the new portfolio but were in the original portfolio list.

IMPORTANT: Ensure 'investment_type_breakdown' values sum to 1.0 (LONG + SHORT = 1.0).
"""
        # Call LLM with system and user messages
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="o4-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        )
        generated_content = response.choices[0].message.content
        
        # Try to find JSON in the response (may be wrapped in code blocks)
        json_pattern = r'```(?:json)?\s*({[\s\S]*?})\s*```'
        json_matches = re.findall(json_pattern, generated_content)
        
        if json_matches:
            # Use the first JSON block found
            json_str = json_matches[0]
            try:
                # Validate JSON by parsing it
                portfolio_data = json.loads(json_str)
                log_info("Successfully generated alternative portfolio JSON")
                return json.dumps(portfolio_data, indent=2)
            except json.JSONDecodeError:
                log_error("Generated content contains invalid JSON")
        else:
            # Try to see if the whole response is valid JSON
            try:
                portfolio_data = json.loads(generated_content)
                log_info("Successfully generated alternative portfolio JSON")
                return json.dumps(portfolio_data, indent=2)
            except json.JSONDecodeError:
                log_error("Could not extract valid JSON from response")
        
        # Direct extraction fallback
        log_info("Falling back to direct extraction for alternative report")
        extracted_data = extract_portfolio_data_from_sections({}, current_date, alt_report_content)
        if extracted_data.get("data", {}).get("assets"):
            log_info(f"Successfully extracted {len(extracted_data['data']['assets'])} assets via extraction fallback")
            return json.dumps(extracted_data, indent=2)
        
        # If everything else failed, create a minimally modified version of the original
        fallback_data = {
            "data": {
                "report_date": current_date,
                "assets": old_assets_list if old_assets_list else [],
                "portfolio_stats": {
                    "total_assets": len(old_assets_list) if old_assets_list else 0,
                    "avg_position_size": 0.1,
                    "sector_exposure": {},
                    "regional_exposure": {},
                    "investment_type_breakdown": {}
                }
            }
        }
        
        return json.dumps(fallback_data, indent=2)
        
    except Exception as e:
        log_error(f"Error generating alternative JSON data: {e}")
        return json.dumps({"status": "error", "message": str(e)}, indent=2)



import json
import re
from collections import defaultdict
from langchain_google_genai import ChatGoogleGenerativeAI

def log_info(msg): print(msg)
def log_error(msg): print(msg)

async def generate_portfolio_json(
    client, # Ignored, for compatibility
    assets_list,
    current_date,
    report_content,
    investment_principles="",
    old_portfolio_weights = None,
    search_client=None,
    search_results=None    ):
    """
    Generate a structured portfolio JSON following the gold standard format using LangChain Gemini.
    """

    try:
        log_info("Generating portfolio JSON using Gemini (LangChain) from report content")

        # ---- Parse old portfolio for tickers ----
        old_tickers = set()
        old_assets = []
        if old_portfolio_weights and isinstance(old_portfolio_weights, dict):
            old_assets = old_portfolio_weights.get("portfolio", {}).get("assets", [])
            old_tickers = set(a.get("ticker", "").upper() for a in old_assets if "ticker" in a)
        num_old = len(old_tickers)

        # ---- PROMPT ----
        gold_standard = """{
  "portfolio": {
    "date": "2025-05-01",
    "assets": [
      {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "position": "LONG",
        "weight": 0.08,
        "target_price": 225.50,
        "horizon": "12-18M",
        "rationale": "Apple's services growth and ecosystem lock-in provide resilient cash flows during market volatility, aligning with our principle of prioritizing companies with strong moats and recurring revenue streams.",
        "region": "North America",
        "sector": "Technology",
        "isNew": true,
        "wasRemoved": false
      }
    ],
    "portfolio_stats": {
      "total_assets": 15,
      "avg_position_size": 0.067,
      "sector_exposure": {
        "Technology": 0.32,
        "Healthcare": 0.18,
        "Consumer Staples": 0.15
      },
      "regional_exposure": {
        "North America": 0.65,
        "Europe": 0.20,
        "Asia": 0.15
      },
      "investment_type_breakdown": {
        "LONG": 0.85,
        "SHORT": 0.15
      },
      "percent_removed": 0.0
    }
  }
}"""

        system_prompt = (
            "You are an expert financial analyst tasked with extracting and structuring portfolio data from investment reports.\n"
            f"{investment_principles if investment_principles else ''}\n"
            "Always output a structured JSON with the following fields for each asset:\n"
            "- ticker\n"
            "- name\n"
            "- position (LONG or SHORT) - It is already provided in the report\n"
            "- weight (decimal, sum of weights should be ~1.0) - It is already provided in the report\n"
            "- target_price (numerical, or null if not specified)\n"
            "- horizon (one of:\"1-3M\", \"3-6M\", \"6-12M\", \"12-18M\", \"18M+\") - It is already provided in the report\n"
            "- rationale (clear, principle-based)\n"
            "- region (one of: North America, Europe, Asia, Latin America, Africa, Oceania, Global)\n"
            "- sector\n"
            "- isNew (true if not in prior portfolio)\n"
            "- wasRemoved (true if removed from prior portfolio)\n"
            "Also, generate portfolio_stats with:\n"
            "- total_assets\n"
            "- avg_position_size\n"
            "- sector_exposure\n"
            "- regional_exposure\n"
            "- investment_type_breakdown\n"
            "- percent_removed (percentage of tickers removed from prior portfolio)\n"
            "Follow the JSON format shown in the gold standard below.\n"
        )

        user_prompt = f"""Generate a structured JSON object representing the current investment portfolio.
The JSON must follow this format:

{gold_standard}

Instructions:
- Extract all assets and their properties from the report content.
- For each asset:
    - Set "isNew": true if the ticker is not in the prior portfolio, otherwise false.
    - Set "wasRemoved": false for current assets.
- For any ticker that appears in the prior portfolio but NOT in the current report content, append it to the end of the assets list with:
    - "wasRemoved": true,
    - "isNew": false,
    - "weight": 0.0,
    - "rationale": "Removed from current portfolio." (or similar)
- Recalculate all portfolio_stats based on the *current* assets (excluding removed positions for position size).
- Set "percent_removed" to the percentage of tickers in the prior portfolio that have been removed.
- Only use allowed values for regions and horizons.

Report content:
{report_content}

Prior portfolio weights:
{json.dumps(old_portfolio_weights) if old_portfolio_weights else "None"}

Today's date: {current_date}
"""

        # ---- LangChain Gemini Model ----
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-preview-05-20")
        response = await llm.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        generated_content = response.content if hasattr(response, "content") else str(response)

        # ---- Extract JSON ----
        json_pattern = r'```(?:json)?\s*({[\s\S]*?})\s*```'
        json_matches = re.findall(json_pattern, generated_content)
        json_str = json_matches[0] if json_matches else generated_content

        try:
            data = json.loads(json_str)
        except Exception:
            log_error("Could not parse JSON from Gemini response.")
            return json.dumps({"status": "error", "message": "Invalid Gemini JSON"}, indent=2)

        # ---- Postprocess assets for isNew/wasRemoved ----
        assets = data.get('portfolio', {}).get('assets', [])
        current_tickers = set(a.get('ticker', '').upper() for a in assets)
        for asset in assets:
            ticker = asset.get('ticker', '').upper()
            asset['isNew'] = ticker not in old_tickers
            asset['wasRemoved'] = False

        # ---- Add removed assets ----
        removed = []
        for a in old_assets:
            ticker = a.get('ticker', '').upper()
            if ticker not in current_tickers:
                removed_asset = a.copy()
                removed_asset['weight'] = 0.0
                removed_asset['isNew'] = False
                removed_asset['wasRemoved'] = True
                removed_asset['rationale'] = "Removed from current portfolio."
                removed.append(removed_asset)
        if removed:
            assets.extend(removed)

        # ---- Recalculate Portfolio Stats ----
        stats = {
            'total_assets': len([a for a in assets if not a.get('wasRemoved')]),
            'avg_position_size': 0.0,
            'sector_exposure': defaultdict(float),
            'regional_exposure': defaultdict(float),
            'investment_type_breakdown': defaultdict(float),
            'percent_removed': 0.0  # NEW!
        }
        total_weight = 0.0
        for a in assets:
            if not a.get('wasRemoved'):
                w = a.get('weight', 0) or 0.0
                total_weight += w
                stats['sector_exposure'][a.get('sector', 'Other')] += w
                stats['regional_exposure'][a.get('region', 'Global')] += w
                stats['investment_type_breakdown'][a.get('position', 'LONG').upper()] += w
        n = stats['total_assets']
        stats['avg_position_size'] = round(total_weight / n, 4) if n else 0.0
        for k in ['sector_exposure', 'regional_exposure', 'investment_type_breakdown']:
            stats[k] = {key: round(val, 4) for key, val in stats[k].items() if val > 0}
        num_removed = len(removed)
        stats['percent_removed'] = round((num_removed / num_old) * 100, 2) if num_old else 0.0

        data['portfolio']['portfolio_stats'] = stats
        data['portfolio']['assets'] = assets

        log_info("Successfully generated portfolio JSON data (LangChain Gemini + strict gold standard + percent_removed)")
        return json.dumps(data, indent=2)

    except Exception as e:
        log_error(f"Error generating JSON data: {e}")
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
