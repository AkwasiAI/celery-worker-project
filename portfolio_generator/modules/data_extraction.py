"""Data extraction utilities for portfolio reports."""
import re
import json
from datetime import datetime, timedelta
from portfolio_generator.modules.logging import log_info, log_warning, log_error
from portfolio_generator.modules.utils import is_date_string, is_placeholder_rationale, allowed_horizons

def extract_portfolio_data_from_sections(sections, current_date, report_content=None):
    """Extract portfolio data from report sections.
    
    Args:
        sections: Dictionary of report sections
        current_date: Current date for the report
        report_content: Full report content to use as source of truth (if provided)
        
    Returns:
        dict: Extracted portfolio data
    """
    log_info("Extracting portfolio data from generated report sections...")
    
    # If report_content is provided, use that as the primary source
    source_text = report_content if report_content else sections.get("Executive Summary", "")
    
    # Initialize the portfolio data structure
    portfolio_data = {
        "data": {
            "report_date": current_date,
            "assets": [],
            "portfolio_stats": {
                "total_assets": 0,
                "avg_position_size": 0,
                "sector_exposure": {},
                "regional_exposure": {},
                "investment_type_breakdown": {}
            },
            "performance": {
                "current_value": 0,
                "historical_values": []
            }
        }
    }
    
    try:
        # Try to extract the portfolio summary table from the executive summary
        # Look for markdown tables in the format: | Asset | Position | Weight | ... |
        portfolio_table_pattern = r"(\|[^\n]*\|\n\|[-: |]+\|\n(?:\|[^\n]*\|\n)+)"
        portfolio_tables = re.findall(portfolio_table_pattern, source_text)
        
        if portfolio_tables:
            # Use the first table found
            table = portfolio_tables[0]
            log_info(f"Found portfolio table in report: {len(table.split('|'))} cells")
            
            # Extract the header row to determine column positions
            rows = table.strip().split('\n')
            header = rows[0].strip()
            
            # Determine column positions
            header_cells = [cell.strip() for cell in header.split('|')]
            header_cells = [cell for cell in header_cells if cell]  # Remove empty cells
            
            # Default column positions (in case header detection fails)
            asset_col, position_col, weight_col = 1, 2, 3
            target_col, horizon_col, rationale_col = 4, 5, 6
            
            # Try to find column positions from headers
            for i, cell in enumerate(header_cells):
                cell_lower = cell.lower()
                if any(kw in cell_lower for kw in ['asset', 'ticker', 'security']):
                    asset_col = i
                elif any(kw in cell_lower for kw in ['position', 'direction']):
                    position_col = i
                elif any(kw in cell_lower for kw in ['weight', 'allocation']):
                    weight_col = i
                elif any(kw in cell_lower for kw in ['target', 'price']):
                    target_col = i
                elif any(kw in cell_lower for kw in ['horizon', 'timeframe']):
                    horizon_col = i
                elif any(kw in cell_lower for kw in ['rationale', 'thesis']):
                    rationale_col = i
            
            # Process data rows
            asset_list = []
            for row_idx in range(2, len(rows)):  # Skip header and separator rows
                row = rows[row_idx].strip()
                if not row or row.count('|') < 3:  # Sanity check
                    continue
                    
                cells = [cell.strip() for cell in row.split('|')]
                cells = [cell for cell in cells if cell != '']  # Remove empty cells
                
                if len(cells) < max(asset_col, position_col, weight_col) + 1:
                    continue  # Skip rows with insufficient columns
                
                # Extract basic asset data
                asset_name = cells[asset_col] if asset_col < len(cells) else "Unknown Asset"
                position_type = cells[position_col] if position_col < len(cells) else "LONG"
                
                # Clean up position type
                position_type = position_type.upper()
                if position_type not in ["LONG", "SHORT"]:
                    position_type = "LONG" if any(kw in position_type.lower() for kw in ["long", "buy"]) else "SHORT"
                
                # Extract weight as number (remove % and convert to decimal)
                weight_text = cells[weight_col] if weight_col < len(cells) else "0%"
                weight = 0.0
                try:
                    # Remove % sign and convert to decimal
                    weight = float(weight_text.strip('%')) / 100
                except ValueError:
                    # Try more aggressive parsing (e.g., "~5%" or "approx. 5%")
                    weight_match = re.search(r'(\d+\.?\d*)', weight_text)
                    if weight_match:
                        weight = float(weight_match.group(1)) / 100
                
                # Extract price target if available
                target_price = None
                if target_col < len(cells):
                    target_text = cells[target_col]
                    if target_text and target_text.lower() not in ["n/a", "-"]:
                        # Try to extract numerical value
                        target_match = re.search(r'(\$?\d+\.?\d*)', target_text)
                        if target_match:
                            try:
                                target_price = float(target_match.group(1).replace('$', ''))
                            except ValueError:
                                pass
                
                # Extract horizon if available
                horizon = None
                if horizon_col < len(cells):
                    horizon_text = cells[horizon_col]
                    # Clean up and normalize horizon
                    if horizon_text and horizon_text.lower() not in ["n/a", "-"]:
                        # Try to match to allowed horizons
                        for allowed in allowed_horizons:
                            if allowed.lower() in horizon_text.lower() or horizon_text.lower() in allowed.lower():
                                horizon = allowed
                                break
                
                # Extract rationale if available
                rationale = None
                if rationale_col < len(cells):
                    rationale = cells[rationale_col]
                    if rationale and is_placeholder_rationale(rationale):
                        rationale = None  # Ignore placeholder rationales
                
                # Create the asset entry
                asset_entry = {
                    "name": asset_name,
                    "position": position_type,
                    "weight": weight,
                    "target_price": target_price,
                    "horizon": horizon if horizon else "6-12M",  # Default horizon
                    "rationale": rationale if rationale else "Investment aligned with market outlook",
                    "region": infer_region_from_asset(asset_name),
                    "sector": "Miscellaneous"  # Default sector
                }
                
                asset_list.append(asset_entry)
            
            # Update the portfolio data with extracted assets
            portfolio_data["data"]["assets"] = asset_list
            portfolio_data["data"]["portfolio_stats"]["total_assets"] = len(asset_list)
            
            # Calculate average position size if we have assets
            if asset_list:
                total_weight = sum(asset["weight"] for asset in asset_list)
                portfolio_data["data"]["portfolio_stats"]["avg_position_size"] = total_weight / len(asset_list)
                
            log_info(f"Successfully extracted {len(asset_list)} assets from portfolio table")
            
        else:
            # If no table found, try to parse from the JSON block if it exists
            json_pattern = r'```json\s*({[\s\S]*?})\s*```'
            json_matches = re.findall(json_pattern, source_text)
            
            if json_matches:
                try:
                    extracted_json = json.loads(json_matches[0])
                    if "data" in extracted_json and "assets" in extracted_json["data"]:
                        portfolio_data = extracted_json
                        log_info(f"Successfully extracted portfolio data from JSON block with {len(portfolio_data['data']['assets'])} assets")
                except json.JSONDecodeError:
                    log_warning("Found JSON block but could not parse it properly")
            else:
                log_warning("No portfolio positions table or JSON found in report content")
    
    except Exception as e:
        log_error(f"Error extracting portfolio data: {e}")
    
    return portfolio_data

def infer_region_from_asset(asset_name):
    """Infer the region an asset belongs to based on its name.
    
    Args:
        asset_name: The name of the asset
        
    Returns:
        str: The inferred region or "Global" if unknown
    """
    # Check for regional indicators in asset name
    if any(keyword in asset_name.lower() for keyword in ["us", "america", "nyse", "nasdaq"]):
        return "North America"
    elif any(keyword in asset_name.lower() for keyword in ["eu", "euro", "german", "france", "uk", "britain"]):
        return "Europe"
    elif any(keyword in asset_name.lower() for keyword in ["china", "japan", "asia", "hong kong", "singapore"]):
        return "Asia"
    elif any(keyword in asset_name.lower() for keyword in ["brazil", "latam", "mexico"]):
        return "Latin America"
    elif any(keyword in asset_name.lower() for keyword in ["africa", "south africa", "nigeria"]):
        return "Africa"
    else:
        return "Global"
