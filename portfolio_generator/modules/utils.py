"""Utility functions for the portfolio generator."""
import re
from datetime import datetime

# Helper functions for post-processing
allowed_horizons = {"1-3M","3-6M","6-12M", "12-18M", "18+"}

def is_date_string(s):
    """Check if a string is a date string.
    Matches formats like (April 2025), (2025-04-18), etc.
    """
    return bool(re.match(r"^\(?[A-Za-z]+\s\d{4}\)?$|^\(?\d{4}-\d{2}-\d{2}\)?$", s))

def is_placeholder_rationale(rationale):
    """Detect if a rationale is a placeholder or template text.
    
    Args:
        rationale: The rationale text to check
        
    Returns:
        bool: True if the rationale is likely a placeholder
    """
    junk_phrases = [
        "with source citations", "explaining how it fits", "see consensus and Orasis view", 
        "rationale not provided", "data-driven rationale", "generic", "filler text"
    ]
    return any(phrase in rationale.lower() for phrase in junk_phrases)

def infer_region_from_asset(asset_name):
    """Infer the region an asset belongs to based on its name.
    
    Args:
        asset_name: The name of the asset
        
    Returns:
        str: The inferred region or "Global" if unknown
    """
    # Basic region inference logic - expand this as needed
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


import json

def news_digest_json_to_markdown() -> str:
    with open("news_human_digests.json", "r", encoding="utf-8") as f:
        digest = json.load(f)
    lines = ["# Executive Summary - News Update\n"]
    for category, news in digest.items():
        # Only print categories that aren't error messages
        if news.strip().lower().startswith("error processing"):
            lines.append(f"## {category}\nError fetching news for this category.\n")
            continue

        lines.append(f"## {category}\n")
        # News field is already a markdown string per news item
        lines.append(news)
        lines.append("")  # Blank line between categories
    return "\n".join(lines)

def clean_markdown_block(text):
    lines = text.strip().splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]  # remove opening ```
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]  # remove closing ```
    return "\n".join(lines).strip()