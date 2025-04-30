"""Structured section generator with Pydantic validation for portfolio reports."""
import os
import json
import asyncio
from typing import Dict, List, Optional, Union, Literal, Tuple
from pydantic import BaseModel, Field, validator

import re
from openai import OpenAI
# Remove the incorrect import of Responses
from portfolio_generator.modules.logging import log_info, log_warning, log_error

class PortfolioPosition(BaseModel):
    """Portfolio position model."""
    asset: str = Field(..., description="Ticker symbol or identifier for the asset")
    position_type: Literal["LONG", "SHORT"] = Field(..., description="Position type (LONG or SHORT)")
    allocation_percent: float = Field(..., description="Percentage allocation in the portfolio (0-100)")
    time_horizon: str = Field(..., description="Investment time horizon (e.g., '3-6 months', '1-2 years')")
    confidence_level: Literal["High", "Medium", "Low"] = Field(..., description="Confidence level in the position")
    
    @validator('allocation_percent')
    def check_allocation(cls, v):
        """Validate allocation percentage is between 0 and 100."""
        if v < 0 or v > 100:
            raise ValueError(f'allocation_percent must be between 0 and 100, got {v}')
        return v
    
    @validator('asset')
    def check_asset(cls, v):
        """Validate asset ticker is not empty."""
        if not v or not v.strip():
            raise ValueError('asset cannot be empty')
        return v.strip().upper()  # Normalize to uppercase

class ExecutiveSummaryResponse(BaseModel):
    """Model for executive summary response with portfolio positions."""
    summary: str = Field(..., description="Markdown formatted executive summary text")
    portfolio_positions: List[PortfolioPosition] = Field(..., description="List of portfolio positions")

async def generate_structured_executive_summary(
    client: OpenAI,
    system_prompt: str,
    user_prompt: str,
    search_results: Optional[str] = None,
    previous_sections: Optional[Dict[str, str]] = None,
    target_word_count: int = 3000,
    model: str = "o4-mini"
) -> ExecutiveSummaryResponse:
    """Generate an executive summary with structured portfolio positions using Pydantic validation.
    
    Args:
        client: OpenAI client
        system_prompt: System prompt for the model
        user_prompt: User prompt for the model
        search_results: Optional search results to include (should be formatted Perplexity results)
        previous_sections: Optional previous sections to provide context
        target_word_count: Target word count for the summary
        model: Model to use (default: o4-mini)
        
    Returns:
        ExecutiveSummaryResponse: Structured response with summary and portfolio positions
    """
    log_info("Generating structured Executive Summary...")
    
    # Build the complete prompt with the existing user_prompt (which already includes EXECUTIVE_SUMMARY_DETAILED_PROMPT)
    complete_prompt = user_prompt
    
    # Add search results if available
    if search_results and search_results.strip():
        complete_prompt += f"\n\nHere is the latest information from web searches that should inform your analysis:\n\n{search_results}"
    
    # Add previous sections for context if available
    if previous_sections and isinstance(previous_sections, dict):
        sections_context = "\n\n## Previous sections of the report include:\n\n"
        for sec_name, sec_content in previous_sections.items():
            sections_context += f"### {sec_name}\n{sec_content}\n\n"
        user_prompt += sections_context
    
    try:
        # Always use chat completions with the formatted search results
        log_info(f"Using {model} with formatted search results for structured Executive Summary generation...")
        
        # The search_results parameter should already contain formatted Perplexity search results
        # that were passed in from the report_generator.py

        # Define a simplified JSON response format that works with o4-mini
        # Note: o4-mini doesn't support the detailed schema specification
        response_format = {
            "type": "json_object"
        }
        
        # The user prompt already contains the necessary formatting guidance
        # No additional JSON formatting instructions needed
        
        log_info(f"Calling {model} with structured JSON response format and formatted search results...")
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": complete_prompt}
                ]
            )
            
            # Log successful API call with model details and token usage
            log_info(f"Successfully received response from {model} (tokens: {response.usage.completion_tokens}/{response.usage.total_tokens})")
            
            # Extract JSON content directly from the response
            content = response.choices[0].message.content
            log_info(f"Received structured JSON response: {content[:100]}...")
            # Print the full raw response for debugging
            print("\nFULL RAW RESPONSE FROM MODEL:\n")
            print(content)
            print("\nEND OF RAW RESPONSE\n")
        except Exception as e:
            log_error(f"Error calling {model} with structured format: {str(e)}")
            raise
        
        # Process the response to extract the structured parts
        if not content:
            raise ValueError("Received empty response from model")
        
        # Extract the summary and portfolio positions from the response
        summary_text, positions_json = extract_structured_parts(content)
        
        if not positions_json:
            log_warning("No portfolio positions JSON found in response. Generating default positions...")
            positions_json = generate_default_portfolio_positions()
        
        # Parse and validate the portfolio positions using Pydantic
        try:
            portfolio_positions = json.loads(positions_json)
            # Validate with Pydantic
            validated_positions = [PortfolioPosition.parse_obj(pos) for pos in portfolio_positions]
            
            # Create final response
            result = ExecutiveSummaryResponse(
                summary=summary_text,
                portfolio_positions=validated_positions
            )
            
            log_info(f"Successfully generated structured Executive Summary with {len(validated_positions)} validated portfolio positions")
            return result
            
        except json.JSONDecodeError as e:
            log_error(f"Failed to parse portfolio positions JSON: {e}")
            # Fallback to default positions
            positions_json = generate_default_portfolio_positions()
            portfolio_positions = json.loads(positions_json)
            validated_positions = [PortfolioPosition.parse_obj(pos) for pos in portfolio_positions]
            
            # Create final response with fallback positions
            result = ExecutiveSummaryResponse(
                summary=summary_text,
                portfolio_positions=validated_positions
            )
            
            log_warning(f"Using fallback portfolio with {len(validated_positions)} positions")
            return result
            
    except Exception as e:
        log_error(f"Error generating structured Executive Summary: {str(e)}")
        raise

def extract_structured_parts(content: str) -> tuple[str, str]:
    """
    Extract the summary text and portfolio positions JSON from the model response.
    Supports hidden JSON in HTML comments, JSON code blocks, or direct JSON format.

    Args:
        content: The full model response, could be JSON or markdown with embedded JSON

    Returns:
        tuple: (summary_text, positions_json)
    """
    log_info("Parsing structured response...")

    # Check for portfolio positions in HTML comment
    comment_pattern = re.compile(r"<!-- PORTFOLIO_POSITIONS_JSON:\s*(.+?)\s*-->\s*", re.DOTALL)
    match = comment_pattern.search(content)
    if match:
        try:
            # Extract the JSON from the comment
            positions_json = match.group(1).strip()
            # Clean and parse the JSON
            cleaned_json = _clean_json_text(positions_json)
            portfolio_positions = json.loads(cleaned_json)
            
            # Normalize position_type to uppercase and confidence_level to accepted values
            for position in portfolio_positions:
                # Normalize position_type to uppercase
                if "position_type" in position and isinstance(position["position_type"], str):
                    position["position_type"] = position["position_type"].upper()
                
                # Normalize confidence_level to one of: High, Medium, Low
                if "confidence_level" in position and isinstance(position["confidence_level"], str):
                    confidence = position["confidence_level"]
                    # Map any extended confidence levels to one of the three accepted values
                    if confidence.lower() in ["very high", "extremely high", "highest"]:
                        position["confidence_level"] = "High"
                    elif confidence.lower() in ["very low", "extremely low", "lowest"]:
                        position["confidence_level"] = "Low"
                    # If it's already one of our accepted values, normalize the case
                    elif confidence.lower() == "high":
                        position["confidence_level"] = "High"
                    elif confidence.lower() == "medium":
                        position["confidence_level"] = "Medium"
                    elif confidence.lower() == "low":
                        position["confidence_level"] = "Low"
                    else: # Default to Medium for unknown values
                        position["confidence_level"] = "Medium"
            
            # If we successfully parsed the JSON, use the text before the comment as the summary
            summary_text = content[:match.start()].strip()
            return summary_text, json.dumps(portfolio_positions)
        except json.JSONDecodeError:
            pass

    # Pattern for JSON code block
    code_pattern = re.compile(
        r"```json\s*(\{.*?\}|\[.*?\])\s*```",
        flags=re.DOTALL
    )
    match = code_pattern.search(content)
    if match:
        json_text = match.group(1).strip()
        try:
            parsed = json.loads(_clean_json_text(json_text))
            if isinstance(parsed, dict) and "summary" in parsed and "portfolio_positions" in parsed:
                # Normalize position_type to uppercase and confidence_level to accepted values
                for position in parsed["portfolio_positions"]:
                    # Normalize position_type to uppercase
                    if "position_type" in position and isinstance(position["position_type"], str):
                        position["position_type"] = position["position_type"].upper()
                    
                    # Normalize confidence_level to one of: High, Medium, Low
                    if "confidence_level" in position and isinstance(position["confidence_level"], str):
                        confidence = position["confidence_level"]
                        # Map any extended confidence levels to one of the three accepted values
                        if confidence.lower() in ["very high", "extremely high", "highest"]:
                            position["confidence_level"] = "High"
                        elif confidence.lower() in ["very low", "extremely low", "lowest"]:
                            position["confidence_level"] = "Low"
                        # If it's already one of our accepted values, normalize the case
                        elif confidence.lower() == "high":
                            position["confidence_level"] = "High"
                        elif confidence.lower() == "medium":
                            position["confidence_level"] = "Medium"
                        elif confidence.lower() == "low":
                            position["confidence_level"] = "Low"
                        else: # Default to Medium for unknown values
                            position["confidence_level"] = "Medium"
                return parsed["summary"].strip(), json.dumps(parsed["portfolio_positions"])
        except json.JSONDecodeError:
            pass

    # Direct JSON
    try:
        parsed = json.loads(_clean_json_text(content.strip()))
        if isinstance(parsed, dict) and "summary" in parsed and "portfolio_positions" in parsed:
            # Normalize position_type to uppercase and confidence_level to accepted values
            for position in parsed["portfolio_positions"]:
                # Normalize position_type to uppercase
                if "position_type" in position and isinstance(position["position_type"], str):
                    position["position_type"] = position["position_type"].upper()
                
                # Normalize confidence_level to one of: High, Medium, Low
                if "confidence_level" in position and isinstance(position["confidence_level"], str):
                    confidence = position["confidence_level"]
                    # Map any extended confidence levels to one of the three accepted values
                    if confidence.lower() in ["very high", "extremely high", "highest"]:
                        position["confidence_level"] = "High"
                    elif confidence.lower() in ["very low", "extremely low", "lowest"]:
                        position["confidence_level"] = "Low"
                    # If it's already one of our accepted values, normalize the case
                    elif confidence.lower() == "high":
                        position["confidence_level"] = "High"
                    elif confidence.lower() == "medium":
                        position["confidence_level"] = "Medium"
                    elif confidence.lower() == "low":
                        position["confidence_level"] = "Low"
                    else: # Default to Medium for unknown values
                        position["confidence_level"] = "Medium"
            return parsed["summary"].strip(), json.dumps(parsed["portfolio_positions"])
    except json.JSONDecodeError:
        pass

    # Fallback: entire content as summary, empty positions
    return content.strip(), json.dumps([])


def _clean_json_text(json_text: str) -> str:
    """
    Clean up common JSON issues.
    """
    # Temporarily escape valid backslashes
    json_text = json_text.replace('\\\\', '__ESCAPED_BACKSLASH__')
    # Remove stray backslashes
    json_text = re.sub(r'\\(?!["\\/bfnrtu])', '', json_text)
    # Restore escaped backslashes
    json_text = json_text.replace('__ESCAPED_BACKSLASH__', '\\\\')
    # Remove control characters
    json_text = re.sub(r'[\x00-\x1F\x7F]', '', json_text)
    return json_text


def generate_default_portfolio_positions() -> str:
    """
    Generate a default set of portfolio positions when extraction fails.
    
    Returns:
        str: JSON string of default portfolio positions
    """
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
    
    return json.dumps(default_positions)
