"""Main entry point for the portfolio generator."""
import asyncio
from celery_config import celery_app
from portfolio_generator.modules.report_generator import generate_investment_portfolio
from portfolio_generator.modules.logging import log_info

@celery_app.task(name="generate_investment_portfolio_task")
def run_portfolio_task():
    """Run the portfolio generation task as a Celery task."""
    log_info("🧠 Starting async investment portfolio generation as a Celery task...")
    return asyncio.run(generate_investment_portfolio())
