"""Main report generation functionality."""
from datetime import datetime, timezone
from portfolio_generator.prompts_config import (EXECUTIVE_SUMMARY_DETAILED_PROMPT,
    SHIPPING_INDUSTRY_PROMPT, CONCLUSION_OUTLOOK_PROMPT, REFERENCES_SOURCES_PROMPT, 
    RISK_ASSESSMENT_PROMPT, GLOBAL_TRADE_ECONOMY_PROMPT, PORTFOLIO_HOLDINGS_PROMPT,
    ENERGY_MARKETS_PROMPT, COMMODITIES_MARKETS_PROMPT, BENCHMARKING_PERFORMANCE_PROMPT,
    BASE_SYSTEM_PROMPT, PERFORMANCE_ANALYSIS_PROMPT, ALLOCATION_CHANGES_PROMPT, INSIGHTS_CHANGES_PROMPT,
    SANITISATION_SYSTEM_PROMPT, SANITISATION_USER_PROMPT)
from portfolio_generator.modules.logging import log_info, log_warning, log_error, log_success
from portfolio_generator.modules.section_generator import generate_section, generate_section_with_web_search
from google.cloud import firestore
from portfolio_generator.firestore_downloader import FirestoreDownloader
from portfolio_generator.firestore_uploader import FirestoreUploader
from google.cloud.firestore_v1.base_query import FieldFilter
import os

report_sections = {}

# Initialize variables that might be referenced before assignment
firestore_report_doc_id = None

# Set target word count: 10,000 on Friday, else 3,000
today = datetime.now().strftime('%A')
total_word_count = 10000 if today == 'Friday' else 3000
# Number of main report sections
main_sections = 9  # executive_summary, global_economy, energy_markets, commodities, shipping, portfolio_items, benchmarking, risk_assessment, conclusion
per_section_word_count = total_word_count // main_sections

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Start generating the report
log_info("Starting report generation...")

# Define the current timestamp (date and time)
current_date = datetime.now().strftime("%Y-%m-%d")

# Define base system prompt using the imported prompt
current_year = datetime.now().year
next_year = current_year + 1
# Use the passed in priority_period parameter
priority_period="month"

base_system_prompt = BASE_SYSTEM_PROMPT.format(
    total_word_count=total_word_count,
    current_year=current_year,
    next_year=next_year,
    priority_period=priority_period,
    current_date = current_date

)


async def create_alt_sections(client, formatted_search_results, alt_report, investment_principles, current_alt_weights,old_alt_portfolio_weights):

    # Initialize storage for generated sections
    report_sections = {"Full Report": alt_report}
    total_sections = 12  # Total number of sections in the report
    completed_sections = 0

    # 1. Generate Global Trade & Economy section
    global_economy_prompt = GLOBAL_TRADE_ECONOMY_PROMPT.format(per_section_word_count=per_section_word_count)

    report_sections["Global Trade & Economy"] = await generate_section_with_web_search(
        client,
        "Global Trade & Economy",
        base_system_prompt,
        global_economy_prompt,
        formatted_search_results,
        {"Full Report": alt_report},
        per_section_word_count,
        investment_principles=investment_principles
    )

    completed_sections += 1
    log_info(f"Completed Alternative Section {completed_sections}/{total_sections}: Global Trade & Economy")

    # 2. Generate Energy Markets section
    energy_markets_prompt = ENERGY_MARKETS_PROMPT.format(per_section_word_count=per_section_word_count)

    report_sections["Energy Markets"] = await generate_section_with_web_search(
        client,
        "Energy Markets",
        base_system_prompt,
        energy_markets_prompt,
        formatted_search_results,
        {"Full Report": alt_report, "Global Trade & Economy": report_sections["Global Trade & Economy"]},
        per_section_word_count,
        investment_principles=investment_principles
    )

    completed_sections += 1
    log_info(f"Completed Alternative Section {completed_sections}/{total_sections}: Energy Markets")

    # 4. Generate Commodities section
    commodities_prompt = COMMODITIES_MARKETS_PROMPT.format(per_section_word_count=per_section_word_count)

    report_sections["Commodities Markets"] = await generate_section_with_web_search(
        client,
        "Commodities Markets",
        base_system_prompt,
        commodities_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Full Report", "Global Trade & Economy", "Energy Markets"]},
        per_section_word_count,
        investment_principles=investment_principles
    )

    completed_sections += 1
    log_info(f"Completed Alternative Section {completed_sections}/{total_sections}: Commodities Markets")

    # 5. Generate Shipping section
    shipping_prompt = SHIPPING_INDUSTRY_PROMPT.format(per_section_word_count=per_section_word_count)

    report_sections["Shipping Industry"] = await generate_section_with_web_search(
        client,
        "Shipping Industry",
        base_system_prompt,
        shipping_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Full Report", "Global Trade & Economy", "Energy Markets", "Commodities Markets"]},
        per_section_word_count,
        investment_principles=investment_principles
    )

    completed_sections += 1
    log_info(f"Completed Alternative Section {completed_sections}/{total_sections}: Shipping Industry")

    # 6. Generate Portfolio Holdings section
    portfolio_prompt = PORTFOLIO_HOLDINGS_PROMPT.format(per_section_word_count=per_section_word_count)

    # Use named parameters for the Portfolio Holdings section to avoid parameter order confusion
    report_sections["Portfolio Holdings"] = await generate_section_with_web_search(
        client=client,
        section_name="Portfolio Holdings",
        system_prompt=base_system_prompt,
        user_prompt=portfolio_prompt,
        search_results=formatted_search_results,
        previous_sections={k: report_sections[k] for k in ["Full Report", "Global Trade & Economy", "Energy Markets", "Commodities Markets", "Shipping Industry"]},
        target_word_count=per_section_word_count,
        investment_principles=investment_principles
    )

    completed_sections += 1
    log_info(f"Completed Alternative Section {completed_sections}/{total_sections}: Portfolio Holdings")

    # 7. Generate Benchmarking & Performance section
    benchmarking_prompt = BENCHMARKING_PERFORMANCE_PROMPT.format(per_section_word_count=per_section_word_count)

    report_sections["Benchmarking & Performance"] = await generate_section_with_web_search(
        client,
        "Benchmarking & Performance",
        base_system_prompt,
        benchmarking_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Full Report", "Portfolio Holdings"]},
        per_section_word_count,
        investment_principles=investment_principles
    )

    completed_sections += 1
    log_info(f"Completed Alternative Section {completed_sections}/{total_sections}: Benchmarking & Performance")

    # 8. Generate Risk Assessment section
    risk_prompt = RISK_ASSESSMENT_PROMPT.format(per_section_word_count=per_section_word_count)

    report_sections["Risk Assessment"] = await generate_section_with_web_search(
        client,
        "Risk Assessment",
        base_system_prompt,
        risk_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Full Report", "Global Trade & Economy", "Portfolio Holdings"]},
        per_section_word_count,
        investment_principles=investment_principles
    )

    completed_sections += 1
    log_info(f"Completed Alternative Section {completed_sections}/{total_sections}: Risk Assessment")

    # 9. Generate Conclusion & Outlook section
    conclusion_prompt = CONCLUSION_OUTLOOK_PROMPT.format(per_section_word_count=per_section_word_count)

    report_sections["Conclusion & Outlook"] = await generate_section_with_web_search(
        client,
        "Conclusion & Outlook",
        base_system_prompt,
        conclusion_prompt,
        formatted_search_results,
        {k: report_sections[k] for k in ["Full Report", "Global Trade & Economy", "Energy Markets", "Portfolio Holdings", "Risk Assessment"]},
        per_section_word_count,
        investment_principles=investment_principles
    )

    completed_sections += 1
    log_info(f"Completed Alternative Section {completed_sections}/{total_sections}: Conclusion & Outlook")

    # # 10. Generate References & Sources section
    # references_prompt = REFERENCES_SOURCES_PROMPT

    # report_sections["References & Sources"] = await generate_section_with_web_search(
    #     client,
    #     "References & Sources",
    #     base_system_prompt,
    #     references_prompt,
    #     formatted_search_results,
    #     {k: report_sections[k] for k in ["Full Report", "Global Trade & Economy", "Energy Markets", "Portfolio Holdings", "Risk Assessment", "Conclusion & Outlook"]},
    #     per_section_word_count,
    #     investment_principles=investment_principles
    # )

    # completed_sections += 1
    # log_info(f"Completed Alternative Section {completed_sections}/{total_sections}: References & Sources")

    # 11. Generate Allocation section
    # Load previous allocation weights from Firestore
    # prev_allocation_weights = FirestoreDownloader().get_latest("portfolio-weights-alternative")
    # allocation_prompt = ALLOCATION_CHANGES_PROMPT.format(
    #     old_portfolio_weights=prev_allocation_weights,
    #     current_portfolio_weights=portfolio_json
    # )
    # report_sections["Executive Summary - Allocation"] = await generate_section_with_web_search(
    #     client,
    #     "Executive Summary - Allocation",
    #     base_system_prompt,
    #     allocation_prompt,
    #     formatted_search_results,
    #     {k: report_sections[k] for k in ["Full Report", "Global Trade & Economy", "Energy Markets", "Portfolio Holdings", "Risk Assessment", "Conclusion & Outlook"]},
    #     target_word_count=50,
    #     investment_principles=investment_principles
    # )
    # completed_sections += 1
    # log_info(f"Completed Alternative Section {completed_sections}/{total_sections}: Allocation")

    # # 12. Generate Insights section
    # insights_prompt = INSIGHTS_CHANGES_PROMPT.format(
    #     old_portfolio_weights=prev_allocation_weights,
    #     current_portfolio_weights=portfolio_json
    # )
    # report_sections["Executive Summary - Insights"] = await generate_section_with_web_search(
    #     client,
    #     "Executive Summary - Insights",
    #     base_system_prompt,
    #     insights_prompt,
    #     formatted_search_results,
    #     {k: report_sections[k] for k in ["Full Report", "Global Trade & Economy", "Energy Markets", "Portfolio Holdings", "Risk Assessment", "Conclusion & Outlook", "Executive Summary - Allocation"]},
    #     target_word_count=50,
    #     investment_principles=investment_principles
    # )
    # completed_sections += 1
    # log_info(f"Completed Alternative Section {completed_sections}/{total_sections}: Executive Summary - Insights")

    # # Combine all sections into a single report
    # report_content = f"""# Standard Report
    # **Date and time last ran: {current_date}, @ {datetime.now().strftime('%H:%M:%S')} (Athens Time).**

    # """

    # log_info("Report generation complete!")

    # # Calculate total word count
    # total_words = len(report_content.split())
    # log_info(f"Total report word count: {total_words}")

    # Extract portfolio data from the report
    # log_info("Extracting portfolio data from generated report sections...")

    try:

        # 11. Generate Performance analysis section 

        # # Fetch from firestore most recent portfolio weights.
        # firestore_downloader = FirestoreDownloader()
        # old_portfolio_weights = firestore_downloader.get_latest("portfolio_weights")
        
        performance_prompt = PERFORMANCE_ANALYSIS_PROMPT.format(per_section_word_count=per_section_word_count, old_portfolio_weights=old_alt_portfolio_weights, current_portfolio_weights=current_alt_weights)

        report_sections["Performance Analysis"] = await generate_section_with_web_search(
            client,
            "Performance Analysis",
            base_system_prompt,
            performance_prompt,
            formatted_search_results,
            {k: report_sections[k] for k in ["Full Report", "Global Trade & Economy", "Energy Markets", "Commodities Markets", "Shipping Industry", "Portfolio Holdings", "Risk Assessment", "Conclusion & Outlook"]},
            per_section_word_count,
            investment_principles=investment_principles
        )

        risk_sections = ["Portfolio Holdings", "Performance Analysis", "Benchmarking & Performance", "Risk Assessment"]
        risk_content = ""
        for sec in risk_sections:
            if sec in report_sections:
                risk_content += report_sections[sec] + "\n\n"
        if risk_content:
            uploader_rb = FirestoreUploader()
            rb_col = uploader_rb.db.collection("risk_and_benchmark_alternative")
            # Mark existing as not latest
            try:
                rb_q = rb_col.filter("doc_type", "==", "risk_and_benchmark_alternative").filter("is_latest", "==", True)
            except AttributeError:
                rb_q = rb_col.where(filter=FieldFilter("doc_type", "==", "risk_and_benchmark_alternative")).where(filter=FieldFilter("is_latest", "==", True))
            for doc in rb_q.stream():
                rb_col.document(doc.id).update({"is_latest": False})
            rb_ref = rb_col.document()
            rb_ref.set({
                "content": risk_content,
                "doc_type": "risk_and_benchmark_alternative",
                "file_format": "markdown",
                "timestamp": firestore.SERVER_TIMESTAMP,
                "is_latest": True,
                "source_report_id": firestore_report_doc_id,
                "created_at": datetime.now(timezone.utc)
            })
            log_success(f"Risk & Benchmark Alternative report uploaded with id: {rb_ref.id}")
    except Exception as e_rb:
        log_warning(f"Failed to upload Risk & Benchmark Alternative report: {e_rb}")

    return (risk_content)