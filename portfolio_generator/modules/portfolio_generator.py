"""Portfolio JSON generation module."""
import json
import re
import asyncio
from datetime import datetime

from portfolio_generator.modules.logging import log_info, log_warning, log_error
from portfolio_generator.modules.data_extraction import extract_portfolio_data_from_sections, infer_region_from_asset
from portfolio_generator.modules.utils import is_placeholder_rationale

async def generate_portfolio_json(client, assets_list, current_date, report_content, investment_principles="", old_portfolio_weights=None, search_client=None, search_results=None):
    """Generate the structured JSON portfolio data based on report content.
    
    The report content is treated as the source of truth for asset weights and allocations.
    This function extracts asset information directly from the report content when possible,
    using the assets_list as supplementary information.
    
    Args:
        client: OpenAI client
        assets_list: List of assets from previous reports or default portfolio
        current_date: Current date for the report
        report_content: Full report content to extract data from
        investment_principles: Investment principles to apply to asset selection and rationale
        old_portfolio_weights: Previous portfolio weights to incorporate for comparisons
        search_client: Optional search client for additional information
        search_results: Optional search results to include
        
    Returns:
        str: JSON string with portfolio data
    """
    try:
        log_info("Generating portfolio JSON from report content")
        
        # Construct a prompt asking to generate portfolio JSON
        system_prompt = f"""You are an expert financial analyst tasked with extracting and structuring portfolio data from investment reports.
        Your goal is to identify all assets mentioned in the report and organize them into a structured JSON format.

        {investment_principles if investment_principles else ""}

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
                "isNew": true/false  (boolean indicating if this is a new position not in the previous portfolio)
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
                "isNew": true/false  (boolean indicating if this is a new position not in the previous portfolio)
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
                "isNew": true/false  (boolean indicating if this is a new position not in the previous portfolio)
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
        
        user_prompt = f"""Generate a structured JSON object representing the current investment portfolio based on the provided report content.
        
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
        
        Here is a gold standard example of what the output should look like:
        {gold_standard}
        
        Report content:
        {report_content}
        
        Prior portfolio weights:
        {old_portfolio_weights}
        
        Include an "isNew" boolean for each asset: set to true if the asset ticker was not in the prior portfolio weights, otherwise false.
        
        TASK REPEATED: Extract all portfolio assets and statistics from the report content and format them in the specified JSON structure.
        
        IMPORTANT GUIDELINES:
        1. Include ALL assets mentioned in the report
        2. Calculate the sector_exposure, regional_exposure, and investment_type_breakdown based on asset weights
        3. Positions must be either "LONG" or "SHORT" (uppercase)
        4. Weights must sum to approximately 1.0
        5. Only include valid numerical target prices when available
        6. Horizons must be one of: "6-12M", "3-6M", "12-18M", or "18M+"
        7. Regions must be one of: "North America", "Europe", "Asia", "Latin America", "Africa", "Oceania", or "Global" (use "Global" if unknown)
        8. Each asset rationale should clearly connect to the investment principles
        """

        
        # Make the API call
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="o4-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        )
        
        # Extract potential JSON from the response
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
                log_info("Successfully generated portfolio JSON data")
                return json.dumps(portfolio_data, indent=2)
            except json.JSONDecodeError:
                log_error("Generated content contains invalid JSON")
        else:
            # Try to see if the whole response is valid JSON
            try:
                portfolio_data = json.loads(generated_content)
                log_info("Successfully generated portfolio JSON data")
                return json.dumps(portfolio_data, indent=2)
            except json.JSONDecodeError:
                log_error("Could not extract valid JSON from response")
        
        # Fallback: direct extraction after AI methods
        log_info("Falling back to direct extraction for portfolio JSON generation")
        extracted_data = extract_portfolio_data_from_sections({}, current_date, report_content)
        if extracted_data and 'assets' in extracted_data and len(extracted_data['assets']) > 0:
            log_info(f"Successfully extracted {len(extracted_data['assets'])} assets via direct extraction fallback")
            return extracted_data
        
        # If everything else failed, create a basic structure with the assets list
        fallback_data = {
            "data": {
                "report_date": current_date,
                "assets": assets_list[:10] if assets_list else [],
                "portfolio_stats": {
                    "total_assets": len(assets_list[:10]) if assets_list else 0,
                    "avg_position_size": 0.1,
                    "sector_exposure": {},
                    "regional_exposure": {},
                    "investment_type_breakdown": {}
                }
            }
        }
        
        return json.dumps(fallback_data, indent=2)
        
    except Exception as e:
        log_error(f"Error generating JSON data: {e}")
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

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
                "sector": "Technology"
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
                "sector": "Consumer Staples"
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
                "sector": "Financials"
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
        "sector": "Sector name"
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

Emphasis: Provide specific, principle-based rationales explicitly tied to the Orasis investment principles; avoid generic statements like "Investment aligned with market outlook".

TASK REPEATED: Extract all portfolio assets and statistics from the alternative report content and format them in the specified JSON structure.
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
