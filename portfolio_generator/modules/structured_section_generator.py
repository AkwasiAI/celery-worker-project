"""Structured section generator with Pydantic validation for portfolio reports."""
import os
import json
import asyncio
from typing import Dict, List, Optional, Union, Literal
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
    
    # Build a comprehensive prompt that includes instructions for the structured output
    structured_prompt = f"""
{user_prompt}

RESPONSE FORMAT:
Your response must be provided in two parts:

PART 1: EXECUTIVE SUMMARY
Provide a well-structured markdown executive summary of approximately {target_word_count} words.

PART 2: PORTFOLIO POSITIONS
After the executive summary, provide a structured list of recommended portfolio positions in this exact JSON format:

```json
[
  {{
    "asset": "TICKER1",
    "position_type": "LONG", 
    "allocation_percent": 15,
    "time_horizon": "6-12 months",
    "confidence_level": "High"
  }},
  {{
    "asset": "TICKER2",
    "position_type": "SHORT",
    "allocation_percent": 5,
    "time_horizon": "3-6 months",
    "confidence_level": "Medium"
  }},
  ...more positions...
]
```

IMPORTANT: 
- Include at least 10-15 positions to create a diversified portfolio
- Ensure the allocation_percent values sum to approximately 100%
- Use only LONG or SHORT for position_type
- Use High, Medium, or Low for confidence_level
- Provide realistic time horizons (e.g., "1-3 months", "6-12 months", "1-2 years")
- Each position must include all 5 required fields
"""
    
    # Add search results if available
    if search_results and search_results.strip():
        structured_prompt += f"\n\nHere is the latest information from web searches that should inform your analysis:\n\n{search_results}"
    
    # Add previous sections for context if available
    if previous_sections and isinstance(previous_sections, dict):
        sections_context = "\n\n## Previous sections of the report include:\n\n"
        for sec_name, sec_content in previous_sections.items():
            sections_context += f"### {sec_name}\n{sec_content}\n\n"
        structured_prompt += sections_context
    
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
        
        # Update the prompt to include clear instructions about the expected JSON structure
        structured_prompt += """
        
IMPORTANT: Your response MUST be a valid JSON object with exactly these two fields:
1. "summary": A string containing the markdown-formatted executive summary
2. "portfolio_positions": An array of objects, each with these exact fields:
   - "asset": Ticker symbol (string)
   - "position_type": Either "LONG" or "SHORT" (string)
   - "allocation_percent": Percentage between 0-100 (number)
   - "time_horizon": Investment timeframe (string)
   - "confidence_level": Either "High", "Medium", or "Low" (string)

Example of the expected response format:
{
  "summary": "# Executive Summary\n\nThe market outlook...",
  "portfolio_positions": [
    {"asset": "STNG", "position_type": "LONG", "allocation_percent": 15, "time_horizon": "6-12 months", "confidence_level": "High"},
    {"asset": "SHEL", "position_type": "SHORT", "allocation_percent": 5, "time_horizon": "3-6 months", "confidence_level": "Medium"}
  ]
}
        """
        
        log_info(f"Calling {model} with structured JSON response format and formatted search results...")
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": structured_prompt}
                ]
            )
            
            # Log successful API call with model details and token usage
            log_info(f"Successfully received response from {model} (tokens: {response.usage.completion_tokens}/{response.usage.total_tokens})")
            
            # Extract JSON content directly from the response
            content = response.choices[0].message.content
            log_info(f"Received structured JSON response: {content[:100]}...")
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
    IMPORTANT: This function enforces strict structured JSON format with 'summary' and 'portfolio_positions' fields.
    
    Args:
        content: The full model response, expected to be JSON formatted
        
    Returns:
        tuple: (summary_text, positions_json)
        
    Raises:
        ValueError: If the response is not in the proper structured JSON format
    """
    log_info("Parsing structured response...")
    
    # First check if we have a code block with proper JSON format
    json_block_start = content.find("```json")
    if json_block_start != -1:
        json_block_end = content.find("```", json_block_start + 7)  # Find the closing triple backticks
        if json_block_end != -1:
            # Extract the content between the backticks
            json_text = content[json_block_start + 7:json_block_end].strip()
            log_info(f"Extracted JSON code block. First 50 chars: {json_text[:50]}...")
            try:
                # Try to parse the JSON block
                # First, try to clean up any invalid escape sequences
                cleaned_json = _clean_json_text(json_text)
                log_info("Cleaned JSON for parsing")
                
                parsed_data = json.loads(cleaned_json)
                if isinstance(parsed_data, dict) and "summary" in parsed_data and "portfolio_positions" in parsed_data:
                    # We got a properly structured response
                    summary_text = parsed_data["summary"]
                    positions_json = json.dumps(parsed_data["portfolio_positions"])
                    log_info(f"Successfully parsed JSON from code block with {len(parsed_data['portfolio_positions'])} positions")
                    return summary_text, positions_json
                else:
                    error_message = "JSON in code block missing required fields (summary, portfolio_positions)"
                    log_error(error_message)
                    raise ValueError(error_message)
            except json.JSONDecodeError as e:
                error_message = f"Failed to parse JSON from code block: {str(e)}"
                log_error(error_message)
                raise ValueError(error_message)
    
    # If we couldn't extract from a code block, try direct JSON parsing
    try:
        # Try to parse the entire content as JSON, first cleaning it
        cleaned_content = _clean_json_text(content)
        parsed_data = json.loads(cleaned_content)
        if isinstance(parsed_data, dict) and "summary" in parsed_data and "portfolio_positions" in parsed_data:
            # We got a properly structured response
            summary_text = parsed_data["summary"]
            positions_json = json.dumps(parsed_data["portfolio_positions"])
            log_info(f"Successfully parsed direct JSON response with {len(parsed_data['portfolio_positions'])} positions")
            return summary_text, positions_json
        else:
            error_message = "Direct JSON missing required fields (summary, portfolio_positions)"
            log_error(error_message)
            raise ValueError(error_message)
    except json.JSONDecodeError as e:
        error_message = f"Failed to parse as structured JSON - incorrect format received from model: {str(e)}"
        log_error(error_message)
        raise ValueError(error_message)
    
    # We should never reach here as the above code will either return or raise an exception
    # But just in case, we'll add a fallback error
    error_message = "Unknown error parsing structured JSON response"
    log_error(error_message)
    raise ValueError(error_message)

def _clean_json_text(json_text: str) -> str:
    """
    Clean up common JSON issues that might cause parsing errors.
    
    Args:
        json_text: The JSON text to clean
        
    Returns:
        Cleaned JSON text ready for parsing
    """
    # Replace invalid escape sequences
    # Common issue: backslashes in text that aren't properly escaped
    # First, handle escaped backslashes (we'll temporarily replace them)
    cleaned = json_text.replace("\\\\", "__ESCAPED_BACKSLASH__")
    
    # Remove lone backslashes not followed by valid escape chars (like ", \, /, b, f, n, r, t, u)
    cleaned = re.sub(r'\\([^"\\/bfnrtu])', r'\1', cleaned)
    
    # Restore properly escaped backslashes
    cleaned = cleaned.replace("__ESCAPED_BACKSLASH__", "\\\\")
    
    # Fix common issues with quotes in JSON
    # Handle cases where there might be unescaped quotes inside strings
    # This is more complex and might require a more sophisticated approach
    # But we can handle some common cases
    
    # Remove control characters
    cleaned = re.sub(r'[\x00-\x1F\x7F]', '', cleaned)
    
    return cleaned

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
