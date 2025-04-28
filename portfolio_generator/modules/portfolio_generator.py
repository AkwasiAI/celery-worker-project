"""Portfolio JSON generation module."""
import json
import re
import asyncio
from datetime import datetime

from portfolio_generator.modules.logging import log_info, log_warning, log_error
from portfolio_generator.modules.data_extraction import extract_portfolio_data_from_sections, infer_region_from_asset
from portfolio_generator.modules.utils import is_placeholder_rationale

async def generate_portfolio_json(client, assets_list, current_date, report_content, search_client=None, search_results=None):
    """Generate the structured JSON portfolio data based on report content.
    
    The report content is treated as the source of truth for asset weights and allocations.
    This function extracts asset information directly from the report content when possible,
    using the assets_list as supplementary information.
    
    Args:
        client: OpenAI client
        assets_list: List of assets from previous reports or default portfolio
        current_date: Current date for the report
        report_content: Full report content to extract data from
        search_client: Optional search client for additional information
        search_results: Optional search results to include
        
    Returns:
        str: JSON string with portfolio data
    """
    try:
        log_info("Generating portfolio JSON data from report content...")
        
        # First attempt direct extraction from report content
        extracted_data = extract_portfolio_data_from_sections({}, current_date, report_content)
        
        # If extraction found assets, use that data
        if extracted_data.get("data", {}).get("assets") and len(extracted_data["data"]["assets"]) > 0:
            log_info(f"Successfully extracted {len(extracted_data['data']['assets'])} assets directly from report")
            portfolio_json = json.dumps(extracted_data, indent=2)
            return portfolio_json
        
        # If direct extraction failed, fall back to generative approach
        log_warning("Direct extraction failed, using generative approach to create portfolio JSON")
        
        # Create a prompt for generating the portfolio JSON
        prompt = f"""
        Based on the investment portfolio report below, extract the portfolio positions and create a detailed JSON structure.
        
        The JSON should follow this exact structure:
        {{
          "data": {{
            "report_date": "{current_date}",
            "assets": [
              {{
                "name": "Asset Name",
                "position": "LONG or SHORT",
                "weight": 0.XX (decimal, not percentage),
                "target_price": XX.XX (numerical target price),
                "horizon": "6-12M or 3-6M or 12-18M or 12M+",
                "rationale": "Specific investment rationale",
                "region": "Region name",
                "sector": "Sector name"
              }}
            ],
            "portfolio_stats": {{
              "total_assets": XX (number of assets),
              "avg_position_size": 0.XX (average position weight),
              "sector_exposure": {{
                "Sector1": 0.XX,
                "Sector2": 0.XX
              }},
              "regional_exposure": {{
                "Region1": 0.XX,
                "Region2": 0.XX
              }},
              "investment_type_breakdown": {{
                "LONG": 0.XX,
                "SHORT": 0.XX
              }}
            }}
          }}
        }}
        
        Important guidelines:
        1. Include ALL assets mentioned in the report
        2. Calculate the sector_exposure, regional_exposure, and investment_type_breakdown based on asset weights
        3. Positions must be either "LONG" or "SHORT" (uppercase)
        4. Weights must sum to approximately 1.0
        5. Only include valid numerical target prices when available
        6. Horizons must be one of: "6-12M", "3-6M", "12-18M", or "12+"
        
        Report content:
        {report_content[:10000]}  # Limit to first 10000 chars for token limits
        """
        
        # Make the API call
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
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

async def generate_alternative_portfolio_weights(client, old_assets_list, alt_report_content, search_client=None):
    """Generate alternative portfolio weights JSON based on old weights and a markdown report.
    
    The alternative report content is treated as the source of truth for asset weights and allocations.
    This function will extract asset information directly from the report content when possible,
    falling back to a generative approach when extraction fails.
    
    Args:
        client: OpenAI client
        old_assets_list: List of assets from the original portfolio
        alt_report_content: Alternative report content to extract data from
        search_client: Optional search client for additional information
        
    Returns:
        str: JSON string with alternative portfolio data
    """
    try:
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # First attempt direct extraction
        extracted_data = extract_portfolio_data_from_sections({}, current_date, alt_report_content)
        
        # If extraction found assets, use that data
        if extracted_data.get("data", {}).get("assets") and len(extracted_data["data"]["assets"]) > 0:
            log_info(f"Successfully extracted {len(extracted_data['data']['assets'])} assets from alternative report")
            portfolio_json = json.dumps(extracted_data, indent=2)
            return portfolio_json
        
        # If direct extraction failed, fall back to generative approach
        log_warning("Direct extraction failed for alternative report, using generative approach")
        
        # Create a prompt for the alternative portfolio
        # Include the old assets list for context
        old_assets_json = json.dumps(old_assets_list, indent=2)
        
        prompt = f"""
        Based on the alternative investment portfolio report below, create a new portfolio weights JSON.
        
        Here is the original portfolio asset list for context:
        {old_assets_json}
        
        The new JSON should follow this exact structure:
        {{
          "data": {{
            "report_date": "{current_date}",
            "assets": [
              {{
                "name": "Asset Name",
                "position": "LONG or SHORT",
                "weight": 0.XX (decimal, not percentage),
                "target_price": XX.XX (numerical target price),
                "horizon": "6-12M or 3-6M or 12-18M or 12+",
                "rationale": "Specific investment rationale",
                "region": "Region name",
                "sector": "Sector name"
              }}
            ],
            "portfolio_stats": {{
              "total_assets": XX (number of assets),
              "avg_position_size": 0.XX (average position weight),
              "sector_exposure": {{
                "Sector1": 0.XX,
                "Sector2": 0.XX
              }},
              "regional_exposure": {{
                "Region1": 0.XX,
                "Region2": 0.XX
              }},
              "investment_type_breakdown": {{
                "LONG": 0.XX,
                "SHORT": 0.XX
              }}
            }}
          }}
        }}
        
        Alternative report content:
        {alt_report_content[:10000]}  # Limit for token constraints
        """
        
        # Make the API call
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
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
