#!/usr/bin/env python3
"""
Portfolio Generator - Main Entry Point
This module serves as the backward-compatible entry point for the portfolio generator functionality.
"""
import os
import sys
import json
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
import re
from google.cloud import firestore

# Direct imports without module dependencies
from celery_config import celery_app

# Import from the new modular structure
from portfolio_generator.modules.logging import log_error, log_warning, log_success, log_info
from portfolio_generator.modules.utils import is_date_string, is_placeholder_rationale, infer_region_from_asset, allowed_horizons
from portfolio_generator.modules.search_utils import format_search_results
from portfolio_generator.modules.section_generator import generate_section
from portfolio_generator.modules.news_update_generator import generate_news_update_section
from portfolio_generator.modules.data_extraction import extract_portfolio_data_from_sections
from portfolio_generator.modules.portfolio_generator import generate_portfolio_json, generate_alternative_portfolio_weights
from portfolio_generator.modules.report_upload import upload_report_to_firestore, generate_and_upload_alternative_report
from portfolio_generator.modules.report_generator import generate_investment_portfolio

# Web search imports
from portfolio_generator.modules.web_search import PerplexitySearch

# --- Firestore Availability ---
FIRESTORE_AVAILABLE = False
try:
    from portfolio_generator.report_improver import FIRESTORE_AVAILABLE as IMPROVER_FIRESTORE_AVAILABLE
    FIRESTORE_AVAILABLE = IMPROVER_FIRESTORE_AVAILABLE
except ImportError:
    pass

# Defensive FirestoreUploader import for direct use in this module
try:
    from portfolio_generator.firestore_uploader import FirestoreUploader
except ImportError:
    FirestoreUploader = None
    print("[ERROR] FirestoreUploader could not be imported in comprehensive_portfolio_generator.py. Firestore uploads will not work.")

# Re-export all the functions for backward compatibility
__all__ = [
    'is_date_string',
    'is_placeholder_rationale',
    'infer_region_from_asset',
    'log_error',
    'log_warning',
    'log_success',
    'log_info',
    'format_search_results',
    'generate_section',
    'extract_portfolio_data_from_sections',
    'generate_alternative_portfolio_weights',
    'generate_portfolio_json',
    'generate_investment_portfolio',
    'generate_and_upload_alternative_report',
    'run_portfolio_task'
]

@celery_app.task(name="generate_investment_portfolio_task")
def run_portfolio_task():
    """Run the portfolio generation task as a Celery task."""
    print("🧠 Starting async investment portfolio generation as a Celery task...")
    return asyncio.run(generate_investment_portfolio())

# Execute main function if run directly
if __name__ == "__main__":
    asyncio.run(generate_investment_portfolio())
