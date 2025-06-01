#!/usr/bin/env python
import os
import logging
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set Google credentials environment variable
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/gcp_creds/hedgefundintelligence-1efd159a68ef.json"

def main():
    logger.info("Starting PDF generation and upload test...")
    
    # Import the PDF service
    from portfolio_generator.modules.pdf_report.report_pdf_service import ReportPDFService
    
    # Create test sections
    test_sections = {
        "Test Tables": """## Test Tables with Problematic Content

Here's a standard markdown table:

| Asset | Weight | Change | Rating |
|-------|--------|--------|--------|
| AAPL  | 8%     | +2%    | Buy    |
| MSFT  | 7%     | +1%    | Hold   |
| AMZN  | 6%     | -1%    | Sell   |

And here's a plain text table format:

STNG    15%    +18.5%    Outperform
SHEL    10%    +12.3%    Neutral
BP      8%     -2.1%     Underperform
""",
        "Special Characters": """## Special Characters Test
        
Testing various special characters:
• Bullet points
• More bullets
"Smart quotes" and 'apostrophes'
Em dash — and en dash –
Ellipsis … and other symbols ©®™
        
This is a stress test for the PDF generator with challenging content.
"""
    }
    
    # Create PDF service
    pdf_service = ReportPDFService(bucket_name="reportpdfhedgefundintelligence")
    
    # Generate and upload PDF
    logger.info("Generating and uploading PDF...")
    
    report_date = datetime.now().strftime("%Y-%m-%d")
    
    # We're explicitly testing GCS upload
    result = pdf_service.generate_and_upload_pdf(
        report_sections=test_sections,
        report_date=report_date,
        upload_to_gcs=True,  # Test upload
        keep_local_copy=True  # Also keep local copy
    )
    
    # Check results
    if result.get('gcs_path'):
        logger.info(f"✅ SUCCESS - PDF uploaded to GCS: {result['gcs_path']}")
    else:
        logger.error("❌ FAILED - PDF was not uploaded to GCS")
        
    if result.get('local_path'):
        logger.info(f"✅ Local PDF saved: {result['local_path']}")
    
    logger.info("Test completed!")

if __name__ == "__main__":
    main()
